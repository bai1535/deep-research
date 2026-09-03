"""Main research pipeline — data-driven StateGraph orchestration.

The 3-phase workflow is declared as a graph rather than hard-coded
sequential awaits.  Nodes are async functions that read/write shared
state; edges route between them (conditional edges allow skipping
phases when there's nothing to do).
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from pathlib import Path

from deep_research.config import get_config
from deep_research.core.blackboard import Blackboard
from deep_research.core.events import EventBus
from deep_research.core.file_cache import FileCache
from deep_research.core.graph import StateGraph
from deep_research.models.schemas import (
    ResearchRun, RunStatus, ResearchCard, VerifiedCard, ScoreResult, InsightResult,
    ReflectionResult,
)
from deep_research.db import Repository
from deep_research.experience import ExperienceStore
from deep_research.crews import (
    ResearchCrewRunner, ReflectionCrewRunner, VerificationCrewRunner, SynthesisCrewRunner,
)
from deep_research.trace import new_trace_id, trace_logger

logger = logging.getLogger("deep_research.pipeline")

B = "━" * 56
half = "─" * 24

# Live event buses per run — the web layer reads these for SSE streaming.
_event_buses: dict[str, EventBus] = {}
# Fix #2: buses are released EVENT_BUS_TTL seconds after their run ends
# (long enough for late-connecting SSE clients to replay history; short
# enough that a long-lived web service doesn't accumulate them forever).
EVENT_BUS_TTL = 300


def get_event_bus(run_id: str) -> EventBus | None:
    """Return the live EventBus for a run (for SSE), or None."""
    return _event_buses.get(run_id)


# ── graph nodes ─────────────────────────────────────────────────────
# Each node: async (state) -> partial_state_update.
# The state dict carries everything the phases need:
#   {question, run_id, blackboard, file_cache, repo, tlog, cost_snapshots, ...}

def _emit(state: dict, event: dict) -> None:
    """Emit an event on the run's EventBus (no-op if absent)."""
    bus = state.get("blackboard")
    if bus is not None:
        eb = bus.read("event_bus")
        if eb is not None:
            eb.emit(event)


async def _research_node(state: dict) -> dict:
    question = state["question"]
    run_id = state["run_id"]
    repo: Repository = state["repo"]
    tlog = state["tlog"]
    blackboard: Blackboard = state["blackboard"]
    file_cache: FileCache = state["file_cache"]

    tlog.info("%s\n  ▸ PHASE 1/3  RESEARCH  —  %s\n%s", B, question[:50], B)
    _emit(state, {"type": "phase_start", "phase": "research"})
    await repo.update_run_status(run_id, RunStatus.RESEARCHING)
    crew = ResearchCrewRunner(blackboard=blackboard, file_cache=file_cache)
    cards = await crew.run(question, run_id)
    findings = sum(len(c.key_findings) for c in cards)
    state["cost_snapshots"]["phase1"] = {k for k in blackboard.keys() if k.startswith("usage:")}
    tlog.info("%s PHASE 1 DONE  —  %d cards / %d findings %s", half, len(cards), findings, half)
    _emit(state, {"type": "phase_done", "phase": "research", "findings": findings})
    return {"cards": cards, "findings": findings}


async def _augment_node(state: dict) -> dict:
    run_id = state["run_id"]
    tlog = state["tlog"]
    blackboard: Blackboard = state["blackboard"]
    file_cache: FileCache = state["file_cache"]
    cards = state.get("cards", [])

    tlog.info("%s\n  ▸ AUGMENT  —  supplementing thin research\n%s", B, B)
    _emit(state, {"type": "phase_start", "phase": "augment"})
    crew = ResearchCrewRunner(blackboard=blackboard, file_cache=file_cache)
    # Reflection Pattern: when the quality gate failed, carry the
    # reviewer's feedback into the re-search instead of a blind retry.
    reflection = state.get("reflection")
    feedback = reflection.feedback if reflection is not None else ""
    updated = await crew.augment(
        cards,
        state["question"],
        run_id,
        feedback=feedback,
        augment_count=state.get("augment_count", 0),
    )
    findings = sum(len(c.key_findings) for c in updated)
    augment_count = state.get("augment_count", 0) + 1
    state["cost_snapshots"]["phase1"] = {k for k in blackboard.keys() if k.startswith("usage:")}
    tlog.info("%s AUGMENT #%d DONE  —  %d findings %s", half, augment_count, findings, half)
    _emit(state, {"type": "phase_done", "phase": "augment", "findings": findings})
    return {"cards": updated, "findings": findings, "augment_count": augment_count}


