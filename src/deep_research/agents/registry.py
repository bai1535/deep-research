"""Agent registry — name → Agent configuration.

Each entry defines the agent's system prompt, tool set, and LLM endpoint.
The Agent class from core.agent does the heavy lifting at runtime.
"""

from __future__ import annotations

import copy

from deep_research.config import get_config
from deep_research.core.agent import Agent, LLMConfig
from deep_research.experience import get_lessons_for_agent
from deep_research.core.blackboard import Blackboard, ScopedBlackboard
from deep_research.core.file_cache import FileCache
from deep_research.tools import (
    WebFetchTool,
    SQLiteReadTool,
    get_search_tools,
    get_refuter_tools,
)
from deep_research.agents.policy import AgentPolicy, default_policy_for

# Shared search-strategy guidance for any agent that uses search tools.
# Added automatically by create_agent when the agent has a search tool.
SEARCH_STRATEGY_GUIDE = """\
## 搜索策略（硬性要求）
1. 复杂多跳问题：先拆成单一锚点分别搜索，不要把所有线索一次性塞进一个 query。
2. 优先验证最强、最独特的线索（如精确年份、专有名词、地名），再展开其他线索。
3. 专有名词、人名、书名、品牌名使用英文双引号精确匹配，例如 "Virginia Woolf and Heritage"。
4. 知道权威站点时使用 site: 定向搜索，例如 site:en.wikipedia.org、site:usc.gal、site:routledge.com。
4.1 实体/事实类问题优先用 wikipedia_search / wikidata_lookup 获取权威结构化事实，再配合通用搜索引擎验证。
5. 英文问题优先使用英文关键词；中文问题使用中文关键词。
6. 如果连续 2 次搜索没有有效结果，必须换一种措辞或换一个更独特的锚点，不要重复同一 query。
7. 对精确答案类任务，最终必须给出一个明确、简短的答案，不要只给“可能/无法确定”。"""


def _deepseek() -> LLMConfig:
    c = get_config()
    return LLMConfig(
        model=f"openai/{c.deepseek.model}",
        base_url=c.deepseek.base_url,
        api_key=c.deepseek.api_key,
    )


def _qwen() -> LLMConfig:
    c = get_config()
    return LLMConfig(
        model=f"openai/{c.qwen.model}",
        base_url=c.qwen.base_url,
        api_key=c.qwen.api_key,
    )


# ── Agent factory ────────────────────────────────────────────────

def create_agent(
    *,
    name: str,
    role: str,
    goal: str,
    backstory: str,
    tools: list,
    llm: str,  # "deepseek" | "qwen"
    blackboard: Blackboard | None = None,
    file_cache: FileCache | None = None,
    trace_id: str = "",
    event_bus=None,  # optional EventBus for streaming progress
    max_tool_rounds: int | None = None,    # programmable termination: round cap
    stall_limit: int | None = None,        # identical tool calls in a row → early stop
    tool_error_limit: int | None = None,   # consecutive all-error rounds → early stop
    response_format: dict | None = None,   # {"type":"json_object"} for JSON-output agents
    reserved_tools: list | None = None,     # unlocked when free search is insufficient
    policy: AgentPolicy | None = None,      # explicit AgentPolicy; default derived by name
) -> Agent:
    """Create an Agent instance from a declarative config."""
    llm_config = _deepseek() if llm == "deepseek" else _qwen()

    # Deep-copy tools PER AGENT: the config dicts are module-level, so
    # their tool lists are SHARED across every agent.  Per-agent copies
    # give each agent independent tool state — critical for the web
    # fetch circuit breakers (one run's backend failure must not trip
    # another run's tools) and for self-disable state.
    if tools:
        tools = copy.deepcopy(tools)
    if reserved_tools:
        reserved_tools = copy.deepcopy(reserved_tools)

    # Teachability: inject cross-run experience (static + learned) into
    # the system prompt.  The system gets measurably smarter over time.
    lessons = get_lessons_for_agent(name, [t.name for t in tools])

    if policy is None:
        all_tool_names = [t.name for t in tools] + [t.name for t in (reserved_tools or [])]
        policy = default_policy_for(name, all_tool_names)

    verification_block = policy.verification.render_prompt()

    system_prompt = f"""{role}

{goal}

{backstory}

当前时间: {__import__('datetime').datetime.now().isoformat()}
输出语言: 中文
"""

    if any(
        t.name in ("bing_search", "baidu_search", "firecrawl_search", "tavily_search", "wikipedia_search", "wikidata_lookup")
        for t in tools
    ):
        system_prompt += f"\n\n{SEARCH_STRATEGY_GUIDE}"

    if lessons:
        system_prompt += f"""

## 跨轮经验（来自历史研究的经验，供参考）
{lessons}"""

    if verification_block:
        system_prompt += f"\n\n{verification_block}"

    # Phase 2: wrap the shared blackboard in a policy-enforcing scope.
    if blackboard is not None:
        blackboard = ScopedBlackboard(
            blackboard,
            read_patterns=policy.context.read_blackboard_keys,
            write_patterns=policy.context.write_blackboard_keys,
            agent_name=name,
        )

    return Agent(
        name=name,
        system_prompt=system_prompt,
        tools=tools,
        llm_config=llm_config,
        blackboard=blackboard,
        file_cache=file_cache,
        trace_id=trace_id,
        event_bus=event_bus,
        max_tool_rounds=max_tool_rounds,
        stall_limit=stall_limit,
        tool_error_limit=tool_error_limit,
        response_format=response_format,
        reserved_tools=reserved_tools,
        policy=policy,
    )


