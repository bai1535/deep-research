"""Tests for claim provenance metric helpers (deep_research.claim_metrics)."""

import json

from deep_research.claim_metrics import audit_granularity, compute_run_metrics


def test_audit_granularity_detects_over_fine_and_over_coarse():
    claims = [
        {"claim_id": "c0", "text": "abc", "parent_claim_id": None},
        {"claim_id": "c1", "text": "abcd", "parent_claim_id": None},
        {"claim_id": "c2", "text": "该产品功能强大并且成本较低", "parent_claim_id": None},
    ]
    audit = audit_granularity(claims)
    assert audit["over_fine_count"] >= 1
    assert audit["over_coarse_count"] == 1
    assert audit["too_short_count"] == 2


def test_compute_run_metrics_reads_claims_file(tmp_path):
    run_dir = tmp_path / "20260902-test"
    run_dir.mkdir()
    claims = {
        "run_id": "20260902-test",
        "original_text": "北京和上海都是中国大城市。未验证内容。",
        "claims": [
            {
                "claim_id": "c0",
                "text": "北京和上海都是中国大城市",
                "span": {"start": 0, "end": 12},
                "status": "verified",
                "confidence": 80,
                "evidence_links": [{"url": "https://example.org"}],
                "event_ids": ["evt-1"],
            },
            {
                "claim_id": "c1",
                "text": "未验证内容",
                "span": {"start": 13, "end": 18},
                "status": "unverifiable",
                "confidence": 0,
                "evidence_links": [],
                "event_ids": [],
            },
        ],
    }
    path = run_dir / "claims.json"
    path.write_text(json.dumps(claims, ensure_ascii=False), encoding="utf-8")
    m = compute_run_metrics(path)
    assert m["total_claims"] == 2
    assert m["evidence_coverage"] == 0.5
    assert m["traceability"] == 0.5
    assert m["verified_rate"] == 0.5
    assert m["unverifiable_rate"] == 0.5
    assert m["avg_confidence"] == 40.0
