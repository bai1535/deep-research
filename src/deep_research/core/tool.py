"""BuildTool — composable tool execution pipeline.

Every tool runs through four stages:
    validateInput → checkPermissions → execute → formatResult

Each stage can be overridden independently.  The base class handles
the orchestration; subclasses only implement the bits that differ.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("deep_research.core.tool")


@dataclass
class ToolResult:
    """Result of a tool execution, before formatting for the LLM."""

    success: bool
    data: Any = None
    error: str = ""


def _is_unrecoverable(exc: Exception) -> bool:
    """Return True if the error indicates the tool is permanently unusable.

    Quota exhaustion, invalid API keys, and auth failures won't fix
    themselves — disabling the tool saves the LLM from wasting rounds.
    Transient errors (timeouts, DNS, 5xx) are NOT unrecoverable.
    """
    msg = str(exc).lower()
    # Quota / billing — "credit" also matches "credits" (Firecrawl's
    # "Insufficient credits to perform this request").
    if "exceeds your plan" in msg or "quota" in msg or "billing" in msg:
        return True
    if any(m in msg for m in ("credit", "payment", "expired")):
        return True
    # Auth / permission
    if "forbidden" in msg or "unauthorized" in msg or "401" in msg or "403" in msg:
        return True
    if "api key" in msg and ("invalid" in msg or "missing" in msg or "not set" in msg):
        return True
    return False


# Process-wide disable registry — keyed by tool name → reason.
#
# Unlike the per-instance circuit breakers in web_fetch (which isolate
# TRANSIENT failures so one run's flaky backend doesn't trip another),
# this is for UNRECOVERABLE errors (quota exhaustion, auth failures):
# those won't self-heal within the process lifetime, so retrying them in
# every fresh agent just wastes an LLM round.  All instances of the same
# tool name share this state.
_DISABLED_TOOLS: dict[str, str] = {}

# Process-wide transient cooldowns (rate limits) — keyed by backend name.
# Unlike _DISABLED_TOOLS (permanent), these EXPIRE and the backend is
# retried automatically once the cooldown elapses.
_COOLDOWN_UNTIL: dict[str, float] = {}

# Seconds a 429'd backend is skipped process-wide before it is retried.
RATE_LIMIT_COOLDOWN = 60.0


def disable_tool_key(key: str, reason: str) -> None:
    """Permanently disable a process-wide key (tool name or backend name)."""
    _DISABLED_TOOLS[key] = reason


def is_tool_key_disabled(key: str) -> bool:
    """True if the given key was permanently disabled."""
    return key in _DISABLED_TOOLS


def set_backend_cooldown(key: str, seconds: float) -> None:
    """Put a backend into transient cooldown (e.g. HTTP 429 rate limit)."""
    _COOLDOWN_UNTIL[key] = time.time() + seconds


def in_backend_cooldown(key: str) -> bool:
    """True while the backend's cooldown window is still active."""
    return _COOLDOWN_UNTIL.get(key, 0.0) > time.time()


def _is_rate_limited(exc: Exception) -> bool:
    """True for HTTP 429 / rate-limit errors (transient, NOT unrecoverable)."""
    msg = str(exc).lower()
    return any(m in msg for m in ("rate limit", "ratelimit", "429"))


class BuildTool(ABC):
    """Composable tool base class.

    Subclasses MUST provide `name`, `description`, and `parameters`
    (the JSON Schema for function calling).  They SHOULD override
    `execute`, and MAY override `validate_input`, `check_permissions`,
    or `format_result`.
    """

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {},
        "required": [],
    })

    def is_disabled(self) -> bool:
        """True if this tool was disabled process-wide (unrecoverable error)."""
        return is_tool_key_disabled(self.name)

    def disable(self, reason: str) -> None:
        """Disable this tool for the rest of the process."""
        disable_tool_key(self.name, reason)

    # ── pipeline stages ──────────────────────────────────────────

    async def validate_input(self, args: dict[str, Any]) -> dict[str, Any]:
        """Validate / normalise incoming arguments.

        Override to add type-coercion, default-filling, or rejection
        of unknown keys.  Return the (possibly modified) args dict.
        Raise ValueError on invalid input.
        """
        return args

    async def check_permissions(self, args: dict[str, Any]) -> bool:
        """Security gate.  Return False to block execution."""
        return True

    @abstractmethod
    async def execute(self, args: dict[str, Any]) -> Any:
        """Do the actual work.  Return raw result."""

    def format_result(self, raw: Any) -> str:
        """Convert the raw result into text the LLM can consume."""
        if isinstance(raw, str):
            return raw
        try:
            return json.dumps(raw, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(raw)

    # ── public API ───────────────────────────────────────────────

    async def run(self, args: dict[str, Any]) -> str:
        """Execute the full pipeline.  Disabled tools return immediately."""
        if self.is_disabled():
            return (
                f"ERROR: {self.name} is unavailable ({_DISABLED_TOOLS[self.name]}). "
                "Use a different search tool."
            )

        try:
            validated = await self.validate_input(args)
        except (ValueError, TypeError) as exc:
            logger.warning("%s: input validation failed — %s", self.name, exc)
            return f"ERROR: invalid input for {self.name}: {exc}"

        if not await self.check_permissions(validated):
            logger.warning("%s: permission denied for args=%s", self.name, args)
            return f"ERROR: {self.name} permission denied"

        try:
            raw = await self.execute(validated)
        except Exception as exc:
            # Unrecoverable errors → disable tool for the rest of the process
            if _is_unrecoverable(exc):
                reason = str(exc)[:120]
                self.disable(reason)
                logger.warning("%s: disabled process-wide — %s", self.name, reason)
            else:
                logger.warning("%s: %s — %s", self.name, type(exc).__name__, exc)
            return f"ERROR: {self.name} failed: {exc}"

        return self.format_result(raw)

    # ── schema helpers ───────────────────────────────────────────

    def to_openai_schema(self) -> dict[str, Any]:
        """Return the tool definition in OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_anthropic_schema(self) -> dict[str, Any]:
        """Return the tool definition in Anthropic tool-use format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }
