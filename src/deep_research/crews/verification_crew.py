"""Phase 2: 3-round adversarial verification per ResearchCard + cross-card analysis.

Each card is independently verified.  Cards with zero findings are skipped.
After per-card verification, a cross-card analyser identifies claims that
appear in multiple perspectives and flags agreements / contradictions.
"""

from __future__ import annotations

import logging

from deep_research.config import get_config
from deep_research.core.blackboard import Blackboard
from deep_research.core.file_cache import FileCache
from deep_research.core.orchestrator import parallel
from deep_research.agents.registry import (
    VERIFIER_CONFIG,
    REFUTER_CONFIG,
    create_agent,
)
from deep_research.db import Repository
from deep_research.models.enums import VerificationStatus
from deep_research.models.schemas import ResearchCard, VerifiedCard, VerificationEntry, RefutationEntry
from deep_research.response_parser import parse_json_response
from deep_research.safe_construct import safe_construct_list
from deep_research.tools import WebFetchTool, SQLiteReadTool, get_quality_search_tools
from deep_research.tools.web_fetch import classify_url

logger = logging.getLogger("deep_research.crews.verification")

def _normalise_verification_status(value: str) -> str:
    """Map loose Verifier status strings to the canonical enum values."""
    text = str(value or "").strip().lower()
    if text in ("verified", "suspect", "false", "disputed"):
        return text
    if "partially" in text or "partial" in text or "uncertain" in text or "unknown" in text:
        return "suspect"
    if "verif" in text or "verf" in text or "true" in text or "correct" in text or "confirm" in text or "支持" in text:
        return "verified"
    if "false" in text or "incorrect" in text or "wrong" in text or "reject" in text or "否定" in text:
        return "false"
    if "disput" in text or "conflict" in text or "争议" in text:
        return "disputed"
    if "suspect" in text or "可疑" in text:
        return "suspect"
    return "suspect"



def _normalise_fact_status(value: str) -> str:
    """Normalize fact_status while allowing 'unverifiable' (not an enum status)."""
    text = str(value or "").strip().lower()
    if text in ("verified", "suspect", "false", "disputed", "unverifiable"):
        return text
    if "unverif" in text or "unable" in text or "cannot verify" in text or "无法" in text:
        return "unverifiable"
    return _normalise_verification_status(text)


def _normalise_entries(entries: list) -> list:
    """Normalize status fields in a list of entry dicts before Pydantic."""
    for e in entries or []:
        if isinstance(e, dict):
            if "status" in e:
                e["status"] = _normalise_verification_status(e["status"])
            if e.get("fact_status") is not None:
                e["fact_status"] = _normalise_fact_status(e["fact_status"])
    return entries


def _entry_status_value(entry) -> str:
    status = getattr(entry, "status", "")
    return getattr(status, "value", str(status))


def _merge_entries(first_entries: list[VerificationEntry], second_entries: list[VerificationEntry]) -> list[VerificationEntry]:
    """Merge first-pass verification with an independent second opinion.

    The second opinion is allowed to upgrade a claim back to verified when it
    confirms the underlying fact, even if the first pass was downgraded for
    presentation/wording reasons.  It can also downgrade a claim when it finds
    a real factual problem.
    """
    second_map = {e.claim_index: e for e in second_entries}
    merged: list[VerificationEntry] = []

    for fe in first_entries:
        se = second_map.get(fe.claim_index)
        if se is None:
            merged.append(fe)
            continue

        f_status = _entry_status_value(fe)
        s_fact = str(getattr(se, "fact_status", "") or _entry_status_value(se)).lower()
        s_status = _entry_status_value(se)

        if "false" in (f_status, s_fact):
            final_status = "false"
        elif f_status == "verified" and s_fact == "verified":
            final_status = "verified"
        elif f_status == "verified" and s_fact in ("suspect", "disputed"):
            # Independent reviewer found a real problem.
            final_status = s_fact
        elif f_status in ("suspect", "disputed") and s_fact == "verified":
            # Independent reviewer confirms the underlying fact.
            final_status = "verified"
        elif f_status == "disputed" or s_fact == "disputed":
            final_status = "disputed"
        elif f_status == "suspect" or s_fact == "suspect":
            final_status = "suspect"
        else:
            final_status = f_status

        reasoning = fe.reasoning
        if se.reasoning:
            reasoning = f"{reasoning} | 独立复核: {se.reasoning}".strip(" |")
        sources = list(dict.fromkeys([*fe.checked_sources, *se.checked_sources]))

        merged.append(VerificationEntry(
            claim_index=fe.claim_index,
            claim_text=fe.claim_text or se.claim_text,
            status=VerificationStatus(final_status),
            reasoning=reasoning,
            checked_sources=sources,
            fact_status=s_fact,
            confidence=se.confidence,
            presentation_issues=list(getattr(se, "presentation_issues", []) or []),
        ))

    return merged


VERIFY_TASK = """你正在核查一份来自「{perspective}」视角的 ResearchCard。

研究问题：{research_question}

待核查声明：
{claims_text}

对以上每条声明：
1. 使用 web_fetch 工具检查引用 URL 是否可访问
2. 阅读来源内容，确认声明是否真正被支持
3. 评估置信度评级（high/medium/low）是否合理

输出 JSON：
{{
  "entries": [
    {{"claim_index": 0, "claim_text": "...", "status": "verified/suspect/false", "reasoning": "...", "checked_sources": ["..."]}}
  ],
  "summary": "总体评估"
}}

严格只输出 JSON。"""

SECOND_OPINION_TASK = """你是一位独立二次核查员。你没有看过之前的核查结论，只根据原始声明和可访问来源独立判断。

研究问题：{research_question}
视角：{perspective}

待核查声明：
{claims_text}

## 要求
1. 使用搜索/抓取工具独立查找支持或反对证据。
2. 对每条声明，区分两件事：
   - `fact_status`：事实本身是否成立（verified / suspect / disputed / false / unverifiable）
   - `status`：综合验证状态（verified / suspect / disputed / false）
   - `presentation_issues`：如果事实成立但原表述有口径、措辞、上下文等提醒，写在这里；**不要因为这些提醒把 fact_status 降级**
3. 给出 0-100 的 `confidence`，表示你对事实判断的把握。

输出 JSON：
{{
  "entries": [
    {{
      "claim_index": 0,
      "claim_text": "...",
      "fact_status": "verified",
      "status": "verified",
      "confidence": 85,
      "reasoning": "独立核查思路",
      "presentation_issues": ["如有口径提醒，写这里；没有则为空"],
      "checked_sources": ["https://..."]
    }}
  ],
  "summary": "独立复核总体结论"
}}

严格只输出 JSON。"""

REFUTE_TASK = """你是魔鬼代言人，正在审查一份 ResearchCard 及其核查报告。

视角：{perspective}
研究问题：{research_question}

原始声明：
{claims_text}

核查结果：
{verification_text}

对每条声明，尝试找出：
1. 削弱或反驳该声明的反向证据
2. 逻辑缺陷或过度泛化
3. 改变解读方式的缺失上下文

使用搜索工具寻找反对观点。

输出 JSON：
{{
  "refutations": [
    {{"claim_index": 0, "claim_text": "...", "challenge": "...", "severity": "critical/moderate/minor", "counter_evidence": ["..."]}}
  ]
}}

严格只输出 JSON。"""

REBUTTAL_TASK = """你是核查员，正在回应反驳者的质疑。

视角：{perspective}

原始声明：
{claims_text}

你的原始核查：
{verification_text}

反驳者质疑：
{refutation_text}

对每条质疑，决定：
- ACCEPT：反驳正确——更新声明状态
- REJECT：反驳错误——解释为什么质疑无效
- DISPUTED：无法确定——标记为 disputed

输出最终 VerifiedCard JSON：
{{
  "entries": [{{"claim_index": 0, "claim_text": "...", "status": "verified/suspect/false/disputed", "reasoning": "...", "checked_sources": ["..."]}}],
  "refutations": [...],
  "resolved": true/false,
  "summary": "最终评估"
}}

严格只输出 JSON。"""

