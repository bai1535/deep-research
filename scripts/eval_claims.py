#!/usr/bin/env python3
"""Evaluate claim-level provenance metrics from completed runs.

Reads `runs/<run_id>/claims.json` files and reports:
- claim count
- answer coverage (characters covered by claim spans / report length)
- evidence coverage (claims with at least one evidence link)
- traceability (claims with at least one event_id)
- verified / suspect / disputed / false / unverifiable rates
- average confidence
- granularity audit flags (over-fine / over-coarse heuristics)

Usage:
  python3 scripts/eval_claims.py --run-id 20260902-025838
  python3 scripts/eval_claims.py --runs-dir runs --limit 10
  python3 scripts/eval_claims.py --audit --limit 10
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from deep_research.claim_metrics import compute_run_metrics

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUNS_DIR = PROJECT_ROOT / "runs"


def collect_run_paths(runs_dir: Path, run_id: str | None, limit: int) -> list[Path]:
    if run_id:
        p = runs_dir / run_id / "claims.json"
        return [p] if p.exists() else []
    paths = sorted(
        (d / "claims.json" for d in runs_dir.iterdir() if d.is_dir() and (d / "claims.json").exists()),
        key=lambda p: p.parent.name,
        reverse=True,
    )
    return paths[:limit]


def print_table(metrics: list[dict]) -> None:
    if not metrics:
        print("No runs with claims.json found.")
        return
    header = [
        "run_id", "claims", "ans_cov", "evi_cov", "trace", "verified",
        "suspect", "disputed", "unverif", "avg_conf", "fine", "coarse", "short",
    ]
    print("\t".join(header))
    for m in metrics:
        print("\t".join([
            m["run_id"],
            str(m["total_claims"]),
            f"{m['answer_coverage']:.2%}",
            f"{m['evidence_coverage']:.2%}",
            f"{m['traceability']:.2%}",
            f"{m['verified_rate']:.2%}",
            f"{m['suspect_rate']:.2%}",
            f"{m['disputed_rate']:.2%}",
            f"{m['unverifiable_rate']:.2%}",
            str(m["avg_confidence"]),
            str(m["over_fine_count"]),
            str(m["over_coarse_count"]),
            str(m["too_short_count"]),
        ]))


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate claim-level provenance metrics.")
    ap.add_argument("--run-id", default=None, help="Single run ID")
    ap.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--json-output", type=Path, default=None, help="Write aggregated metrics as JSON")
    ap.add_argument("--audit", action="store_true", help="Include granularity audit columns (always included in JSON)")
    args = ap.parse_args()

    paths = collect_run_paths(args.runs_dir, args.run_id, args.limit)
    metrics = [compute_run_metrics(p) for p in paths]

    print_table(metrics)

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Wrote {args.json_output}")


if __name__ == "__main__":
    main()
