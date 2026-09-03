"""Agent independence governance — declarative AgentPolicy models.

Phase 1: define the policy objects and attach a default policy to every
agent at creation time.  Enforcement (ScopedBlackboard, tool permission
proxy, resource budgets, verification standards) is added in later phases.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

WILDCARD = "*"


class ContextPolicy(BaseModel):
    """Which shared state an agent may read/write and whether it may see
    other agents' intermediate outputs."""

    read_blackboard_keys: list[str] = Field(
        default_factory=lambda: [WILDCARD],
        description="Blackboard key patterns this agent may read",
    )
    write_blackboard_keys: list[str] = Field(
        default_factory=lambda: [WILDCARD],
        description="Blackboard key patterns this agent may write",
    )
    can_read_other_agents: bool = Field(
        default=True,
        description="Whether this agent may see other agents' raw transcripts/conclusions",
    )


class ToolPolicy(BaseModel):
    """Per-agent tool availability and quotas."""

    allowed_tools: list[str] | None = Field(
        default=None,
        description="Explicit allowlist; None means all tools assigned to the agent are allowed",
    )
    denied_tools: list[str] = Field(
        default_factory=list,
        description="Tools explicitly forbidden for this agent",
    )
    per_tool_max_calls: dict[str, int] = Field(
        default_factory=dict,
        description="Optional per-tool call budget, e.g. {'firecrawl_search': 10}",
    )


class DataPolicy(BaseModel):
    """Which database tables / file prefixes an agent may access."""

    allowed_db_tables: list[str] = Field(
        default_factory=lambda: [WILDCARD],
        description="DB table patterns this agent may access",
    )
    allowed_file_prefixes: list[str] = Field(
        default_factory=lambda: [WILDCARD],
        description="File path prefix patterns this agent may access",
    )


class ResourceBudget(BaseModel):
    """Per-agent execution budget (enforced in later phases)."""

    max_tool_calls: int | None = Field(default=None, description="Max tool calls")
    max_llm_calls: int | None = Field(default=None, description="Max LLM calls")
    max_tokens: int | None = Field(default=None, description="Max total tokens")
    max_cost_usd: float | None = Field(default=None, description="Max cost in USD")


class VerificationStandard(BaseModel):
    """Per-agent verification/rubric standard.

    Phase 4 renders this standard into the agent system prompt so scoring
    rules come from Policy instead of being hardcoded in each task prompt.
    """

    name: str = Field(default="default", description="Standard name")
    status_allowed: list[str] = Field(
        default_factory=list,
        description="Statuses this agent is allowed to emit",
    )
    confidence_rubric: dict[str, int] = Field(
        default_factory=dict,
        description="Rubric label -> score, e.g. {'multi-source official': 90}",
    )
    min_confidence: int = Field(default=0, ge=0, le=100)
    independent_review_required: bool = Field(
        default=False,
        description="Whether this agent's output must be independently reviewed",
    )
    can_see_first_pass: bool = Field(
        default=True,
        description="Whether an independent reviewer may see the first-pass result",
    )

    def render_prompt(self) -> str:
        """Render this standard as a system-prompt block."""
        if (
            self.name == "default"
            and not self.status_allowed
            and not self.confidence_rubric
            and not self.min_confidence
            and not self.independent_review_required
            and self.can_see_first_pass
        ):
            return ""

        lines: list[str] = []
        if self.name != "default":
            lines.append(f"【验证标准 {self.name}】")
        if self.status_allowed:
            lines.append(f"允许的状态: {', '.join(self.status_allowed)}")
        if self.confidence_rubric:
            lines.append("置信度评分参考:")
            for label, score in self.confidence_rubric.items():
                lines.append(f"- {label}: {score}")
        if self.min_confidence:
            lines.append(f"最低置信度: {self.min_confidence}")
        if self.independent_review_required:
            lines.append("本角色的输出要求独立复核。")
        if not self.can_see_first_pass:
            lines.append("本角色不得查看第一轮核查结论。")
        return "\n".join(lines)


class AgentPolicy(BaseModel):
    """Complete policy for one agent (or agent family)."""

    agent_name: str = Field(default=WILDCARD, description="Agent name or pattern")
    context: ContextPolicy = Field(default_factory=ContextPolicy)
    tools: ToolPolicy = Field(default_factory=ToolPolicy)
    data: DataPolicy = Field(default_factory=DataPolicy)
    budget: ResourceBudget = Field(default_factory=ResourceBudget)
    verification: VerificationStandard = Field(default_factory=VerificationStandard)


def _default_policy_for(agent_name: str, tool_names: list[str]) -> AgentPolicy:
    """Create a permissive default policy that preserves current behavior.

    Phase 1 intentionally does not restrict anything.  It only attaches
    metadata and marks special roles for later enforcement.
    """
    name = agent_name.lower()
    policy = AgentPolicy(agent_name=agent_name)
    policy.tools.allowed_tools = None
    policy.tools.denied_tools = []
    policy.tools.per_tool_max_calls = {}

    # Role-specific metadata (not enforced yet).
    if name.startswith("second-opinion") or name == "contradiction-adjudicator":
        policy.context.can_read_other_agents = False
        policy.context.read_blackboard_keys = [
            "run_id",
            "trace_id",
            "event_bus",
            "search_plan",
            "usage:*",
        ]
        policy.context.write_blackboard_keys = ["usage:*"]
        policy.verification.name = "independent_review_v1"
        policy.verification.status_allowed = ["verified", "suspect", "false", "disputed", "unverifiable"]
        policy.verification.confidence_rubric = {
            "多源官方/一手来源": 90,
            "单源权威来源": 75,
            "单源普通/二手来源": 50,
            "仅反证/无法核实": 20,
        }
        policy.verification.independent_review_required = True
        policy.verification.can_see_first_pass = False
    elif name.startswith("verifier") or name.startswith("refuter"):
        policy.verification.name = "verifier_rubric_v1"
        policy.verification.status_allowed = ["verified", "suspect", "false", "disputed"]
        policy.verification.confidence_rubric = {
            "多源官方/一手来源": 90,
            "单源权威来源": 75,
            "单源普通/二手来源": 50,
            "仅反证/无法核实": 20,
        }
        policy.verification.independent_review_required = True
    elif name.startswith("researcher"):
        policy.verification.name = "researcher_confidence_v1"
        policy.verification.status_allowed = ["high", "medium", "low"]
        policy.verification.confidence_rubric = {
            "high": 80,
            "medium": 60,
            "low": 40,
        }
    elif name == "reflector":
        policy.verification.name = "reflector_rubric_v1"
        policy.verification.status_allowed = ["acceptable", "unacceptable"]
    elif name == "scorer":
        policy.verification.name = "scorer_rubric_v1"
        policy.verification.status_allowed = ["A", "B", "C", "D"]
        policy.verification.confidence_rubric = {
            "A (13-15)": 90,
            "B (10-12)": 70,
            "C (7-9)": 50,
            "D (<7)": 30,
        }
    elif name == "editor":
        policy.verification.name = "editor_style_v1"

    # Tool name list is kept for observability.
    if tool_names:
        policy.tools.allowed_tools = list(tool_names)

    return policy


def default_policy_for(agent_name: str, tool_names: list[str] | None = None) -> AgentPolicy:
    """Public helper used by create_agent to attach a default policy."""
    return _default_policy_for(agent_name, list(tool_names or []))


__all__ = [
    "AgentPolicy",
    "ContextPolicy",
    "DataPolicy",
    "ResourceBudget",
    "ToolPolicy",
    "VerificationStandard",
    "default_policy_for",
]
