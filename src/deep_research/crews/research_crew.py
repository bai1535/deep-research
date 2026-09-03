"""Phase 1: Orchestrator → 4 parallel Researchers (Fan-out).

Pure async/await + core.Agent — no CrewAI dependency.
"""

from __future__ import annotations

import logging

from deep_research.config import get_config
from deep_research.core.agent import Agent
from deep_research.core.blackboard import Blackboard
from deep_research.core.file_cache import FileCache
from deep_research.core.orchestrator import parallel
from deep_research.core.tool import BuildTool
from deep_research.agents.registry import (
    ORCHESTRATOR_CONFIG,
    RESEARCHER_CONFIGS,
    create_agent,
)
from deep_research.agents.policy import default_policy_for
from deep_research.db import Repository
from deep_research.models.enums import Perspective, Confidence
from deep_research.models.schemas import ResearchCard, Claim
from deep_research.tools import get_search_tools, get_quality_search_tools, WebFetchTool
from deep_research.response_parser import parse_json_response
from deep_research.query_planner import QueryPlanner, format_search_plan
from deep_research.safe_construct import safe_construct_list
from deep_research.adaptive import (
    ComputeAllocation,
    allocation_for_augment,
    build_compute_plan,
    select_augment_targets,
)

logger = logging.getLogger("deep_research.crews.research")

ORCHESTRATOR_TASK = """
把以下研究问题拆成多份独立的研究简报。

研究问题：{question}

你要做四件事：

**铁律（高于一切，先读）：**
每个视角的 sub_question 必须**保持原始研究问题的研究对象和范围不变**：
- 研究对象不可替换：问"个人 PC"，就研究"个人 PC"，不能把对象换成"AI PC""服务器"等其他品类。
- 范围不可擅自收窄或扩大：原始问题若没有限定细分品类，子问题也不得自行聚焦到某个细分品类。
- 子问题是对原问题某方面的深入，不是对原问题的重新定义。
反例（错误示范）：问"个人 PC 价格走势"，子问题却写"AI PC 各厂商定价策略"——这替换了研究对象，禁止。

**第一，判断问题类型。**从以下类型中选一个最贴切的：
- technical：技术原理/实现/机制类（如"GIL 是什么"、"Redis 为什么快"）
- business：商业决策/市场/产品类（如"D2C 值不值得做"）
- academic：学术/理论/研究类
- policy：政策/法规/合规类
- comparative：对比/选型类
- general：混合型或都不太像

**第二，根据问题类型确定视角构成（数量与角色）。**
角色决定该视角研究员的研究姿态与搜索方向。推荐构成（视角总数 3-6 个）：

- technical（3-4 个）：技术专家（原理与机制）、技术专家（实现与生态）、批判者（局限与陷阱）、对比者（与替代方案）
- business（3-4 个）：行业分析师（市场现状与规模）、商业分析师（成本与盈利模型）、批判者（风险与失败案例）、未来趋势（发展与替代）
- academic（4-5 个）：文献综述（已有研究）、方法论（研究设计）、批判者（争议与反证）、领域对比（相关学科）、未来方向（开放问题）
- policy（4-5 个）：原文解读（法规条文）、受影响方（行业/个人）、合规分析师（成本与路径）、国际对比（他国做法）、批判者（执行风险）
- comparative（3-4 个）：A方案深度、B方案深度、对比分析（关键维度）、批判者（隐藏成本）
- general（3-5 个）：自由组合，至少包含一个批判者

**第三，给每个视角起名。**
不要用固定的 technical/industry/critical/future 模板。根据这个问题的具体内容，起能体现切入角度的名字。例如：
- 问"AI 编程助手效果" → "独立研究佐证"、"用户实际体验"、"商业定价策略"、"替代方案对比"
- 问"自建 NAS" → "硬件成本拆解"、"软件生态对比"、"功耗与噪音"、"数据安全风险"、"长期维护成本"
- 问"碳排放政策影响" → "法规原文解读"、"受影响行业"、"企业合规成本"、"国际对比"、"应对策略"

**第四，对每个视角提供：**
1. role（从推荐构成中选一个角色名）
2. 聚焦的子问题
3. 推荐搜索关键词（3-5 个，英文）
4. 优先来源类型

输出 JSON：
{{
  "question_type": "technical",
  "perspectives": [
    {{"name": "视角名称", "role": "技术专家", "sub_question": "...", "keywords": ["..."], "source_types": ["..."]}},
    ...
  ]
}}

严格只输出 JSON，不要任何其他文字。
"""

