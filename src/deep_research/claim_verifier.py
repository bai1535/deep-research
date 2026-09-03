"""Atomic claim verification (Phase B).

After ClaimAnnotator produces claims.json, claims that are not already
covered by the research-phase verification are checked one-by-one using
quality search tools.  The results update status, confidence, evidence,
reasoning, and event IDs in the claim document.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from deep_research.agents.registry import create_agent
from deep_research.config import get_config
from deep_research.core.blackboard import Blackboard
from deep_research.core.file_cache import FileCache
from deep_research.eventsourcing import EventStore
from deep_research.models.schemas import EvidenceLink
from deep_research.response_parser import parse_json_response
from deep_research.tools import get_quality_search_tools
from deep_research.tools.web_fetch import WebFetchTool

logger = logging.getLogger("deep_research.claim_verifier")

ATOMIC_CLAIM_VERIFIER_TASK = """你是原子事实核查员。对下面这条 claim 进行独立核查。

用户问题：{question}

Claim：{claim_text}
Claim 类型：{claim_type}

## 要求
1. 使用搜索/抓取工具查找支持或反对这条 claim 的证据。
2. 如果 claim 属于常识性、低风险或当前无法验证的内容，可以输出 status=unverifiable 并说明原因。
3. 证据必须给出真实 URL；没有 URL 的证据不要写入。
4. 严格只输出 JSON，不要任何其他文字。

输出 JSON：
{{
  "status": "verified | suspect | disputed | false | unverifiable",
  "confidence": 0,
  "reasoning": "简要验证思路",
  "evidence": [
    {{
      "url": "https://...",
      "snippet": "关键原文片段",
      "support": "support | contradict | neutral",
      "source_reliability": 0,
      "tool": "bing_search | baidu_search | wikipedia_search | web_fetch | ..."
    }}
  ]
}}
"""


def _needs_verification(claim: dict) -> bool:
    """Return True when a claim has not been verified yet."""
    status = str(claim.get("status", "")).strip().lower()
    return status not in ("verified", "suspect", "disputed", "false")


_STATUS_MAP = {
    "verified": "verified",
    "confirm": "verified",
    "confirmed": "verified",
    "true": "verified",
    "suspect": "suspect",
    "uncertain": "suspect",
    "partial": "suspect",
    "partially verified": "suspect",
    "disputed": "disputed",
    "conflict": "disputed",
    "contradicted": "disputed",
    "contradict": "disputed",
    "false": "false",
    "refuted": "false",
    "refute": "false",
    "unverifiable": "unverifiable",
    "unknown": "unverifiable",
    "unable": "unverifiable",
    "unable to verify": "unverifiable",
}


def _normalize_status(status: str) -> str:
    s = status.strip().lower()
    if s in _STATUS_MAP:
        return _STATUS_MAP[s]
    if s.startswith("verif"):
        return "verified"
    if s.startswith("unverif"):
        return "unverifiable"
    if s.startswith("disput"):
        return "disputed"
    if s.startswith("suspect") or "partial" in s:
        return "suspect"
    if s.startswith("false") or s.startswith("refut"):
        return "false"
    return ""


def _normalize_confidence(value: Any) -> int:
    """Normalize a confidence value to 0-100.

    The model sometimes returns 0-1 decimals (0.9) or strings like "90%".
    """
    if value is None:
        return 0
    if isinstance(value, str):
        value = value.strip().rstrip("%").strip()
        if not value:
            return 0
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 0
    if 0 < num <= 1:
        num = num * 100
    return max(0, min(100, round(num)))


def _normalize_atomic_result(data: dict) -> dict | None:
    """Normalize the atomic verifier's JSON output."""
    status = _normalize_status(str(data.get("status", "")))
    if not status:
        logger.warning("Atomic claim verifier returned unknown status: %s", data.get("status"))
        return None

    confidence = _normalize_confidence(data.get("confidence"))
    if confidence == 0:
        # Missing/ambiguous confidence should still get a sensible default
        # that matches the verification status.
        if status == "verified":
            confidence = 70
        elif status == "suspect":
            confidence = 50
        elif status in ("disputed", "false"):
            confidence = 20

    raw_evidence = data.get("evidence") or []
    if not isinstance(raw_evidence, list):
        raw_evidence = []

    evidence: list[dict] = []
    for item in raw_evidence:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        support = str(item.get("support") or "neutral").lower()
        if support not in ("support", "contradict", "neutral"):
            support = "neutral"
        try:
            reliability = int(item.get("source_reliability", 0))
        except (TypeError, ValueError):
            reliability = 0
        evidence.append(
            EvidenceLink(
                url=url,
                tool=str(item.get("tool") or ""),
                event_id="",
                snippet=str(item.get("snippet") or "")[:300],
                source_reliability=max(0, min(5, reliability)),
                support=support,
            ).model_dump()
        )

    return {
        "status": status,
        "confidence": confidence,
        "reasoning": str(data.get("reasoning") or "")[:1000],
        "evidence": evidence,
    }


