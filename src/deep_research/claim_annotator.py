"""Claim-level provenance annotator (Phase A).

The final report is never rewritten.  This module adds a non-destructive
annotation layer (claims.json) that maps answer sentences to the
research-phase claims, verification status, and available evidence URLs.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from deep_research.agents.registry import create_agent
from deep_research.core.blackboard import Blackboard
from deep_research.core.file_cache import FileCache
from deep_research.models.schemas import (
    AnswerDocument,
    ClaimNode,
    ClaimSourceRef,
    EvidenceLink,
)
from deep_research.response_parser import parse_json_response

logger = logging.getLogger("deep_research.claim_annotator")

MAX_SCOPE_CHARS = 16000

_HEADING_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
_SECTION_PATTERNS = [
    re.compile(r"^##\s*1\.\s*直接回答\s*$", re.MULTILINE),
    re.compile(r"^##\s*直接回答\s*$", re.MULTILINE),
    re.compile(r"^##\s*1\.\s*Direct Answer\s*$", re.MULTILINE),
    re.compile(r"^##\s*2\.\s*关键证据\s*$", re.MULTILINE),
    re.compile(r"^##\s*关键证据\s*$", re.MULTILINE),
    re.compile(r"^##\s*执行摘要\s*$", re.MULTILINE),
    re.compile(r"^##\s*Executive Summary\s*$", re.MULTILINE),
]

CLAIM_ANNOTATOR_TASK = """你是 Claim 标注员。你的任务是从最终报告中抽取“可独立验证的事实单元”，并尽量映射到研究阶段已有的 claim。

用户问题：
{question}

## 待标注文本
以下是最终报告的原文（可能是截取片段）。**claim 的 text 必须是这段文本的连续子串，原样复制，不允许改写、概括或新增内容。**

{scope}

## 研究 Claim 池
以下是研究阶段已经发现并验证过的 claim，供你映射复用：

{claim_pool}

## 抽取规则
1. 一个 claim 必须同时满足：
   - 可独立验证（单独拿出来能判断真伪）
   - 原子事实（只含一个主谓宾事实，不含并列事实）
   - 对回答用户问题有支撑作用
2. 不要拆时间状语、修饰语、逻辑连接词、元话语（如“根据多个来源”）。
3. 如果一句包含多个并列事实，拆成多个 claim；如果拿不准，保留一个较概括的父 claim，并把细分作为子 claim（parent_claim_index 指向父 claim 在 claims 数组中的下标）。
4. 优先把答案 claim 映射到研究 Claim 池中已有的 claim；能映射就填 source_claim_ref，不能映射就填 null。
5. 只输出 JSON，不要任何其他文字。

