"""Tests for the async PostgreSQL repository layer."""

import uuid

import pytest

from deep_research.db import init_db, Repository
from deep_research.models import (
    ResearchRun,
    ResearchCard,
    Perspective,
    Claim,
    Confidence,
    VerifiedCard,
    VerificationEntry,
    VerificationStatus,
    ScoreResult,
    InsightResult,
    RunStatus,
)


def _new_run_id() -> str:
    return f"test-{uuid.uuid4().hex}"


async def _cleanup_run(pool, rid: str) -> None:
    await pool.execute("DELETE FROM insights WHERE run_id=$1", rid)
    await pool.execute("DELETE FROM scores WHERE run_id=$1", rid)
    await pool.execute("DELETE FROM verified_cards WHERE run_id=$1", rid)
    await pool.execute("DELETE FROM claims WHERE run_id=$1", rid)
    await pool.execute("DELETE FROM research_cards WHERE run_id=$1", rid)
    await pool.execute("DELETE FROM run_checkpoints WHERE run_id=$1", rid)
    await pool.execute("DELETE FROM research_runs WHERE id=$1", rid)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

async def test_init_db_creates_tables():
    """init_db should create all expected tables."""
    pool = await init_db()
    rows = await pool.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    )
    table_names = {row["tablename"] for row in rows}
    assert {
        "research_runs",
        "research_cards",
        "verified_cards",
        "claims",
        "scores",
        "insights",
        "run_checkpoints",
    }.issubset(table_names)


async def test_init_db_idempotent():
    """Calling init_db twice should return the same shared pool."""
    pool1 = await init_db()
    pool2 = await init_db()
    assert pool1 is pool2


# ---------------------------------------------------------------------------
# ResearchRun CRUD
# ---------------------------------------------------------------------------

async def test_create_and_get_run():
    """Create a ResearchRun and retrieve it by ID."""
    rid = _new_run_id()
    pool = await init_db()
    repo = Repository()
    try:
        run = ResearchRun(id=rid, question="What is CrewAI?")
        assert await repo.create_run(run) == rid

        retrieved = await repo.get_run(rid)
        assert retrieved is not None
        assert retrieved["question"] == "What is CrewAI?"
        assert retrieved["status"] == "pending"
    finally:
        await _cleanup_run(pool, rid)


async def test_get_nonexistent_run():
    """get_run for an unknown ID returns None."""
    rid = _new_run_id()
    pool = await init_db()
    repo = Repository()
    try:
        assert await repo.get_run(rid) is None
    finally:
        await _cleanup_run(pool, rid)


async def test_update_run_status():
    """update_run_status should persist the new status."""
    rid = _new_run_id()
    pool = await init_db()
    repo = Repository()
    try:
        run = ResearchRun(id=rid, question="Test")
        await repo.create_run(run)

        await repo.update_run_status(rid, RunStatus.RESEARCHING)
        assert (await repo.get_run(rid))["status"] == RunStatus.RESEARCHING.value
    finally:
        await _cleanup_run(pool, rid)


async def test_update_run_status_to_completed():
    """Setting status to COMPLETED should also set completed_at."""
    rid = _new_run_id()
    pool = await init_db()
    repo = Repository()
    try:
        run = ResearchRun(id=rid, question="Test")
        await repo.create_run(run)

        await repo.update_run_status(rid, RunStatus.COMPLETED)
        retrieved = await repo.get_run(rid)
        assert retrieved["status"] == "completed"
        assert retrieved["completed_at"] is not None
    finally:
        await _cleanup_run(pool, rid)


# ---------------------------------------------------------------------------
# ResearchCard persistence
# ---------------------------------------------------------------------------

async def test_save_and_retrieve_research_card():
    """Save a ResearchCard and retrieve it via get_research_cards."""
    rid = _new_run_id()
    pool = await init_db()
    repo = Repository()
    try:
        run = ResearchRun(id=rid, question="Test")
        await repo.create_run(run)

        card = ResearchCard(
            perspective=Perspective.TECHNICAL,
            research_question="How does X work?",
            key_findings=[
                Claim(
                    text="X works via Y",
                    confidence=Confidence.HIGH,
                    sources=["http://example.com"],
                    counterpoints=[],
                ),
            ],
        )
        card_id = await repo.save_research_card(rid, card)
        assert card_id is not None

        cards = await repo.get_research_cards(rid)
        assert len(cards) == 1
        assert cards[0].perspective == Perspective.TECHNICAL
        assert cards[0].research_question == "How does X work?"
        assert len(cards[0].key_findings) == 1
        assert cards[0].key_findings[0].text == "X works via Y"
        assert cards[0].key_findings[0].confidence == Confidence.HIGH
    finally:
        await _cleanup_run(pool, rid)