async def _reflect_node(state: dict) -> dict:
    """Quality gate (Reflection Pattern): review research output.

    A dedicated REFLECTOR agent scores the findings on concreteness,
    evidence, coverage, relevance and quantity.  When below threshold,
    the router sends the researchers back with the reviewer's feedback
    (see `_route_after_reflect`).  Acceptability is decided HERE
    deterministically — the model only reports a score.
    """
    run_id = state["run_id"]
    tlog = state["tlog"]
    blackboard: Blackboard = state["blackboard"]
    file_cache: FileCache = state["file_cache"]
    cards = state.get("cards", [])
    question = state["question"]
    findings = state.get("findings", 0)

    # Fix #G: reflect is reentrant, so a crashed run's resume re-runs it.
    # Distinguish that in the log (the reviewer output is identical — the
    # cards haven't changed — but the audit trail should say so).
    resumed = "reflect" in set(state.get("__visited__", []) or [])
    tlog.info("%s\n  ▸ REFLECT%s  —  quality gate\n%s",
              B, " (resumed)" if resumed else "", B)
    _emit(state, {"type": "phase_start", "phase": "reflection"})

    crew = ReflectionCrewRunner(blackboard=blackboard, file_cache=file_cache)
    reflection = await crew.reflect(cards, question, run_id)

    # Deterministic quality gate: score + finding-count thresholds.
    # The model's raw score is the only input; acceptability is ours.
    reflection.acceptable = (
        reflection.quality_score >= QUALITY_THRESHOLD and findings >= MIN_FINDINGS
    )

    state["cost_snapshots"]["phase1"] = {k for k in blackboard.keys() if k.startswith("usage:")}
    verdict = "✓ acceptable" if reflection.acceptable else "✗ needs work"
    tlog.info("%s REFLECT: score=%d %s %s", half, reflection.quality_score, verdict, half)
    _emit(state, {
        "type": "reflection",
        "score": reflection.quality_score,
        "acceptable": reflection.acceptable,
        "findings": findings,
        "feedback": reflection.feedback[:200] if reflection.feedback else "",
    })
    return {"reflection": reflection}


async def _verify_node(state: dict) -> dict:
    run_id = state["run_id"]
    repo: Repository = state["repo"]
    tlog = state["tlog"]
    blackboard: Blackboard = state["blackboard"]
    file_cache: FileCache = state["file_cache"]
    cards = state.get("cards", [])

    tlog.info("%s\n  ▸ PHASE 2/3  VERIFICATION\n%s", B, B)
    _emit(state, {"type": "phase_start", "phase": "verification"})
    await repo.update_run_status(run_id, RunStatus.VERIFYING)
    crew = VerificationCrewRunner(blackboard=blackboard, file_cache=file_cache)
    verified = await crew.run(cards, run_id)
    state["cost_snapshots"]["phase2"] = {k for k in blackboard.keys() if k.startswith("usage:")}
    tlog.info("%s PHASE 2 DONE  —  %d verified %s", half, len(verified), half)
    _emit(state, {"type": "phase_done", "phase": "verification", "verified": len(verified)})
    return {"verified_cards": verified}


