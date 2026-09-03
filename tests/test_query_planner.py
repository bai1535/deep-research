"""Tests for the query planner (offline: parsing/formatting)."""

from deep_research.query_planner import (
    parse_search_plan,
    format_search_plan,
    DEFAULT_PLAN,
)


def test_parse_valid_plan():
    raw = """{
      "question_type": "multi_hop_clue",
      "key_constraints": ["首都", "2002"],
      "search_plan": {
        "strategy_summary": "先候选生成再逐条验证",
        "priority_sources": ["官网", "Wayback"],
        "sub_queries": [
          {"purpose": "候选生成", "query": "capital universities", "site": "", "tools": ["baidu_search"]}
        ],
        "verification_steps": ["逐条验证"],
        "use_quality_tools": true
      }
    }"""
    plan = parse_search_plan(raw, "test")
    assert plan["question_type"] == "multi_hop_clue"
    assert plan["search_plan"]["use_quality_tools"] is True
    assert plan["search_plan"]["sub_queries"][0]["query"] == "capital universities"


def test_parse_invalid_falls_back_to_generic():
    plan = parse_search_plan("not json at all", "some question")
    assert plan["question_type"] == "general"
    assert plan["search_plan"]["sub_queries"][0]["query"] == "some question"


def test_format_plan_includes_type_and_queries():
    plan = {
        "question_type": "technical",
        "key_constraints": ["GIL"],
        "search_plan": {
            "strategy_summary": "官方文档优先",
            "priority_sources": ["官方文档", "源码"],
            "sub_queries": [{"purpose": "原理", "query": "CPython GIL", "site": "docs.python.org", "tools": ["bing_search"]}],
            "verification_steps": ["以源码为准"],
            "use_quality_tools": False,
        },
    }
    text = format_search_plan(plan)
    assert "technical" in text
    assert "CPython GIL" in text
    assert "docs.python.org" in text


def test_default_plan_shape():
    assert DEFAULT_PLAN["question_type"] == "general"
    assert "sub_queries" in DEFAULT_PLAN["search_plan"]
