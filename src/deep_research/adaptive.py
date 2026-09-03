"""Adaptive compute allocation for research crews.

This module turns the generic ResourceBudget machinery into a small
adaptive scheduler:

- A research question is first classified by the Query Planner.
- Each perspective gets a ``ComputeAllocation`` (depth + tool budget)
  derived from question type, role, keyword breadth and perspective count.
- When the Reflection quality gate asks for more research, each card is
  scored by how weak it looks (too few findings, low confidence, missing
  sources, many gaps).  Weak cards receive a deeper budget; already-strong
  cards are either given a shallow budget or skipped entirely.

The module is intentionally pure/deterministic (no LLM calls) so the
policy is auditable and unit-testable.  The actual enforcement is done by
the existing ``AgentPolicy.ResourceBudget`` and ``Agent.max_tool_rounds``.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from deep_research.models.enums import Confidence
from deep_research.models.schemas import ResearchCard

# The Reflection quality gate considers a card "thin" below this many
# findings (same default as pipeline.MIN_FINDINGS per whole run is 3,
# but per-perspective a card with 2 solid findings is usually acceptable).
DEFAULT_MIN_CLAIMS = 2

# Base budget per depth.  max_llm_calls is intentionally left unset:
# cutting LLM calls mid-conversation can turn a recoverable research task
# into an empty reply, while tool-call caps only force the model to
# converge with the evidence it already has.
_BASE_TOOL_CALLS = {1: 10, 2: 16, 3: 24}
_BASE_TOOL_ROUNDS = {1: 10, 2: 14, 3: 18}

# Question complexity → base research depth (1=light, 2=normal, 3=deep).
_QTYPE_DEPTH = {
    "entity_fact": 1,
    "news_current": 2,
    "general": 2,
    "business_market": 2,
    "comparative": 3,
    "technical": 3,
    "academic": 3,
    "policy_legal": 3,
    "historical_archive": 3,
    "multi_hop_clue": 3,
}

# Roles that usually benefit from more tool calls.
_DEEP_ROLES = {
    "技术专家",
    "批判者",
    "对比者",
    "原文解读",
    "方法论",
    "领域对比",
}


@dataclass(frozen=True)
class ComputeAllocation:
    """How much tool budget one research attempt should receive."""

    depth: int = 2
    max_tool_calls: int | None = None
    max_tool_rounds: int | None = None
    max_llm_calls: int | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clamp_depth(value: float) -> int:
    """Clamp a possibly fractional depth into the 1..3 integer range."""
    return max(1, min(3, int(round(value))))


def base_depth_for_question_type(question_type: str) -> int:
    """Map a Query Planner question type to a base research depth."""
    return _QTYPE_DEPTH.get(str(question_type or "").strip().lower(), 2)


def _brief_role(brief: Any) -> str:
    if isinstance(brief, tuple) and len(brief) >= 2:
        b = brief[1]
    else:
        b = brief
    if isinstance(b, dict):
        return str(b.get("role", "") or "")
    return ""


def _brief_keywords(brief: Any) -> list[str]:
    if isinstance(brief, tuple) and len(brief) >= 2:
        b = brief[1]
    else:
        b = brief
    if isinstance(b, dict):
        kw = b.get("keywords", [])
        return [str(k) for k in kw] if isinstance(kw, list) else []
    return []


def perspective_depth(
    question_type: str,
    role: str = "",
    keywords: Iterable[str] | None = None,
    perspective_count: int = 4,
) -> int:
    """Compute one perspective's depth from deterministic signals."""
    kw = list(keywords or [])
    base = float(base_depth_for_question_type(question_type))

    # Roles that are paid to find what the others miss get a little more.
    if role in _DEEP_ROLES:
        base += 0.5

    # A broad keyword list means the angle is wider and needs more
    # exploration; an empty keyword list is usually a sign the orchestrator
    # gave a weak brief, so we do not burn extra budget on it.
    if len(kw) >= 5:
        base += 0.5
    elif len(kw) == 0:
        base -= 0.5

    # With many parallel perspectives, keep the per-perspective budget from
    # multiplying unboundedly (orchestrator can emit up to 6).
    if perspective_count >= 6:
        base -= 0.5
    elif perspective_count == 5:
        base -= 0.25

    return clamp_depth(base)


