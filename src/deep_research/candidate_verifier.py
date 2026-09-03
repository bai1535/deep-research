"""Candidate answer verification loop.

For discrete-answer question types (entity_fact, multi_hop_clue,
historical_archive), after research produces candidate entities we run a
focused verification pass: each candidate is checked against the
question's constraints using quality search tools, and a final_candidate
is selected.

For open-ended types (technical, academic, news, etc.) this loop is
skipped entirely.
"""

from __future__ import annotations

import logging
from typing import Any

from deep_research.agents.registry import create_agent
from deep_research.core.blackboard import Blackboard
from deep_research.core.file_cache import FileCache
from deep_research.response_parser import parse_json_response
from deep_research.tools import get_quality_search_tools

logger = logging.getLogger("deep_research.candidate_verifier")

# Only these question types get the candidate verification loop.
SUITABLE_TYPES = {"entity_fact", "multi_hop_clue", "historical_archive"}

# A candidate below this score/confidence is not forced as the final answer.
MIN_FINAL_CONFIDENCE = 50

CANDIDATE_VERIFIER_TASK = """你是候选答案验证员。用户的问题有明确候选答案，你需要用搜索工具逐条验证，最终给出最可能的唯一答案。

问题：{question}
问题类型：{question_type}
关键约束：{constraints}

## 研究阶段发现的候选与线索
{findings_summary}

## 要求
1. 从研究内容中提取候选实体（机构/人物/地点/作品等），不要凭空编造。
2. 对每个候选，逐条对照关键约束进行搜索验证。
3. 能直接证实某条约束的，记录证据 URL；不能证实的标记为未匹配。
4. 只有证据最完整、匹配线索最多的候选才能作为 final_candidate。
5. 如果所有候选都无法满足足够线索，final_candidate 可以为 null，并说明原因。

输出 JSON：
{{
  "candidates": [
    {{
      "name": "候选名称",
      "score": 0,
      "matched_clues": ["已匹配的约束"],
      "unmatched_clues": ["未匹配的约束"],
      "evidence_urls": ["https://..."],
      "verdict": "candidate"
    }}
  ],
  "final_candidate": "最终候选名称或 null",
  "confidence": 0,
  "reasoning": "验证思路与结论"
}}

严格只输出 JSON，不要任何其他文字。"""


def _is_suitable(question_type: str) -> bool:
    return question_type in SUITABLE_TYPES


def _build_findings_summary(cards: list, verified: list) -> str:
    lines: list[str] = []
    for card in cards:
        p = getattr(card, "perspective", "?")
        lines.append(f"━━━ {p} ━━━")
        for claim in getattr(card, "key_findings", []) or []:
            text = getattr(claim, "text", "")
            sources = getattr(claim, "sources", []) or []
            lines.append(f"- {text[:300]}")
            if sources:
                lines.append(f"  来源: {', '.join(str(s) for s in sources[:5])}")
    for vc in verified or []:
        lines.append(f"━━━ 验证 {getattr(vc, 'perspective', '?')} ━━━")
        for entry in getattr(vc, "entries", []) or []:
            lines.append(f"- 声明#{getattr(entry, 'claim_index', '?')}: {getattr(entry, 'status', '?')} — {getattr(entry, 'reasoning', '')[:200]}")
    text = "\n".join(lines)
    return text[:8000]


def _normalize_result(data: dict) -> dict:
    """Normalize LLM candidate output into the canonical candidates[] shape.

    The model sometimes returns a single candidate object instead of
    {"candidates": [...], "final_candidate": ...}.  Accept both shapes.
    """
    if "candidates" in data and isinstance(data.get("candidates"), list):
        return data
    if data.get("name"):
        candidate = {
            "name": data.get("name"),
            "score": data.get("score", 0),
            "matched_clues": data.get("matched_clues", []) or [],
            "unmatched_clues": data.get("unmatched_clues", []) or [],
            "evidence_urls": data.get("evidence_urls", []) or [],
            "verdict": data.get("verdict", "candidate"),
        }
        final_candidate = data.get("final_candidate")
        score = candidate.get("score") or 0
        if not final_candidate and candidate.get("verdict") == "candidate" and score >= MIN_FINAL_CONFIDENCE:
            final_candidate = candidate["name"]
        return {
            "candidates": [candidate],
            "final_candidate": final_candidate,
            "confidence": data.get("confidence") or data.get("score"),
            "reasoning": data.get("reasoning", ""),
        }
    return data


