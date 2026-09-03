"""Tests for the data model layer — enums and Pydantic schemas."""

import json
import pytest
from deep_research.models import (
    Perspective,
    Confidence,
    VerificationStatus,
    RunStatus,
    Claim,
    ResearchCard,
    VerifiedCard,
    ScoreResult,
    InsightResult,
    ResearchRun,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

def test_perspective_values():
    assert Perspective.TECHNICAL == "technical"
    assert Perspective.INDUSTRY == "industry"
    assert Perspective.CRITICAL == "critical"
    assert Perspective.FUTURE == "future"


def test_confidence_values():
    assert Confidence.HIGH == "high"
    assert Confidence.MEDIUM == "medium"
    assert Confidence.LOW == "low"


def test_verification_status_values():
    assert VerificationStatus.VERIFIED == "verified"
    assert VerificationStatus.SUSPECT == "suspect"
    assert VerificationStatus.FALSE == "false"
    assert VerificationStatus.DISPUTED == "disputed"


def test_run_status_values():
    assert RunStatus.PENDING == "pending"
    assert RunStatus.RESEARCHING == "researching"
    assert RunStatus.VERIFYING == "verifying"
    assert RunStatus.SYNTHESIZING == "synthesizing"
    assert RunStatus.COMPLETED == "completed"
    assert RunStatus.FAILED == "failed"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

def test_claim_creation():
    c = Claim(
        text="DeepSeek V3 is cost-effective",
        confidence=Confidence.HIGH,
        sources=["https://example.com"],
        counterpoints=["Some say otherwise"],
    )
    assert c.confidence == Confidence.HIGH
    assert len(c.sources) == 1


def test_claim_defaults():
    """Claim sources and counterpoints default to empty lists."""
    c = Claim(text="test", confidence=Confidence.LOW)
    assert c.sources == []
    assert c.counterpoints == []


def test_claim_serialization():
    c = Claim(text="test", confidence=Confidence.MEDIUM, sources=["https://a.com"])
    d = c.model_dump()
    assert d["text"] == "test"
    assert d["confidence"] == "medium"
    assert d["sources"] == ["https://a.com"]


def test_research_card_serialization():
    card = ResearchCard(
        perspective=Perspective.TECHNICAL,
        research_question="How does CrewAI handle parallel tasks?",
        key_findings=[
            Claim(text="CrewAI supports @task decorator for async", confidence=Confidence.HIGH)
        ],
        gaps=["Did not explore error handling in parallel mode"],
    )
    d = card.model_dump()
    assert d["perspective"] == "technical"
    assert len(d["key_findings"]) == 1


def test_research_card_defaults():
    """Gaps defaults to empty list, raw_transcript defaults to empty string."""
    card = ResearchCard(
        perspective=Perspective.INDUSTRY,
        research_question="Q?",
        key_findings=[],
    )
    assert card.gaps == []
    assert card.raw_transcript == ""


def test_verified_card_rounds():
    from deep_research.models import VerificationEntry, RefutationEntry

    card = VerifiedCard(
        perspective=Perspective.TECHNICAL,
        verification_round=2,
        entries=[
            VerificationEntry(
                claim_index=0,
                claim_text="X is true",
                status="verified",
                reasoning="Source confirms",
            )
        ],
        refutations=[
            RefutationEntry(
                claim_index=0,
                claim_text="X is true",
                challenge="But what about Y?",
                severity="moderate",
            )
        ],
        resolved=False,
    )
    assert card.verification_round == 2
    assert not card.resolved


def test_verified_card_defaults():
    """VerifiedCard has sensible defaults."""
    card = VerifiedCard(perspective=Perspective.CRITICAL)
    assert card.verification_round == 1
    assert card.entries == []
    assert card.refutations == []
    assert card.resolved is False
    assert card.summary == ""
    assert card.original_card_id == ""


def test_score_result_validation():
    """ScoreResult enforces 0-100 range on overall_score."""
    s = ScoreResult(overall_score=85)
    assert s.overall_score == 85

    # Bound checks
    ScoreResult(overall_score=0)
    ScoreResult(overall_score=100)

    with pytest.raises(Exception):
        ScoreResult(overall_score=-1)

    with pytest.raises(Exception):
        ScoreResult(overall_score=101)


def test_insight_result_defaults():
    """InsightResult fields default to empty lists."""
    ir = InsightResult()
    assert ir.consensus_signals == []
    assert ir.contradictions == []
    assert ir.blind_spots == []
    assert ir.time_sensitive_items == []


def test_research_run_lifecycle():
    run = ResearchRun(question="Test question")
    assert run.status.value == "pending"
    run.status = RunStatus.COMPLETED
    assert run.status == RunStatus.COMPLETED


def test_research_run_defaults():
    """ResearchRun auto-generates id and created_at, starts with empty lists."""
    run = ResearchRun(question="Q?")
    assert run.id  # auto-generated timestamp-based id
    assert run.created_at  # ISO format timestamp
    assert run.status == RunStatus.PENDING
    assert run.research_cards == []
    assert run.verified_cards == []
    assert run.score is None
    assert run.insights is None
    assert run.completed_at is None


def test_research_run_roundtrip():
    """ResearchRun can be serialized to JSON and back."""
    run = ResearchRun(question="Test roundtrip")
    run.status = RunStatus.COMPLETED
    run.completed_at = "2026-01-01T00:00:00"

    d = run.model_dump()
    j = json.dumps(d)
    reloaded = json.loads(j)
    assert reloaded["question"] == "Test roundtrip"
    assert reloaded["status"] == "completed"