# Fallback when orchestrator fails — 4 classic perspectives
_DEFAULT_RESEARCHER = {
    "role": "研究员",
    "goal": "从指定视角深入研究问题，产出有来源支撑的发现。",
    "backstory": (
        "你是一位资深研究员，擅长从特定角度切入复杂问题。"
        "你广泛搜索、深度阅读，产出的每条发现都附带来源 URL 和反面证据。"
    ),
    "tools": [*get_search_tools(), WebFetchTool()],
    "llm": "deepseek",
}

_DEFAULT_PERSPECTIVES: list[tuple[str, dict]] = [
    ("技术分析", {"sub_question": "", "keywords": [], "source_types": [], "role": "技术专家"}),
    ("行业现状", {"sub_question": "", "keywords": [], "source_types": [], "role": "行业分析师"}),
    ("风险与挑战", {"sub_question": "", "keywords": [], "source_types": [], "role": "批判者"}),
    ("未来趋势", {"sub_question": "", "keywords": [], "source_types": [], "role": "未来趋势"}),
]

# Question types the orchestrator may emit (anything else → "general")
_QUESTION_TYPES = {"technical", "business", "academic", "policy", "comparative", "general"}

# Role → research stance injected into the researcher's prompt.
# Unknown roles get no stance line (the role name still travels).
# Fix #8: roles are normalised back to this fixed pool (via _ROLE_ALIASES
# + containment) before they reach the teachability stats — otherwise a
# free-form role like "半导体专家" would fragment the stats forever and
# MIN_RUNS_FOR_STRONG would never accumulate.
_ROLE_ALIASES = {
    "批判": "批判者", "技术": "技术专家", "行业": "行业分析师", "商业": "商业分析师",
    "未来": "未来趋势", "对比": "对比者", "文献": "文献综述", "方法": "方法论",
    "原文": "原文解读", "合规": "合规分析师", "受影响": "受影响方", "领域": "领域对比",
}


def _normalise_role(raw) -> str:
    """Map a possibly free-form role back to the canonical pool."""
    raw = str(raw or "").strip()
    if not raw:
        return ""
    if raw in _ROLE_GUIDANCE:
        return raw
    for alias, canonical in _ROLE_ALIASES.items():
        if alias in raw:
            return canonical
    for known in _ROLE_GUIDANCE:
        if known in raw:  # "资深技术专家" → "技术专家"
            return known
    return ""  # teachability aggregates these under "未标注角色"


_ROLE_GUIDANCE = {
    "技术专家": "深挖原理、机制、性能数据与实现细节，给出可验证的技术事实。",
    "行业分析师": "聚焦市场规模、增速、主要玩家与商业模式，给出具体数字。",
    "商业分析师": "拆解成本结构、盈利模型、ROI 与定价，给出可量化的商业判断。",
    "批判者": "主动寻找反例、失败案例、隐藏成本与风险。对每条乐观结论提出质疑。",
    "未来趋势": "基于当前数据推断 1-3 年内的趋势，明确标注不确定性。",
    "对比者": "建立统一的对比维度，逐项比较，给出取舍结论。",
    "文献综述": "梳理已有研究脉络，标注证据强度与共识度。",
    "方法论": "关注研究设计、数据可得性与验证方法。",
    "原文解读": "逐条解读条文/原文，标注精确表述与常见误读。",
    "受影响方": "从具体受影响群体的视角评估影响，引用一手体验。",
    "合规分析师": "评估合规路径、成本与时间线，给出分步建议。",
    "领域对比": "与相邻领域/学科对照，揭示被忽视的交叉点。",
}

# Alignment gate threshold: a perspective whose sub-question shares less
# than this fraction of significant characters with the original question
# is flagged as likely off-topic (logged, not dropped).
ALIGNMENT_MIN_OVERLAP = 0.2


def _check_alignment(question: str, sub_q: str) -> float:
    """Cheap topical-overlap heuristic for the alignment gate.

    Returns the fraction of the question's "significant" characters that
    also appear in the sub-question.  This is a COARSE filter — it catches
    gross drift (object swapped entirely, e.g. "PC价格" → "手机价格") but
    NOT prefix-substitution ("个人PC" → "AI PC", which still shares "PC").
    The prompt 铁律 is the real defence against the latter.
    """
    _STOP = set("的了吗呢在是有和与及或对从到关于如何为什么什么哪些怎么哪里是否能否可以应该需要请给为我你他它这那")

    def _sig(text: str) -> set[str]:
        return {
            c for c in text
            if c not in _STOP and not c.isspace()
            and c not in "，。、；：？！\"'（）()【】[]·"
        }

    q = _sig(question)
    if not q:
        return 1.0
    return len(q & _sig(sub_q)) / len(q)


