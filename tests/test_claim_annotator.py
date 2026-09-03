"""Tests for ClaimAnnotator Phase A helpers and document building."""

from deep_research.claim_annotator import (
    _build_claim_pool,
    _enrich_claim,
    _extract_annotation_scope,
    _find_span,
    ClaimAnnotator,
)
from deep_research.models.schemas import ClaimNode, ClaimSourceRef


def test_find_span_exact_substring():
    text = "答案是 Queen Arwa University 成立于 1999 年。"
    sub = "Queen Arwa University 成立于 1999 年"
    span = _find_span(text, sub)
    assert span == {"start": text.find(sub), "end": text.find(sub) + len(sub)}


def test_find_span_missing_returns_none():
    assert _find_span("hello world", "not there") is None


def test_extract_annotation_scope_short_text_unchanged():
    text = "短报告"
    assert _extract_annotation_scope(text) == text


def test_extract_annotation_scope_prefers_answer_section():
    long_prefix = "前言\n" * 500
    report = long_prefix + "## 1. 直接回答\nQueen Arwa University 成立于 1999 年。\n## 2. 关键证据\n来源可靠。"
    scope = _extract_annotation_scope(report, max_chars=200)
    assert "直接回答" in scope
    assert "Queen Arwa University" in scope


def test_build_claim_pool_inherits_verification():
    cards = [
        {
            "perspective": "technical",
            "key_findings": [
                {
                    "text": "Queen Arwa University 成立于 1999 年",
                    "confidence": "high",
                    "sources": ["https://example.org/a"],
                }
            ],
        }
    ]
    verified = [
        {
            "perspective": "technical",
            "entries": [
                {
                    "claim_index": 0,
                    "status": "verified",
                    "reasoning": "多源确认",
                    "checked_sources": ["https://example.org/b"],
                }
            ],
        }
    ]
    pool = _build_claim_pool(cards, verified)
    assert pool[0]["status"] == "verified"
    assert pool[0]["checked_sources"] == ["https://example.org/b"]


def test_enrich_claim_fills_status_confidence_evidence():
    pool = [
        {
            "card_index": 0,
            "perspective": "technical",
            "claim_index": 0,
            "text": "Queen Arwa University 成立于 1999 年",
            "confidence": "high",
            "sources": ["https://example.org/a"],
            "status": "verified",
            "reasoning": "多源确认",
            "checked_sources": ["https://example.org/b"],
        }
    ]
    claim = ClaimNode(claim_id="c0", text="Queen Arwa University 成立于 1999 年")
    _enrich_claim(claim, pool, ClaimSourceRef(card_index=0, claim_index=0))
    assert claim.status == "verified"
    assert claim.confidence == 80
    assert len(claim.evidence_links) == 2


def test_build_document_keeps_original_text_and_span():
    report = "Queen Arwa University 成立于 1999 年。"
    data = {
        "claims": [
            {
                "text": "Queen Arwa University 成立于 1999 年",
                "claim_type": "direct_answer",
                "parent_claim_index": None,
                "source_claim_ref": {"card_index": 0, "claim_index": 0},
            }
        ],
        "overall_confidence": 82,
    }
    pool = [
        {
            "card_index": 0,
            "perspective": "technical",
            "claim_index": 0,
            "text": "Queen Arwa University 成立于 1999 年",
            "confidence": "high",
            "sources": ["https://example.org/a"],
            "status": "verified",
            "reasoning": "多源确认",
            "checked_sources": [],
        }
    ]
    doc = ClaimAnnotator()._build_document("run-1", report, data, pool)
    assert doc.original_text == report
    assert doc.overall_confidence == 82
    assert len(doc.claims) == 1
    assert doc.claims[0].span == {"start": 0, "end": len(report) - 1}
