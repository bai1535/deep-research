"""File-cache for deduplicating reads.

When two agents fetch the same URL, the second read returns the cached
content instead of hitting the network again.  Cache entries expire
after a configurable TTL.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("deep_research.core.file_cache")


@dataclass
class _CacheEntry:
    content: Any
    fetched_at: float = field(default_factory=time.time)


class FileCache:
    """A simple URL → content cache with TTL-based expiration."""

    def __init__(self, ttl_seconds: float = 300.0) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, _CacheEntry] = {}

    # ── public API ───────────────────────────────────────────────

    def get(self, key: str) -> Any | None:
        """Return cached content, or None if missing / expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() - entry.fetched_at > self._ttl:
            del self._store[key]
            return None
        logger.debug("Cache HIT  for %s", key[:80])
        return entry.content

    def set(self, key: str, content: Any) -> None:
        """Store content in the cache."""
        logger.debug("Cache MISS for %s — caching", key[:80])
        self._store[key] = _CacheEntry(content=content, fetched_at=time.time())

    def invalidate(self, key: str) -> None:
        """Force-remove a key."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Drop all entries."""
        self._store.clear()

    def get_or_fetch(self, key: str, fetcher):
        """Return cached value or call *fetcher* (a sync callable)."""
        cached = self.get(key)
        if cached is not None:
            return cached
        content = fetcher()
        self.set(key, content)
        return content