_ALIGNMENT_TASK = """你是研究对象一致性检查器。检查每个子问题是否围绕原始研究问题展开，跑题的就修正。

原始研究问题：{question}

子问题列表：
{sub_questions}

判断标准：子问题的**研究对象**必须与原问题一致（不替换对象、不擅自收窄/扩大范围）。
例如原问题问"个人 PC 价格走势"，子问题"AI PC 定价策略"就是跑题（对象被替换成 AI PC）。

对每个子问题：
- aligned=true：研究对象一致，sub_question 保持原样
- aligned=false：研究对象跑题，sub_question 给出修正版（保留原视角的切入角度，但把研究对象拉回原问题）

严格只输出 JSON，不要其他文字：
{{"results": [{{"name": "视角名", "aligned": true, "sub_question": "..."}}, ...]}}
"""


RESEARCHER_TASK = """你被分配了「{perspective}」视角（角色：{role}）来研究这个课题。

研究简报：
- 子问题：{sub_question}
- 搜索关键词：{keywords}
- 优先来源类型：{source_types}

原始研究问题：{question}

研究方法：
第一轮：一次性同时发出 3-5 个搜索请求（在一次回复中调用多个工具），广泛覆盖关键词的不同方面。
拿到所有搜索结果后，选出 2-3 个最有价值的 URL 用 web_fetch 读取详细内容。

对每条发现生成一个论点。
同时列出研究盲区——这个视角未能充分覆盖的重要方面。

最终把所有发现输出为一个 JSON 对象：
{{
  "perspective": "{perspective}",
  "research_question": "{sub_question}",
  "key_findings": [
    {{
      "text": "论点内容（用中文写）",
      "confidence": "high/medium/low",
      "sources": ["来源URL"],
      "counterpoints": ["反面证据或注意事项"]
    }}
  ],
  "gaps": ["未能覆盖的盲区"],
  "raw_transcript": "你的研究过程简述"
}}

严格只输出 JSON 对象本身。
禁止输出 Markdown、标题、解释、列表、代码块、加粗，禁止以"基于我的研究"等文字开头。
最终回复必须是合法 JSON，字段只能包含 perspective/research_question/key_findings/gaps/raw_transcript。
"""

RESEARCHER_SALVAGE_TASK = """你是一个研究结果格式化员。下面是一个 Researcher 输出的非 JSON 研究内容（可能是 Markdown、散文或部分结构化文本）。

请把它整理成严格 JSON，不要遗漏具体事实、数字、来源 URL 和反面证据。

输出字段必须为：
{{
  "perspective": "{perspective}",
  "research_question": "{research_question}",
  "key_findings": [
    {{"text": "论点内容（中文）", "confidence": "high/medium/low", "sources": ["来源URL"], "counterpoints": ["反面证据或注意事项"]}}
  ],
  "gaps": ["未能覆盖的盲区"],
  "raw_transcript": "简短研究过程说明"
}}

要求：
- 从原文中提取每条可独立验证的发现作为 key_findings
- 如果原文有 Markdown 标题/列表/加粗，只提取信息，不要保留格式
- sources 只填原文中真实出现的 URL；没有就空数组
- 如果原文是长文，尽量拆成多条发现，不要只塞成一条
- 严格只输出 JSON，不要代码块、不要解释

待格式化的 Researcher 原始输出：
{raw_text}
"""

MAX_RETRIES = 2