async def _synthesis_node(state: dict) -> dict:
    run_id = state["run_id"]
    repo: Repository = state["repo"]
    tlog = state["tlog"]
    blackboard: Blackboard = state["blackboard"]
    file_cache: FileCache = state["file_cache"]

    tlog.info("%s\n  ▸ PHASE 3/3  SYNTHESIS\n%s", B, B)
    _emit(state, {"type": "phase_start", "phase": "synthesis"})
    await repo.update_run_status(run_id, RunStatus.SYNTHESIZING)
    crew = SynthesisCrewRunner(blackboard=blackboard, file_cache=file_cache)
    result = await crew.run(run_id)
    state["cost_snapshots"]["phase3"] = {k for k in blackboard.keys() if k.startswith("usage:")}
    tlog.info("%s PHASE 3 DONE  —  score=%d %s", half, result["score"].overall_score, half)
    _emit(state, {"type": "phase_done", "phase": "synthesis", "score": result["score"].overall_score})
    return {"score": result["score"], "insights": result["insights"]}


async def _complete_node(state: dict) -> dict:
    run_id = state["run_id"]
    repo: Repository = state["repo"]
    tlog = state["tlog"]
    blackboard: Blackboard = state["blackboard"]
    cost_snapshots: dict = state["cost_snapshots"]
    findings = state.get("findings", 0)
    score = state.get("score")

    await repo.update_run_status(run_id, RunStatus.COMPLETED)
    cost_report = _summarise_cost(blackboard, cost_snapshots)
    tlog.info(
        "%s\n  ✅ RUN %s COMPLETED  —  score=%d  —  %d findings\n%s\n  📄 runs/%s/report.md\n%s",
        B, run_id, score.overall_score if score else 0, findings, cost_report, run_id, B,
    )
    _emit(state, {"type": "run_done", "score": score.overall_score if score else 0,
                  "findings": findings, "status": "completed"})
    return {"run_status": RunStatus.COMPLETED}


async def _empty_result_node(state: dict) -> dict:
    """Research produced zero findings — bail out without burning tokens.

    Writes a minimal evidence.json so the run isn't a total dead end,
    then completes.
    """
    import json
    run_id = state["run_id"]
    repo: Repository = state["repo"]
    tlog = state["tlog"]
    blackboard: Blackboard = state["blackboard"]
    question = state["question"]
    config = get_config()

    tlog.warning("Research produced 0 findings — completing without synthesis")

    output_dir = Path(config.output_dir) / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence = {"run_id": run_id, "question": question, "cards": [], "verified": [],
                "score": {"overall_score": 0, "claim_scores": [], "summary": "No findings produced"},
                "insights": {"consensus_signals": [], "contradictions": [], "blind_spots": [], "time_sensitive_items": []},
                "final_answer": ""}
    (output_dir / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False), encoding="utf-8")

    await repo.update_run_status(run_id, RunStatus.COMPLETED)
    cost_report = _summarise_cost(blackboard, state["cost_snapshots"])
    tlog.info("%s\n  ⚠️ RUN %s COMPLETED (EMPTY)  —  0 findings\n%s\n  📄 runs/%s/evidence.json\n%s",
              B, run_id, cost_report, run_id, B)
    return {"run_status": RunStatus.COMPLETED}


# ── conditional edges ──────────────────────────────────────────────

# Quantity gate: minimum findings before a run is worth verifying.
# Quality gate: minimum reflector score (0-100) before findings are
# considered acceptable.  Either failing → augment with feedback.
MIN_FINDINGS = 3
MAX_AUGMENTS = 2
QUALITY_THRESHOLD = 60


def _route_after_reflect(state: dict) -> str:
    """Dynamic routing after the quality gate (and each augment round).

    - acceptable (score >= QUALITY_THRESHOLD AND findings >= MIN_FINDINGS)
      → verify
    - unacceptable + augment budget left → augment (re-search, feedback-driven)
    - unacceptable + budget exhausted → verify if anything found,
      else empty_result (write minimal evidence)
    """
    findings = state.get("findings", 0)
    augment_count = state.get("augment_count", 0)
    reflection = state.get("reflection")
    acceptable = (
        reflection is not None
        and reflection.acceptable
    )

    if acceptable:
        return "verify"

    if augment_count < MAX_AUGMENTS:
        return "augment"

    # Budget exhausted — go verify if anything found, else bail out
    return "verify" if findings > 0 else "empty_result"


