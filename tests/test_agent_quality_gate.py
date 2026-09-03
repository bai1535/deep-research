"""Tests for the per-round free-search quality gate in core.agent."""

from deep_research.core.agent import Agent
from deep_research.core.tool import BuildTool


class _FakeTool(BuildTool):
    def __init__(self, name: str) -> None:
        self.name = name

    async def execute(self, args):
        return []


def _agent_with_reserved():
    return Agent(
        name="researcher-test",
        system_prompt="",
        tools=[_FakeTool("baidu_search"), _FakeTool("bing_search")],
        reserved_tools=[_FakeTool("firecrawl_search")],
    )


def test_unlock_when_all_free_search_insufficient():
    agent = _agent_with_reserved()
    results = [
        {"tool": "baidu_search", "content": "1. title\n   URL: http://a.com"},
        {"tool": "bing_search", "content": "No results found."},
    ]
    agent._maybe_unlock_quality_tools(results)
    assert "firecrawl_search" in agent.tools
    assert agent._quality_unlocked is True
    assert any("免费搜索引擎" in m["content"] for m in agent.messages if m["role"] == "user")


def test_no_unlock_when_free_search_has_enough_results():
    agent = _agent_with_reserved()
    results = [
        {"tool": "baidu_search", "content": "1. a\n   URL: http://a.com\n2. b\n   URL: http://b.com"},
        {"tool": "bing_search", "content": "No results found."},
    ]
    agent._maybe_unlock_quality_tools(results)
    assert "firecrawl_search" not in agent.tools
    assert agent._quality_unlocked is False


def test_no_unlock_when_no_free_search_called():
    agent = _agent_with_reserved()
    agent._maybe_unlock_quality_tools([{"tool": "web_fetch", "content": "some content"}])
    assert "firecrawl_search" not in agent.tools


def test_unlock_only_once():
    agent = _agent_with_reserved()
    results = [
        {"tool": "baidu_search", "content": "1. a\n   URL: http://a.com"},
        {"tool": "bing_search", "content": "ERROR: boom"},
    ]
    agent._maybe_unlock_quality_tools(results)
    assert "firecrawl_search" in agent.tools
    n = sum(1 for m in agent.messages if m["role"] == "user" and "免费搜索引擎" in m["content"])
    assert n == 1
    # Second call must not add another message.
    agent._maybe_unlock_quality_tools(results)
    n = sum(1 for m in agent.messages if m["role"] == "user" and "免费搜索引擎" in m["content"])
    assert n == 1
