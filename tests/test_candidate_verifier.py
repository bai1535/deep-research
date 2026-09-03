"""Tests for candidate verification (offline: gating/formatting)."""

from deep_research.candidate_verifier import (
    SUITABLE_TYPES,
    _is_suitable,
    format_candidate_verification,
)


def test_suitable_types_are_discrete_answer_types():
    assert "entity_fact" in SUITABLE_TYPES
    assert "multi_hop_clue" in SUITABLE_TYPES
    assert "historical_archive" in SUITABLE_TYPES


def test_open_ended_types_are_not_suitable():
    assert not _is_suitable("technical")
    assert not _is_suitable("academic")
    assert not _is_suitable("news_current")
    assert not _is_suitable("general")


def test_format_result_contains_final_candidate():
    result = {
        "final_candidate": "Queen Arwa University",
        "confidence": 72,
        "reasoning": "匹配线索最多",
        "candidates": [
            {
                "name": "Queen Arwa University",
                "score": 80,
                "matched_clues": ["A", "B", "C", "D", "E"],
                "unmatched_clues": [],
                "evidence_urls": ["https://qau.edu.ye"],
                "verdict": "candidate",
            }
        ],
    }
    text = format_candidate_verification(result)
    assert "Queen Arwa University" in text
    assert "72" in text
    assert "candidate" in text


def test_format_none_returns_empty():
    assert format_candidate_verification(None) == ""


from deep_research.candidate_verifier import _normalize_result


def test_normalize_single_object_with_weak_candidate():
    raw = {
        "name": "Sana'a University",
        "score": 2,
        "matched_clues": ["E"],
        "unmatched_clues": ["B", "C", "D"],
        "evidence_urls": ["https://example.com"],
        "verdict": "weak_candidate",
    }
    out = _normalize_result(raw)
    assert len(out["candidates"]) == 1
    assert out["candidates"][0]["name"] == "Sana'a University"
    assert out["final_candidate"] is None  # weak candidates should not be forced


def test_normalize_single_object_with_candidate_verdict():
    raw = {
        "name": "Queen Arwa University",
        "score": 80,
        "matched_clues": ["A", "B", "C", "D", "E"],
        "unmatched_clues": [],
        "evidence_urls": ["https://qau.edu.ye"],
        "verdict": "candidate",
    }
    out = _normalize_result(raw)
    assert out["final_candidate"] == "Queen Arwa University"
    assert len(out["candidates"]) == 1


def test_normalize_already_list_shape_unchanged():
    raw = {"candidates": [{"name": "X"}], "final_candidate": "X", "confidence": 50, "reasoning": ""}
    out = _normalize_result(raw)
    assert out is raw


def test_normalize_low_score_candidate_not_forced():
    raw = {
        "name": "Trinity College Dublin",
        "score": 3,
        "matched_clues": ["E"],
        "unmatched_clues": ["A", "B", "C", "D"],
        "evidence_urls": [],
        "verdict": "candidate",
    }
    out = _normalize_result(raw)
    assert len(out["candidates"]) == 1
    assert out["final_candidate"] is None