# ── graph construction ─────────────────────────────────────────────

def build_graph(*, checkpoint_cb=None) -> StateGraph:
    """Declare the research workflow as a graph."""
    g = StateGraph(name="deep-research", checkpoint=checkpoint_cb)
    g.add_node("research", _research_node)
    # reflect is REENTRANT: each augment round must be re-reviewed, so
    # the loop is reflect → augment → reflect → … until acceptable.
    g.add_node("reflect", _reflect_node, reentrant=True)  # quality gate
    g.add_node("augment", _augment_node, reentrant=True)  # loops via counter
    g.add_node("verify", _verify_node)
    g.add_node("synthesize", _synthesis_node)
    g.add_node("empty_result", _empty_result_node)
    g.add_node("complete", _complete_node)

    # research → reflect (quality gate), then router decides
    g.add_edge("research", "reflect")
    # augment → reflect: every augment round is RE-REVIEWED so the next
    # round carries fresh feedback (fix #1: feedback must not go stale —
    # "reflect → augment → reflect → …" until acceptable or budget out).
    # augment_count gates the loop; reflect is re-entered per round.
    g.add_conditional_edges("reflect", _route_after_reflect, default="verify")
    g.add_edge("augment", "reflect")
    g.add_edge("verify", "synthesize")
    g.add_edge("empty_result", "complete")
    g.add_edge("synthesize", "complete")
    return g


# ── checkpoint serialisation ───────────────────────────────────────
# Only the JSON-serialisable subset of state is persisted.  The
# blackboard/repo/tlog objects are rebuilt fresh on resume.

def _serialisable_state(state: dict) -> dict:
    """Extract JSON-serialisable fields from a graph state."""
    out: dict = {
        "question": state.get("question", ""),
        "run_id": state.get("run_id", ""),
        "trace_id": state.get("trace_id", ""),
        "findings": state.get("findings", 0),
        "augment_count": state.get("augment_count", 0),
        "cost_snapshots": {k: sorted(v) for k, v in state.get("cost_snapshots", {}).items()},
        "__visited__": sorted(state.get("__visited__", [])),
    }
    for key in ("cards", "verified_cards"):
        if key in state:
            out[key] = [m.model_dump() for m in state[key]]
    for key in ("score", "insights", "reflection"):
        if key in state and state[key] is not None:
            out[key] = state[key].model_dump()

    # Persist blackboard usage counters — without these, a resumed run's
    # cost breakdown loses every agent that finished before the crash.
    bb = state.get("blackboard")
    if bb is not None:
        usage = {k[len("usage:"):]: bb.read(k)
                 for k in bb.keys() if k.startswith("usage:")}
        if usage:
            out["usage"] = usage
    return out


def _restore_state(checkpoint: dict) -> tuple[dict, set[str]]:
    """Rebuild the serialisable part of state from a checkpoint dict."""
    state = {
        "question": checkpoint.get("question", ""),
        "run_id": checkpoint.get("run_id", ""),
        "trace_id": checkpoint.get("trace_id", ""),
        "findings": checkpoint.get("findings", 0),
        "augment_count": checkpoint.get("augment_count", 0),
        "cost_snapshots": {k: set(v) for k, v in checkpoint.get("cost_snapshots", {}).items()},
    }
    if "cards" in checkpoint:
        state["cards"] = [ResearchCard(**c) for c in checkpoint["cards"]]
    if "verified_cards" in checkpoint:
        state["verified_cards"] = [VerifiedCard(**c) for c in checkpoint["verified_cards"]]
    if "score" in checkpoint:
        state["score"] = ScoreResult(**checkpoint["score"])
    if "insights" in checkpoint:
        state["insights"] = InsightResult(**checkpoint["insights"])
    if "reflection" in checkpoint:
        state["reflection"] = ReflectionResult(**checkpoint["reflection"])
    if "usage" in checkpoint:
        state["usage"] = checkpoint["usage"]
    visited = set(checkpoint.get("__visited__", []))
    return state, visited


