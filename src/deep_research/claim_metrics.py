"""Offline metrics and granularity audit for claim-level provenance.

These helpers are importable both from scripts/eval_claims.py and from
pytest, so the evaluation logic can be unit-tested inside the container.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CONJUNCTION_RE = re.compile(r"并且|同时|以及|此外|而且|也")
TOO_SHORT_CHARS = 6


def _span_len(text: str, claim: dict) -> int:
    span = claim.get("span")
    if not isinstance(span, dict):
        return 0
    try:
        start = int(span.get("start", 0))
        end = int(span.get("end", 0))
    except (TypeError, ValueError):
        return 0
    return max(0, min(end, len(text)) - max(start, 0))


def audit_granularity(claims: list[dict]) -> dict[str, int]:
    """Run lightweight over-fine / over-coarse heuristics on claims."""
    texts = [str(c.get("text") or "") for c in claims]
    over_fine = 0
    too_short = 0
    for i, text in enumerate(texts):
        if text and len(text) < TOO_SHORT_CHARS:
            too_short += 1
        for j, other in enumerate(texts):
            if i == j or not text or not other:
                continue
            if text != other and text in other:
                # If the short one is explicitly a child of the long one, it's intended.
                parent = claims[i].get("parent_claim_id")
                if parent and parent == claims[j].get("claim_id"):
                    continue
                over_fine += 1
                break

    over_coarse = sum(1 for c in claims if CONJUNCTION_RE.search(str(c.get("text") or "")))
    return {
        "over_fine_count": over_fine,
        "over_coarse_count": over_coarse,
        "too_short_count": too_short,
    }


def compute_run_metrics(claims_path: Path) -> dict[str, Any]:
    """Compute provenance metrics from one runs/<id>/claims.json file."""
    data = json.loads(claims_path.read_text(encoding="utf-8", errors="replace"))
    claims = data.get("claims") or []
    text = str(data.get("original_text") or "")

    total = len(claims)
    if total == 0:
        return {
            "run_id": claims_path.parent.name,
            "total_claims": 0,
            "answer_coverage": 0.0,
            "evidence_coverage": 0.0,
            "traceability": 0.0,
            "verified_rate": 0.0,
            "suspect_rate": 0.0,
            "disputed_rate": 0.0,
            "false_rate": 0.0,
            "unverifiable_rate": 0.0,
            "avg_confidence": 0.0,
            "over_fine_count": 0,
            "over_coarse_count": 0,
            "too_short_count": 0,
        }

    covered = sum(_span_len(text, c) for c in claims)
    evidence_count = sum(1 for c in claims if c.get("evidence_links"))
    trace_count = sum(1 for c in claims if c.get("event_ids"))
    status_counts = {
        "verified": 0,
        "suspect": 0,
        "disputed": 0,
        "false": 0,
        "unverifiable": 0,
    }
    conf_sum = 0
    for c in claims:
        status = str(c.get("status") or "unverifiable").lower()
        status_counts[status] = status_counts.get(status, 0) + 1
        try:
            conf_sum += int(c.get("confidence") or 0)
        except (TypeError, ValueError):
            pass

    audit = audit_granularity(claims)

    return {
        "run_id": claims_path.parent.name,
        "total_claims": total,
        "answer_coverage": round(covered / len(text), 4) if text else 0.0,
        "evidence_coverage": round(evidence_count / total, 4),
        "traceability": round(trace_count / total, 4),
        "verified_rate": round(status_counts["verified"] / total, 4),
        "suspect_rate": round(status_counts["suspect"] / total, 4),
        "disputed_rate": round(status_counts["disputed"] / total, 4),
        "false_rate": round(status_counts["false"] / total, 4),
        "unverifiable_rate": round(status_counts["unverifiable"] / total, 4),
        "avg_confidence": round(conf_sum / total, 1),
        "over_fine_count": audit["over_fine_count"],
        "over_coarse_count": audit["over_coarse_count"],
        "too_short_count": audit["too_short_count"],
    }


__all__ = [
    "CONJUNCTION_RE",
    "TOO_SHORT_CHARS",
    "_span_len",
    "audit_granularity",
    "compute_run_metrics",
]
