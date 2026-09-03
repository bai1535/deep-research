"""Shared blackboard for inter-agent communication.

Agents read / write named slots.  Writers can optionally publish
an event that triggers subscribers.  This keeps agents decoupled — they
agree on slot names, not on who produces or consumes.
"""

from __future__ import annotations

import logging
from fnmatch import fnmatchcase
from typing import Any

from deep_research.core.policy_audit import log_policy_event

logger = logging.getLogger("deep_research.core.blackboard")


class Blackboard:
    """Key-value store with optional pub/sub.

    Usage::

        bb = Blackboard()
        bb.write("run:42:cards", cards)
        cards = bb.read("run:42:cards")  # or bb.read("run:42:cards", default=[])
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    # ── basic CRUD ───────────────────────────────────────────────

    def write(self, key: str, value: Any) -> None:
        """Write a value to a named slot, overwriting any previous value."""
        self._store[key] = value

    def read(self, key: str, default: Any = None) -> Any:
        """Read a value.  Returns *default* if the key hasn't been written."""
        return self._store.get(key, default)

    def delete(self, key: str) -> None:
        """Remove a key."""
        self._store.pop(key, None)

    def keys(self) -> list[str]:
        """Return all currently populated slot names."""
        return list(self._store.keys())

    # ── snapshot helpers ─────────────────────────────────────────

    def snapshot(self, keys: list[str] | None = None) -> dict[str, Any]:
        """Return a shallow copy of the store (or a subset of keys)."""
        if keys is None:
            return dict(self._store)
        return {k: self._store[k] for k in keys if k in self._store}

    def __contains__(self, key: str) -> bool:
        return key in self._store


class ScopedBlackboard:
    """Policy-enforcing wrapper around a shared Blackboard.

    Phase 2 of Agent independence governance: an agent only sees/reads the
    keys allowed by its ContextPolicy and can only write keys it owns.
    """

    def __init__(
        self,
        inner: Blackboard,
        *,
        read_patterns: list[str] | None = None,
        write_patterns: list[str] | None = None,
        agent_name: str = "",
    ) -> None:
        self._inner = inner
        self._read = read_patterns or ["*"]
        self._write = write_patterns or ["*"]
        self._agent_name = agent_name

    @staticmethod
    def _matches(patterns: list[str], key: str) -> bool:
        return any(fnmatchcase(key, p) for p in patterns)

    def _denied(self, action: str, key: str, patterns: list[str]) -> bool:
        if not self._matches(patterns, key):
            logger.warning(
                "ScopedBlackboard: agent %s %s denied for key %s (allowed=%s)",
                self._agent_name, action, key, patterns,
            )
            log_policy_event(
                agent=self._agent_name,
                action=f"blackboard_{action}",
                target=key,
                reason=f"not allowed by ContextPolicy patterns {patterns}",
                allowed=False,
            )
            return True
        return False

    def write(self, key: str, value: Any) -> None:
        if self._denied("write", key, self._write):
            return
        self._inner.write(key, value)

    def read(self, key: str, default: Any = None) -> Any:
        if self._denied("read", key, self._read):
            return default
        return self._inner.read(key, default)

    def delete(self, key: str) -> None:
        if self._denied("delete", key, self._write):
            return
        self._inner.delete(key)

    def keys(self) -> list[str]:
        return [k for k in self._inner.keys() if self._matches(self._read, k)]

    def snapshot(self, keys: list[str] | None = None) -> dict[str, Any]:
        if keys is None:
            keys = self.keys()
        return {k: self._inner.read(k) for k in keys if self._matches(self._read, k)}

    def __contains__(self, key: str) -> bool:
        return self._matches(self._read, key) and key in self._inner