CROSS_CHECK_TASK = """你正在对所有视角的研究声明做交叉比对。

以下是各视角的声明汇总：
{cross_text}

找出以下情况：
1. **同一事实、不同表述**：两个视角描述了同一个事实但措辞不同。标注为 "consistent"。
2. **直接矛盾**：一个视角的声明与另一个视角的声明冲突。标注为 "contradiction"。
3. **互补证据**：两个视角各自提供了同一主题的不同侧面，合在一起更完整。标注为 "complementary"。

输出 JSON：
{{
  "cross_checks": [
    {{
      "topic": "简短主题描述",
      "perspectives": ["technical", "industry"],
      "relation": "consistent/contradiction/complementary",
      "claim_a": "视角A的声明原文",
      "claim_b": "视角B的声明原文",
      "assessment": "为什么它们是 consistent/contradiction/complementary"
    }}
  ]
}}

输出所有有实际交叉关系的条目，严格只输出 JSON。"""



CONTRADICTION_ADJUDICATOR_TASK = """你是矛盾裁决员。研究的不同视角对同一问题给出了矛盾结论，你需要根据已有证据判定哪一方更可信。

以下是各视角的声明和核查摘要：
{cross_text}

对每一组矛盾，输出：
{{
  "resolutions": [
    {{
      "topic": "矛盾主题",
      "winner": "更可信的一方/结论",
      "loser": "被削弱的一方",
      "reason": "为什么这一方更可信",
      "evidence_urls": ["支持 winner 的 URL"]
    }}
  ],
  "summary": "总体裁决说明"
}}

严格只输出 JSON。"""
class VerificationCrewRunner:
    """Runs Phase 2 with core.Agent."""

    def __init__(
        self,
        blackboard: Blackboard | None = None,
        file_cache: FileCache | None = None,
    ) -> None:
        self.config = get_config()
        self.blackboard = blackboard or Blackboard()
        self.file_cache = file_cache or FileCache()

    def _trace_id(self) -> str:
        return str(self.blackboard.read("trace_id", ""))

    async def run(self, cards: list[ResearchCard], run_id: str) -> list[VerifiedCard]:
        # ── Per-card verification (parallel) ──────────────────────
        async def verify_one(card: ResearchCard) -> VerifiedCard | None:
            if not card.key_findings:
                return None
            return await self._verify_card(card)

        results = await parallel(*[verify_one(c) for c in cards])
        verified: list[VerifiedCard] = [r for r in results if r is not None and not isinstance(r, Exception)]

        # ── Cross-card analysis ───────────────────────────────────
        cards_with_findings = [c for c in cards if c.key_findings]
        if len(cards_with_findings) >= 2:
            cross = await self._cross_check(cards_with_findings)
            if "⚠️ 矛盾" in cross or "contradiction" in cross.lower():
                adj = await self._adjudicate_contradictions(cards_with_findings)
                if adj:
                    cross = cross + adj
            for vc in verified:
                vc.summary = (vc.summary or "") + cross
            self.blackboard.write(f"run:{run_id}:cross_checks", cross)

        # ── Persist ───────────────────────────────────────────────
        repo = Repository()
        for vc in verified:
            await repo.save_verified_card(run_id, vc)

        self.blackboard.write(f"run:{run_id}:verified", verified)
        return verified


    async def _adjudicate_contradictions(self, cards: list[ResearchCard]) -> str:
        """Resolve cross-perspective contradictions with a dedicated adjudicator."""
        lines: list[str] = []
        for card in cards:
            lines.append(f"\n### {card.perspective}")
            for j, c in enumerate(card.key_findings):
                lines.append(f"  [{j}] {c.text[:200]}")
        cross_text = "\n".join(lines)

        agent = create_agent(
            name="contradiction-adjudicator",
            role="矛盾裁决员",
            goal="根据已有证据判定矛盾双方谁更可信。",
            backstory=(
                "你只依据已有证据和核查状态做裁决，不引入新事实。"
                "当证据不足时，明确说无法裁决。"
            ),
            tools=[],
            llm="deepseek",
            blackboard=self.blackboard,
            file_cache=self.file_cache,
            trace_id=self._trace_id(),
            response_format={"type": "json_object"},
        )
        try:
            raw = await agent.run(CONTRADICTION_ADJUDICATOR_TASK.format(cross_text=cross_text))
        except Exception as exc:
            logger.warning("Contradiction adjudicator failed: %s", exc)
            return ""
        data = parse_json_response(raw, context="contradiction-adjudicator")
        if not data.success:
            logger.warning("Contradiction adjudicator parse failed: %s", data.errors)
            return ""
        resolutions = data.data.get("resolutions", [])
        if not resolutions:
            return ""
        parts = ["\n\n## Contradiction Adjudication"]
        for r in resolutions:
            parts.append(
                f"\n**{r.get('topic', '?')}** — winner: {r.get('winner', '?')}\n"
                f"> 理由: {r.get('reason', '')[:300]}\n"
                f"> 证据: {', '.join(r.get('evidence_urls', [])[:5])}"
            )
        parts.append(f"\n总体: {data.data.get('summary', '')[:400]}")
        self.blackboard.write("contradiction_resolution", data.data)
        return "\n".join(parts)
    def _claims_text(self, card: ResearchCard) -> str:
        return "\n".join(
            f"Claim {i}: [{c.confidence.value}] {c.text}\n  Sources: "
            + ", ".join(f"{s} {classify_url(s)}" for s in c.sources)
            for i, c in enumerate(card.key_findings)
        )

    async def _second_opinion(self, card: ResearchCard) -> list[VerificationEntry]:
        """Run an independent second-pass verifier with full quality tools."""
        perspective = card.perspective
        claims_text = self._claims_text(card)
        try:
            agent = create_agent(
                name=f"second-opinion-{perspective}",
                role="独立二次核查员",
                goal="不参考先前核查结论，独立判断每条声明的事实是否成立。",
                backstory=(
                    "你不会因为表述风格、口径提醒或缺少补充指标就否定事实；"
                    "你只依据可访问来源判断事实本身。"
                ),
                tools=[*get_quality_search_tools(), WebFetchTool(), SQLiteReadTool()],
                llm="deepseek",
                blackboard=self.blackboard,
                file_cache=self.file_cache,
                trace_id=self._trace_id(),
                response_format={"type": "json_object"},
            )
            raw = await agent.run(SECOND_OPINION_TASK.format(
                perspective=perspective, research_question=card.research_question, claims_text=claims_text,
            ))
        except Exception as exc:
            logger.warning("Second opinion failed for %s: %s", perspective, exc)
            return []

        data = parse_json_response(raw, context=f"second-opinion/{perspective}")
        if not data.success:
            logger.warning("Second opinion parse failed for %s", perspective)
            return []

        return safe_construct_list(
            VerificationEntry,
            _normalise_entries(data.data.get("entries", [])),
            context=f"second-opinion/{perspective}",
        )

    async def _verify_card(self, card: ResearchCard) -> VerifiedCard:
        """Run the 3-round debate protocol plus an independent second opinion.

        The second opinion only runs when the first pass produced at least one
        non-verified claim.  It can upgrade claims that were downgraded for
        presentation reasons, and can downgrade claims when it finds real
        factual problems.
        """
        perspective = card.perspective
        claims_text = self._claims_text(card)

        # Round 1: Verify
        tid = self._trace_id()
        active_names = {t.name for t in VERIFIER_CONFIG.get("tools", [])}
        reserved = [t for t in get_quality_search_tools() if t.name not in active_names]
        verifier = create_agent(**VERIFIER_CONFIG, blackboard=self.blackboard, file_cache=self.file_cache, name=f"verifier-{perspective}", trace_id=tid, reserved_tools=reserved)
        vraw = await verifier.run(VERIFY_TASK.format(
            perspective=perspective, research_question=card.research_question, claims_text=claims_text,
        ))
        vdata = parse_json_response(vraw, context=f"verifier/{perspective}/round-1")
        entries = safe_construct_list(VerificationEntry, _normalise_entries(vdata.data.get("entries", [])), context=f"verifier/{perspective}")

        if entries and all(
            hasattr(e, "status") and getattr(e.status, "value", str(e.status)) == "verified" for e in entries
        ):
            return VerifiedCard(
                perspective=card.perspective, verification_round=1, entries=entries, refutations=[],
                resolved=True, summary=vdata.data.get("summary", "All verified"),
            )

        # Round 2: Refute
        refuter = create_agent(**REFUTER_CONFIG, blackboard=self.blackboard, file_cache=self.file_cache, name=f"refuter-{perspective}", trace_id=tid, reserved_tools=reserved)
        rraw = await refuter.run(REFUTE_TASK.format(
            perspective=perspective, research_question=card.research_question,
            claims_text=claims_text, verification_text=vraw,
        ))
        rdata = parse_json_response(rraw, context=f"refuter/{perspective}/round-2")
        refutations = safe_construct_list(RefutationEntry, rdata.data.get("refutations", []), context=f"refuter/{perspective}")
        # The model sometimes omits claim_text — backfill it from the
        # original claims via claim_index so no refutation is lost.
        for r in refutations:
            if not r.claim_text:
                idx = r.claim_index
                if 0 <= idx < len(card.key_findings):
                    r.claim_text = card.key_findings[idx].text
                    logger.info("refuter[%s] backfilled claim_text for claim %d", perspective, idx)
                else:
                    logger.warning("refuter[%s] claim_index %d out of range — claim_text stays empty", perspective, idx)

        if not refutations:
            second = await self._second_opinion(card)
            final_entries = _merge_entries(entries, second) if second else entries
            resolved = all(
                getattr(e.status, "value", str(e.status)) == "verified" for e in final_entries
            )
            return VerifiedCard(
                perspective=card.perspective, verification_round=2, entries=final_entries, refutations=[],
                resolved=resolved, summary=vdata.data.get("summary", "No refutations found") + " | 独立二次复核完成",
            )

        # Round 3: Rebuttal
        v2raw = await verifier.run(REBUTTAL_TASK.format(
            perspective=perspective, claims_text=claims_text,
            verification_text=vraw, refutation_text=rraw,
        ))
        v2data = parse_json_response(v2raw, context=f"verifier/{perspective}/round-3")
        final_entries = safe_construct_list(VerificationEntry, _normalise_entries(v2data.data.get("entries", [])), context=f"verifier/{perspective}")

        # Independent second opinion — can correct over-conservative downgrades.
        second = await self._second_opinion(card)
        if second:
            final_entries = _merge_entries(final_entries, second)
            logger.info("Second opinion merged for %s: %d entries", perspective, len(final_entries))

        return VerifiedCard(
            perspective=card.perspective, verification_round=3, entries=final_entries, refutations=refutations,
            resolved=v2data.data.get("resolved", False), summary=v2data.data.get("summary", "") + " | 独立二次复核完成",
        )

    async def _cross_check(self, cards: list[ResearchCard]) -> str:
        """Identify related claims across perspectives and flag agreements/contradictions."""
        lines: list[str] = []
        for card in cards:
            lines.append(f"\n### {card.perspective}")
            for j, c in enumerate(card.key_findings):
                lines.append(f"  [{j}] {c.text[:200]}")
        cross_text = "\n".join(lines)

        cfg = {**VERIFIER_CONFIG, "tools": []}  # no tools needed — pure analysis
        agent = create_agent(**cfg, blackboard=self.blackboard, file_cache=self.file_cache, name="cross-checker", trace_id=self._trace_id())
        raw = await agent.run(CROSS_CHECK_TASK.format(cross_text=cross_text))
        data = parse_json_response(raw, context="cross-check")
        if not data.success:
            logger.warning("Cross-check parse failed: %s", data.errors)
            return "\n\n[Cross-card analysis: unavailable]"

        checks = data.data.get("cross_checks", [])
        if not checks:
            return "\n\n[Cross-card analysis: no cross-perspective relationships found]"

        parts = ["\n\n## Cross-Perspective Analysis"]
        for ck in checks:
            tag = {"consistent": "✅ 一致", "contradiction": "⚠️ 矛盾", "complementary": "🔗 互补"}.get(
                ck.get("relation", ""), "—"
            )
            parts.append(
                f"\n**{ck.get('topic', '?')}** ({'+'.join(ck.get('perspectives', []))}) — {tag}\n"
                f"> A: {ck.get('claim_a', '?')[:150]}\n"
                f"> B: {ck.get('claim_b', '?')[:150]}\n"
                f"{ck.get('assessment', '')}"
            )
        annotation = "\n".join(parts)
        logger.info("Cross-check found %d cross-perspective relationships", len(checks))
        return annotation