# ── pipeline entry ─────────────────────────────────────────────────

async def run_research(question: str, *, run_id: str | None = None) -> ResearchRun:
    """Execute the research workflow as a state graph, resumable on crash."""
    config = get_config()

    blackboard = Blackboard()
    file_cache = FileCache()
    event_bus = EventBus()

    run = ResearchRun(id=run_id, question=question) if run_id else ResearchRun(question=question)
    output_dir = Path(config.output_dir) / run.id
    output_dir.mkdir(parents=True, exist_ok=True)

    blackboard.write("event_bus", event_bus)  # agents read this for streaming
    _event_buses[run.id] = event_bus  # web layer streams from this

    repo = Repository()

    # ── resume support ─────────────────────────────────────────────
    checkpoint = await repo.get_last_checkpoint(run.id) if run_id else None
    if checkpoint:
        # asyncpg returns JSONB columns as strings — parse to dict
        checkpoint_state = json.loads(checkpoint["state"]) if isinstance(checkpoint["state"], str) else checkpoint["state"]
        serial_state, visited = _restore_state(checkpoint_state)
        trace_id = serial_state.get("trace_id") or new_trace_id()
        tlog = trace_logger(logger, trace_id)
        tlog.info("♻️  RESUMING run %s from checkpoint '%s' (visited=%s)",
                  run.id, checkpoint["node_name"], sorted(visited))
    else:
        trace_id = new_trace_id()
        tlog = trace_logger(logger, trace_id)
        if run_id:
            await repo.update_run_status(run.id, RunStatus.RESEARCHING)
        else:
            await repo.create_run(run)
        tlog.info("Run %s started: %s", run.id, question[:80])
        serial_state = {
            "question": question,
            "run_id": run.id,
            "trace_id": trace_id,
            "findings": 0,
            "cost_snapshots": {},
        }
        visited = set()

    blackboard.write("trace_id", trace_id)
    blackboard.write("run_id", run.id)

    # Shared state handed to every node
    state: dict = {
        **serial_state,
        "question": question,
        "run_id": run.id,
        "blackboard": blackboard,
        "file_cache": file_cache,
        "repo": repo,
        "tlog": tlog,
        "cost_snapshots": serial_state.get("cost_snapshots", {}),
        "__visited__": visited,
    }
    # Restore persisted artifacts back onto the blackboard for later phases
    if "cards" in serial_state:
        blackboard.write(f"run:{run.id}:cards", serial_state["cards"])
    if "verified_cards" in serial_state:
        blackboard.write(f"run:{run.id}:verified", serial_state["verified_cards"])
    for agent_name, usage_data in serial_state.get("usage", {}).items():
        blackboard.write(f"usage:{agent_name}", usage_data)

    # ── checkpoint callback ────────────────────────────────────────
    async def _checkpoint(node_name: str, st: dict) -> None:
        """Persist state after each node completes.

        graph.run() has already set ``st["__visited__"]`` (the set of
        nodes executed this session) before calling this callback.
        """
        payload = _serialisable_state(st)
        await repo.save_checkpoint(run.id, node_name, json.dumps(payload, ensure_ascii=False))

    try:
        graph = build_graph(checkpoint_cb=_checkpoint)
        final = await graph.run(state)
        # Reflect results back onto the ResearchRun object
        run.research_cards = final.get("cards", [])
        run.verified_cards = final.get("verified_cards", [])
        run.score = final.get("score")
        run.insights = final.get("insights")
        run.status = final.get("run_status", RunStatus.COMPLETED)
        run.completed_at = _now_iso() if run.status == RunStatus.COMPLETED else None
        # Clear checkpoints on successful completion — a failure here must
        # not flip a completed run to FAILED.
        if run.status == RunStatus.COMPLETED and run_id:
            try:
                await repo.clear_checkpoints(run.id)
            except Exception as exc:
                tlog.warning("Failed to clear checkpoints: %s", exc)
            # Teachability: feed this run's real outcomes back into the
            # experience layer — the next runs start smarter.
            try:
                _learn_from_run(run.id, config)
            except Exception as exc:
                tlog.warning("teachability: learn failed: %s", exc)

    except Exception:
        run.status = RunStatus.FAILED
        await repo.update_run_status(run.id, RunStatus.FAILED)
        tlog.error("%s\n  ❌ RUN %s FAILED\n%s\n%s", B, run.id, traceback.format_exc(), B)

    finally:
        # Fix #2: release the run's EventBus after a delay — SSE clients
        # that connect late (or reconnect) can still replay history, but
        # the bus doesn't stay in the global dict forever.
        async def _release_bus() -> None:
            await asyncio.sleep(EVENT_BUS_TTL)
            _event_buses.pop(run.id, None)

        asyncio.create_task(_release_bus())

    return run


