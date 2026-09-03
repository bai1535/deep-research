"""Tests for Verifier active search + contradiction adjudicator (offline)."""

from deep_research.agents.registry import VERIFIER_CONFIG
from deep_research.crews.verification_crew import CONTRADICTION_ADJUDICATOR_TASK


def test_verifier_has_search_tools():
    names = {t.name for t in VERIFIER_CONFIG["tools"]}
    assert "bing_search" in names
    assert "baidu_search" in names


def test_verifier_still_has_fetch_and_db():
    names = {t.name for t in VERIFIER_CONFIG["tools"]}
    assert "web_fetch" in names
    assert "sqlite_read" in names


def test_contradiction_adjudicator_task_defined():
    assert "resolutions" in CONTRADICTION_ADJUDICATOR_TASK
    assert "winner" in CONTRADICTION_ADJUDICATOR_TASK
