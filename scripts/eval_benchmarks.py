#!/usr/bin/env python3
"""Run public deep-research benchmarks against the local deep-research system.

Supported benchmarks:
- deepresearch    : DeepResearch Bench (100 PhD-level tasks, long reports)
- browsecomp_plus : BrowseComp-Plus (830 deep-search questions + gold answers)

The script runs on the host and launches one `docker compose run` per task, so
the benchmark data does not need to be mounted into the application container.

Examples:
  python3 scripts/eval_benchmarks.py --list
  python3 scripts/eval_benchmarks.py --benchmark deepresearch --limit 2
  python3 scripts/eval_benchmarks.py --benchmark browsecomp_plus --limit 2
  python3 scripts/eval_benchmarks.py --benchmark all --limit 2
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BENCHMARKS_DIR = Path("/home/admin/benchmarks")
REPORT_RE = re.compile(r"Report:\s*(\S+)")


# ── loaders ──────────────────────────────────────────────────────────

def load_deepresearch_tasks(benchmarks_dir: Path) -> list[dict]:
    path = benchmarks_dir / "deep_research_bench" / "data" / "prompt_data" / "query.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"DeepResearch Bench query file not found: {path}")
    tasks = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            tasks.append({
                "benchmark": "deepresearch",
                "task_id": str(row.get("id")),
                "prompt": row.get("prompt", ""),
                "language": row.get("language", ""),
                "topic": row.get("topic", ""),
                "gold": None,
            })
    return tasks


def load_browsecomp_tasks(benchmarks_dir: Path) -> list[dict]:
    path = benchmarks_dir / "BrowseComp-Plus" / "browsecomp_plus_queries_decrypted.jsonl"
    if not path.exists():
        raise FileNotFoundError(
            f"BrowseComp-Plus decrypted query file not found: {path}\n"
            "Please download/decrypt Tevatron/browsecomp-plus first."
        )
    tasks = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            tasks.append({
                "benchmark": "browsecomp_plus",
                "task_id": str(row.get("query_id")),
                "prompt": row.get("query", ""),
                "language": "en",
                "topic": "browsecomp",
                "gold": row.get("answer"),
            })
    return tasks


def load_tasks(benchmark: str, benchmarks_dir: Path) -> list[dict]:
    if benchmark in ("deepresearch", "all"):
        dr_tasks = load_deepresearch_tasks(benchmarks_dir)
    else:
        dr_tasks = []
    if benchmark in ("browsecomp_plus", "all"):
        bc_tasks = load_browsecomp_tasks(benchmarks_dir)
    else:
        bc_tasks = []
    return dr_tasks + bc_tasks


# ── runner ───────────────────────────────────────────────────────────

def run_one_task(task: dict, output_dir: Path) -> dict:
    benchmark = task["benchmark"]
    task_id = task["task_id"]
    prompt = task["prompt"]
    record = {
        "benchmark": benchmark,
        "task_id": task_id,
        "prompt": prompt,
        "gold": task.get("gold"),
        "status": "failed",
        "run_id": None,
        "report_path": None,
        "report_excerpt": None,
        "final_answer": None,
        "error": None,
    }

    # docker compose run --rm --no-deps deep-research python -m deep_research.main "<prompt>"
    cmd = [
        "docker", "compose", "run", "--rm", "--no-deps",
        "deep-research", "python", "-m", "deep_research.main", prompt,
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except subprocess.TimeoutExpired as exc:
        record["error"] = f"timeout: {exc}"
        return record
    except Exception as exc:  # noqa: BLE001
        record["error"] = f"subprocess error: {exc}"
        return record

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    if proc.returncode != 0:
        record["error"] = (stderr or stdout)[-2000:]
        return record

    m = REPORT_RE.search(stdout)
    if not m:
        record["error"] = f"report path not found in output. stdout tail: {stdout[-500:]}"
        return record

    report_rel = m.group(1)
    report_path = (PROJECT_ROOT / report_rel).resolve()
    if not report_path.exists():
        record["error"] = f"report file missing: {report_path}"
        return record

    report_text = report_path.read_text(encoding="utf-8", errors="replace")
    evidence_path = report_path.parent / "evidence.json"
    final_answer = ""
    if evidence_path.exists():
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8", errors="replace"))
            final_answer = str(evidence.get("final_answer") or "")
        except (json.JSONDecodeError, OSError):
            final_answer = ""
    record.update({
        "status": "completed",
        "run_id": report_path.parent.name,
        "report_path": str(report_path),
        "report_excerpt": report_text[:1000],
        "final_answer": final_answer,
    })

    # Save a copy under eval_results/<benchmark>/<task_id>.md
    out_sub = output_dir / benchmark
    out_sub.mkdir(parents=True, exist_ok=True)
    (out_sub / f"{task_id}.md").write_text(report_text, encoding="utf-8")

    return record


def main() -> None:
    ap = argparse.ArgumentParser(description="Run public deep-research benchmarks.")
    ap.add_argument("--benchmark", choices=["deepresearch", "browsecomp_plus", "all"], default="all")
    ap.add_argument("--benchmarks-dir", type=Path, default=DEFAULT_BENCHMARKS_DIR)
    ap.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "eval_results")
    ap.add_argument("--limit", type=int, default=2, help="Max tasks to run (default 2).")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--list", action="store_true", help="Only list task counts and exit.")
    args = ap.parse_args()

    tasks = load_tasks(args.benchmark, args.benchmarks_dir)
    if args.list:
        print(f"benchmark={args.benchmark} total_tasks={len(tasks)}")
        for task in tasks[:5]:
            print(f"  [{task['benchmark']}] {task['task_id']}: {task['prompt'][:80]}")
        return

    selected = tasks[args.offset:args.offset + args.limit]
    if not selected:
        print("No tasks selected.")
        return

    print(f"Running {len(selected)} task(s) from {args.benchmark} ...")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_path = args.output_dir / f"run-{args.benchmark}.jsonl"
    with results_path.open("a", encoding="utf-8") as out:
        for task in selected:
            print(f"  -> [{task['benchmark']}] {task['task_id']}: {task['prompt'][:60]}...", flush=True)
            record = run_one_task(task, args.output_dir)
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            print(f"     status={record['status']}" + (f" error={record['error'][:100]}" if record["error"] else ""))

    print(f"Results appended to {results_path}")


if __name__ == "__main__":
    main()
