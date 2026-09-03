#!/usr/bin/env python3
"""Automated judge for deep-research evaluation results.

Reads an eval JSONL (from scripts/eval_benchmarks.py), compares each
record's `final_answer` against `gold` using DeepSeek as a judge, and
appends a `judge` field to each record.

Usage:
  python scripts/eval_judge.py --input eval_results/run-browsecomp_plus.jsonl
  python scripts/eval_judge.py --input eval_results/run-browsecomp_plus.jsonl --limit 10
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import deep_research.qwen_patch  # noqa: F401
import litellm

from deep_research.config import get_config
from deep_research.response_parser import parse_json_response

JUDGE_PROMPT = """你是一个严谨的评测裁判。判断模型的最终答案是否与标准答案匹配。

问题：{question}

标准答案（gold）：{gold}

模型最终答案：{answer}

判断规则：
- 如果模型答案与标准答案含义一致（包括翻译、别名、大小写差异），输出 yes
- 如果部分相关但不够准确，输出 partial
- 如果错误或无法确定，输出 no
- score 0-100，表示匹配程度

严格只输出 JSON：
{{"match": "yes|partial|no", "score": 0, "reason": "简要说明"}}"""


def judge_one(question: str, gold: str, answer: str, config) -> dict:
    """Call the LLM judge for one record."""
    prompt = JUDGE_PROMPT.format(question=question, gold=gold, answer=answer)
    try:
        resp = litellm.completion(
            model=f"openai/{config.deepseek.model}",
            base_url=config.deepseek.base_url,
            api_key=config.deepseek.api_key,
            messages=[
                {"role": "system", "content": "你是一个严格的答案评测裁判。"},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or ""
        result = parse_json_response(raw, context="eval_judge")
        if not result.success or not isinstance(result.data, dict):
            return {"match": "error", "score": 0, "reason": f"judge parse failed: {raw[:200]}"}
        data = result.data
        match = str(data.get("match", "no")).lower()
        if match not in ("yes", "partial", "no"):
            match = "no"
        try:
            score = int(data.get("score", 0))
        except (TypeError, ValueError):
            score = 0
        return {
            "match": match,
            "score": max(0, min(100, score)),
            "reason": str(data.get("reason", ""))[:500],
        }
    except Exception as exc:  # noqa: BLE001
        return {"match": "error", "score": 0, "reason": str(exc)[:300]}


def main() -> None:
    ap = argparse.ArgumentParser(description="Judge eval results with an LLM.")
    ap.add_argument("--input", type=Path, required=True, help="Path to eval JSONL")
    ap.add_argument("--output", type=Path, default=None, help="Output JSONL (default: overwrite input with .judged.jsonl)")
    ap.add_argument("--limit", type=int, default=0, help="Max records to judge (0=all)")
    args = ap.parse_args()

    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    output = args.output or args.input.with_suffix(".judged.jsonl")
    config = get_config()
    rows = []
    with args.input.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    judged = 0
    with output.open("w", encoding="utf-8") as out:
        for row in rows:
            if args.limit and judged >= args.limit:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                continue
            gold = row.get("gold")
            answer = row.get("final_answer") or ""
            question = row.get("prompt") or ""
            if not gold or not answer:
                row["judge"] = {"match": "skipped", "score": 0, "reason": "missing gold or final_answer"}
            else:
                row["judge"] = judge_one(question, str(gold), answer, config)
                judged += 1
            out.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Summary
    from collections import Counter
    counts = Counter((r.get("judge") or {}).get("match") for r in rows if r.get("judge"))
    print(f"Judged {judged} record(s), wrote {output}")
    print("Summary:", dict(counts))


if __name__ == "__main__":
    main()
