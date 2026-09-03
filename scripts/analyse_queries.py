"""Analyse search quality: persistently-weak perspectives + per-agent query stats.

Two reports, meant to answer "why is this perspective consistently weak?":

  1. Persistently-weak perspectives — reads runs/*/evidence.json, builds each
     perspective's findings count per run (in time order), and flags any that
     stayed below the weak threshold for the last N consecutive runs.  A
     perspective that is weak across multiple runs has a broken search-keyword
     template, not a one-off bad day.

  2. Per-agent query quality — reads logs/search_calls.jsonl (written by the
     P1 call-logging layer), aggregating calls / error rate / distinct queries
     / engine mix per agent.  A weak perspective's agent shows here whether the
     problem is dead engines (high error rate) or repeating the same query.

Usage:
  python scripts/analyse_queries.py [--runs-dir runs] [--log logs/search_calls.jsonl]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

# A perspective with fewer than WEAK_FINDINGS findings in a run is "weak".
# WEAK_STREAK consecutive weak runs → flagged as persistently weak.
WEAK_FINDINGS = 2
WEAK_STREAK = 2


def _load_json(path: Path) -> dict:
    raw = path.read_bytes()
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"):
        try:
            return json.loads(raw.decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return {}


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _agent_perspective(agent: str) -> str:
    """'researcher-technical' → 'technical'; other names pass through."""
    if agent.startswith("researcher-"):
        return agent[len("researcher-"):]
    return agent


# ── report 1: persistently-weak perspectives ────────────────────────

def build_perspective_history(runs_dir: Path) -> dict[str, list[int]]:
    """Return perspective → findings count per run, in run-id (time) order."""
    seq: dict[str, list[int]] = defaultdict(list)
    # run_id is YYYYMMDD-HHMMSS, so lexicographic sort == chronological sort.
    for ev in sorted(runs_dir.glob("*/evidence.json")):
        data = _load_json(ev)
        counts: dict[str, int] = {}
        for card in data.get("cards", []):
            p = str(card.get("perspective", "") or "?").strip() or "?"
            counts[p] = max(counts.get(p, 0), len(card.get("key_findings", [])))
        seen = set()
        for p, n in counts.items():
            seq[p].append(n)
            seen.add(p)
        # perspectives absent this run get 0 (so gaps count against them)
        for p in list(seq.keys()):
            if p not in seen:
                seq[p].append(0)
    return dict(seq)


def detect_persistently_weak(
    history: dict[str, list[int]],
    *,
    weak_findings: int = WEAK_FINDINGS,
    weak_streak: int = WEAK_STREAK,
) -> list[tuple[str, list[int]]]:
    """Return (perspective, recent_findings) for perspectives weak in the last
    `weak_streak` consecutive runs."""
    weak: list[tuple[str, list[int]]] = []
    for p, counts in history.items():
        if len(counts) < weak_streak:
            continue
        recent = counts[-weak_streak:]
        if all(n < weak_findings for n in recent):
            weak.append((p, counts))
    return sorted(weak, key=lambda x: sum(x[1]) / len(x[1]))


# ── report 2: per-agent query quality ───────────────────────────────

def analyse_queries(calls: list[dict]) -> dict[str, dict]:
    """Aggregate search_calls.jsonl per agent: calls, errors, distinct queries,
    engine mix."""
    per_agent: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "errors": 0, "queries": set(), "tools": Counter()}
    )
    for c in calls:
        agent = c.get("agent", "?")
        a = per_agent[agent]
        a["calls"] += 1
        if c.get("status") == "error":
            a["errors"] += 1
        q = str(c.get("query", "") or "").strip()
        if q:
            a["queries"].add(q)
        a["tools"][c.get("tool", "?")] += 1
    return per_agent


def _fmt_agent(agent_stats: dict, *, show_queries: bool = False) -> str:
    calls = agent_stats["calls"]
    errors = agent_stats["errors"]
    distinct = len(agent_stats["queries"])
    err_rate = (errors / calls * 100) if calls else 0.0
    tools = ", ".join(f"{t}×{n}" for t, n in agent_stats["tools"].most_common(4))
    line = f"  {calls} 次调用 | 错误率 {err_rate:.0f}% | 去重 query {distinct} 个 | {tools or '—'}"
    if show_queries and agent_stats["queries"]:
        for q in sorted(agent_stats["queries"])[:5]:
            line += f"\n     · {q[:80]}"
    return line


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyse search quality per perspective/agent.")
    ap.add_argument("--runs-dir", default="runs")
    ap.add_argument("--log", default="logs/search_calls.jsonl")
    ap.add_argument("--weak-findings", type=int, default=WEAK_FINDINGS)
    ap.add_argument("--weak-streak", type=int, default=WEAK_STREAK)
    args = ap.parse_args()

    runs_dir = Path(args.runs_dir)
    calls = _load_jsonl(Path(args.log))

    # ── Report 1: persistently-weak perspectives ──────────────────
    history = build_perspective_history(runs_dir)
    weak = detect_persistently_weak(
        history, weak_findings=args.weak_findings, weak_streak=args.weak_streak
    )

    print("=" * 64)
    print(f"持续弱视角（连续 {args.weak_streak} run 发现数 < {args.weak_findings}）")
    print("=" * 64)
    if not weak:
        print("  无 —— 没有视角持续弱。")
    for p, counts in weak:
        recent = counts[-args.weak_streak:]
        print(f"\n◆ {p}  最近 {len(counts)} 轮 findings: {counts}")
        print(f"  最近 {args.weak_streak} 轮 = {recent} → 建议调整该视角的搜索关键词模板")

    # ── Report 2: per-agent query quality ─────────────────────────
    per_agent = analyse_queries(calls)
    print("\n" + "=" * 64)
    print("各 Agent 搜索质量（logs/search_calls.jsonl）")
    print("=" * 64)
    if not per_agent:
        print("  （无 search_calls 数据 — 尚未运行或日志路径不对）")
    for agent in sorted(per_agent):
        print(f"\n▶ {agent}")
        print(_fmt_agent(per_agent[agent]))

    # cross-reference: for each weak perspective, show its agent's queries
    if weak and per_agent:
        print("\n" + "=" * 64)
        print("弱视角的 query 明细（排查：引擎差 还是 query 写得差）")
        print("=" * 64)
        for p, counts in weak:
            ag = per_agent.get(f"researcher-{p}")
            if ag:
                print(f"\n◆ {p}（researcher-{p}）")
                print(_fmt_agent(ag, show_queries=True))
            else:
                print(f"\n◆ {p} — search_calls 里无 researcher-{p} 记录")


if __name__ == "__main__":
    main()