def format_candidate_verification(result: dict | None) -> str:
    """Render candidate verification result for the Editor data summary."""
    if not result:
        return ""
    lines = ["━━━ 候选答案验证 ━━━"]
    final_candidate = result.get("final_candidate")
    confidence = result.get("confidence")
    if final_candidate:
        lines.append(f"最终候选: {final_candidate}（置信度 {confidence}/100）")
    if result.get("reasoning"):
        lines.append(f"验证思路: {result['reasoning'][:600]}")
    candidates = result.get("candidates") or []
    for c in candidates[:6]:
        name = c.get("name", "?")
        score = c.get("score", 0)
        verdict = c.get("verdict", "?")
        matched = "、".join(c.get("matched_clues", [])[:5]) or "无"
        unmatched = "、".join(c.get("unmatched_clues", [])[:5]) or "无"
        lines.append(f"- {name} [score={score} verdict={verdict}]")
        lines.append(f"  匹配: {matched}")
        lines.append(f"  未匹配: {unmatched}")
    return "\n".join(lines)


class CandidateVerifier:
    """Runs the candidate verification loop for suitable question types."""

    def __init__(
        self,
        blackboard: Blackboard | None = None,
        file_cache: FileCache | None = None,
    ) -> None:
        self.blackboard = blackboard or Blackboard()
        self.file_cache = file_cache or FileCache()

    def _trace_id(self) -> str:
        return str(self.blackboard.read("trace_id", ""))

    async def verify(
        self,
        question: str,
        cards: list,
        verified: list,
    ) -> dict | None:
        """Verify candidates; returns None when the question type is unsuitable."""
        search_plan = self.blackboard.read("search_plan") or {}
        qtype = str(search_plan.get("question_type", "general"))
        if not _is_suitable(qtype):
            logger.info("Candidate verification skipped: type=%s", qtype)
            return None

        constraints = search_plan.get("key_constraints") or []
        findings = _build_findings_summary(cards, verified)
        task = CANDIDATE_VERIFIER_TASK.format(
            question=question,
            question_type=qtype,
            constraints="、".join(str(c) for c in constraints[:12]) or "无",
            findings_summary=findings,
        )

        try:
            agent = create_agent(
                name="candidate-verifier",
                role="候选答案验证员",
                goal="对候选实体逐条验证，输出最可能的唯一答案。",
                backstory=(
                    "你擅长把候选答案放到题目约束下逐条检验，"
                    "用搜索证据排除错误候选。"
                ),
                tools=get_quality_search_tools(),
                llm="deepseek",
                blackboard=self.blackboard,
                file_cache=self.file_cache,
                trace_id=self._trace_id(),
                response_format={"type": "json_object"},
            )
            raw = await agent.run(task)
        except Exception as exc:
            logger.warning("Candidate verifier agent failed: %s", exc)
            return None

        result = parse_json_response(raw, context="candidate_verifier")
        if not result.success or not isinstance(result.data, dict):
            logger.warning("Candidate verifier parse failed; skipping")
            return None

        data = _normalize_result(result.data)
        # Never force a very low-confidence candidate as the final answer.
        if data.get("final_candidate"):
            try:
                conf = float(data.get("confidence") if data.get("confidence") is not None else 0)
            except (TypeError, ValueError):
                conf = 0
            if conf < MIN_FINAL_CONFIDENCE:
                logger.info("Candidate verification final suppressed: confidence=%.1f < %d", conf, MIN_FINAL_CONFIDENCE)
                data["final_candidate"] = None
        self.blackboard.write("candidate_verification", data)
        logger.info(
            "Candidate verification: final=%s confidence=%s candidates=%d",
            data.get("final_candidate"),
            data.get("confidence"),
            len(data.get("candidates") or []),
        )
        return data


__all__ = [
    "CandidateVerifier",
    "SUITABLE_TYPES",
    "CANDIDATE_VERIFIER_TASK",
    "format_candidate_verification",
]
