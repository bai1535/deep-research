"""Structured per-call logging — logs/search_calls.jsonl.

Every tool invocation (search + web_fetch) is appended as one JSON line so
operators can answer "which engine, how many calls, how many succeeded,
what latency, what errors" without reading the transcript.

Appends are single-line writes opened in append mode; on Linux this is
line-atomic enough for concurrent agents.  Writes are synchronous and tiny
by design — logging must never become a bottleneck in the research loop.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


def _log_path() -> Path:
    return Path(os.getenv("SEARCH_CALLS_LOG", "logs/search_calls.jsonl"))


def log_call(record: dict) -> None:
    """Append one call record as a JSON line.  Best-effort — never raises."""
    record = dict(record)
    record.setdefault("ts", datetime.now().isoformat())
    try:
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass
