"""Patch: monkey-patch litellm.completion so Qwen thinking-mode responses
with null content but valid tool_calls or reasoning are fixed in-place on
the ModelResponse object.  This is reliable because all downstream code
(CrewAI included) reads the same object reference, unlike dict-based
callbacks that can be bypassed when objects are rebuilt from dicts."""

from __future__ import annotations

import litellm
from litellm.types.utils import ModelResponse

_original_completion = litellm.completion


def _patched_completion(*args, **kwargs) -> ModelResponse:
    response = _original_completion(*args, **kwargs)

    # Fix Qwen thinking-mode responses: content is None but useful data
    # lives in reasoning_content (LiteLLM attribute) or tool_calls.
    for choice in response.choices:
        msg = choice.message

        if msg.content is not None:
            continue  # already fine

        if msg.tool_calls:
            # Valid tool-call response, just fill empty content
            msg.content = ""
        else:
            # No tool calls either — move reasoning into content
            reasoning = getattr(msg, "reasoning_content", None) or getattr(
                msg, "reasoning", None
            )
            if reasoning:
                msg.content = reasoning

    return response


litellm.completion = _patched_completion
