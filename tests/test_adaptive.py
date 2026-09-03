"""Tests for adaptive compute allocation (F34)."""

from deep_research.adaptive import (
    ComputeAllocation,
    DEFAULT_MIN_CLAIMS,
    allocation_for_augment,
    base_depth_for_question_type,
    build_compute_plan,
    card_weakness_score,
    clamp_depth,
    perspective_depth,
    select_augment_targets,
)
from deep_research.models.enums import Confidence
from deep_research.models.schemas import Claim, ResearchCard


def _card(*, findings: int = 2, low: int = 0, unsourced: int = 0, gaps: int = 0) -> ResearchCard:
    claims = []
    for i in range(findings):
        confidence = Confidence.LOW if i < low else Confidence.HIGH
        sources = [] if i < unsourced else [f"https://example.com/{i}"]
        claims.append(Claim(
            text=f"claim {i}",
            confidence=confidence,
            sources=sources,
        ))
    return ResearchCard(
        perspective="测试视角",
        role="技术专家",
        research_question="测试问题",
        key_findings=claims,
        gaps=[f"gap {i}" for i in range(gaps)],
    )


def test_clamp_depth():
    assert clamp_depth(0) == 1
    assert clamp_depth(1.2) == 1
    assert clamp_depth(2.4) == 2
    assert clamp_depth(4) == 3


def test_question_type_depth_mapping():
    assert base_depth_for_question_type("entity_fact") == 1
    assert base_depth_for_question_type("technical") == 3
    assert base_depth_for_question_type("multi_hop_clue") == 3
    assert base_depth_for_question_type("unknown") == 2


def test_perspective_depth_adjusts_for_role_and_keywords():
    # Deep role + broad keywords gets at least a 3.
    assert perspective_depth("technical", role="技术专家", keywords=["a", "b", "c", "d", "e"]) == 3
    # Unknown/weak brief with no keywords drops to 1.
    assert perspective_depth("entity_fact", role="", keywords=[]) == 1
    # Many perspectives pull a normal question down but not below 1.
    assert 1 <= perspective_depth("general", role="", keywords=[], perspective_count=6) <= 2


def test_build_compute_plan_returns_one_allocation_per_brief():
    briefs = [
        ("视角A", {"role": "技术专家", "keywords": ["a", "b", "c", "d", "e"]}),
        ("视角B", {"role": "批判者", "keywords": ["x", "y"]}),
        ("视角C", {"role": "未来趋势", "keywords": ["m"]}),
    ]
    plan = build_compute_plan("technical", briefs, {"search_plan": {"sub_queries": []}})
    assert len(plan) == 3
    for alloc in plan:
        assert isinstance(alloc, ComputeAllocation)
        assert 1 <= alloc.depth <= 3
        assert alloc.max_tool_calls is not None
        assert alloc.max_tool_rounds is not None


def test_build_compute_plan_handles_plain_dict_briefs():
    plan = build_compute_plan("general", [{"role": "行业分析师", "keywords": ["a"]}])
    assert len(plan) == 1
    assert plan[0].depth >= 1


def test_card_weakness_score_empty_is_max():
    card = ResearchCard(perspective="p", role="", research_question="q", key_findings=[])
    assert card_weakness_score(card) == 10


def test_card_weakness_score_rich_card_is_low():
    card = _card(findings=5, low=0, unsourced=0, gaps=1)
    assert card_weakness_score(card) <= 1


def test_card_weakness_score_poor_card_is_high():
    card = _card(findings=1, low=1, unsourced=1, gaps=3)
    assert card_weakness_score(card) >= 5


def test_allocation_for_augment_scales_with_weakness():
    poor = _card(findings=1, low=1, unsourced=1, gaps=3)
    rich = _card(findings=5, low=0, unsourced=0, gaps=1)

    poor_alloc = allocation_for_augment(poor)
    rich_alloc = allocation_for_augment(rich)

    assert poor_alloc.depth >= rich_alloc.depth
    assert poor_alloc.max_tool_calls >= rich_alloc.max_tool_calls
    # Later augment rounds get a slightly larger budget.
    later = allocation_for_augment(poor, augment_count=2)
    assert later.max_tool_calls >= poor_alloc.max_tool_calls


def test_select_augment_targets_without_feedback_only_thin_cards():
    rich = _card(findings=4)
    thin = _card(findings=0)
    targets = select_augment_targets([rich, thin], feedback=False, min_claims=2)
    assert targets == [thin]


def test_select_augment_targets_with_feedback_skips_strong_cards():
    rich = _card(findings=5, low=0, unsourced=0, gaps=0)
    poor = _card(findings=1, low=1, unsourced=1, gaps=2)
    targets = select_augment_targets([rich, poor], feedback=True, min_claims=2)
    assert poor in targets
    assert rich not in targets


def test_select_augment_targets_with_feedback_never_empty_when_all_strong():
    cards = [_card(findings=4) for _ in range(4)]
    targets = select_augment_targets(cards, feedback=True, min_claims=2)
    assert len(targets) >= 1
    assert len(targets) <= 2  # weakest half
