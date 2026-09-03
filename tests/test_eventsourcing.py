"""Tests for event sourcing infrastructure (offline)."""

from pathlib import Path

from deep_research.eventsourcing import Event, EventStore, record_event, hash_payload


def test_hash_payload_stable():
    assert hash_payload({"a": 1, "b": [2, 3]}) == hash_payload({"b": [2, 3], "a": 1})


def test_append_and_load(tmp_path):
    store = EventStore(tmp_path)
    ev = Event(event_id="e1", run_id="r1", seq=1, action="search", payload={"query": "x"})
    store.append(ev)
    loaded = store.load("r1")
    assert len(loaded) == 1
    assert loaded[0].event_id == "e1"
    assert loaded[0].payload["query"] == "x"


def test_record_event_sets_seq(tmp_path):
    store = EventStore(tmp_path)
    e1 = record_event(run_id="r1", action="search", payload={"input": {"q": "a"}}, store=store)
    e2 = record_event(run_id="r1", action="fetch", parent_event_id=e1.event_id, payload={"input": {"url": "u"}}, store=store)
    assert e1.seq == 1
    assert e2.seq == 2
    assert e2.parent_event_id == e1.event_id
    ancestors = store.ancestors("r1", e2.event_id)
    assert [a.event_id for a in ancestors] == [e1.event_id, e2.event_id]


def test_trace_text(tmp_path):
    store = EventStore(tmp_path)
    record_event(run_id="r1", action="search", payload={"output": "Queen Arwa University"}, store=store)
    hits = store.trace_text("r1", "arwa")
    assert len(hits) == 1
    assert hits[0].action == "search"


def test_rollback_to_prefix(tmp_path):
    store = EventStore(tmp_path)
    e1 = record_event(run_id="r1", action="a", store=store)
    e2 = record_event(run_id="r1", action="b", store=store)
    record_event(run_id="r1", action="c", store=store)
    rolled = store.rollback_to("r1", e2.event_id)
    assert [e.event_id for e in rolled] == [e1.event_id, e2.event_id]
