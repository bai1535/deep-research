"""Phase 1 quality gate — Reflection Pattern (AutoGen-inspired).

After the researchers produce findings, a dedicated REFLECTOR agent
reviews the output for *quality* (not just format): are the claims
concrete, evidence-backed, on-topic, and sufficient?  If not, its
feedback drives the next augment round — the researchers re-search
WITH the reviewer's notes, instead of blindly retrying.

Pipeline decides acceptability deterministically (score + finding
count thresholds); the model only has to score honestly.
"""

from __future__ import annotations

import logging

from deep_research.agents.registry import REFLECTOR_CONFIG, create_agent
from deep_research.config import get_config
from deep_research.core.blackboard import Blackboard
from deep_research.core.file_cache import FileCache
from deep_research.models.schemas import ReflectionResult, ResearchCard
from deep_research.response_parser import parse_json_response

logger = logging.getLogger("deep_research.crews.reflection")

REFLECTOR_TASK = """你是一位研究质量评审。审视研究员刚完成的产出，判断质量是否足以进入下一阶段。

研究问题：{question}

研究产出（按视角列出，每条发现含来源数和反面证据数）：

{cards_block}

从以下维度评审：
1. **具体性**：结论是否包含数字、时间、对比等具体信息，还是"有助于提升""存在一定风险"这类没有信息量的空话
2. **证据支撑**：关键结论是否附有来源 URL，是否列出反面证据（counterpoints）
3. **覆盖度**：是否回答了研究问题的核心方面，是否有明显遗漏
4. **相关性**：是否有跑题、与问题无关的内容
5. **数量**：关键发现是否足够（总计至少 {min_findings} 条）

输出 JSON（严格只输出 JSON 对象，不要代码块、不要其他文字）：
{{
  "quality_score": 0到100的整数（60 分以下表示需要改进）,
  "issues": ["具体指出哪些结论太笼统、缺证据、漏了哪些方面"],
  "feedback": "给研究员下一轮搜索的具体改进指导——要补充搜索什么关键词、往哪个方向深挖、哪条结论需要补数字/来源证据。必须具体可执行，禁止'请更加深入'这类空话。"
}}
"""

MAX_RETRIES = 1


class ReflectionCrewRunner:
    """Runs the quality gate on Phase 1 output."""

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

    async def reflect(
        self,
        cards: list[ResearchCard],
        question: str,
        run_id: str,
        *,
        min_findings: int = 3,
    ) -> ReflectionResult:
        """Review the research output.  Returns a ReflectionResult.

        Skips the LLM call entirely when there is nothing to review
        (zero findings) — the pipeline's router handles that case.
        """
        total_findings = sum(len(c.key_findings) for c in cards)
        if total_findings == 0:
            logger.info("Reflector skipped — no findings to review")
            return ReflectionResult(
                quality_score=0,
                issues=["no findings produced"],
                feedback="",
                skipped=True,
            )

        task = REFLECTOR_TASK.format(
            question=question,
            cards_block=self._cards_block(cards),
            min_findings=min_findings,
        )

        for attempt in range(MAX_RETRIES + 1):
            agent = create_agent(
                **REFLECTOR_CONFIG,
                blackboard=self.blackboard,
                file_cache=self.file_cache,
                name="reflector",
                trace_id=self._trace_id(),
            )
            raw = await agent.run(task)
            logger.info("Reflector attempt %d: %d chars", attempt, len(raw))

            result = parse_json_response(raw, context=f"reflector/attempt-{attempt}")
            if not result.success:
                logger.warning("Reflector attempt %d parse failed: %s", attempt, result.errors)
                continue

            try:
                return self._build_result(result.data)
            except Exception as exc:
                logger.warning("Reflector attempt %d malformed data: %s", attempt, exc)
                continue

        # Conservative fallback: score 0 → pipeline treats as unacceptable.
        # Fix #9: feedback is NOT left empty — an empty feedback would
        # silently downgrade augment to the quantity-driven path.  A
        # generic quality instruction keeps the feedback loop meaningful
        # even when the reviewer itself failed.
        logger.error("Reflector all attempts exhausted — returning score 0 with generic feedback")
        return ReflectionResult(
            quality_score=0,
            issues=["reflector failed to produce a valid review"],
            feedback=(
                "上一轮研究未能通过质量评审（评审环节故障）。请针对研究问题补充："
                "具体的数字/时间/对比信息、每个关键结论的来源证据，并覆盖问题尚未涉及的核心方面。"
            ),
        )

    # ── helpers ───────────────────────────────────────────────────

    def _cards_block(self, cards: list[ResearchCard]) -> str:
        """Render the findings summary the reviewer reads (bounded size)."""
        blocks = []
        for i, card in enumerate(cards, 1):
            lines = [f"[视角{i}] {card.perspective}（子问题：{card.research_question or '—'}）"]
            if not card.key_findings:
                lines.append("  （无发现）")
            for j, claim in enumerate(card.key_findings, 1):
                text = claim.text[:160].replace("\n", " ")
                lines.append(
                    f"  {j}. {text} [置信度:{claim.confidence.value} | "
                    f"来源:{len(claim.sources)}个 | 反面证据:{len(claim.counterpoints)}条]"
                )
            if card.gaps:
                gaps = "；".join(g[:60] for g in card.gaps[:3])
                lines.append(f"  盲区: {gaps}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    def _build_result(self, data: dict) -> ReflectionResult:
        score = int(data.get("quality_score", 0))
        # issues is a plain list of strings, NOT dicts — safe_construct_list
        # (Pydantic models + dict items) would silently drop every entry.
        raw_issues = data.get("issues", [])
        if isinstance(raw_issues, list):
            issues = [str(i).strip() for i in raw_issues if i][:20]
        else:
            issues = []
        feedback = str(data.get("feedback", ""))
        # Clamp the score; the model has been told 0-100 but verify anyway
        score = max(0, min(100, score))
        return ReflectionResult(
            quality_score=score,
            issues=issues,
            feedback=feedback[:2000],
        )
