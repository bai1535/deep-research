"""Phase 3: Score + Extract (barrier) → Editor (report).

Barrier pattern: Scorer and Extractor run in parallel; Editor waits for both.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime

from deep_research.config import get_config
from deep_research.core.agent import Agent
from deep_research.core.blackboard import Blackboard
from deep_research.core.file_cache import FileCache
from deep_research.core.orchestrator import parallel
from deep_research.agents.registry import (
    SCORER_CONFIG,
    EXTRACTOR_CONFIG,
    EDITOR_CONFIG,
    create_agent,
)
from deep_research.db import Repository
from deep_research.models.schemas import ScoreResult, InsightResult
from deep_research.response_parser import parse_json_response
from deep_research.final_answer import extract_final_answer
from deep_research.candidate_verifier import CandidateVerifier, format_candidate_verification
from deep_research.safe_construct import safe_construct_one

logger = logging.getLogger("deep_research.crews.synthesis")

SCORER_TASK = """你是质量评分员。使用 sqlite_read 工具获取 Run ID: {run_id} 的所有研究数据。

对每条声明在三个维度上评分：
1. 来源可靠性 (1-5)：来源 URL 后面的 [标签 ★] 是来源分级，据此给分：
   ★★★★（学术论文/官方文档/政府/国际标准）→ 5
   ★★★（权威媒体/工程博客/行业报告/百科）→ 4
   ★★（商业网站/社区讨论/自媒体）→ 2
   ★（未知来源）→ 1
   声明若无任何 ★★★★ 来源支撑，来源可靠性最多给 3；全部是 ★★/★ 来源则给 1-2。
2. 核查一致性 (1-5)：双方一致=5, 单方确认=3, 有争议=1
3. 视角覆盖度 (1-5)：3+ 视角确认=5, 2 视角=3, 1 视角=1

等级: A (13-15), B (10-12), C (7-9), D (<7)

输出 JSON:
{{
  "overall_score": 85,
  "claim_scores": [
    {{"perspective": "technical", "claim_index": 0, "claim_text": "...", "source_reliability": 4, "verification_consistency": 5, "perspective_coverage": 3, "grade": "B"}}
  ],
  "summary": "总体质量评估"
}}

严格只输出 JSON。"""

EXTRACTOR_TASK = """使用 sqlite_read 工具获取 Run ID: {run_id} 的所有数据，提取跨视角洞察。

识别:
1. CONSENSUS_SIGNALS: 2+ 视角独立确认的声明（高置信度）
2. CONTRADICTIONS: 一个视角的发现与另一个视角冲突的地方
3. BLIND_SPOTS: 没有视角充分覆盖的重要方面
4. TIME_SENSITIVE: 与特定版本/事件相关、可能过时的发现

输出 JSON:
{{
  "consensus_signals": ["洞察 1", "洞察 2"],
  "contradictions": ["冲突 1", "冲突 2"],
  "blind_spots": ["盲区 1"],
  "time_sensitive_items": ["时效性发现 1"]
}}

严格只输出 JSON。"""

EDITOR_TASK = """你是一份深度研究报告的主编。以下是已完成的研究数据，**不需要使用任何工具**——所有数据已经提供在下方。

用户提出的问题：
  「{question}」

═══════════════════════════════════════
研究数据（结构化摘要）
═══════════════════════════════════════
{data_summary}
═══════════════════════════════════════

你的任务是**回答用户的问题**。撰写一份面向用户的中文报告，严格遵循以下结构。

引用数据时使用精确指代，例如"技术视角的第 3 条声明指出..."、"行业视角的第 1 条声明（置信度 high）表明..."。

# [根据研究内容自拟标题——要能回答用户的问题]
*生成时间: [日期] | 置信度评分: [分数]/100*

## 1. 直接回答
用 3-5 句话直接回答用户的问题。这是全报告最重要的部分——用户只看这个也要能得到答案。给出结论的同时标注把握有多大。

