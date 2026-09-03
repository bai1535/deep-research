"""Event bus — fine-grained progress events for streaming output.

Every agent emits events as it works (LLM call started, tool invoked,
finding produced, run finished).  The web layer subscribes and pushes
them to the frontend via SSE.

Event shapes (all carry "ts" and "agent" where relevant):
    {"type": "phase_start", "phase": "research"}
    {"type": "phase_done",  "phase": "research"}
    {"type": "agent_start", "agent": "researcher-technical"}
    {"type": "llm_call",    "agent": ..., "round": 1}
    {"type": "tool_call",   "agent": ..., "tool": "bing_search", "query": "..."}
    {"type": "tool_done",   "agent": ..., "tool": "bing_search", "chars": 1234}
    {"type": "finding",     "agent": ..., "index": 0, "text": "claim..."}
    {"type": "agent_done",  "agent": ..., "calls": 3, "tokens": 14900, "cost": 0.006}
    {"type": "run_done",    "score": 72, "findings": 30, "cost": 0.15}
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime
from typing import Any

logger = logging.getLogger("deep_research.events")

MAX_HISTORY = 1000       # events retained for late subscribers
MAX_SUBSCRIBER_QUEUE = 200  # per-subscriber buffer; overflow drops events


class EventBus:
    """In-memory event store with fan-out to SSE subscribers.

    One bus per research run.  Late subscribers first receive a replay
    of everything that already happened, then live events.
    """

    def __init__(self) -> None:
        self._history: deque[dict] = deque(maxlen=MAX_HISTORY)
        self._subscribers: list[asyncio.Queue] = []

    # ── emit ────────────────────────────────────────────────────────

    def emit(self, event: dict) -> None:
        """Record an event and fan it out to all subscribers."""
        event = dict(event)
        # #8: ISO timestamp — %H:%M:%S would "go backwards" across midnight
        event.setdefault("ts", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self._history.append(event)

        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # #7: a dropped event looks like a gap in the frontend
                # stream — log it so it's distinguishable from "never emitted"
                logger.warning(
                    "events: subscriber queue full, dropped %s (type=%s)",
                    event.get("ts"), event.get("type"),
                )

    # ── subscribe ───────────────────────────────────────────────────

    def subscribe(self) -> asyncio.Queue:
        """Create a subscriber queue.  Returns an asyncio.Queue."""
        q: asyncio.Queue = asyncio.Queue(maxsize=MAX_SUBSCRIBER_QUEUE)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def replay(self) -> list[dict]:
        """Return all events so far (oldest → newest)."""
        return list(self._history)
