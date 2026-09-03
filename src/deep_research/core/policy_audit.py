"""Policy audit log for Agent independence governance.

Writes JSONL records to logs/policy_audit.jsonl whenever an AgentPolicy
denies a Blackboard access, a tool call, or an LLM/budget action.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("deep_research.policy_audit")


def audit_path() -> Path:
    base = os.getenv("RESEARCH_OUTPUT_DIR", "./runs")
    return Path(base).parent / "logs" / "policy_audit.jsonl"


def log_policy_event(
    *,
    agent: str = "",
    action: str = "",
    target: str = "",
    reason: str = "",
    allowed: bool = False,
) -> None:
    """Append one policy decision to the audit log (best-effort)."""
    try:
        path = audit_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "action": action,
            "target": target,
            "reason": reason,
            "allowed": allowed,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        logger.debug("policy audit write failed: %s", exc)


__all__ = ["audit_path", "log_policy_event"]
