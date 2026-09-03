"""Query Planner — classify a research question and produce a search plan.

The planner runs before the Orchestrator.  It decides which of the
supported question types the input belongs to, extracts key constraints
(entities, time, place, clues), and emits a concrete search plan:
priority sources, sub-queries, and verification steps.

It is intentionally non-blocking: if the LLM output cannot be parsed,
a conservative generic plan is returned so research always proceeds.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from deep_research.agents.registry import create_agent
from deep_research.core.blackboard import Blackboard
from deep_research.core.file_cache import FileCache
from deep_research.response_parser import parse_json_response

logger = logging.getLogger("deep_research.query_planner")

QUERY_PLANNER_TASK = """你是搜索策略规划师。请分析用户的研究问题，判断问题类型，并生成一套可执行的搜索方案。

问题：{question}

## 问题类型（选一个）
- entity_fact：实体事实，问“是什么/谁/哪一年/在哪里”，答案通常是唯一事实
- multi_hop_clue：多跳线索题，给出多条线索要求锁定唯一实体（如 BrowseComp）
- comparative：对比选型，问“A 和 B 哪个好/有什么区别/怎么选”
- news_current：实时新闻/动态，问“最近/最新/今天”
- technical：技术原理/实现/为什么
- academic：学术文献/研究现状
- policy_legal：政策法规/合规
- business_market：商业市场/竞品/规模
- historical_archive：历史档案/旧事件/旧网页
- general：以上都不像

## 输出 JSON 格式
{{
  "question_type": "multi_hop_clue",
  "key_constraints": ["首都", "2002年活动", "2003年毕业典礼", "2022年植物采集"],
  "search_plan": {{
    "strategy_summary": "一句话说明整体搜索策略",
    "priority_sources": ["官网", "Wikipedia/Wikidata", "Wayback Machine"],
    "sub_queries": [
      {{
        "purpose": "候选生成",
        "query": "capital city universities 2002 support event",
        "site": "",
        "tools": ["baidu_search", "bing_search"]
      }},
      {{
        "purpose": "逐条验证",
        "query": "site:qau.edu.ye 2002 three-day event",
        "site": "qau.edu.ye",
        "tools": ["bing_search", "firecrawl_search"]
      }}
    ],
    "verification_steps": ["候选逐条满足线索数打分", "线索冲突直接淘汰"],
    "use_quality_tools": true
  }}
}}

要求：
1. sub_queries 要具体、可直接用于搜索，不要写“搜索相关资料”这种空话。
2. 每个 sub_query 的 tools 里，默认只写 baidu_search/bing_search；
   只有当免费引擎明显不够、或需要官网/历史档案/知识库时，才加入 wikipedia_search、wikidata_lookup、firecrawl_search、tavily_search。