输出 JSON：
{{
  "claims": [
    {{
      "text": "原文连续子串",
      "claim_type": "direct_answer | supporting | contextual",
      "parent_claim_index": null,
      "source_claim_ref": {{"card_index": 0, "claim_index": 0}}
    }}
  ],
  "overall_confidence": 80
}}
"""


def _extract_annotation_scope(report_text: str, max_chars: int = MAX_SCOPE_CHARS) -> str:
    """Return a compact annotation scope, preferring answer-like sections.

    The scope is only for the LLM prompt; spans are later located in the
    full original report_text.
    """
    if len(report_text) <= max_chars:
        return report_text

    parts: list[str] = []
    for pattern in _SECTION_PATTERNS:
        m = pattern.search(report_text)
        if m:
            start = m.start()
            nxt = _HEADING_RE.search(report_text, m.end())
            end = nxt.start() if nxt else len(report_text)
            section = report_text[start:end].strip()
            if section:
                parts.append(section)

    if parts:
        text = "\n\n".join(parts)
        return text[:max_chars] if len(text) > max_chars else text
    return report_text[:max_chars]


def _find_span(report_text: str, claim_text: str) -> dict | None:
    """Return the first exact-substring span of claim_text in report_text."""
    start = report_text.find(claim_text)
    if start < 0:
        return None
    return {"start": start, "end": start + len(claim_text)}


def _build_verification_map(verified: list) -> dict:
    """Map (perspective, claim_index) -> verification info."""
    result: dict[tuple, dict] = {}
    for vc in verified or []:
        if isinstance(vc, dict):
            perspective = vc.get("perspective", "")
            entries = vc.get("entries", []) or []
        else:
            perspective = getattr(vc, "perspective", "")
            entries = getattr(vc, "entries", []) or []
        for entry in entries:
            if isinstance(entry, dict):
                idx = entry.get("claim_index")
                status = entry.get("status", "")
                reasoning = entry.get("reasoning", "")
                checked = entry.get("checked_sources", []) or []
            else:
                idx = getattr(entry, "claim_index", None)
                status = getattr(entry, "status", "")
                reasoning = getattr(entry, "reasoning", "")
                checked = getattr(entry, "checked_sources", []) or []
            if hasattr(status, "value"):
                status = status.value
            result[(perspective, idx)] = {
                "status": str(status),
                "reasoning": str(reasoning),
                "checked_sources": list(checked),
            }
    return result


def _build_claim_pool(cards: list, verified: list) -> list[dict]:
    """Build a compact pool of research-phase claims with verification info."""
    vmap = _build_verification_map(verified)
    pool: list[dict] = []
    for ci, card in enumerate(cards or []):
        if isinstance(card, dict):
            perspective = card.get("perspective", "")
            findings = card.get("key_findings", []) or []
        else:
            perspective = getattr(card, "perspective", "")
            findings = getattr(card, "key_findings", []) or []
        for ji, claim in enumerate(findings):
            if isinstance(claim, dict):
                text = claim.get("text", "")
                conf = claim.get("confidence", "")
                sources = claim.get("sources", []) or []
            else:
                text = getattr(claim, "text", "")
                conf = getattr(claim, "confidence", "")
                sources = getattr(claim, "sources", []) or []
            if hasattr(conf, "value"):
                conf = conf.value
            vinfo = vmap.get((perspective, ji), {})
            pool.append({
                "card_index": ci,
                "perspective": perspective,
                "claim_index": ji,
                "text": text,
                "confidence": str(conf),
                "sources": list(sources),
                "status": vinfo.get("status", ""),
                "reasoning": vinfo.get("reasoning", ""),
                "checked_sources": vinfo.get("checked_sources", []) or [],
            })
    return pool


def _format_claim_pool(pool: list[dict]) -> str:
    if not pool:
        return "(无)"
    lines: list[str] = []
    for item in pool:
        sources = "、".join(str(s) for s in item["sources"][:5]) or "无"
        status = item["status"] or "未验证"
        lines.append(
            f"[{item['card_index']}-{item['claim_index']}] ({item['perspective']}) "
            f"{item['text'][:300]}"
        )
        lines.append(f"  置信度: {item['confidence']} | 来源: {sources}")
        lines.append(f"  验证: {status} — {item['reasoning'][:200]}")
    return "\n".join(lines)


def _confidence_from_pool(item: dict) -> int:
    status = item.get("status", "")
    if status == "verified":
        return 80
    if status == "suspect":
        return 50
    if status == "disputed":
        return 40
    if status == "false":
        return 10
    conf = str(item.get("confidence", "")).lower()
    if conf in ("high", "high置信度", "高"):
        return 75
    if conf in ("medium", "中"):
        return 55
    if conf in ("low", "低"):
        return 35
    return 0


def _enrich_claim(claim: ClaimNode, pool: list[dict], source_ref: ClaimSourceRef | None) -> None:
    """Fill status/confidence/evidence from the research-phase claim pool."""
    if source_ref is None:
        claim.status = "unverifiable"
        claim.confidence = 0
        return

    match = None
    for item in pool:
        if (
            item["card_index"] == source_ref.card_index
            and item["claim_index"] == source_ref.claim_index
        ):
            match = item
            break

    if match is None:
        claim.status = "unverifiable"
        claim.confidence = 0
        return

    status = match.get("status", "")
    if status in ("verified", "suspect", "disputed", "false"):
        claim.status = status
    else:
        claim.status = "unverifiable"

    claim.confidence = _confidence_from_pool(match)
    claim.reasoning = match.get("reasoning", "")

    urls: list[str] = []
    seen: set[str] = set()
    for raw_url in [*match.get("sources", []), *match.get("checked_sources", [])]:
        url = str(raw_url).strip()
        if url and url not in seen:
            seen.add(url)
            urls.append(url)

    for url in urls[:10]:
        claim.evidence_links.append(
            EvidenceLink(
                url=url,
                tool="",
                event_id="",
                snippet="",
                source_reliability=0,
                support="neutral",
            )
        )


class ClaimAnnotator:
    """Extract non-destructive claim annotations from a final report."""

    def __init__(
        self,
        blackboard: Blackboard | None = None,
        file_cache: FileCache | None = None,
    ) -> None:
        self.blackboard = blackboard or Blackboard()
        self.file_cache = file_cache or FileCache()

    def _trace_id(self) -> str:
        return str(self.blackboard.read("trace_id", ""))

    async def annotate(
        self,
        run_id: str,
        report_text: str,
        question: str,
        cards: list,
        verified: list,
        score: Any | None = None,
    ) -> dict | None:
        """Run the annotator and return an AnswerDocument as a dict.

        Returns None on any failure so the main pipeline is never blocked.
        """
        if not report_text or not report_text.strip():
            logger.warning("Claim annotation skipped: empty report")
            return None

        scope = _extract_annotation_scope(report_text)
        pool = _build_claim_pool(cards, verified)
        task = CLAIM_ANNOTATOR_TASK.format(
            question=question,
            scope=scope,
            claim_pool=_format_claim_pool(pool),
        )

        try:
            agent = create_agent(
                name="claim-annotator",
                role="Claim 标注员",
                goal="从最终报告中抽取可独立验证的事实单元，并映射到研究阶段的 claim。",
                backstory=(
                    "你擅长在不改写原文的前提下，把答案拆成适合验证的原子事实，"
                    "并尽量复用研究阶段已有的 claim。"
                ),
                tools=[],
                llm="deepseek",
                blackboard=self.blackboard,
                file_cache=self.file_cache,
                trace_id=self._trace_id(),
                response_format={"type": "json_object"},
            )
            raw = await agent.run(task)
        except Exception as exc:
            logger.warning("Claim annotator agent failed: %s", exc)
            return None

        result = parse_json_response(raw, context="claim_annotator")
        if not result.success or not isinstance(result.data, dict):
            logger.warning("Claim annotator parse failed; skipping")
            return None

        doc = self._build_document(run_id, report_text, result.data, pool, score)
        logger.info(
            "Claim annotation: run=%s claims=%d overall=%d",
            run_id,
            len(doc.claims),
            doc.overall_confidence,
        )
        return doc.model_dump()

    def _build_document(
        self,
        run_id: str,
        report_text: str,
        data: dict,
        pool: list[dict],
        score: Any | None = None,
    ) -> AnswerDocument:
        raw_claims = data.get("claims") or []
        if not isinstance(raw_claims, list):
            raw_claims = []

        claims: list[ClaimNode] = []
        for i, raw in enumerate(raw_claims):
            if not isinstance(raw, dict):
                continue
            text = str(raw.get("text") or "").strip()
            if not text:
                continue
            span = _find_span(report_text, text)
            if span is None:
                logger.debug("Claim text not found in report; skipped: %s", text[:80])
                continue

            source_ref = None
            ref = raw.get("source_claim_ref")
            if isinstance(ref, dict) and (
                ref.get("card_index") is not None or ref.get("claim_index") is not None
            ):
                source_ref = ClaimSourceRef(
                    perspective=str(ref.get("perspective") or ""),
                    card_index=ref.get("card_index"),
                    claim_index=ref.get("claim_index"),
                )

            parent_id = None
            parent_index = raw.get("parent_claim_index")
            if isinstance(parent_index, int) and 0 <= parent_index < len(claims):
                parent_id = claims[parent_index].claim_id

            claim = ClaimNode(
                claim_id=f"c{i}",
                text=text,
                claim_type=str(raw.get("claim_type") or "direct_answer"),
                span=span,
                parent_claim_id=parent_id,
                source_claim_ref=source_ref,
            )
            _enrich_claim(claim, pool, source_ref)
            claims.append(claim)

        overall = data.get("overall_confidence")
        try:
            overall = int(overall)
        except (TypeError, ValueError):
            overall = None
        if overall is None and score is not None:
            overall = getattr(score, "overall_score", None)
        if overall is None and claims:
            overall = round(sum(c.confidence for c in claims) / len(claims))
        if overall is None:
            overall = 0

        return AnswerDocument(
            run_id=run_id,
            original_text=report_text,
            overall_confidence=overall,
            claims=claims,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )


__all__ = [
    "ClaimAnnotator",
    "CLAIM_ANNOTATOR_TASK",
    "_extract_annotation_scope",
    "_find_span",
    "_build_claim_pool",
    "_format_claim_pool",
    "_enrich_claim",
]
