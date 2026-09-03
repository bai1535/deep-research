"""Causal backtracking engine.

Given a final claim (or a suspicious event), walk the event DAG backwards
and score each upstream event as a potential pollution source.
"""

from __future__ import annotations

import json
import re
from typing import Any

from deep_research.eventsourcing import Event, EventStore

# Actions that directly bring external content into the run.
_SOURCE_ACTIONS = {
    "bing_search",
    "baidu_search",
    "firecrawl_search",
    "tavily_search",
    "wikipedia_search",
    "wikidata_lookup",
    "wayback_lookup",
    "web_fetch",
}

_URL_RE = re.compile(r"https?://[^\s)\]]+")


def _payload_text(event: Event) -> str:
    return json.dumps(event.payload, ensure_ascii=False)


def _event_score(event: Event, claim_text: str) -> tuple[int, str]:
    """Return (score, reason) for an event as a pollution source."""
    text = _payload_text(event).lower()
    needle = claim_text.lower()

    if needle and needle in text:
        if event.action in _SOURCE_ACTIONS:
            return 90, "外部来源事件直接包含该声明文本"
        if event.action == "llm_call":
            return 70, "LLM 生成事件中包含该声明文本，可能是幻觉产生点"
        return 60, "事件载荷中包含该声明文本"

    if event.action in _SOURCE_ACTIONS:
        return 40, "外部来源事件位于因果链上"
    if event.action == "llm_call":
        return 30, "LLM 调用位于因果链上"
    return 10, "普通中间事件"


def trace_claim(
    run_id: str,
    claim_text: str,
    store: EventStore | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Trace a final claim back through the event DAG.

    Returns ranked suspicious events plus the chains that led to the claim.
    """
    store = store or EventStore()
    events = store.load(run_id)
    if not events:
        return {"run_id": run_id, "claim": claim_text, "claim_events": [], "chains": [], "suspicious": []}

    needle = claim_text.lower()
    claim_events = [
        ev for ev in events
        if needle and needle in _payload_text(ev).lower()
    ][:limit]

    chains: list[list[Event]] = []
    for ev in claim_events:
        chain = store.ancestors(run_id, ev.event_id)
        if chain:
            chains.append(chain)

    scored: dict[str, tuple[int, str, Event]] = {}
    for chain in chains:
        for ev in chain:
            score, reason = _event_score(ev, claim_text)
            # Keep the highest score for each event.
            if ev.event_id not in scored or score > scored[ev.event_id][0]:
                scored[ev.event_id] = (score, reason, ev)

    suspicious = [
        {
            "event_id": ev.event_id,
            "seq": ev.seq,
            "action": ev.action,
            "agent": ev.agent,
            "score": score,
            "reason": reason,
            "urls": _extract_urls(ev),
            "payload_preview": json.dumps(ev.payload, ensure_ascii=False)[:300],
        }
        for ev_id, (score, reason, ev) in sorted(
            scored.items(), key=lambda x: x[1][0], reverse=True
        )
    ][:limit]

    return {
        "run_id": run_id,
        "claim": claim_text,
        "claim_events": [
            {"event_id": e.event_id, "action": e.action, "agent": e.agent, "seq": e.seq}
            for e in claim_events
        ],
        "chains": [
            [
                {"event_id": e.event_id, "action": e.action, "agent": e.agent, "seq": e.seq}
                for e in chain
            ]
            for chain in chains
        ],
        "suspicious": suspicious,
    }


def trace_event(
    run_id: str,
    event_id: str,
    store: EventStore | None = None,
) -> dict[str, Any]:
    """Trace a specific event's full ancestry."""
    store = store or EventStore()
    chain = store.ancestors(run_id, event_id)
    return {
        "run_id": run_id,
        "event_id": event_id,
        "chain": [
            {"event_id": e.event_id, "action": e.action, "agent": e.agent, "seq": e.seq}
            for e in chain
        ],
    }


def _extract_urls(event: Event) -> list[str]:
    text = _payload_text(event)
    return list(dict.fromkeys(_URL_RE.findall(text)))[:10]


__all__ = ["trace_claim", "trace_event"]
