"""Context compressor — sliding window + LLM summary.

When an agent's message list grows beyond *max_messages*, older messages
are compressed into a short summary.  The model sees:

    [system, blackboard_context, SUMMARY, ...recent N messages...]

This keeps token usage bounded without losing earlier context.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import litellm

logger = logging.getLogger("deep_research.core.compressor")

SUMMARY_SYSTEM = (
    "You are a context summariser.  Condense the conversation below into "
    "a brief paragraph that preserves: key facts discovered, tool calls "
    "made and their results, decisions taken, and anything still unresolved. "
    "Write in the same language as the conversation.  Output ONLY the summary, "
    "no preamble."
)


@dataclass
class Compressor:
    """Sliding-window context compressor.

    Parameters
    ----------
    max_messages:
        When the message list exceeds this count, older messages are
        compressed into a summary.
    keep_recent:
        Number of most-recent messages to keep verbatim.
    api_base:
        LLM endpoint for summary generation (defaults to DeepSeek).
    api_key:
        API key for summary generation.
    """

    max_messages: int = 30
    keep_recent: int = 20
    summary_label: str = "summary"
    api_base: str = "https://api.deepseek.com/v1"
    api_key: str = ""

    async def compress(self, messages: list[dict]) -> list[dict]:
        """Return a compressed message list.

        If the list is short enough it is returned unchanged.
        Otherwise old messages are summarised — but the split point is
        adjusted so that a tool_calls assistant and its tool results are
        never separated.  This prevents orphaned tool messages.
        """
        if len(messages) <= self.max_messages:
            return messages

        split_point = max(0, len(messages) - self.keep_recent)

        # ── prevent orphans ───────────────────────────────────────
        # If the split separates a tool_calls assistant from its tool
        # results, push those orphaned tool messages back into *old*
        # so they are summarised together with their requester.
        while split_point < len(messages) and messages[split_point].get("role") == "tool":
            split_point += 1

        old = messages[:split_point]
        recent = messages[split_point:]

        summary_text = await self._summarise(old)
        summary_msg = {
            "role": "user",
            "content": f"[{self.summary_label}]: {summary_text}",
        }
        logger.debug("Compressed %d messages → summary (%d chars)", len(old), len(summary_text))
        return [summary_msg] + recent

    async def _summarise(self, messages: list[dict]) -> str:
        """Ask the LLM to summarise a block of old messages."""
        # Build a plain-text rendering of the conversation so the
        # summariser model (which has no tool context) can understand it.
        transcript = _render_for_summary(messages)
        if not transcript.strip():
            return "(empty)"

        try:
            response = await litellm.acompletion(
                model="openai/deepseek-chat",
                messages=[
                    {"role": "system", "content": SUMMARY_SYSTEM},
                    {"role": "user", "content": transcript},
                ],
                api_base=self.api_base,
                api_key=self.api_key,
                max_tokens=800,
                timeout=60,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("Summary generation failed: %s — falling back to truncation", exc)
            return "(summary unavailable)"


def _render_for_summary(messages: list[dict]) -> str:
    """Flatten a message list into a readable transcript."""
    lines: list[str] = []
    for m in messages:
        role = m.get("role", "?")
        content = m.get("content", "")
        tool_calls = m.get("tool_calls")
        tool_call_id = m.get("tool_call_id")

        if tool_calls:
            for tc in tool_calls:
                func = tc.get("function", {})
                lines.append(f"[{role}] called {func.get('name', '?')}({func.get('arguments', '')})")
        elif tool_call_id:
            lines.append(f"[tool result] {content[:300]}")
        elif content:
            lines.append(f"[{role}] {content[:500]}")
    return "\n".join(lines)