class ResearchCrewRunner:
    """Runs Phase 1 with core.Agent — no CrewAI."""

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

    def _emit_event(self, event: dict) -> None:
        """Emit a progress event on the run's EventBus (no-op if absent)."""
        eb = self.blackboard.read("event_bus")
        if eb is not None:
            eb.emit(event)

    async def run(self, question: str, run_id: str) -> list[ResearchCard]:
        tid = self._trace_id()
        # Step 0: Query Planner — classify question and build a search plan
        planner = QueryPlanner(blackboard=self.blackboard, file_cache=self.file_cache)
        search_plan = await planner.plan(question)

        # Step 1: Orchestrator (Group Chat Manager) — classifies the
        # question and picks the perspective/role composition
        logger.info("Orchestrator starting for: %s", question[:80])
        orchestrator = create_agent(**ORCHESTRATOR_CONFIG, blackboard=self.blackboard, file_cache=self.file_cache, name="orchestrator", trace_id=tid)
        question_type, briefs = await self._run_orchestrator(orchestrator, question, search_plan)
        logger.info("Orchestrator done: type=%s, %d briefs", question_type, len(briefs))
        self._emit_event({
            "type": "perspectives",
            "question_type": question_type,
            "names": [n for n, _ in briefs],
            "roles": [b.get("role", "") for _, b in briefs],
        })

        # Adaptive compute plan: a deterministic per-perspective allocation
        # derived from question type, role, keyword breadth and perspective
        # count.  It is written to the blackboard for observability and used
        # to set per-researcher ResourceBudgets below.
        allocations = build_compute_plan(question_type, briefs, search_plan)
        if allocations:
            self.blackboard.write("compute_plan", [a.to_dict() for a in allocations])
            self._emit_event({
                "type": "compute_plan",
                "items": [a.to_dict() for a in allocations],
            })

        # Step 2: Parallel researchers (dynamic count from orchestrator)
        async def research_one(
            perspective_name: str, brief: dict, allocation: ComputeAllocation | None
        ) -> ResearchCard:
            return await self._research_with_retry(
                perspective_name, brief, question, allocation=allocation,
            )

        results = await parallel(*[
            research_one(name, brief, alloc)
            for (name, brief), alloc in zip(briefs, allocations)
        ])
        cards: list[ResearchCard] = []
        for i, r in enumerate(results):
            name = briefs[i][0] if i < len(briefs) else f"perspective-{i}"
            if r is None or isinstance(r, Exception):
                logger.error("Researcher [%s] failed: %s", name, r)
                cards.append(ResearchCard(
                    perspective=name,
                    research_question="",
                    key_findings=[],
                    gaps=[f"Researcher failed: {r}"],
                    raw_transcript="",
                ))
            else:
                cards.append(r)

        # Write to blackboard for Phase 2
        self.blackboard.write(f"run:{run_id}:cards", cards)

        # Save to DB
        repo = Repository()
        for card in cards:
            await repo.save_research_card(run_id, card)

        return cards

    async def augment(
        self,
        cards: list[ResearchCard],
        question: str,
        run_id: str,
        *,
        min_claims: int = 2,
        feedback: str = "",
        augment_count: int = 0,
    ) -> list[ResearchCard]:
        """Graph-level augmentation: re-run researchers, quality-gate aware.

        Two modes:
        - *feedback* given (Reflection Pattern): the adaptive selector picks
          weak cards first, and every selected card carries the reviewer's
          concrete notes ("this claim lacks numbers", "cover X").  New
          claims are MERGED into the original card (dedup by source-URL),
          so evidence accumulates across rounds instead of being replaced.
        - otherwise: only cards below *min_claims* get the standard
          "your previous research was insufficient" re-run (replaces).

        Each selected card receives a *dynamic* ResourceBudget based on its
        weakness score; stronger cards get a light pass, weak cards get a
        deeper one.

        Returns the updated card list; DB and blackboard are refreshed.
        """
        targets = select_augment_targets(
            cards,
            feedback=bool(feedback),
            min_claims=min_claims,
        )
        if not targets:
            return cards

        logger.info(
            "Augmenting %d/%d card(s)%s",
            len(targets), len(cards), " (feedback-driven)" if feedback else "",
        )

        async def augment_one(card: ResearchCard) -> ResearchCard:
            brief = {
                "sub_question": card.research_question or question,
                "keywords": [],
                "source_types": [],
                # Fix #F: carry the original role through — a feedback-driven
                # re-search without the role loses the stance guidance
                # ("技术专家" must keep its deep-dive posture).
                "role": card.role,
            }
            if feedback:
                instruction = (
                    f"研究质量评审认为你的产出不达标，你必须逐条回应以下评审反馈：\n"
                    f"【评审反馈】\n{feedback}\n\n"
                    "针对反馈指出的问题重新搜索：笼统结论补上数字/时间/对比，"
                    "关键结论补充来源证据，覆盖反馈指出的遗漏方面。"
                    "在保留原有发现的基础上补充新证据，最终输出完整的 JSON 对象"
                    "（包含原有+新增的所有发现）。"
                )
            else:
                instruction = (
                    f"你上一轮对「{card.perspective}」视角的研究产出不足（少于 {min_claims} 条发现）。"
                    "请针对该子问题重新进行更深入的搜索，这次至少产出 "
                    f"{min_claims} 条有来源支撑的发现。不要重复你上一轮已经写过的内容。"
                )
            allocation = allocation_for_augment(
                card,
                min_claims=min_claims,
                augment_count=augment_count,
            )
            new_card = await self._research_with_retry(
                card.perspective, brief, question,
                extra_instruction=instruction,
                # Only the quality-gate (Reflector feedback) round unlocks
                # Firecrawl/Tavily; normal/min-claims augmentation stays free.
                use_quality_tools=bool(feedback),
                allocation=allocation,
            )
            if feedback:
                # Quality-driven round: merge rather than replace, so good
                # findings survive even if the re-search is a partial miss.
                merged = self._merge_cards(card, new_card, merge_gaps=True)
                logger.info("  [%s] feedback-augmented: %d → %d findings",
                            card.perspective, len(card.key_findings), len(merged.key_findings))
                return merged
            if len(new_card.key_findings) > len(card.key_findings):
                logger.info("  [%s] augmented: %d → %d findings",
                            card.perspective, len(card.key_findings), len(new_card.key_findings))
                return new_card
            logger.info("  [%s] augment produced no gain, keeping original", card.perspective)
            return card

        results = await parallel(*[augment_one(c) for c in targets])
        # Replace cards in the original list, preserving order
        by_id = {id(c): r for c, r in zip(targets, results)}
        updated = [by_id[id(c)] if by_id.get(id(c)) is not None else c for c in cards]

        # Refresh DB + blackboard — replace=true keeps the table free of
        # duplicate cards when augment loops or resumes re-run a perspective
        repo = Repository()
        for card in updated:
            await repo.save_research_card(run_id, card, replace=True)
        self.blackboard.write(f"run:{run_id}:cards", updated)
        return updated

    async def _run_orchestrator(
        self, agent: Agent, question: str, search_plan: dict | None = None
    ) -> tuple[str, list[tuple[str, dict]]]:
        """Run orchestrator (Group Chat Manager).

        Returns (question_type, [(name, brief), ...]).  The briefs carry
        a "role" that drives each researcher's stance; question_type is
        validated against the known set, anything else → "general".
        """
        task = ORCHESTRATOR_TASK.format(question=question)
        plan_text = format_search_plan(search_plan)
        if plan_text:
            task = task + chr(10) + chr(10) + plan_text
        raw = await agent.run(task)
        result = parse_json_response(raw, context="orchestrator")
        if not result.success:
            logger.error("Orchestrator parse failed: %s", result.errors)
            return "general", _DEFAULT_PERSPECTIVES

        data = result.data
        qtype = str(data.get("question_type", "general")).strip().lower()
        if qtype not in _QUESTION_TYPES:
            logger.warning("Orchestrator unknown question_type '%s', using general", qtype)
            qtype = "general"

        # New format: {"question_type": ..., "perspectives": [{"name", "role", ...}, ...]}
        if "perspectives" in data:
            items = data["perspectives"]
            if isinstance(items, list) and len(items) >= 2:
                briefs = []
                for i, p in enumerate(items):
                    name = p.get("name")
                    if not name or not str(name).strip():
                        name = f"视角{i + 1}"
                    briefs.append((str(name)[:40], {
                        "sub_question": str(p.get("sub_question", question)),
                        "keywords": p.get("keywords", []) if isinstance(p.get("keywords", []), list) else [],
                        "source_types": p.get("source_types", []) if isinstance(p.get("source_types", []), list) else [],
                        "role": _normalise_role(p.get("role"))[:20],
                    }))
                # Alignment gate: flag sub-questions that drifted from the
                # original subject (diagnostic only — dropping could leave
                # zero perspectives).
                for name, brief in briefs:
                    score = _check_alignment(question, brief.get("sub_question", ""))
                    if score < ALIGNMENT_MIN_OVERLAP:
                        logger.warning(
                            "Orchestrator [%s] 子问题与原问题重叠率 %.0f%%（可能跑题）：%s",
                            name, score * 100, brief.get("sub_question", ""),
                        )
                # LLM 对齐门：语义级检查 + 修正跑题子问题（字符重叠门抓不到
                # 的"对象前缀替换"靠这里）
                briefs = await self._align_perspectives(question, briefs)
                return qtype, briefs
            logger.warning("Orchestrator returned empty 'perspectives' list")
            return "general", _DEFAULT_PERSPECTIVES

        # Old format fallback: {"technical": {...}, "industry": {...}, ...}
        if "technical" in data or "industry" in data:
            logger.info("Orchestrator returned old-format 4-perspective output")
            return "general", [
                ("technical", {**data.get("technical", {}), "role": "技术专家"}),
                ("industry", {**data.get("industry", {}), "role": "行业分析师"}),
                ("critical", {**data.get("critical", {}), "role": "批判者"}),
                ("future", {**data.get("future", {}), "role": "未来趋势"}),
            ]

        logger.warning("Orchestrator returned unrecognised format, using defaults")
        return "general", _DEFAULT_PERSPECTIVES

    async def _align_perspectives(
        self, question: str, briefs: list[tuple[str, dict]]
    ) -> list[tuple[str, dict]]:
        """LLM alignment gate — semantically check + fix off-topic sub-questions.

        The character-overlap gate can't catch "object prefix substitution"
        ("个人PC" → "AI PC" still shares "PC").  This asks a cheap qwen
        call to judge each sub-question against the original question and
        rewrite any that drifted.  Any failure degrades to the original
        briefs — alignment must never block research.
        """
        sub_qs = "\n".join(
            f"- {name}: {brief.get('sub_question', '')}" for name, brief in briefs
        )
        task = _ALIGNMENT_TASK.format(question=question, sub_questions=sub_qs)
        try:
            agent = create_agent(
                name="alignment-checker",
                role="研究对象一致性检查器",
                goal="检查每个子问题是否围绕原问题，跑题的就修正研究对象。",
                backstory=(
                    "你严格比对子问题与原问题的研究对象，发现对象被替换、"
                    "收窄或扩大时就给出修正版。"
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
            logger.warning("Alignment check skipped (agent failed): %s", exc)
            return briefs

        result = parse_json_response(raw, context="alignment")
        if not result.success:
            logger.warning("Alignment check parse failed: %s", result.errors)
            return briefs

        items = result.data.get("results", [])
        if not isinstance(items, list):
            return briefs
        by_name = {str(r.get("name", "")): r for r in items if isinstance(r, dict)}

        aligned: list[tuple[str, dict]] = []
        for name, brief in briefs:
            r = by_name.get(name)
            if r and not r.get("aligned", True):
                fixed = str(r.get("sub_question", "")).strip()
                if fixed and fixed != brief.get("sub_question", ""):
                    logger.info(
                        "Alignment: 修正跑题子问题 [%s]\n  原: %s\n  改: %s",
                        name, brief.get("sub_question", ""), fixed,
                    )
                    brief = {**brief, "sub_question": fixed}
            aligned.append((name, brief))
        return aligned

    async def _salvage_researcher_output(
        self,
        pname: str,
        sub_q: str,
        raw_text: str,
        role: str = "",
    ) -> ResearchCard | None:
        """Try to convert a non-JSON researcher output (Markdown/prose) into a card."""
        if not raw_text or not raw_text.strip():
            return None

        task = RESEARCHER_SALVAGE_TASK.format(
            perspective=pname,
            research_question=sub_q,
            raw_text=raw_text[:12000],
        )
        try:
            agent = create_agent(
                name=f"researcher-salvage-{pname}",
                role="研究结果格式化员",
                goal="把非 JSON 的研究输出整理成结构化 JSON。",
                backstory=(
                    "你擅长从 Markdown/散文研究中提取事实、来源 URL 和反面证据，"
                    "并整理成 Researcher 的标准 JSON 结构。"
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
            logger.warning("Researcher salvage failed for %s: %s", pname, exc)
            return None

        result = parse_json_response(raw, context=f"researcher/{pname}/salvage")
        if not result.success or not isinstance(result.data, dict):
            logger.warning("Researcher salvage parse failed for %s", pname)
            return None

        card = self._build_card(result.data, pname, raw_text, role=role)
        if card is not None and card.key_findings:
            logger.info(
                "Researcher [%s] salvaged non-JSON output into %d findings",
                pname, len(card.key_findings),
            )
            return card
        return None

    async def _research_with_retry(
        self, pname: str, brief: dict, question: str, *,
        extra_instruction: str = "", use_quality_tools: bool = False,
        allocation: ComputeAllocation | None = None,
    ) -> ResearchCard:
        sub_q = brief.get("sub_question", question)
        keywords = brief.get("keywords", [])
        sources = brief.get("source_types", [])
        # Role drives the researcher's stance (Group Chat manager choice)
        role = str(brief.get("role", "")).strip() or "综合研究者"
        guidance = _ROLE_GUIDANCE.get(role, "")

        base_task = RESEARCHER_TASK.format(
            perspective=pname,
            role=role,
            sub_question=sub_q,
            keywords=", ".join(keywords) if keywords else "自行判断",
            source_types=", ".join(sources) if sources else "所有相关来源",
            question=question,
        )
        if guidance:
            base_task = base_task + f"\n\n你的研究姿态：{guidance}"
        plan_text = format_search_plan(self.blackboard.read("search_plan") if self.blackboard else None)
        if plan_text:
            base_task = base_task + chr(10) + chr(10) + plan_text
        if extra_instruction:
            base_task = base_task + "\n\n" + extra_instruction

        last_parse_failed = False
        for attempt in range(MAX_RETRIES + 1):
            task = base_task if attempt == 0 else f"⚠️ 你上一次的输出不是合法 JSON。请只输出一个 JSON 对象，不要 Markdown、不要解释、不要代码块。字段必须为 perspective / research_question / key_findings / gaps / raw_transcript。\n\n{base_task}"

            cfg = RESEARCHER_CONFIGS.get(pname, _DEFAULT_RESEARCHER)
            if use_quality_tools:
                # Quality-gate round: allow Firecrawl/Tavily as a last resort.
                cfg = {**cfg, "tools": get_quality_search_tools()}
            active_names = {t.name for t in cfg.get("tools", [])}
            reserved = [t for t in get_quality_search_tools() if t.name not in active_names]
            extra_kwargs: dict = {}
            if allocation is not None:
                # Turn the deterministic allocation into a real
                # ResourceBudget for this research attempt.
                all_tool_names = sorted(active_names | {t.name for t in reserved})
                policy = default_policy_for(f"researcher-{pname}", all_tool_names)
                policy.budget.max_tool_calls = allocation.max_tool_calls
                policy.budget.max_llm_calls = allocation.max_llm_calls
                extra_kwargs["policy"] = policy
                if allocation.max_tool_rounds is not None:
                    extra_kwargs["max_tool_rounds"] = allocation.max_tool_rounds
            agent = create_agent(
                **cfg,
                blackboard=self.blackboard,
                file_cache=self.file_cache,
                name=f"researcher-{pname}",
                trace_id=self._trace_id(),
                reserved_tools=reserved,
                **extra_kwargs,
            )
            raw = await agent.run(task)
            logger.info("Researcher [%s] attempt %d: %d chars", pname, attempt, len(raw))

            result = parse_json_response(raw, context=f"researcher/{pname}/attempt-{attempt}")
            if not result.success:
                last_parse_failed = True
                logger.warning("Researcher [%s] attempt %d parse failed: %s", pname, attempt, result.errors)
                continue

            last_parse_failed = False
            card = self._build_card(result.data, pname, raw, role=role)
            if card is not None and card.key_findings:
                # Deep follow-up: fill gaps and boost low-confidence claims
                card = await self._follow_up(card, pname, pname, sub_q, question)
                return card

        # All retries exhausted — if the last output was not JSON, try to
        # salvage the Markdown/prose into a structured card before giving up.
        if last_parse_failed and raw:
            salvaged = await self._salvage_researcher_output(pname, sub_q, raw, role=role)
            if salvaged is not None:
                return salvaged

        logger.error("Researcher [%s] all attempts exhausted", pname)
        return ResearchCard(
            perspective=pname,
            research_question=sub_q,
            key_findings=[],
            gaps=[f"Failed after {MAX_RETRIES + 1} attempts"],
            raw_transcript="",
        )

    @staticmethod
    def _merge_cards(
        base: ResearchCard, extra: ResearchCard, *, merge_gaps: bool = True
    ) -> ResearchCard:
        """Merge *extra* into *base*, deduping claims by source-URL overlap.

        THE single merge implementation (fix #5) — used by both
        feedback-driven augmentation and low-confidence follow-up, so
        both accumulate evidence identically: claims that share any
        source URL with an existing claim are dropped, gaps are UNIONED
        (bounded, order-preserving, never replaced), transcript appended.
        """
        existing_urls = {s for c in base.key_findings for s in c.sources}
        for claim in extra.key_findings:
            if not any(s in existing_urls for s in claim.sources):
                base.key_findings.append(claim)
                existing_urls.update(claim.sources)
        if merge_gaps:
            base.gaps = list(dict.fromkeys([*(base.gaps or []), *(extra.gaps or [])]))[:5]
        base.raw_transcript = (base.raw_transcript or "") + "\n\n[merged]\n" + (extra.raw_transcript or "")
        return base

    def _build_card(self, data: dict, pname: str, raw: str, role: str = "") -> ResearchCard | None:
        data["perspective"] = pname
        data.setdefault("research_question", "")
        data.setdefault("gaps", [])
        data.setdefault("raw_transcript", raw[:2000])

        raw_claims = data.pop("key_findings", [])
        claims = safe_construct_list(Claim, raw_claims, context=f"claims/{pname}")

        try:
            return ResearchCard(
                perspective=pname,
                role=role,
                research_question=data.get("research_question", ""),
                key_findings=claims,
                gaps=data.get("gaps", []),
                raw_transcript=data.get("raw_transcript", raw[:2000]),
            )
        except Exception:
            return None

    async def _follow_up(
        self, card: ResearchCard, pname: str, _perspective: str, sub_q: str, question: str
    ) -> ResearchCard:
        """Boost LOW-CONFIDENCE claims with one extra research round.

        Fix #4: only low-confidence claims trigger this.  Gaps alone no
        longer spawn a full re-search — nearly every card self-reports
        gaps (they are asked to), so gappy cards re-searching would
        almost double Phase 1 cost.  Filling gaps is the graph-level
        Reflection quality gate's job.
        """
        low_claims = [c for c in card.key_findings if c.confidence == Confidence.LOW]

        if not low_claims:
            return card  # nothing to follow up on

        logger.info(
            "Researcher [%s] follow-up triggered: %d low-confidence claims",
            pname, len(low_claims),
        )

        low_lines = "\n".join(f"  - [{c.confidence.value}] {c.text[:120]}" for c in low_claims)

        # Fix #F (follow-up variant): keep the original role's stance
        role = card.role or "综合研究者"
        guidance = _ROLE_GUIDANCE.get(role, "")
        task = (
            f"你已经完成了「{pname}」视角（角色：{role}）的初步研究，但有些声明置信度较低。\n\n"
            f"## 置信度较低、需要进一步验证的声明\n{low_lines}\n\n"
            f"请针对以上每一项，使用搜索工具补充证据（找到来源 URL 或反证），"
            f"然后将所有发现（包括已有的和新增的）合并输出为一个完整的 JSON 对象：\n"
            f"{{\n"
            f'  "perspective": "{pname}",\n'
            f'  "research_question": "{sub_q}",\n'
            f'  "key_findings": [\n'
            f'    {{"text": "论点（中文）", "confidence": "high/medium/low", '
            f'"sources": ["URL"], "counterpoints": ["注意事项"]}}\n'
            f'  ],\n'
            f'  "gaps": ["仍未覆盖的盲区"],\n'
            f'  "raw_transcript": "研究过程简述"\n'
            f"}}\n\n"
            f"严格只输出 JSON，不要代码块包裹。"
        )
        if guidance:
            task = task + f"\n\n你的研究姿态：{guidance}"

        cfg = RESEARCHER_CONFIGS.get(pname, _DEFAULT_RESEARCHER)
        active_names = {t.name for t in cfg.get("tools", [])}
        reserved = [t for t in get_quality_search_tools() if t.name not in active_names]
        agent = create_agent(**cfg, blackboard=self.blackboard, file_cache=self.file_cache, name=f"researcher-{pname}-fu", trace_id=self._trace_id(), reserved_tools=reserved)
        raw = await agent.run(task)
        logger.info("Researcher [%s] follow-up: %d chars", pname, len(raw))

        result = parse_json_response(raw, context=f"researcher/{pname}/follow-up")
        if not result.success:
            logger.warning("Researcher [%s] follow-up parse failed: %s", pname, result.errors)
            return card  # keep original card

        new = self._build_card(result.data, pname, raw)
        if new is None or not new.key_findings:
            return card

        # Fix #5: same merge semantics as feedback-driven augmentation —
        # claims deduped by source-URL, gaps UNIONED (never replaced:
        # follow-up search finding nothing must not wipe the researcher's
        # self-reported blind spots).
        before_findings = len(card.key_findings)
        before_gaps = len(card.gaps)
        card = self._merge_cards(card, new, merge_gaps=True)
        logger.info(
            "Researcher [%s] follow-up done: %d → %d findings, %d → %d gaps",
            pname, before_findings, len(card.key_findings), before_gaps, len(card.gaps),
        )
        return card