def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat()


def _learn_from_run(run_id: str, config) -> None:
    """Teachability: aggregate a completed run's outcomes by role.

    Reads runs/{run_id}/evidence.json (written by the synthesis crew)
    and merges per-card findings counts into runs/experience.json.
    """
    evidence_path = Path(config.output_dir) / run_id / "evidence.json"
    if not evidence_path.exists():
        logger.info("teachability: no evidence.json for %s, skip learning", run_id)
        return
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("teachability: cannot read %s: %s", evidence_path, exc)
        return
    store = ExperienceStore(Path(config.output_dir) / "experience.json")
    store.learn(run_id, evidence)


def _summarise_cost(blackboard: Blackboard, snapshots: dict[str, set[str]]) -> str:
    """Aggregate token/cost usage, broken down by phase."""

    def _read_agent(key: str) -> dict:
        u = blackboard.read(key, {})
        return u if isinstance(u, dict) else {}

    def _phase_total(phase_keys: set[str]) -> dict:
        tokens = 0; cost = 0.0; calls = 0
        for k in phase_keys:
            u = _read_agent(k)
            tokens += u.get("total", 0)
            cost += u.get("cost", 0.0)
            calls += u.get("calls", 0)
        return {"tokens": tokens, "cost": cost, "calls": calls}

    p1_keys = snapshots.get("phase1", set())
    p2_keys = snapshots.get("phase2", set()) - p1_keys
    p3_keys = snapshots.get("phase3", set()) - snapshots.get("phase2", set())

    p1 = _phase_total(p1_keys)
    p2 = _phase_total(p2_keys)
    p3 = _phase_total(p3_keys)

    def _fmt(d: dict) -> str:
        return f"{d['tokens']:,} tokens / ${d['cost']:.4f} ({d['calls']} calls)"

    agent_lines: list[str] = []
    for key in sorted(blackboard.keys()):
        if not key.startswith("usage:"):
            continue
        u = _read_agent(key)
        name = key.replace("usage:", "")
        agent_lines.append(f"    {name}: {u.get('total', 0):,} tokens / ${u.get('cost', 0):.4f}")

    lines = [
        f"💰 COST BREAKDOWN",
        f"  Phase 1 (Research):     {_fmt(p1)}",
        f"  Phase 2 (Verification): {_fmt(p2)}",
        f"  Phase 3 (Synthesis):    {_fmt(p3)}",
        f"  ─────────────────────────────",
        f"  TOTAL:                  {_fmt(_phase_total(p1_keys | p2_keys | p3_keys))}",
    ]
    if agent_lines:
        lines.append("  Per-agent:")
        lines.extend(agent_lines)

    return "\n".join(lines)