## 2. 关键证据
列出支撑上述回答的核心证据（4-6 条）。每条标注来源视角和置信度。

## 3. 不同观点与争议
如果研究中有相互矛盾的发现或存在争议的结论，如实呈现双方论据。不要只挑支持你答案的证据。

## 4. 如果你要行动
基于研究发现，给用户 3-5 条具体的行动建议。每条必须引用至少一个来源。

## 5. 我们还不确定的
列出研究中未能充分回答的方面——诚实告知用户哪些结论可能不牢靠。

## 6. 来源索引
所有引用 URL 及验证状态。

只输出 Markdown 报告，不要其他文字。"""


class SynthesisCrewRunner:
    """Runs Phase 3 with core.Agent."""

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

    async def run(self, run_id: str) -> dict:
        output_dir = Path(self.config.output_dir) / run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        tid = self._trace_id()

        # Barrier: Scorer + Extractor in parallel
        async def run_scorer() -> dict | None:
            agent = create_agent(**SCORER_CONFIG, blackboard=self.blackboard, file_cache=self.file_cache, name="scorer", trace_id=tid)
            raw = await agent.run(SCORER_TASK.format(run_id=run_id))
            result = parse_json_response(raw, context="scorer")
            return result.data if result.success else None

        async def run_extractor() -> dict | None:
            agent = create_agent(**EXTRACTOR_CONFIG, blackboard=self.blackboard, file_cache=self.file_cache, name="extractor", trace_id=tid)
            raw = await agent.run(EXTRACTOR_TASK.format(run_id=run_id))
            result = parse_json_response(raw, context="extractor")
            return result.data if result.success else None

        score_data, insight_data = await parallel(run_scorer(), run_extractor())

        score = safe_construct_one(ScoreResult, score_data, context="scorer", fallback=ScoreResult(overall_score=0))
        if score is None:
            score = ScoreResult(overall_score=0)
        insights = safe_construct_one(InsightResult, insight_data, context="extractor", fallback=InsightResult())
        if insights is None:
            insights = InsightResult()

        # Save to DB
        repo = Repository()
        await repo.save_score(run_id, score)
        await repo.save_insights(run_id, insights)
        run_record = await repo.get_run(run_id)
        cards = await repo.get_research_cards(run_id)
        verified = await repo.get_verified_cards(run_id)

        question = run_record["question"] if run_record else ""

        # Candidate verification loop (only for suitable question types)
        candidate_result = None
        try:
            verifier = CandidateVerifier(blackboard=self.blackboard, file_cache=self.file_cache)
            candidate_result = await verifier.verify(question, cards, verified)
        except Exception as exc:
            logger.warning("Candidate verification skipped: %s", exc)

        # Editor composes final report — no tools needed, data is in the prompt
        data_summary = self._build_data_summary(question, cards, verified, score, insights, candidate_result=candidate_result)
        editor_cfg = {**EDITOR_CONFIG, "tools": []}
        editor = create_agent(**editor_cfg, blackboard=self.blackboard, file_cache=self.file_cache, name="editor", trace_id=tid)
        editor_raw = await editor.run(EDITOR_TASK.format(question=question, data_summary=data_summary))

        # Append cost appendix to report
        cost_appendix = self._build_cost_appendix()
        report_body = editor_raw.strip() if editor_raw.strip() else self._fallback_report(
            run_id, question, score, insights, cards, verified,
        )
        report_text = report_body + cost_appendix

        report_path = output_dir / "report.md"
        report_path.write_text(report_text, encoding="utf-8")
        final_answer = extract_final_answer(report_text)
        if candidate_result and candidate_result.get("final_candidate"):
            final_answer = f"{candidate_result['final_candidate']}（置信度 {candidate_result.get('confidence', '?')}/100）"
        (output_dir / "answer.txt").write_text(final_answer, encoding="utf-8")

        # Claim-level provenance annotation (Phase A) — non-destructive.
        claims_doc = None
        try:
            from deep_research.claim_annotator import ClaimAnnotator
            claims_doc = await ClaimAnnotator(
                blackboard=self.blackboard,
                file_cache=self.file_cache,
            ).annotate(
                run_id=run_id,
                report_text=report_text,
                question=question,
                cards=cards,
                verified=verified,
                score=score,
            )
        except Exception as exc:
            logger.warning("Claim annotation skipped: %s", exc)

        # Atomic verification for uncovered claims (Phase B).
        if claims_doc:
            try:
                from deep_research.claim_verifier import AtomicClaimVerifier
                claims_doc = await AtomicClaimVerifier(
                    blackboard=self.blackboard,
                    file_cache=self.file_cache,
                ).verify_claims(
                    run_id=run_id,
                    claims_doc=claims_doc,
                    question=question,
                )
            except Exception as exc:
                logger.warning("Atomic claim verification skipped: %s", exc)

        if claims_doc:
            (output_dir / "claims.json").write_text(
                json.dumps(claims_doc, indent=2, ensure_ascii=False), encoding="utf-8"
            )

        # Write evidence.json and audit.jsonl
        evidence = {
            "run_id": run_id,
            "question": question,
            "cards": [c.model_dump() for c in cards],
            "verified": [v.model_dump() for v in verified],
            "score": score.model_dump(),
            "insights": insights.model_dump(),
            "final_answer": final_answer,
            "candidate_verification": candidate_result,
            "claims": claims_doc,
        }
        (output_dir / "evidence.json").write_text(
            json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        audit = [json.dumps({"event": "run_start", "run_id": run_id})]
        for c in cards:
            audit.append(json.dumps({"event": "research_card", "data": c.model_dump()}))
        for v in verified:
            audit.append(json.dumps({"event": "verified_card", "data": v.model_dump()}))
        audit.append(json.dumps({"event": "score", "data": score.model_dump()}))
        audit.append(json.dumps({"event": "insights", "data": insights.model_dump()}))
        (output_dir / "audit.jsonl").write_text("\n".join(audit) + "\n")

        return {"score": score, "insights": insights, "output_dir": str(output_dir)}

    def _fallback_report(self, run_id, question, score, insights, cards, verified) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        title = question or f"研究报告 ({run_id})"
        lines = [
            f"# {title}",
            f"*生成时间: {now} | 置信度评分: {score.overall_score}/100*",
            "",
            "## 1. 执行摘要",
            "",
            f"整体置信度评分: **{score.overall_score}/100**。",
            "",
            "> ⚠️ 此报告由结构化数据自动生成，因主编 Agent 未产生输出。",
            "",
            "## 2. 共识信号",
            "",
        ]
        for s in insights.consensus_signals:
            lines.append(f"- ✅ {s}")
        lines.extend(["", "## 3. 矛盾", ""])
        for c in insights.contradictions:
            lines.append(f"- ⚠️ {c}")
        lines.extend(["", "## 4. 盲区", ""])
        for b in insights.blind_spots:
            lines.append(f"- 🔍 {b}")
        lines.extend(["", "## 5. 时效性条目", ""])
        for t in insights.time_sensitive_items:
            lines.append(f"- ⏰ {t}")
        lines.extend(["", "## 6. 声明评分摘要", "", f"总评分声明数: {len(score.claim_scores)}", ""])
        for cs in score.claim_scores:
            lines.append(
                f"- **{cs.get('grade', '?')}** [{cs.get('perspective', '?')}:{cs.get('claim_index', '?')}] "
                f"{cs.get('claim_text', 'N/A')[:120]}"
            )
        lines.extend(["", "---", f"*Run ID: {run_id} | 完整数据: evidence.json*"])
        return "\n".join(lines)

    def _build_data_summary(self, question, cards, verified, score, insights, candidate_result=None) -> str:
        """Render structured research data as a precise, indexed text block.

        The Editor reads this directly instead of making sqlite_read tool calls.
        Each claim gets a unique index so the Editor can reference it precisely
        (e.g. "技术视角的第 3 条声明指出...").
        """
        parts = [f"整体置信度评分: {score.overall_score}/100\n"]

        # Per-perspective cards with indexed claims
        for card in cards:
            p = card.perspective
            parts.append(f"━━━ {p} 视角 ━━━")
            parts.append(f"研究问题: {card.research_question}")
            if not card.key_findings:
                parts.append("  (无发现)")
            for j, c in enumerate(card.key_findings):
                parts.append(f"  声明#{j}: [{c.confidence.value}] {c.text}")
                if c.sources:
                    parts.append(f"    来源: {', '.join(c.sources[:5])}")
                if c.counterpoints:
                    for cp in c.counterpoints:
                        parts.append(f"    反面: {cp}")
            if card.gaps:
                parts.append(f"  盲区: {'; '.join(card.gaps[:5])}")
            parts.append("")

        # Verification results
        if verified:
            parts.append("━━━ 验证结果 ━━━")
            for vc in verified:
                parts.append(f"  [{vc.perspective}] Round {vc.verification_round}, resolved={vc.resolved}")
                for e in vc.entries:
                    parts.append(f"    声明#{e.claim_index}: {e.status.value} — {e.reasoning[:200]}")
                if vc.summary:
                    parts.append(f"    摘要: {vc.summary[:300]}")
            parts.append("")

        # Insights
        parts.append("━━━ 洞察提炼 ━━━")
        if insights.consensus_signals:
            parts.append("共识信号:")
            for s in insights.consensus_signals:
                parts.append(f"  ✅ {s}")
        if insights.contradictions:
            parts.append("矛盾:")
            for c in insights.contradictions:
                parts.append(f"  ⚠️ {c}")
        if insights.blind_spots:
            parts.append("盲区:")
            for b in insights.blind_spots:
                parts.append(f"  🔍 {b}")
        if insights.time_sensitive_items:
            parts.append("时效性:")
            for t in insights.time_sensitive_items:
                parts.append(f"  ⏰ {t}")

        cand_text = format_candidate_verification(candidate_result)
        if cand_text:
            parts.append("\n" + cand_text)

        return "\n".join(parts)

    def _build_cost_appendix(self) -> str:
        """Read token/cost usage from the blackboard and build a cost appendix.

        Appended to the end of every report so readers can see what the
        research cost to run.
        """
        usage_keys = [k for k in self.blackboard.keys() if k.startswith("usage:")]
        if not usage_keys:
            return ""

        lines = ["\n\n---\n\n## 💰 本次研究成本\n"]
        lines.append("| Agent | LLM 调用 | 输入 Token | 输出 Token | 总 Token | 内存峰值 | 费用 (USD) |")
        lines.append("|-------|----------|------------|------------|----------|----------|------------|")

        total_calls = 0
        total_prompt = 0
        total_completion = 0
        total_tokens = 0
        total_cost = 0.0

        for key in sorted(usage_keys):
            u = self.blackboard.read(key, {})
            if not isinstance(u, dict):
                continue
            name = key.replace("usage:", "")
            calls = u.get("calls", 0)
            prompt = u.get("prompt", 0)
            completion = u.get("completion", 0)
            tokens = u.get("total", 0)
            cost = u.get("cost", 0.0)

            kb = u.get("peak_messages_kb", 0)
            total_calls += calls
            total_prompt += prompt
            total_completion += completion
            total_tokens += tokens
            total_cost += cost

            mem_str = f"{kb} KB" if kb else "—"
            lines.append(
                f"| {name} | {calls} | {prompt:,} | {completion:,} | {tokens:,} | {mem_str} | ${cost:.4f} |"
            )

        lines.append(
            f"| **合计** | **{total_calls}** | **{total_prompt:,}** | "
            f"**{total_completion:,}** | **{total_tokens:,}** | **—** | **${total_cost:.4f}** |"
        )
        lines.append("")
        lines.append(f"*计费模型: DeepSeek ($0.27/M 输入, $1.10/M 输出)*")

        return "\n".join(lines)
