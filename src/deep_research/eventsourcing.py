"""Event Sourcing infrastructure for DeepResearch.

Phase 1: immutable event model + JSONL event store + basic provenance
traversal.  Later phases add deterministic replay and branch-level
rollback; this module provides the foundation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger("deep_research.eventsourcing")


def hash_payload(obj: Any) -> str:
    """Stable content hash for an event input/output."""
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class Event:
    """An immutable atomic action in a research run."""

    event_id: str
    run_id: str
    seq: int
    action: str
    agent: str = ""
    parent_event_id: str | None = None
    input_hash: str = ""
    output_hash: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_line(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class EventStore:
    """Append-only JSONL event store, one file per run."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir else Path("./runs")

    def path_for(self, run_id: str) -> Path:
        return self.base_dir / run_id / "events.jsonl"

    def append(self, event: Event) -> Event:
        path = self.path_for(event.run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(event.to_line() + "\n")
        return event

    def load(self, run_id: str) -> list[Event]:
        path = self.path_for(run_id)
        if not path.exists():
            return []
        events: list[Event] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    events.append(Event(**data))
                except Exception as exc:
                    logger.warning("eventsourcing: skip bad event line: %s", exc)
        return events

    def get(self, run_id: str, event_id: str) -> Event | None:
        for ev in self.load(run_id):
            if ev.event_id == event_id:
                return ev
        return None

    def children(self, run_id: str, event_id: str) -> list[Event]:
        return [ev for ev in self.load(run_id) if ev.parent_event_id == event_id]

    def descendants(self, run_id: str, event_id: str) -> list[Event]:
        """Return all events in the causal subtree rooted at event_id."""
        events = self.load(run_id)
        children_map: dict[str, list[Event]] = {}
        for ev in events:
            if ev.parent_event_id:
                children_map.setdefault(ev.parent_event_id, []).append(ev)
        out: list[Event] = []
        stack = list(children_map.get(event_id, []))
        seen: set[str] = set()
        while stack:
            ev = stack.pop()
            if ev.event_id in seen:
                continue
            seen.add(ev.event_id)
            out.append(ev)
            stack.extend(children_map.get(ev.event_id, []))
        return out

    def ancestors(self, run_id: str, event_id: str) -> list[Event]:
        """Return the chain from the root to this event (inclusive)."""
        by_id = {ev.event_id: ev for ev in self.load(run_id)}
        chain: list[Event] = []
        cur = by_id.get(event_id)
        seen: set[str] = set()
        while cur and cur.event_id not in seen:
            chain.append(cur)
            seen.add(cur.event_id)
            cur = by_id.get(cur.parent_event_id or "")
        chain.reverse()
        return chain

    def trace_text(self, run_id: str, text: str, limit: int = 20) -> list[Event]:
        """Find events whose payload text mentions the given text."""
        needle = text.lower()
        hits: list[Event] = []
        for ev in self.load(run_id):
            blob = json.dumps(ev.payload, ensure_ascii=False).lower()
            if needle in blob:
                hits.append(ev)
                if len(hits) >= limit:
                    break
        return hits

    def rollback_to(self, run_id: str, event_id: str) -> list[Event]:
        """Basic rollback: return the event prefix up to and including the target.

        Branch-level incremental replay is a later phase; this gives a
        deterministic prefix that callers can use to rebuild state.
        """
        events = self.load(run_id)
        out: list[Event] = []
        for ev in events:
            out.append(ev)
            if ev.event_id == event_id:
                break
        return out


def record_event(
    *,
    run_id: str,
    action: str,
    agent: str = "",
    parent_event_id: str | None = None,
    payload: dict[str, Any] | None = None,
    store: EventStore | None = None,
) -> Event:
    """Create and persist one event."""
    payload = payload or {}
    store = store or EventStore()
    events = store.load(run_id)
    seq = len(events) + 1
    ev = Event(
        event_id=str(uuid.uuid4()),
        run_id=run_id,
        seq=seq,
        action=action,
        agent=agent,
        parent_event_id=parent_event_id,
        input_hash=hash_payload(payload.get("input")),
        output_hash=hash_payload(payload.get("output")),
        payload=payload,
    )
    store.append(ev)
    return ev


__all__ = ["Event", "EventStore", "record_event", "hash_payload"]
