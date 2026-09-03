"""Tests for AgentPolicy Phase 1/2 models, scoped blackboard, and tool enforcement."""

from deep_research.agents.policy import (
    AgentPolicy,
    ContextPolicy,
    DataPolicy,
    ResourceBudget,
    ToolPolicy,
    VerificationStandard,
    default_policy_for,
)
from deep_research.agents.registry import create_agent
from deep_research.core.blackboard import Blackboard, ScopedBlackboard


def test_policy_models_have_defaults():
    policy = AgentPolicy(agent_name="test")
    assert isinstance(policy.context, ContextPolicy)
    assert isinstance(policy.tools, ToolPolicy)
    assert isinstance(policy.data, DataPolicy)
    assert isinstance(policy.budget, ResourceBudget)
    assert isinstance(policy.verification, VerificationStandard)


def test_default_policy_is_permissive():
    policy = default_policy_for("researcher-x", ["bing_search"])
    assert policy.agent_name == "researcher-x"
    assert policy.tools.allowed_tools == ["bing_search"]
    assert policy.context.can_read_other_agents is True


def test_verifier_policy_marks_independent_review():
    policy = default_policy_for("verifier-technical", ["bing_search", "web_fetch"])
    assert policy.verification.independent_review_required is True
    assert "verified" in policy.verification.status_allowed


def test_second_opinion_cannot_see_first_pass():
    policy = default_policy_for("second-opinion-technical", ["bing_search"])
    assert policy.verification.can_see_first_pass is False
    assert policy.context.can_read_other_agents is False


def test_create_agent_attaches_default_policy():
    agent = create_agent(
        name="unit-test-agent",
        role="tester",
        goal="test",
        backstory="test",
        tools=[],
        llm="deepseek",
    )
    assert agent.policy is not None
    assert agent.policy.agent_name == "unit-test-agent"


def test_scoped_blackboard_enforces_read_write_patterns():
    inner = Blackboard()
    inner.write("run:1:cards", "secret")
    inner.write("run_id", "r1")

    scoped = ScopedBlackboard(
        inner,
        read_patterns=["run_id"],
        write_patterns=["usage:*"],
        agent_name="test-agent",
    )
    assert scoped.read("run_id") == "r1"
    assert scoped.read("run:1:cards") is None

    scoped.write("run:1:cards", "hacked")
    assert inner.read("run:1:cards") == "secret"

    scoped.write("usage:test-agent", {"calls": 1})
    assert inner.read("usage:test-agent") == {"calls": 1}


def test_agent_tool_policy_blocks_disallowed_tools():
    policy = AgentPolicy(
        agent_name="restricted",
        tools=ToolPolicy(allowed_tools=["allowed_tool"], denied_tools=["bad_tool"]),
    )
    agent = create_agent(
        name="restricted",
        role="tester",
        goal="test",
        backstory="test",
        tools=[],
        llm="deepseek",
        policy=policy,
    )
    allowed, _ = agent._tool_allowed("allowed_tool")
    assert allowed is True
    blocked, reason = agent._tool_allowed("bad_tool")
    assert blocked is False
    assert "denied" in reason
    blocked, reason = agent._tool_allowed("other_tool")
    assert blocked is False
    assert "allowed_tools" in reason


def test_resource_budget_blocks_tool_calls():
    policy = AgentPolicy(
        agent_name="budget-tool",
        tools=ToolPolicy(allowed_tools=["tool"]),
        budget=ResourceBudget(max_tool_calls=0),
    )
    agent = create_agent(
        name="budget-tool",
        role="tester",
        goal="test",
        backstory="test",
        tools=[],
        llm="deepseek",
        policy=policy,
    )
    blocked, reason = agent._tool_allowed("tool")
    assert blocked is False
    assert "tool-call budget exceeded" in reason


async def test_resource_budget_blocks_llm_calls():
    policy = AgentPolicy(
        agent_name="budget-llm",
        budget=ResourceBudget(max_llm_calls=0),
    )
    agent = create_agent(
        name="budget-llm",
        role="tester",
        goal="test",
        backstory="test",
        tools=[],
        llm="deepseek",
        policy=policy,
    )
    result = await agent._call_llm()
    assert result is None


def test_verification_standard_renders_prompt_block():
    std = VerificationStandard(
        name="test_rubric",
        status_allowed=["verified", "suspect"],
        confidence_rubric={"多源官方": 90, "单源": 50},
        min_confidence=50,
        independent_review_required=True,
        can_see_first_pass=False,
    )
    text = std.render_prompt()
    assert "test_rubric" in text
    assert "多源官方: 90" in text
    assert "不得查看第一轮核查结论" in text


def test_default_verifier_prompt_includes_rubric():
    agent = create_agent(
        name="verifier-test",
        role="verifier",
        goal="verify",
        backstory="verify",
        tools=[],
        llm="deepseek",
    )
    assert "verifier_rubric_v1" in agent.system_prompt
    assert "多源官方/一手来源: 90" in agent.system_prompt


def test_default_second_opinion_prompt_cannot_see_first_pass():
    agent = create_agent(
        name="second-opinion-test",
        role="reviewer",
        goal="review",
        backstory="review",
        tools=[],
        llm="deepseek",
    )
    assert "不得查看第一轮核查结论" in agent.system_prompt


def test_second_opinion_policy_restricts_blackboard_keys():
    policy = default_policy_for("second-opinion-x", ["bing_search"])
    assert "run_id" in policy.context.read_blackboard_keys
    assert "usage:*" in policy.context.write_blackboard_keys
    assert not any(k.startswith("run:") for k in policy.context.read_blackboard_keys)


def test_second_opinion_agent_cannot_read_run_data_from_blackboard():
    bb = Blackboard()
    bb.write("run_id", "r1")
    bb.write("run:1:verified", "secret-first-pass")
    policy = default_policy_for("second-opinion-x", [])
    agent = create_agent(
        name="second-opinion-x",
        role="reviewer",
        goal="review",
        backstory="review",
        tools=[],
        llm="deepseek",
        blackboard=bb,
        policy=policy,
    )
    assert agent.blackboard.read("run_id") == "r1"
    assert agent.blackboard.read("run:1:verified") is None
