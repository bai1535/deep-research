"""Tests for Verifier status normalization and Researcher JSON constraints."""

from deep_research.crews.verification_crew import (
    _merge_entries,
    _normalise_entries,
    _normalise_fact_status,
    _normalise_verification_status,
)
from deep_research.crews.research_crew import RESEARCHER_TASK
from deep_research.models.enums import VerificationStatus
from deep_research.models.schemas import VerificationEntry


def test_normalise_common_typos():
    assert _normalise_verification_status("verfied") == "verified"
    assert _normalise_verification_status("verify") == "verified"
    assert _normalise_verification_status("partially verified") == "suspect"
    assert _normalise_verification_status("false") == "false"
    assert _normalise_verification_status("disputed") == "disputed"


def test_normalise_entries_updates_status():
    entries = [
        {"claim_index": 0, "status": "verfied", "reasoning": "x"},
        {"claim_index": 1, "status": "partially verified", "reasoning": "y"},
    ]
    out = _normalise_entries(entries)
    assert out[0]["status"] == "verified"
    assert out[1]["status"] == "suspect"


def test_normalise_fact_status_allows_unverifiable():
    assert _normalise_fact_status("unverifiable") == "unverifiable"
    assert _normalise_fact_status("unable to verify") == "unverifiable"
    assert _normalise_fact_status("verified") == "verified"


def test_merge_entries_second_opinion_can_upgrade_suspect():
    first = VerificationEntry(
        claim_index=0,
        claim_text="X",
        status=VerificationStatus.SUSPECT,
        reasoning="表述口径有提醒",
        checked_sources=[],
    )
    second = VerificationEntry(
        claim_index=0,
        claim_text="X",
        status=VerificationStatus.VERIFIED,
        fact_status="verified",
        confidence=85,
        reasoning="事实成立",
        checked_sources=["https://example.org"],
    )
    merged = _merge_entries([first], [second])
    assert merged[0].status == VerificationStatus.VERIFIED
    assert merged[0].confidence == 85
    assert "独立复核" in merged[0].reasoning


def test_merge_entries_second_opinion_can_downgrade_verified():
    first = VerificationEntry(
        claim_index=0,
        claim_text="X",
        status=VerificationStatus.VERIFIED,
        reasoning="first pass",
        checked_sources=[],
    )
    second = VerificationEntry(
        claim_index=0,
        claim_text="X",
        status=VerificationStatus.SUSPECT,
        fact_status="suspect",
        confidence=45,
        reasoning="独立发现数据口径问题",
        checked_sources=[],
    )
    merged = _merge_entries([first], [second])
    assert merged[0].status == VerificationStatus.SUSPECT


def test_researcher_task_has_strong_json_instruction():
    assert "禁止输出 Markdown" in RESEARCHER_TASK
    assert "字段只能包含 perspective/research_question/key_findings/gaps/raw_transcript" in RESEARCHER_TASK
