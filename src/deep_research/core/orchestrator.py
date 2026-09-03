"""Lightweight task orchestrator — no external framework dependency.

Provides three composition primitives:

    parallel(*coros)         — run all, return results (with exception tolerance)
    pipeline(item, *stages)  — run item through sequential stages
    barrier(*coros)          — alias for parallel (semantic clarity)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger("deep_research.core.orchestrator")


async def parallel(*coros: Awaitable[Any]) -> list[Any]:
    """Run multiple coroutines concurrently.

    Each coroutine runs independently; failures are captured and
    replaced with ``None`` in the result list.  Other coroutines
    are **not** cancelled when one fails.
    """
    results = await asyncio.gather(*coros, return_exceptions=True)
    out: list[Any] = []
    for i, r in enumerate(results):
        if isinstance(r, BaseException):
            logger.error("parallel task %d failed: %s", i, r)
            out.append(None)
        else:
            out.append(r)
    return out


async def pipeline(initial: Any, *stages: Callable[[Any], Awaitable[Any]]) -> Any:
    """Run *initial* through a chain of async stages.

    Each stage receives the previous stage's return value.  If any stage
    raises, the pipeline stops and the exception propagates.
    """
    value = initial
    for i, stage in enumerate(stages):
        try:
            value = await stage(value)
        except Exception:
            logger.error("pipeline stage %d (%s) failed", i, getattr(stage, "__name__", stage))
            raise
    return value


# semantic alias
barrier = parallel
