#!/usr/bin/env python3
"""Search/effect evaluation for deep-research.

Reads:
- logs/search_calls.jsonl  — per-call records (status, duration_ms, result_urls)
- runs/*/evidence.json     — final cited sources per run (weak relevance labels)

Reports:
- availability: ok / total per engine and overall
- latency: mean / p50 / p95 for successful calls
- Hit@k / nDCG@k: when `result_urls` is present in call logs, using the run's
  cited sources as a weak relevance set.

Historical logs without `result_urls` will only produce availability/latency;
Hit@k/nDCG@k will be reported once new runs log returned URLs.

Usage:
  python scripts/search_eval.py [--runs-dir runs] [--log logs/search_calls.jsonl] [--topk 5]
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


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


def _norm_url(url: str) -> str:
    """Normalize a URL for weak-label matching.

    Strips fragments and trailing slashes.  Does not aggressively normalize
    because search engines and evidence may use slightly different encodings;
    this is a weak-label approximation.
    """
    url = str(url or "").strip()
    if not url:
        return url
    url = url.split("#", 1)[0]
    if url.endswith("/") and not url.endswith("://"):
        url = url[:-1]
    return url


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)


def load_evidence_sources(runs_dir: Path) -> dict[str, set[str]]:
    """Map run_id -> normalized set of cited source URLs from evidence.json."""
    sources_by_run: dict[str, set[str]] = defaultdict(set)
    for ev in runs_dir.glob("*/evidence.json"):
        data = _load_json(ev)
        run_id = str(data.get("run_id") or ev.parent.name)
        for card in data.get("cards", []):
            for finding in card.get("key_findings", []):
                for src in finding.get("sources", []):
                    norm = _norm_url(src)
                    if norm:
                        sources_by_run[run_id].add(norm)
    return dict(sources_by_run)


def analyse_calls(
    calls: list[dict],
    sources_by_run: dict[str, set[str]],
    *,
    topk: int = 5,
) -> dict:
    """Aggregate availability/latency and retrieval metrics."""
    overall = {"total": 0, "ok": 0, "durations": []}
    per_tool: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "ok": 0, "durations": [], "retrieval_calls": 0, "hits": 0, "ndcg_sum": 0.0}
    )
    retrieval_calls = 0
    hit_total = 0
    ndcg_sum = 0.0

    for call in calls:
        tool = str(call.get("tool") or "?")
        status = str(call.get("status") or "")
        duration = call.get("duration_ms")
        try:
            duration = float(duration) if duration is not None else None
        except (TypeError, ValueError):
            duration = None

        overall["total"] += 1
        per_tool[tool]["total"] += 1

        if status == "ok":
            overall["ok"] += 1
            per_tool[tool]["ok"] += 1
            if duration is not None:
                overall["durations"].append(duration)
                per_tool[tool]["durations"].append(duration)

        result_urls = call.get("result_urls") or []
        if not result_urls:
            continue
        run_id = str(call.get("run_id") or "")
        relevant = sources_by_run.get(run_id, set())
        if not relevant:
            continue

        retrieved = [_norm_url(u) for u in result_urls[:topk]]
        rel = [1 if u in relevant else 0 for u in retrieved]

        retrieval_calls += 1
        per_tool[tool]["retrieval_calls"] += 1

        hit = 1 if any(rel) else 0
        dcg = sum(r / math.log2(i + 2) for i, r in enumerate(rel) if r)
        ideal_count = min(len(relevant), topk)
        idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_count)) if ideal_count else 0.0
        ndcg = dcg / idcg if idcg else 0.0

        hit_total += hit
        ndcg_sum += ndcg
        per_tool[tool]["hits"] += hit
        per_tool[tool]["ndcg_sum"] += ndcg

    return {
        "overall": overall,
        "per_tool": dict(per_tool),
        "retrieval_calls": retrieval_calls,
        "hit_total": hit_total,
        "ndcg_sum": ndcg_sum,
    }


def _fmt_latency(durations: list[float]) -> str:
    if not durations:
        return "n/a"
    sorted_d = sorted(durations)
    mean = statistics.fmean(sorted_d)
    p50 = _percentile(sorted_d, 0.50)
    p95 = _percentile(sorted_d, 0.95)
    return f"mean={mean:.0f}ms p50={p50:.0f}ms p95={p95:.0f}ms"


def main() -> None:
    ap = argparse.ArgumentParser(description="Search/effect evaluation for deep-research.")
    ap.add_argument("--runs-dir", default="runs")
    ap.add_argument("--log", default="logs/search_calls.jsonl")
    ap.add_argument("--topk", type=int, default=5)
    args = ap.parse_args()

    runs_dir = Path(args.runs_dir)
    calls = _load_jsonl(Path(args.log))
    sources_by_run = load_evidence_sources(runs_dir)

    print("=" * 68)
    print("效果评估：搜索调用可用率 / 延迟 / Hit@k / nDCG@k")
    print("=" * 68)
    if not calls:
        print("没有 search_calls 数据。")
        return

    stats = analyse_calls(calls, sources_by_run, topk=args.topk)
    overall = stats["overall"]
    availability = overall["ok"] / overall["total"] * 100 if overall["total"] else 0.0

    print(f"\n总调用: {overall['total']} | 成功: {overall['ok']} | 可用率: {availability:.1f}%")
    print(f"成功调用延迟: {_fmt_latency(overall['durations'])}")

    print("\n按工具统计:")
    print(f"  {'tool':<24} {'calls':>6} {'ok':>6} {'avail%':>8} {'latency':<28} {'hit@k':>8} {'ndcg@k':>8}")
    for tool in sorted(stats["per_tool"]):
        t = stats["per_tool"][tool]
        avail = t["ok"] / t["total"] * 100 if t["total"] else 0.0
        hit = t["hits"] / t["retrieval_calls"] if t["retrieval_calls"] else float("nan")
        ndcg = t["ndcg_sum"] / t["retrieval_calls"] if t["retrieval_calls"] else float("nan")
        hit_s = f"{hit:.3f}" if t["retrieval_calls"] else "n/a"
        ndcg_s = f"{ndcg:.3f}" if t["retrieval_calls"] else "n/a"
        print(f"  {tool:<24} {t['total']:>6} {t['ok']:>6} {avail:>7.1f}% {_fmt_latency(t['durations']):<28} {hit_s:>8} {ndcg_s:>8}")

    print("\n检索质量（弱标注：evidence.json 来源）:")
    if stats["retrieval_calls"] == 0:
        print(
            "  当前 search_calls 中没有 result_urls，无法计算 Hit@k / nDCG@k。\n"
            "  已修改 agent 日志记录 result_urls；新 run 产生数据后本脚本会自动计算。"
        )
    else:
        hit_at_k = stats["hit_total"] / stats["retrieval_calls"]
        ndcg_at_k = stats["ndcg_sum"] / stats["retrieval_calls"]
        print(f"  可计算 query 数: {stats['retrieval_calls']}")
        print(f"  Hit@{args.topk}: {hit_at_k:.3f}")
        print(f"  nDCG@{args.topk}: {ndcg_at_k:.3f}")
        print("  注意：使用 evidence.json 最终引用来源作为弱相关标注，仅供趋势参考。")


if __name__ == "__main__":
    main()
