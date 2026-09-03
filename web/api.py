"""FastAPI web service for deep-research.

Endpoints:
    GET  /health                  — liveness probe
    POST /research               — submit a research question
    GET  /research/{run_id}      — poll status & results
    GET  /research/{run_id}/report  — get the final report (markdown)
    GET  /research/{run_id}/evidence  — get the evidence JSON
    GET  /research/              — list recent runs
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Ensure the project root is on sys.path so that "deep_research" is importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv(_PROJECT_ROOT / ".env")

import deep_research.qwen_patch  # noqa: F401, E402 — must load before LLM calls

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel, Field

from deep_research.pipeline import run_research, get_event_bus
from deep_research.config import get_config
from deep_research.db import init_db, Repository
from deep_research.eventsourcing import EventStore
from deep_research.causal_backtracking import trace_claim
from deep_research.replay import ReplayEngine, OutputCache

# ── concurrency gate ────────────────────────────────────────────────
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_RESEARCH", "20"))
_semaphore = asyncio.Semaphore(MAX_CONCURRENT)

# ── logging ──────────────────────────────────────────────────────────
# ── logging ──────────────────────────────────────────────────────────
LOG_DIR = Path(os.getenv("RESEARCH_OUTPUT_DIR", "./runs")).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "current.log"

fmt = logging.Formatter(
    "%(asctime)s [%(levelname)-7s] %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

# File handler — for `less +F logs/current.log`
file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(fmt)

# Console handler — for `docker compose logs`
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(fmt)

root = logging.getLogger()
root.setLevel(logging.DEBUG)
root.handlers.clear()
root.addHandler(file_handler)
root.addHandler(console_handler)

for noisy in ("LiteLLM", "httpx", "urllib3", "openai", "asyncio"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger("deep_research.web")

# ── app ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Deep Research API",
    version="0.2.0",
    description="Multi-agent deep research — submit a question, get a cited report.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── lifecycle ───────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    """Initialise the database pool on first request."""
    await init_db()
    logger.info("DB pool ready (max_concurrent=%d)", MAX_CONCURRENT)


# ── models ───────────────────────────────────────────────────────────
class ResearchRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="Research question")


class RollbackRequest(BaseModel):
    event_id: str = Field(..., min_length=1, description="Event ID to rollback to")
    execute: bool = Field(default=True, description="Execute the rollback (clear affected cache + write state)")
    replay: bool = Field(default=False, description="Also replay affected external tool events after rollback")
    regenerate: bool = Field(default=False, description="Also regenerate the final report after replay")


class ResearchStatus(BaseModel):
    run_id: str
    question: str
    status: str  # pending | researching | verifying | synthesizing | completed | failed
    created_at: str | None = None
    completed_at: str | None = None
    score: int | None = None
    findings: int = 0
    verified: int = 0
    report_url: str | None = None


# ── in-memory run tracker (for background tasks) ─────────────────────
# Keyed by run_id; stores the asyncio Task + metadata.
_run_tasks: dict[str, dict[str, Any]] = {}


# ── helpers ──────────────────────────────────────────────────────────
async def _run_snapshot(run_id: str) -> dict[str, Any] | None:
    """Read the current state of a run from the database."""
    repo = Repository()
    rec = await repo.get_run(run_id)
    if rec is None:
        return None
    cards = await repo.get_research_cards(run_id)
    verified = await repo.get_verified_cards(run_id)
    return {
            "run_id": run_id,
            "question": rec["question"],
            "status": rec["status"],           # "pending" / "researching" / … / "completed" / "failed"
            "created_at": rec.get("created_at"),
            "completed_at": rec.get("completed_at"),
            "findings": sum(len(c.key_findings) for c in cards),
            "verified": len(verified),
            "score": None,  # filled below if completed
        }


def _event_summary(ev) -> dict:
    """Compact event dict for API responses."""
    return {
        "event_id": ev.event_id,
        "seq": ev.seq,
        "action": ev.action,
        "agent": ev.agent,
        "parent_event_id": ev.parent_event_id,
        "created_at": ev.created_at,
        "payload_preview": str(ev.payload)[:200],
    }


async def _background_research(run_id: str, question: str) -> None:
    """Run the full research pipeline in the background."""
    try:
        result = await run_research(question, run_id=run_id)
        logger.info("Run %s completed — score=%d", run_id, result.score.overall_score if result.score else 0)
    except Exception as exc:
        logger.error("Run %s failed: %s", run_id, exc, exc_info=True)
    finally:
        # Clean up the task reference (keep metadata for polling)
        if run_id in _run_tasks:
            _run_tasks[run_id]["done"] = True


async def _gated_research(run_id: str, question: str) -> None:
    """Run research with concurrency gating via semaphore."""
    async with _semaphore:
        await _background_research(run_id, question)


# ── frontend ─────────────────────────────────────────────────────────
@app.get("/")
async def index():
    """Serve the web frontend."""
    html_path = Path(__file__).parent / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# ── log viewer (read-only) ───────────────────────────────────────────
LOG_VIEWER_TOKEN = os.getenv("LOG_VIEWER_TOKEN", "")

# Cache for full-file scans (search_calls.jsonl / log search).  Keyed by
# (path, mtime, size); invalidated automatically when the file changes.
_full_text_cache: dict[str, tuple[float, int, list[str]]] = {}


def _log_viewer_authorized(token: str) -> None:
    """Raise 403 when LOG_VIEWER_TOKEN is set and the token doesn't match."""
    if LOG_VIEWER_TOKEN and token != LOG_VIEWER_TOKEN:
        raise HTTPException(status_code=403, detail="invalid or missing log viewer token")