def build_compute_plan(
    question_type: str,
    briefs: list[Any],
    search_plan: dict[str, Any] | None = None,
) -> list[ComputeAllocation]:
    """Build one allocation per orchestrator perspective.

    ``briefs`` is the research crew's internal format:
    a list of ``(perspective_name, brief_dict)`` tuples, or a list of
    plain brief dicts for callers that only have the dicts.
    """
    n = len(briefs)
    if n == 0:
        return []

    sub_query_count = 0
    if search_plan:
        sp = search_plan.get("search_plan") or {}
        sub_queries = sp.get("sub_queries") or []
        if isinstance(sub_queries, list):
            sub_query_count = len(sub_queries)

    allocations: list[ComputeAllocation] = []
    for brief in briefs:
        name = ""
        if isinstance(brief, tuple) and len(brief) >= 2:
            name = str(brief[0])
        role = _brief_role(brief)
        kw = _brief_keywords(brief)
        depth = perspective_depth(question_type, role=role, keywords=kw, perspective_count=n)

        # A richer search plan can justify pushing a normal-depth card to
        # deep, but never below depth 1.
        if sub_query_count >= 6 and depth < 3:
            depth += 1
        depth = clamp_depth(depth)

        tool_calls = _BASE_TOOL_CALLS[depth]
        tool_rounds = _BASE_TOOL_ROUNDS[depth]
        reason = (
            f"qtype={question_type}; role={role or '-'}; "
            f"keywords={len(kw)}; perspectives={n}; depth={depth}"
        )
        allocations.append(ComputeAllocation(
            depth=depth,
            max_tool_calls=tool_calls,
            max_tool_rounds=tool_rounds,
            reason=reason,
        ))
    return allocations


def card_weakness_score(
    card: ResearchCard,
    *,
    min_claims: int = DEFAULT_MIN_CLAIMS,
) -> int:
    """Return a deterministic weakness score for one research card.

    Higher = more likely to benefit from an extra research round.
    """
    if card is None:
        return 10
    findings = card.key_findings or []
    n = len(findings)
    if n == 0:
        return 10

    score = 0

    # Quantity: below target is the strongest signal.
    if n < min_claims:
        score += 2
    elif n < min_claims + 2:
        score += 1

    # Confidence: many low-confidence claims still need evidence.
    low = sum(1 for c in findings if getattr(c, "confidence", None) == Confidence.LOW)
    low_ratio = low / n
    if low_ratio >= 0.5:
        score += 2
    elif low_ratio >= 0.25:
        score += 1

    # Sources: findings with no URL are weak.
    no_source = sum(1 for c in findings if not (c.sources or []))
    if no_source:
        score += 2 if no_source >= (n + 1) // 2 else 1

    # Gaps: a card that admits many holes deserves another pass.
    if len(card.gaps or []) >= 3:
        score += 1

    return min(score, 10)


def allocation_for_augment(
    card: ResearchCard,
    *,
    min_claims: int = DEFAULT_MIN_CLAIMS,
    augment_count: int = 0,
) -> ComputeAllocation:
    """Allocate a re-search budget for one card during an augment round."""
    weakness = card_weakness_score(card, min_claims=min_claims)

    # Empty/very weak cards get the deepest budget; strong cards get a
    # light pass so we still honour feedback without over-spending.
    if weakness >= 5:
        depth = 3
    elif weakness >= 2:
        depth = 2
    else:
        depth = 1

    # Later augment rounds may spend a little more (the question has already
    # failed the quality gate, so the marginal value of one more try is
    # higher than the first augment's).
    multiplier = 1.0 + 0.15 * max(0, augment_count)
    tool_calls = int(round(_BASE_TOOL_CALLS[depth] * multiplier))
    tool_rounds = int(round(_BASE_TOOL_ROUNDS[depth] * multiplier))

    reason = (
        f"weakness={weakness}; depth={depth}; augment_round={augment_count}; "
        f"findings={len(card.key_findings or [])}; low={weakness >= 2}"
    )
    return ComputeAllocation(
        depth=depth,
        max_tool_calls=tool_calls,
        max_tool_rounds=tool_rounds,
        reason=reason,
    )


def select_augment_targets(
    cards: list[ResearchCard],
    *,
    feedback: bool = False,
    min_claims: int = DEFAULT_MIN_CLAIMS,
    max_targets: int | None = None,
) -> list[ResearchCard]:
    """Choose which cards actually need another research round.

    - Without feedback (quantity-driven augment): only thin cards.
    - With feedback (quality-gate augment): weak cards first; if none are
      weak, still take the weakest half so a global quality failure never
      turns into a no-op.
    """
    if not feedback:
        return [c for c in cards if len(c.key_findings or []) < min_claims]

    scored = [(card_weakness_score(c, min_claims=min_claims), i, c) for i, c in enumerate(cards)]
    weak = [item for item in scored if item[0] >= 2]
    if weak:
        selected = weak
    else:
        # Keep deterministic order on ties (sort by score desc, then index).
        scored.sort(key=lambda item: (-item[0], item[1]))
        k = max(1, math.ceil(len(cards) / 2))
        if max_targets is not None:
            k = min(k, max_targets)
        selected = scored[:k]

    selected.sort(key=lambda item: item[1])
    return [item[2] for item in selected]


__all__ = [
    "ComputeAllocation",
    "DEFAULT_MIN_CLAIMS",
    "allocation_for_augment",
    "base_depth_for_question_type",
    "build_compute_plan",
    "card_weakness_score",
    "clamp_depth",
    "perspective_depth",
    "select_augment_targets",
]