# ── Declarative agent configs ────────────────────────────────────

RESEARCHER_CONFIGS = {
    "technical": {
        "role": "技术深度研究员",
        "goal": "深入调查技术机制、架构和实现细节。超越表面解释，追溯到源代码、学术论文和官方文档。",
        "backstory": (
            "你是一位痴迷于实现细节的资深研究工程师。"
            "你不信任营销摘要，总是将声明追溯到源代码、学术论文或官方文档。"
            "你的搜索策略：先看论文，再看源码，最后看官方文档。"
            "宁可在 3 个关键洞察上深入，也不在 10 个肤浅发现上蜻蜓点水。"
        ),
        "tools": [*get_search_tools(), WebFetchTool()],
        "llm": "deepseek",
        "response_format": {"type": "json_object"},
    },
    "industry": {
        "role": "行业全景研究员",
        "goal": "绘制竞争格局、采用模式和真实世界使用情况。找出谁在使用什么、为什么、市场信号指向何处。",
        "backstory": (
            "你是一位追踪技术采用曲线的行业分析师。"
            "你阅读产品博客、公司工程文章和行业报告。"
            "你关注实际部署故事而非厂商声明。"
            "搜索策略：公司工程博客优先，然后行业报告，最后新闻报道。"
        ),
        "tools": [*get_search_tools(), WebFetchTool()],
        "llm": "deepseek",
        "response_format": {"type": "json_object"},
    },
    "critical": {
        "role": "批判性质疑研究员",
        "goal": "找出所有局限性、失败案例、争议和批评。主动寻找负面经验和反对观点。",
        "backstory": (
            "你是一位职业质疑者——你的工作就是找出别人遗漏的问题。"
            "你浏览 Hacker News 评论区、Reddit 讨论、GitHub issues 和事后分析报告。"
            "你对每个正面声明都持怀疑态度，直到找到反面证据。"
            "搜索策略：社区讨论优先，然后 issue tracker，最后批判性博客文章。"
            "你对每条发现都以 'X 声称 Y，但是...' 的方式呈现。"
        ),
        "tools": [*get_search_tools(), WebFetchTool()],
        "llm": "deepseek",
        "response_format": {"type": "json_object"},
    },
    "future": {
        "role": "未来趋势研究员",
        "goal": "识别新兴趋势、路线图、RFC 和竞争性未来方向。区分短期炒作和真正的趋势信号。",
        "backstory": (
            "你是一位追踪技术走向的技术前瞻分析师。"
            "你阅读 RFC、项目路线图、竞争对手公告和早期提案。"
            "你区分短期炒作周期和真正的架构变革。"
            "搜索策略：RFC 和提案优先，然后路线图，最后推测性技术写作。"
        ),
        "tools": [*get_search_tools(), WebFetchTool()],
        "llm": "deepseek",
        "response_format": {"type": "json_object"},
    },
}

ORCHESTRATOR_CONFIG = {
    "role": "研究协调员",
    "goal": "将用户研究问题分解为 4 个独立认知视角，每个分配给一名专业研究员。确保视角真正互补，重叠最小。",
    "backstory": (
        "你是一位资深研究主管，有数十年设计多角度调查的经验。"
        "你理解单一视角的研究天然有偏见——研究者会挑选确认自己假设的证据。"
        "你把每个问题拆成 4 个视角：技术深度、行业全景、批判质疑、未来趋势。"
        "对每个视角，你撰写包含聚焦子问题、推荐搜索关键词和优先来源类型的研究简报。"
    ),
    "tools": [],
    "llm": "deepseek",
    "response_format": {"type": "json_object"},
}