def _resolve_log_file(file: str) -> Path:
    """Resolve a user-supplied file name strictly inside LOG_DIR.

    Only basenames are allowed (no path separators), and only files that
    currently exist under LOG_DIR.  This prevents path traversal.
    """
    name = Path(file).name
    if name != file or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="invalid log file name")
    path = LOG_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"log file not found: {name}")
    return path


def _cached_full_lines(path: Path) -> list[str]:
    """Read a text file and split into lines, cached by mtime+size."""
    stat = path.stat()
    key = str(path)
    cached = _full_text_cache.get(key)
    if cached and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
        return cached[2]
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    _full_text_cache[key] = (stat.st_mtime, stat.st_size, lines)
    return lines


def _tail_lines(path: Path, limit: int) -> list[str]:
    """Read the last *limit* lines without loading the whole file."""
    with path.open("rb") as f:
        f.seek(0, 2)
        size = f.tell()
        # current.log lines average ~100 bytes; 256KB is enough for a
        # 2000-line tail and keeps polling cheap.
        read_size = min(size, 256 * 1024)
        f.seek(size - read_size)
        data = f.read()
    lines = data.decode("utf-8", errors="replace").splitlines()
    # If we started mid-file, the first line is partial — drop it.
    if size > read_size and lines:
        lines = lines[1:]
    return lines[-limit:]


def _search_lines(path: Path, q: str, level: str, limit: int) -> str:
    """Search the full file; return the LAST matching lines with 1-based numbers.

    Keeping the last matches (rather than the first) means a level filter
    like "ERROR" shows the most recent errors, which is what an operator
    usually wants.
    """
    lines = _cached_full_lines(path)
    # Log lines use a padded level like "[ERROR  ]" (7-char field), so a
    # plain "[ERROR]" substring never matches.  Match with a regex that
    # tolerates spaces inside the brackets.
    level_re = re.compile(rf"\[\s*{re.escape(level.upper())}\s*\]") if level else None
    q_lower = q.lower() if q else ""
    matches: deque[tuple[int, str]] = deque(maxlen=limit)
    for i, line in enumerate(lines, 1):
        if q_lower and q_lower not in line.lower():
            continue
        if level_re and not level_re.search(line):
            continue
        matches.append((i, line))
    return "\n".join(f"{i}: {line}" for i, line in matches)


@app.get("/logs")
async def logs_page(token: str = ""):
    """Serve the log viewer frontend."""
    _log_viewer_authorized(token)
    html_path = Path(__file__).parent / "logs.html"
    if not html_path.is_file():
        raise HTTPException(status_code=404, detail="logs.html not found")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/api/logs/files")
