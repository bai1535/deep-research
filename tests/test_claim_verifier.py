"""Tests for AtomicClaimVerifier Phase B helpers."""

from deep_research.claim_verifier import (
    _apply_verification,
    _needs_verification,
    _normalize_atomic_result,
    _normalize_confidence,
    _normalize_status,
)


def test_needs_verification_only_for_unverified():
    assert _needs_verification({"status": "unverifiable"})
    assert _needs_verification({"status": ""})
    assert not _needs_verification({"status": "verified"})
    assert not _needs_verification({"status": "suspect"})
    assert not _needs_verification({"status": "disputed"})
    assert not _needs_verification({"status": "false"})


def test_normalize_status_maps_synonyms():
    assert _normalize_status("verified") == "verified"
    assert _normalize_status("confirmed") == "verified"
    assert _normalize_status("partially verified") == "suspect"
    assert _normalize_status("contradicted") == "disputed"
    assert _normalize_status("refuted") == "false"
    assert _normalize_status("unable to verify") == "unverifiable"
    assert _normalize_status("garbage") == ""


def test_normalize_atomic_result_builds_evidence():
    raw = {
        "status": "verified",
        "confidence": 85,
        "reasoning": "官方页面确认",
        "evidence": [
            {
                "url": "https://example.org",
                "snippet": "Founded in 1898",
                "support": "support",
                "source_reliability": 5,
                "tool": "web_fetch",
            }
        ],
    }
    out = _normalize_atomic_result(raw)
    assert out["status"] == "verified"
    assert out["confidence"] == 85
    assert len(out["evidence"]) == 1
    assert out["evidence"][0]["url"] == "https://example.org"
    assert out["evidence"][0]["support"] == "support"


def test_normalize_atomic_result_filters_missing_url():
    raw = {
        "status": "suspect",
        "confidence": 40,
        "reasoning": "",
        "evidence": [{"snippet": "no url"}],
    }
    out = _normalize_atomic_result(raw)
    assert out["evidence"] == []


def test_normalize_confidence_handles_decimal_and_percent():
    assert _normalize_confidence(0.9) == 90
    assert _normalize_confidence("85%") == 85
    assert _normalize_confidence(50) == 50
    assert _normalize_confidence(0) == 0
    assert _normalize_confidence(None) == 0
    assert _normalize_confidence("high") == 0


def test_apply_verification_updates_claim():
    claim = {
        "claim_id": "c0",
        "status": "unverifiable",
        "confidence": 0,
        "reasoning": "",
        "evidence_links": [],
        "event_ids": ["old"],
    }
    result = {
        "status": "verified",
        "confidence": 90,
        "reasoning": "ok",
        "evidence": [{"url": "https://example.org"}],
    }
    _apply_verification(claim, result, ["evt-1", "evt-2"])
    assert claim["status"] == "verified"
    assert claim["confidence"] == 90
    assert claim["reasoning"] == "ok"
    assert claim["evidence_links"] == [{"url": "https://example.org"}]
    assert set(claim["event_ids"]) == {"old", "evt-1", "evt-2"}
