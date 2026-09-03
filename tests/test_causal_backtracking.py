"""Tests for causal backtracking engine."""

from deep_research.eventsourcing import EventStore, record_event
from deep_research.causal_backtracking import trace_claim, trace_event


def _build_chain(tmp_path):
    store = EventStore(tmp_path)
    s = record_event(
        run_id="r1", action="bing_search", payload={"output": "URL: http://bad.example Queen Arwa University"}, store=store
    )
    f = record_event(
        run_id="r1", action="web_fetch", parent_event_id=s.event_id,
        payload={"input": {"url": "http://bad.example"}, "output": "Queen Arwa University founded"}, store=store
    )
    l = record_event(
        run_id="r1", action="llm_call", parent_event_id=f.event_id,
        payload={"output": {"content": "The answer is Queen Arwa University"}}, store=store
    )
    return store, s, f, l


def test_trace_claim_finds_source(tmp_path):
    store, s, f, l = _build_chain(tmp_path)
    result = trace_claim("r1", "Queen Arwa University", store=store)
    assert len(result["claim_events"]) >= 1
    assert result["suspicious"][0]["event_id"] == s.event_id
    assert result["suspicious"][0]["score"] >= 90


def test_trace_event_returns_chain(tmp_path):
    store, s, f, l = _build_chain(tmp_path)
    result = trace_event("r1", l.event_id, store=store)
    ids = [e["event_id"] for e in result["chain"]]
    assert ids == [s.event_id, f.event_id, l.event_id]