def _apply_verification(claim: dict, result: dict, event_ids: list[str]) -> None:
    """Write atomic verification results back into a claim dict."""
    claim["status"] = result["status"]
    claim["confidence"] = result["confidence"]
    claim["reasoning"] = result.get("reasoning", "")
    claim["evidence_links"] = result.get("evidence", [])
    if event_ids:
        existing = set(claim.get("event_ids") or [])
        existing.update(event_ids)
        claim["event_ids"] = sorted(existing)


class AtomicClaimVerifier:
    """Verify uncovered claims one by one using quality search tools."""

    def __init__(
        self,
        blackboard: Blackboard | None = None,
        file_cache: FileCache | None = None,
        base_dir: str | Path | None = None,
    ) -> None:
        self.blackboard = blackboard or Blackboard()
        self.file_cache = file_cache or FileCache()
        self.event_store = EventStore(base_dir or Path(get_config().output_dir))
        self._before_count = 0

    def _trace_id(self) -> str:
        return str(self.blackboard.read("trace_id", ""))

    def _collect_event_ids(self, run_id: str) -> list[str]:
        events = self.event_store.load(run_id)
        return [e.event_id for e in events if e.seq > self._before_count]

    async def _verify_one(self, run_id: str, claim: dict, question: str) -> dict | None:
        self._before_count = len(self.event_store.load(run_id))
        task = ATOMIC_CLAIM_VERIFIER_TASK.format(
            question=question,
            claim_text=str(claim.get("text", "")),
            claim_type=str(claim.get("claim_type", "")),
        )
        try:
            agent = create_agent(
                name="claim-atomic-verifier",
                role="原子事实核查员",
                goal="对单条 claim 进行独立核查，输出状态、置信度和证据。",
                backstory=(
                    "你擅长把一条 claim 放到问题约束下用搜索证据检验，"
                    "既不轻信也不过度怀疑。"
                ),
                tools=[*get_quality_search_tools(), WebFetchTool()],
                llm="deepseek",
                blackboard=self.blackboard,
                file_cache=self.file_cache,
                trace_id=self._trace_id(),
                response_format={"type": "json_object"},
            )
            raw = await agent.run(task)
        except Exception as exc:
            logger.warning("Atomic claim verifier agent failed for %s: %s", claim.get("claim_id"), exc)
            return None

        result = parse_json_response(raw, context="claim_atomic_verifier")
        if not result.success or not isinstance(result.data, dict):
            logger.warning("Atomic claim verifier parse failed for %s", claim.get("claim_id"))
            return None
        return _normalize_atomic_result(result.data)

    async def verify_claims(
        self,
        run_id: str,
        claims_doc: dict[str, Any] | None,
        question: str,
    ) -> dict[str, Any] | None:
        """Verify all uncovered claims in an AnswerDocument dict in place."""
        if not claims_doc or not isinstance(claims_doc, dict):
            return claims_doc

        claims = claims_doc.get("claims")
        if not isinstance(claims, list):
            return claims_doc

        verified_count = 0
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            if not _needs_verification(claim):
                continue
            result = await self._verify_one(run_id, claim, question)
            if result is None:
                continue
            event_ids = self._collect_event_ids(run_id)
            _apply_verification(claim, result, event_ids)
            verified_count += 1
            logger.info(
                "Atomic claim verified: claim=%s status=%s confidence=%d evidence=%d events=%d",
                claim.get("claim_id"),
                result["status"],
                result["confidence"],
                len(result.get("evidence", [])),
                len(event_ids),
            )

        logger.info(
            "Atomic claim verification: run=%s verified=%d total=%d",
            run_id,
            verified_count,
            len(claims),
        )
        return claims_doc


__all__ = [
    "AtomicClaimVerifier",
    "ATOMIC_CLAIM_VERIFIER_TASK",
    "_needs_verification",
    "_normalize_status",
    "_normalize_confidence",
    "_normalize_atomic_result",
    "_apply_verification",
]
