"""Deterministic replay support for event-sourced runs.

Phase 3: an output cache keyed by action+input_hash, and a ReplayEngine
that can walk a list of events and reuse cached outputs instead of
re-executing external calls.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deep_research.eventsourcing import Event, EventStore, hash_payload

logger = logging.getLogger("deep_research.replay")


class OutputCache:
    """Content-addressed output cache, one JSONL file per run."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir else Path("./runs")

    def path_for(self, run_id: str) -> Path:
        return self.base_dir / run_id / "output_cache.jsonl"

    def get(self, run_id: str, key: str) -> Any | None:
        path = self.path_for(run_id)
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if row.get("key") == key:
                    return row.get("value")
        return None

    def put(self, run_id: str, key: str, value: Any) -> None:
        path = self.path_for(run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "value": value}, ensure_ascii=False) + "\n")

    def delete(self, run_id: str, key: str) -> None:
        """Remove a key from the cache by rewriting the file without it."""
        path = self.path_for(run_id)
        if not path.exists():
            return
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if row.get("key") != key:
                    rows.append(row)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def load_all(self, run_id: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        path = self.path_for(run_id)
        if not path.exists():
            return out
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    out[row["key"]] = row["value"]
                except Exception:
                    continue
        return out


def _cache_key(event: Event) -> str:
    return f"{event.action}:{event.input_hash}"


class ReplayEngine:
    """Replay a list of events, reusing cached outputs where possible."""

    def __init__(
        self,
        store: EventStore | None = None,
        cache: OutputCache | None = None,
    ) -> None:
        self.store = store or EventStore()
        self.cache = cache or OutputCache()

    def replay_events(self, run_id: str, events: list[Event]) -> list[dict[str, Any]]:
        """Return replay steps; each step says whether output was reused."""
        steps: list[dict[str, Any]] = []
        for ev in events:
            key = _cache_key(ev)
            cached = self.cache.get(run_id, key)
            if cached is not None:
                steps.append({
                    "event_id": ev.event_id,
                    "action": ev.action,
                    "reused": True,
                    "output": cached,
                })
                continue
            # Fall back to the output already stored in the immutable event.
            output = ev.payload.get("output")
            if output is not None:
                self.cache.put(run_id, key, output)
                steps.append({
                    "event_id": ev.event_id,
                    "action": ev.action,
                    "reused": False,
                    "output": output,
                })
            else:
                steps.append({
                    "event_id": ev.event_id,
                    "action": ev.action,
                    "reused": False,
                    "output": None,
                })
        return steps

    def build_replay_plan(self, run_id: str, rollback_event_id: str) -> dict[str, Any]:
        """Build a replay plan for the event prefix up to rollback_event_id."""
        events = self.store.rollback_to(run_id, rollback_event_id)
        steps = self.replay_events(run_id, events)
        return {
            "run_id": run_id,
            "rollback_event_id": rollback_event_id,
            "event_count": len(events),
            "reused_count": sum(1 for s in steps if s["reused"]),
            "steps": steps,
        }

    def build_branch_rollback_plan(self, run_id: str, rollback_event_id: str) -> dict[str, Any]:
        """Compute a branch-level rollback plan.

        - trusted_prefix: events up to and including the rollback point
        - affected: descendants of the rollback point (must be re-executed)
        - unaffected: parallel events after the rollback point that are not
          descendants (kept as-is)
        """
        target = self.store.get(run_id, rollback_event_id)
        if target is None:
            raise ValueError(f"event not found: {rollback_event_id}")

        all_events = self.store.load(run_id)
        prefix = self.store.rollback_to(run_id, rollback_event_id)
        prefix_ids = {e.event_id for e in prefix}
        affected = self.store.descendants(run_id, rollback_event_id)
        affected_ids = {e.event_id for e in affected}
        unaffected = [
            e for e in all_events
            if e.event_id not in prefix_ids and e.event_id not in affected_ids
        ]

        prefix_steps = self.replay_events(run_id, prefix)
        return {
            "run_id": run_id,
            "rollback_event_id": rollback_event_id,
            "trusted_prefix_count": len(prefix),
            "affected_count": len(affected),
            "unaffected_count": len(unaffected),
            "affected_events": [
                {"event_id": e.event_id, "action": e.action, "agent": e.agent, "seq": e.seq}
                for e in affected
            ],
            "unaffected_events": [
                {"event_id": e.event_id, "action": e.action, "agent": e.agent, "seq": e.seq}
                for e in unaffected
            ],
            "replay_plan": prefix_steps,
        }
    def execute_rollback(self, run_id: str, rollback_event_id: str) -> dict[str, Any]:
        """Execute a rollback at the cache/state level.

        Removes affected branch outputs from the cache and writes a
        rollback_state.json marker.  Full report regeneration from the
        replayed branch is the next step; this makes the rollback real
        and prevents poisoned outputs from being reused.
        """
        plan = self.build_branch_rollback_plan(run_id, rollback_event_id)
        events_by_id = {e.event_id: e for e in self.store.load(run_id)}
        affected_ids = [e["event_id"] for e in plan["affected_events"]]
        for eid in affected_ids:
            ev = events_by_id.get(eid)
            if ev:
                self.cache.delete(run_id, f"{ev.action}:{ev.input_hash}")

        state = {
            "run_id": run_id,
            "rollback_event_id": rollback_event_id,
            "affected_event_ids": affected_ids,
            "status": "pending_replay",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        path = self.store.base_dir / run_id / "rollback_state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        plan["executed"] = True
        plan["rollback_state"] = state
        plan["affected_event_ids"] = affected_ids
        plan["status"] = state["status"]
        return plan


    async def replay_affected_tools(self, run_id: str, rollback_event_id: str) -> dict[str, Any]:
        """Replay affected external tool events after a rollback.

        Re-executes search/fetch/etc. events in the affected branch using
        current tool instances, writes new outputs to the cache and a
        replay_output.jsonl log, and updates rollback state to
        tools_replayed.  LLM/report regeneration is a later step.
        """
        plan = self.execute_rollback(run_id, rollback_event_id)
        from deep_research.tools import get_quality_search_tools
        from deep_research.tools.web_fetch import WebFetchTool

        tools = {t.name: t for t in [*get_quality_search_tools(), WebFetchTool()]}
        events_by_id = {e.event_id: e for e in self.store.load(run_id)}
        replayed: list[dict[str, Any]] = []
        replay_path = self.store.base_dir / run_id / "replay_output.jsonl"
        replay_path.parent.mkdir(parents=True, exist_ok=True)

        for item in plan["affected_events"]:
            ev = events_by_id.get(item["event_id"])
            if not ev or ev.action not in tools:
                continue
            args = ev.payload.get("input") or {}
            try:
                result = await tools[ev.action].run(args)
            except Exception as exc:
                result = f"ERROR: {exc}"
            self.cache.put(run_id, f"{ev.action}:{ev.input_hash}", result)
            row = {
                "event_id": ev.event_id,
                "action": ev.action,
                "replayed_at": datetime.now(timezone.utc).isoformat(),
                "output": result,
            }
            replayed.append(row)
            with replay_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        state_path = self.store.base_dir / run_id / "rollback_state.json"
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                state["status"] = "tools_replayed"
                state["replayed_count"] = len(replayed)
                state["replayed_at"] = datetime.now(timezone.utc).isoformat()
                state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

        plan["status"] = "tools_replayed"
        plan["replayed_tools"] = replayed
        return plan


    async def replay_and_regenerate(self, run_id: str, rollback_event_id: str) -> dict[str, Any]:
        """Replay affected tools, then regenerate the final report.

        After replaying external tool events, this re-runs the synthesis
        phase (Scorer/Extractor/Editor + candidate verification when
        applicable) so the report and evidence are rebuilt from current
        state.
        """
        plan = await self.replay_affected_tools(run_id, rollback_event_id)
        from deep_research.crews.synthesis_crew import SynthesisCrewRunner

        result = await SynthesisCrewRunner().run(run_id)
        plan["report_regenerated"] = True
        plan["report_score"] = result.get("score").overall_score if result.get("score") else None
        plan["status"] = "report_regenerated"

        state_path = self.store.base_dir / run_id / "rollback_state.json"
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                state["status"] = "report_regenerated"
                state["report_regenerated_at"] = datetime.now(timezone.utc).isoformat()
                state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
        return plan



__all__ = ["OutputCache", "ReplayEngine"]