async def test_save_multiple_research_cards():
    """Multiple cards for the same run should all be retrievable."""
    rid = _new_run_id()
    pool = await init_db()
    repo = Repository()
    try:
        run = ResearchRun(id=rid, question="Multi-card test")
        await repo.create_run(run)

        await repo.save_research_card(
            rid,
            ResearchCard(
                perspective=Perspective.TECHNICAL,
                research_question="Q1",
                key_findings=[Claim(text="C1", confidence=Confidence.MEDIUM)],
            ),
        )
        await repo.save_research_card(
            rid,
            ResearchCard(
                perspective=Perspective.INDUSTRY,
                research_question="Q2",
                key_findings=[Claim(text="C2", confidence=Confidence.LOW)],
            ),
        )

        cards = await repo.get_research_cards(rid)
        assert len(cards) == 2
    finally:
        await _cleanup_run(pool, rid)


# ---------------------------------------------------------------------------
# VerifiedCard persistence
# ---------------------------------------------------------------------------

async def test_save_and_retrieve_verified_card():
    """Save a VerifiedCard and retrieve it via get_verified_cards."""
    rid = _new_run_id()
    pool = await init_db()
    repo = Repository()
    try:
        run = ResearchRun(id=rid, question="Test")
        await repo.create_run(run)

        research_card = ResearchCard(
            perspective=Perspective.TECHNICAL,
            research_question="How does X work?",
            key_findings=[
                Claim(
                    text="X works via Y",
                    confidence=Confidence.HIGH,
                    sources=["http://example.com"],
                ),
            ],
        )
        await repo.save_research_card(rid, research_card)

        verified_card = VerifiedCard(
            perspective=Perspective.TECHNICAL,
            verification_round=1,
            entries=[
                VerificationEntry(
                    claim_index=0,
                    claim_text="X works via Y",
                    status=VerificationStatus.VERIFIED,
                    reasoning="Source confirmed",
                    checked_sources=["http://example.com"],
                ),
            ],
        )
        await repo.save_verified_card(rid, verified_card)

        cards = await repo.get_verified_cards(rid)
        assert len(cards) == 1
        assert cards[0].perspective == Perspective.TECHNICAL
        assert cards[0].verification_round == 1
        assert len(cards[0].entries) == 1
        assert cards[0].entries[0].status == VerificationStatus.VERIFIED
        assert cards[0].entries[0].claim_index == 0
    finally:
        await _cleanup_run(pool, rid)


# ---------------------------------------------------------------------------
# Score and Insights persistence
# ---------------------------------------------------------------------------

async def test_save_and_retrieve_score():
    """save_score should persist a ScoreResult and the JSON survives roundtrip."""
    rid = _new_run_id()
    pool = await init_db()
    repo = Repository()
    try:
        run = ResearchRun(id=rid, question="Score test")
        await repo.create_run(run)

        score = ScoreResult(
            overall_score=85,
            claim_scores=[
                {"claim_index": 0, "source_reliability": 90, "grade": "A"},
            ],
            summary="Solid research overall.",
        )
        await repo.save_score(rid, score)

        row = await pool.fetchrow(
            "SELECT score_json FROM scores WHERE run_id = $1", rid
        )
        assert row is not None

        from deep_research.models import ScoreResult as SR

        restored = SR.model_validate_json(row["score_json"])
        assert restored.overall_score == 85
        assert restored.summary == "Solid research overall."
        assert len(restored.claim_scores) == 1
    finally:
        await _cleanup_run(pool, rid)


async def test_save_and_retrieve_insights():
    """save_insights should persist an InsightResult."""
    rid = _new_run_id()
    pool = await init_db()
    repo = Repository()
    try:
        run = ResearchRun(id=rid, question="Insights test")
        await repo.create_run(run)

        insights = InsightResult(
            consensus_signals=["X is true"],
            contradictions=["A vs B"],
            blind_spots=["Nobody covered Z"],
            time_sensitive_items=["Q2 data is stale"],
        )
        await repo.save_insights(rid, insights)

        row = await pool.fetchrow(
            "SELECT insights_json FROM insights WHERE run_id = $1", rid
        )
        assert row is not None

        from deep_research.models import InsightResult as IR

        restored = IR.model_validate_json(row["insights_json"])
        assert restored.consensus_signals == ["X is true"]
        assert restored.blind_spots == ["Nobody covered Z"]
    finally:
        await _cleanup_run(pool, rid)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

async def test_save_research_card_without_run_fails():
    """Foreign key should prevent inserting a card for a non-existent run."""
    rid = _new_run_id()
    pool = await init_db()
    repo = Repository()
    try:
        card = ResearchCard(
            perspective=Perspective.CRITICAL,
            research_question="Q?",
            key_findings=[Claim(text="C", confidence=Confidence.LOW)],
        )
        with pytest.raises(Exception):
            await repo.save_research_card(rid, card)
    finally:
        await _cleanup_run(pool, rid)
