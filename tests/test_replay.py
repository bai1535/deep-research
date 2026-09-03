"""Tests for deterministic replay (offline)."""

from deep_research.eventsourcing import Event, EventStore, record_event
from deep_research.replay import OutputCache, ReplayEngine


def test_output_cache_put_get(tmp_path):
    cache = OutputCache(tmp_path)
    cache.put("r1", "k", {"a": 1})
    assert cache.get("r1", "k") == {"a": 1}


def test_replay_reuses_cached_output(tmp_path):
    store = EventStore(tmp_path)
    cache = OutputCache(tmp_path)
    ev = record_event(
        run_id="r1", action="bing_search",
        payload={"input": {"q": "x"}, "output": "URL: http://a.com"}, store=store,
    )
    # Put a different cached output for the same key to simulate reuse.
    cache.put("r1", f"bing_search:{ev.input_hash}", "CACHED")
    engine = ReplayEngine(store=store, cache=cache)
    steps = engine.replay_events("r1", [ev])
    assert steps[0]["reused"] is True
    assert steps[0]["output"] == "CACHED"


def test_replay_plan_counts(tmp_path):
    store = EventStore(tmp_path)
    cache = OutputCache(tmp_path)
    e1 = record_event(run_id="r1", action="a", payload={"input": {"x": 1}, "output": "o1"}, store=store)
    e2 = record_event(run_id="r1", action="b", payload={"input": {"x": 2}, "output": "o2"}, store=store)
    cache.put("r1", f"a:{e1.input_hash}", "cached-o1")
    engine = ReplayEngine(store=store, cache=cache)
    plan = engine.build_replay_plan("r1", e2.event_id)
    assert plan["event_count"] == 2
    assert plan["reused_count"] == 1


def test_branch_rollback_plan_separates_parallel_branch(tmp_path):
    store = EventStore(tmp_path)
    cache = OutputCache(tmp_path)
    root = record_event(run_id="r1", action="root", payload={"input": {}, "output": "root"}, store=store)
    a = record_event(run_id="r1", action="branch_a", parent_event_id=root.event_id, payload={"input": {}, "output": "a"}, store=store)
    b = record_event(run_id="r1", action="branch_b", parent_event_id=root.event_id, payload={"input": {}, "output": "b"}, store=store)
    engine = ReplayEngine(store=store, cache=cache)
    plan = engine.build_branch_rollback_plan("r1", a.event_id)
    assert plan["trusted_prefix_count"] == 2  # root + branch_a
    assert plan["affected_count"] == 0        # branch_a has no children
    assert plan["unaffected_count"] == 1      # branch_b
    assert plan["unaffected_events"][0]["action"] == "branch_b"


def test_execute_rollback_clears_affected_cache(tmp_path):
    store = EventStore(tmp_path)
    cache = OutputCache(tmp_path)
    root = record_event(run_id="r1", action="root", payload={"input": {"x": 1}, "output": "root"}, store=store)
    bad = record_event(run_id="r1", action="web_fetch", parent_event_id=root.event_id, payload={"input": {"url": "bad"}, "output": "poisoned"}, store=store)
    # Simulate cached poisoned output.
    cache.put("r1", f"web_fetch:{bad.input_hash}", "poisoned-cache")
    engine = ReplayEngine(store=store, cache=cache)
    plan = engine.execute_rollback("r1", root.event_id)
    assert plan["executed"] is True
    assert plan["affected_count"] == 1
    assert cache.get("r1", f"web_fetch:{bad.input_hash}") is None
    state_path = tmp_path / "r1" / "rollback_state.json"
    assert state_path.exists()


import pytest


@pytest.mark.asyncio
async def test_replay_affected_tools_skips_non_tool_events(tmp_path):
    store = EventStore(tmp_path)
    cache = OutputCache(tmp_path)
    root = record_event(run_id="r1", action="root", payload={"input": {}, "output": "root"}, store=store)
    llm = record_event(run_id="r1", action="llm_call", parent_event_id=root.event_id, payload={"input": {}, "output": "text"}, store=store)
    engine = ReplayEngine(store=store, cache=cache)
    plan = await engine.replay_affected_tools("r1", root.event_id)
    assert plan["status"] == "tools_replayed"
    assert plan["replayed_tools"] == []
    assert llm.event_id in plan["affected_event_ids"]