async def api_log_files(token: str = ""):
    """List log files available to the viewer."""
    _log_viewer_authorized(token)
    items = []
    for p in sorted(LOG_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not p.is_file():
            continue
        if p.name == "current.log" or p.suffix == ".log" or p.suffix == ".jsonl":
            st = p.stat()
            items.append({
                "name": p.name,
                "size": st.st_size,
                "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            })
    return items


@app.get("/api/logs/text")
async def api_log_text(
    file: str = "current.log",
    mode: str = "tail",
    lines: int = 300,
    q: str = "",
    level: str = "",
    token: str = "",
):
    """Read a text log.

    - mode=tail: last N lines (cheap, used by the live tail)
    - mode=search: grep the whole file for q/level
    """
    _log_viewer_authorized(token)
    path = _resolve_log_file(file)
    limit = max(20, min(lines, 5000))
    if mode == "search":
        content = _search_lines(path, q, level, limit)
    else:
        content = "\n".join(_tail_lines(path, limit))
    return {
        "file": path.name,
        "size": path.stat().st_size,
        "mode": mode,
        "content": content,
    }


@app.get("/api/logs/calls")
async def api_log_calls(
    run_id: str = "",
    tool: str = "",
    status: str = "",
    q: str = "",
    lines: int = 200,
    token: str = "",
):
    """Read the last N records from logs/search_calls.jsonl (newest first)."""
    _log_viewer_authorized(token)
    path = LOG_DIR / "search_calls.jsonl"
    if not path.is_file():
        return {"records": [], "file": path.name, "size": 0}
    limit = max(10, min(lines, 1000))
    records: list[dict[str, Any]] = []
    q_lower = q.lower() if q else ""
    for raw in _cached_full_lines(path):
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if run_id and rec.get("run_id") != run_id:
            continue
        if tool and rec.get("tool") != tool:
            continue
        if status and rec.get("status") != status:
            continue
        if q_lower:
            blob = f"{rec.get('query','')} {rec.get('error','')} {rec.get('agent','')} {rec.get('tool','')}".lower()
            if q_lower not in blob:
                continue
        records.append(rec)
    records = records[-limit:]
    records.reverse()
    return {"records": records, "file": path.name, "size": path.stat().st_size}


# ── endpoints ────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    """Liveness / readiness probe."""
    return {"status": "ok", "time": datetime.now().isoformat()}


@app.post("/research", status_code=202)
async def submit_research(req: ResearchRequest):
    """Submit a research question.  Returns immediately with a run_id.

    The research runs in the background.  Poll ``GET /research/{run_id}``
    to track progress.
    """
    # Create the run record (so the run_id exists immediately)
    from deep_research.models.schemas import ResearchRun

    run = ResearchRun(question=req.question)
    repo = Repository()
    await repo.create_run(run)
    config = get_config()

    # Ensure output directory exists (parent may have been deleted)
    base = Path(config.output_dir)
    base.mkdir(parents=True, exist_ok=True)
    output_dir = base / run.id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Launch background research — semaphore gates concurrency
    task = asyncio.create_task(_gated_research(run.id, req.question))
    _run_tasks[run.id] = {"task": task, "question": req.question, "done": False}

    logger.info("Research submitted: run_id=%s, question=%s", run.id, req.question[:80])

    return {
        "run_id": run.id,
        "status": "pending",
        "message": "Research started. Poll GET /research/{run_id} for progress.",
    }


@app.post("/research/{run_id}/resume", status_code=202)
async def resume_research(run_id: str):
    """Resume a crashed/interrupted research run from its last checkpoint.

    Only works for runs that are not already completed or in-flight.
    The pipeline reads the run's checkpoint and skips already-finished
    phases.
    """
    snap = await _run_snapshot(run_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    # Already finished — nothing to resume
    if snap["status"] in ("completed", "failed"):
        return {
            "run_id": run_id,
            "status": snap["status"],
            "message": f"Run already {snap['status']} — nothing to resume.",
        }

    # Already in flight on this process — don't double-launch
    if run_id in _run_tasks and not _run_tasks[run_id].get("done", True):
        return {
            "run_id": run_id,
            "status": "running",
            "message": "Run is already in progress.",
        }

    question = snap["question"]
    # Ensure output directory exists
    base = Path(get_config().output_dir)
    base.mkdir(parents=True, exist_ok=True)
    (base / run_id).mkdir(parents=True, exist_ok=True)

    task = asyncio.create_task(_gated_research(run_id, question))
    _run_tasks[run_id] = {"task": task, "question": question, "done": False}
    logger.info("Research RESUMED: run_id=%s, question=%s", run_id, question[:80])

    return {
        "run_id": run_id,
        "status": "resuming",
        "message": "Research resumed from checkpoint. Poll GET /research/{run_id} for progress.",
    }


@app.get("/research/{run_id}", response_model=ResearchStatus)
async def get_research_status(run_id: str):
    """Return the current status of a research run."""
    snap = await _run_snapshot(run_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    score = snap.get("score")
    report_url = None
    if snap["status"] == "completed":
        report_url = f"/research/{run_id}/report"

    return ResearchStatus(
        run_id=run_id,
        question=snap["question"],
        status=snap["status"],
        created_at=snap.get("created_at"),
        completed_at=snap.get("completed_at"),
        score=score,
        findings=snap["findings"],
        verified=snap["verified"],
        report_url=report_url,
    )


@app.get("/research/{run_id}/stream")
async def stream_research(run_id: str):
    """Server-Sent Events stream of live research progress.

    Subscribers first receive a replay of all events so far, then live
    events as the run progresses.  The stream ends when the run finishes
    (or the client disconnects).
    """
    import json
    from fastapi.responses import StreamingResponse

    bus = get_event_bus(run_id)
    if bus is None:
        raise HTTPException(status_code=404, detail=f"No event stream for run: {run_id}")

    async def event_gen():
        # Fix #3: subscribe FIRST, then replay.  Events emitted between
        # the replay snapshot and the subscribe would otherwise be lost;
        # with subscribe-first they land in the queue and are delivered
        # after the snapshot (worst case: one event appears twice, which
        # is harmless for the frontend).
        q = bus.subscribe()
        try:
            for ev in bus.replay():
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=20)
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                    # End the stream once the run has completed
                    if ev.get("type") == "run_done":
                        yield "data: {\"type\":\"stream_end\"}\n\n"
                        break
                except asyncio.TimeoutError:
                    # Heartbeat to keep the connection alive.  NOTE: if a
                    # reverse proxy sits in front, its idle timeout must
                    # be > 20s (nginx: proxy_read_timeout 60s+).
                    yield ": keep-alive\n\n"
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.get("/research/{run_id}/report")
async def get_report(run_id: str):
    """Return the final markdown report.  404 if not yet completed."""
    snap = await _run_snapshot(run_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    if snap["status"] not in ("completed", "failed", "synthesizing"):
        raise HTTPException(status_code=425, detail=f"Not ready — current status: {snap['status']}")

    config = get_config()
    report_path = Path(config.output_dir) / run_id / "report.md"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found. The run may have failed during synthesis.")

    return PlainTextResponse(
        content=report_path.read_text(encoding="utf-8"),
        media_type="text/markdown; charset=utf-8",
    )


@app.get("/research/{run_id}/evidence")
async def get_evidence(run_id: str):
    """Return the evidence JSON for a run."""
    snap = await _run_snapshot(run_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    config = get_config()
    evidence_path = Path(config.output_dir) / run_id / "evidence.json"
    if not evidence_path.exists():
        raise HTTPException(status_code=404, detail="Evidence file not found.")

    import json
    return JSONResponse(content=json.loads(evidence_path.read_text(encoding="utf-8")))


@app.get("/research/{run_id}/answer")
async def get_answer(run_id: str):
    """Return the extracted concise final answer (plain text)."""
    snap = await _run_snapshot(run_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    config = get_config()
    evidence_path = Path(config.output_dir) / run_id / "evidence.json"
    if not evidence_path.exists():
        raise HTTPException(status_code=404, detail="Evidence file not found.")

    import json
    data = json.loads(evidence_path.read_text(encoding="utf-8"))
    return PlainTextResponse(
        content=str(data.get("final_answer", "")),
        media_type="text/plain; charset=utf-8",
    )


@app.get("/research/{run_id}/claims")
async def get_run_claims(run_id: str):
    """Return the claim-level provenance document (claims.json)."""
    snap = await _run_snapshot(run_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    config = get_config()
    claims_path = Path(config.output_dir) / run_id / "claims.json"
    if not claims_path.exists():
        raise HTTPException(status_code=404, detail="Claims file not found.")

    import json
    return JSONResponse(content=json.loads(claims_path.read_text(encoding="utf-8")))


@app.get("/research/{run_id}/claims/{claim_id}/trace")
async def trace_claim_by_id(run_id: str, claim_id: str):
    """Return the event-sourcing chains behind a specific claim."""
    snap = await _run_snapshot(run_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    config = get_config()
    claims_path = Path(config.output_dir) / run_id / "claims.json"
    if not claims_path.exists():
        raise HTTPException(status_code=404, detail="Claims file not found.")

    import json
    claims_data = json.loads(claims_path.read_text(encoding="utf-8"))
    claim = next(
        (c for c in claims_data.get("claims", []) if c.get("claim_id") == claim_id),
        None,
    )
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim not found: {claim_id}")

    store = EventStore(Path(config.output_dir))
    chains = []
    for event_id in claim.get("event_ids") or []:
        ev = store.get(run_id, event_id)
        if ev is None:
            continue
        chains.append({
            "event_id": event_id,
            "event": _event_summary(ev),
            "ancestors": [_event_summary(e) for e in store.ancestors(run_id, event_id)],
        })

    return {
        "run_id": run_id,
        "claim_id": claim_id,
        "claim_text": claim.get("text", ""),
        "chains": chains,
    }


@app.get("/report/{run_id}")
async def report_viewer(run_id: str):
    """Serve the claim-level report/evidence viewer page."""
    html_path = Path(__file__).parent / "report.html"
    if not html_path.is_file():
        raise HTTPException(status_code=404, detail="report.html not found")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/research/{run_id}/events")
async def get_run_events(run_id: str, limit: int = Query(default=200, le=2000)):
    """Return event-sourcing events for a run (newest first)."""
    store = EventStore(Path(get_config().output_dir))
    events = store.load(run_id)
    events.reverse()
    return {
        "run_id": run_id,
        "count": len(events),
        "events": [
            {
                "event_id": e.event_id,
                "seq": e.seq,
                "action": e.action,
                "agent": e.agent,
                "parent_event_id": e.parent_event_id,
                "created_at": e.created_at,
                "payload_preview": str(e.payload)[:200],
            }
            for e in events[:limit]
        ],
    }


@app.post("/research/{run_id}/rollback", status_code=200)
async def rollback_run(run_id: str, req: RollbackRequest):
    """Return a branch-level rollback plan (does not execute the rollback yet)."""
    base = Path(get_config().output_dir)
    engine = ReplayEngine(store=EventStore(base), cache=OutputCache(base))
    try:
        if req.regenerate:
            plan = await engine.replay_and_regenerate(run_id, req.event_id)
        elif req.replay:
            plan = await engine.replay_affected_tools(run_id, req.event_id)
        elif req.execute:
            plan = engine.execute_rollback(run_id, req.event_id)
        else:
            plan = engine.build_branch_rollback_plan(run_id, req.event_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return plan


@app.get("/research/{run_id}/trace")
async def trace_run_claim(run_id: str, claim: str = Query(..., min_length=1)):
    """Trace a claim back through the event DAG and return suspicious sources."""
    store = EventStore(Path(get_config().output_dir))
    return trace_claim(run_id, claim, store=store)


@app.get("/research")
async def list_runs(limit: int = Query(default=20, le=100)):
    """Return a list of recent runs (newest first)."""
    config = get_config()
    runs_dir = Path(config.output_dir)
    if not runs_dir.exists():
        return []

    # Collect run dirs that have at least an evidence.json or report.md
    runs = []
    for d in sorted(runs_dir.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        snap = await _run_snapshot(d.name)
        if snap is None:
            continue
        runs.append({
            "run_id": d.name,
            "question": snap["question"][:120],
            "status": snap["status"],
            "created_at": snap.get("created_at"),
            "findings": snap["findings"],
            "verified": snap["verified"],
        })
        if len(runs) >= limit:
            break
    return runs


# ── main (for `python web/api.py`) ───────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("WEB_PORT", "8000"))
    uvicorn.run("web.api:app", host="0.0.0.0", port=port, reload=True)
