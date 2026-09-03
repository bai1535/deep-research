"""Compare research quality metrics across runs.

Usage:
  python scripts/compare_runs.py runs/20260714-142553 runs/20260717-060933 ...
"""

import json, sys
from pathlib import Path
from collections import Counter


def analyse(run_dir: str) -> dict:
    path = Path(run_dir) / "evidence.json"
    if not path.exists():
        return {"error": f"Not found: {path}"}

    raw = path.read_bytes()
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"):
        try:
            data = json.loads(raw.decode(enc))
            break
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    else:
        return {"error": f"Cannot decode: {path}"}

    all_sources: list[str] = []
    statuses: list[str] = []
    claims_count = 0
    cards_with_data = 0

    for card in data.get("cards", []):
        if not card.get("key_findings"):
            continue
        cards_with_data += 1
        for claim in card["key_findings"]:
            claims_count += 1
            all_sources.extend(claim.get("sources", []))

    for vc in data.get("verified", []):
        for entry in vc.get("entries", []):
            statuses.append(entry.get("status", "unknown"))

    score = data.get("score", {}).get("overall_score", None)
    question = data.get("question", "")

    status_counts = Counter(statuses)
    total_statuses = len(statuses)
    problem_ratio = (
        round((status_counts.get("false", 0) + status_counts.get("disputed", 0)) / total_statuses * 100, 1)
        if total_statuses else 0.0
    )

    return {
        "question": question[:80],
        "cards_with_data": f"{cards_with_data}/4",
        "claims": claims_count,
        "unique_sources": len(set(all_sources)),
        "verified": status_counts.get("verified", 0),
        "suspect": status_counts.get("suspect", 0),
        "false": status_counts.get("false", 0),
        "disputed": status_counts.get("disputed", 0),
        "problem_ratio": problem_ratio,
        "overall_score": score,
    }


def main():
    runs = sys.argv[1:] if len(sys.argv) > 1 else []
    if not runs:
        # Auto-discover from the runs directory
        base = Path("runs")
        runs = sorted(
            [str(d) for d in base.iterdir() if d.is_dir() and (d / "evidence.json").exists()],
            reverse=True,
        )[:10]

    headers = ["run_id", "question", "cards", "claims", "sources", "v/s/f/d", "问题率", "score"]
    rows = []
    for run_dir in runs:
        rid = Path(run_dir).name
        m = analyse(run_dir)
        if "error" in m:
            continue
        v = m["verified"]; s = m["suspect"]; f = m["false"]; d = m["disputed"]
        rows.append([
            rid,
            m["question"][:50],
            m["cards_with_data"],
            str(m["claims"]),
            str(m["unique_sources"]),
            f"{v}/{s}/{f}/{d}",
            f"{m['problem_ratio']}%",
            str(m["overall_score"]) if m["overall_score"] else "N/A",
        ])

    # Print table
    widths = [max(len(r[i]) for r in rows + [headers]) + 2 for i in range(len(headers))]
    fmt = "".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print("-" * sum(widths))
    for row in rows:
        print(fmt.format(*row))


if __name__ == "__main__":
    main()