3. use_quality_tools 表示该问题是否预计需要质量增强工具；false 时研究员默认只用免费引擎。
4. 严格只输出 JSON，不要任何其他文字。"""


DEFAULT_PLAN: dict[str, Any] = {
    "question_type": "general",
    "key_constraints": [],
    "search_plan": {
        "strategy_summary": "使用通用搜索策略，先宽泛搜索再逐条验证。",
        "priority_sources": ["通用搜索引擎", "官网"],
        "sub_queries": [],
        "verification_steps": ["检查来源是否可靠", "多源交叉验证"],
        "use_quality_tools": False,
    },
}


def _default_plan(question: str) -> dict[str, Any]:
    plan = json.loads(json.dumps(DEFAULT_PLAN))
    plan["search_plan"]["sub_queries"] = [
        {
            "purpose": "通用搜索",
            "query": question,
            "site": "",
            "tools": ["baidu_search", "bing_search"],
        }
    ]
    return plan


def parse_search_plan(raw: str, question: str = "") -> dict[str, Any]:
    """Parse planner JSON; fall back to a generic plan on any failure."""
    if not raw or not raw.strip():
        return _default_plan(question)
    result = parse_json_response(raw, context="query_planner")
    if not result.success or not isinstance(result.data, dict):
        logger.warning("Query planner parse failed; using generic plan")
        return _default_plan(question)
    data = result.data
    if "search_plan" not in data or not isinstance(data.get("search_plan"), dict):
        logger.warning("Query planner output missing search_plan; using generic plan")
        return _default_plan(question)
    return data


def format_search_plan(plan: dict[str, Any] | None) -> str:
    """Render a search plan as concise text for researchers/orchestrator."""
    if not plan:
        return ""
    qtype = plan.get("question_type", "general")
    sp = plan.get("search_plan") or {}
    lines = [
        "## 搜索计划（来自查询规划器）",
        f"- 问题类型：{qtype}",
    ]
    if plan.get("key_constraints"):
        lines.append(f"- 关键约束：{'、'.join(str(x) for x in plan['key_constraints'][:8])}")
    if sp.get("strategy_summary"):
        lines.append(f"- 策略：{sp['strategy_summary']}")
    if sp.get("priority_sources"):
        lines.append(f"- 优先来源：{'、'.join(str(x) for x in sp['priority_sources'][:8])}")
    sub_queries = sp.get("sub_queries") or []
    if sub_queries:
        lines.append("- 子查询：")
        for i, q in enumerate(sub_queries[:8], 1):
            if isinstance(q, dict):
                query = q.get("query", "")
                site = q.get("site", "")
                tools = q.get("tools") or []
                site_txt = f" site:{site}" if site else ""
                tools_txt = "、".join(str(t) for t in tools[:5]) if tools else ""
                lines.append(f"  {i}. {query}{site_txt}" + (f"（{tools_txt}）" if tools_txt else ""))
    if sp.get("verification_steps"):
        lines.append("- 验证步骤：")
        for v in sp["verification_steps"][:8]:
            lines.append(f"  - {v}")
    if sp.get("use_quality_tools"):
        lines.append("- 允许质量工具：是（Wikipedia/Wikidata/Firecrawl/Tavily）")
    return "\n".join(lines)


class QueryPlanner:
    """Runs the query-planner agent and returns a structured search plan."""

    def __init__(
        self,
        blackboard: Blackboard | None = None,
        file_cache: FileCache | None = None,
    ) -> None:
        self.blackboard = blackboard or Blackboard()
        self.file_cache = file_cache or FileCache()

    def _trace_id(self) -> str:
        return str(self.blackboard.read("trace_id", ""))

    async def plan(self, question: str) -> dict[str, Any]:
        """Generate and return a search plan. Never raises."""
        try:
            agent = create_agent(
                name="query-planner",
                role="搜索策略规划师",
                goal="分析问题类型并生成可执行的搜索方案。",
                backstory=(
                    "你擅长把复杂研究问题拆成具体搜索动作，并知道不同问题"
                    "该用官网、百科、知识库、历史档案还是实时新闻。"
                ),
                tools=[],
                llm="deepseek",
                blackboard=self.blackboard,
                file_cache=self.file_cache,
                trace_id=self._trace_id(),
                response_format={"type": "json_object"},
            )
            raw = await agent.run(QUERY_PLANNER_TASK.format(question=question))
        except Exception as exc:
            logger.warning("Query planner agent failed: %s", exc)
            return _default_plan(question)

        plan = parse_search_plan(raw, question)
        self.blackboard.write("search_plan", plan)
        logger.info(
            "Query planner: type=%s, sub_queries=%d, quality=%s",
            plan.get("question_type", "general"),
            len((plan.get("search_plan") or {}).get("sub_queries") or []),
            (plan.get("search_plan") or {}).get("use_quality_tools", False),
        )
        return plan


__all__ = [
    "QueryPlanner",
    "QUERY_PLANNER_TASK",
    "parse_search_plan",
    "format_search_plan",
    "DEFAULT_PLAN",
]
