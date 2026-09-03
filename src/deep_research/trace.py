"""Lightweight trace context — injects trace_id into log messages.

Usage:
    tlog = trace_logger(logger, trace_id)
    tlog.info("Phase 1 starting")  # → "[trace=abc123] Phase 1 starting"
"""

from __future__ import annotations

import logging
import uuid
from typing import Any


def new_trace_id() -> str:
    """Generate a short, human-readable trace ID."""
    return uuid.uuid4().hex[:8]


class TraceAdapter(logging.LoggerAdapter):
    """LoggerAdapter that prepends [trace=xxx] to every log message."""

    def __init__(self, logger: logging.Logger, trace_id: str, *, prefix: str = "") -> None:
        super().__init__(logger, {})
        self._trace = trace_id
        self._prefix = prefix  # optional extra context, e.g. agent name

    def process(self, msg: Any, kwargs: Any) -> tuple[Any, Any]:
        extra = f"[trace={self._trace}]"
        if self._prefix:
            extra += f" [{self._prefix}]"
        return f"{extra} {msg}", kwargs


def trace_logger(
    logger: logging.Logger | str,
    trace_id: str,
    *,
    prefix: str = "",
) -> TraceAdapter:
    """Create a logger adapter that injects *trace_id* into every log line."""
    if isinstance(logger, str):
        logger = logging.getLogger(logger)
    return TraceAdapter(logger, trace_id, prefix=prefix)