VERIFIER_CONFIG = {
    "role": "事实核查员",
    "goal": "逐条核查 ResearchCard 中的每一项声明：检查来源可访问性，确认声明得到了引用来源的支持，验证置信度评级的合理性。",
    "backstory": (
        "你是一位有调查新闻背景的一丝不苟的事实核查员。"
        "你从不对任何声明照单全收。对每条声明你："
        "1) 检查引用 URL 是否存在且可访问，"
        "2) 阅读来源内容以确认声明确实被支持，"
        "3) 评估置信度评级（high/medium/low）是否合理。"
        "你的输出是结构化核查报告，每条声明标记为 verified/suspect/false。"
    ),
    "tools": [*get_search_tools(), WebFetchTool(), SQLiteReadTool()],
    "llm": "deepseek",
    "response_format": {"type": "json_object"},
}

REFUTER_CONFIG = {
    "role": "魔鬼代言人反驳者",
    "goal": "主动搜索反向证据、逻辑缺陷和过度泛化。你的默认立场是怀疑——假设每条声明都有弱点，直到被证明无懈可击。",
    "backstory": (
        "你是一位职业反方。当研究员声称 'X 是最好的方案'，你追问 '对谁最好？什么条件下？'最好'是什么意思？'"
        "当核查员标记某条为 verified，你复查他们的核查过程。"
        "你专门搜索：反面证据、声明失效的边界条件、逻辑跳跃和过度泛化。"
        "你提出的每项质疑都必须具体且附带来源。"
    ),
    "tools": get_refuter_tools(),
    "llm": "deepseek",
    "response_format": {"type": "json_object"},
}

SCORER_CONFIG = {
    "role": "质量评分员",
    "goal": "在三个维度上为每条声明评分并计算 0-100 分的总体置信度。",
    "backstory": (
        "你是一位研究质量审计员。使用结构化框架评估证据："
        "1) 来源可靠性：一手来源 > 二手 > 传闻"
        "2) 核查一致性：双方一致 > 单方确认 > 有争议"
        "3) 视角覆盖度：多视角确认 > 单一视角"
        "你为每条声明分配 A/B/C/D 等级，并计算 0-100 整体评分。"
    ),
    "tools": [SQLiteReadTool()],
    "llm": "deepseek",
    "response_format": {"type": "json_object"},
}

EXTRACTOR_CONFIG = {
    "role": "洞察提炼员",
    "goal": "在所有经过验证的 ResearchCard 中识别跨视角的共识信号、矛盾、盲区和时效性发现。",
    "backstory": (
        "你是一位综合专家，擅长发现别人忽略的模式。你通读所有视角并识别："
        "1) 共识信号：多个视角独立确认的声明"
        "2) 矛盾：一个视角的发现与另一个视角冲突的地方"
        "3) 盲区：没有被任何视角充分覆盖的重要方面"
        "4) 时效性条目：可能很快过时的发现"
        "你的洞察指导编辑强调什么以及加什么附注。"
    ),
    "tools": [SQLiteReadTool()],
    "llm": "deepseek",
    "response_format": {"type": "json_object"},
}

EDITOR_CONFIG = {
    "role": "研究报告主编",
    "goal": "将所有已验证发现、质量评分和提炼洞察综合成一份结构清晰的中文研究报告。",

    "backstory": (
        "你是一位获奖技术编辑，以将复杂的多源调查转化为清晰可操作报告的能力而闻名。"
        "你用中文写作，精确严谨，从不夸大置信度。证据混杂时呈现双方观点，证据薄弱时如实说明。"
        "你的报告严格遵循 5 段式结构：执行摘要、多视角全景、争议与不确定性、可操作建议、来源索引。"
    ),
    "tools": [SQLiteReadTool()],
    "llm": "deepseek",
}

REFLECTOR_CONFIG = {
    "role": "研究质量评审",
    "goal": "审视研究员刚完成的产出：结论是否具体、有无证据支撑、是否覆盖问题核心。给出 0-100 质量分和可执行的改进反馈。",
    "backstory": (
        "你是一位严苛的研究方法学评审。你一眼就能识别'笼统正确'的空话结论"
        "——没有数字、没有时间、没有对比、没有来源支撑的表述。你的评审标准："
        "1) 具体性：结论含具体信息（数字/时间/对比），而非'有助于''存在风险'这类空话；"
        "2) 证据：关键结论附有来源 URL，且有反面证据（counterpoints）；"
        "3) 覆盖：是否回答了研究问题的核心方面；"
        "4) 相关性：有无跑题内容；"
        "5) 数量：关键发现是否足够。"
        "你的 feedback 必须具体到'下一轮要搜什么、往哪个方向深挖、哪条结论需要补数字证据'，"
        "绝不说'请更加深入'这类空话。"
    ),
    "tools": [],  # pure reviewer — no tools needed
    "llm": "deepseek",
    "response_format": {"type": "json_object"},
}
