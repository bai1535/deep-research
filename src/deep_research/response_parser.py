"""Unified, multi-strategy response parser for LLM outputs.

This module is the SINGLE source of truth for extracting structured data from
raw model responses. Every crew uses it — no more duplicated, diverging
parse_json implementations.

Design principles:
1. Try strategies in order of reliability: direct JSON → fence-stripped →
   regex extraction → repair attempts → graceful failure.
2. Log every failure with enough context to debug, never swallow silently.
3. Return a ParseResult with metadata about which strategy succeeded,
   so callers can adjust retry logic accordingly.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("deep_research.parser")


@dataclass
class ParseResult:
    """Result of a parse attempt with metadata for diagnostics."""

    data: dict[str, Any] = field(default_factory=dict)
    success: bool = False
    strategy: str = "none"  # which strategy succeeded
    raw_preview: str = ""  # first 300 chars of input, for debugging
    errors: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.success


# ── Multi-language ReAct / thinking-pattern detection ──────────────────────

# Patterns that indicate the model is "thinking out loud" instead of
# producing a final answer. We use these for detection AND for content
# extraction — if we find JSON after these patterns, we still try to
# extract it rather than rejecting the whole output.
REACT_PATTERNS = [
    # English
    r"\bThought\s*:", r"\bAction\s*:", r"\bObservation\s*:",
    r"\bPlan\s*:", r"\bStep\s*\d+\s*:", r"\bFinal Answer\s*:",
    r"\bI (will|need to|should|must|can|am going to)\b",
    # Chinese
    r"思考\s*[：:]", r"行动\s*[：:]", r"观察\s*[：:]",
    r"最终答案\s*[：:]", r"步骤\s*\d+\s*[：:]",
    # Japanese
    r"思考\s*[：:]", r"行動\s*[：:]", r"観察\s*[：:]",
    # Generic bot-like prefixes
    r"^\s*(Sure|Okay|Let me|Here|I'll|First|Next|Now)\s*[,:.]",
]

# Patterns for extracting JSON blocks from mixed text
JSON_BLOCK_RE = re.compile(
    r"""
    \{                    # opening brace
    (?:[^{}]|\{[^{}]*\})*  # content (handles 1 level of nesting)
    \}                    # closing brace
    """,
    re.VERBOSE | re.DOTALL,
)

# Simple JSON-in-markdown fence
FENCE_RE = re.compile(
    r"```(?:json|JSON)?\s*\n?(.*?)\n?```",
    re.DOTALL,
)

# Alternative fence styles: ~~~, ''' (Python-style), <<< >>>
ALT_FENCE_RE = re.compile(
    r"(?:~~~|'''|<<<)\s*\n?(.*?)\n?(?:~~~|'''|>>>)",
    re.DOTALL,
)

# Common JSON syntax errors we can auto-repair
# 1. Trailing commas before } or ]
TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")
# 2. Single-quoted strings (risky — only try as last resort)
# 3. Unquoted keys: {key: "value"} → {"key": "value"}
UNQUOTED_KEY_RE = re.compile(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:')
# 4. Python-style None/True/False → JSON null/true/false
PYTHON_BOOL_RE = re.compile(r"\b(None)\b")
PYTHON_TRUE_RE = re.compile(r"\b(True)\b")
PYTHON_FALSE_RE = re.compile(r"\b(False)\b")


def _normalize_smart_quotes(text: str) -> str:
    """Replace typographic/Chinese quotes with ASCII quotes.

    LLMs sometimes emit full-width quotes (“ ”) around JSON keys/strings,
    which makes the output invalid JSON.  JSON only accepts ASCII double
    quotes as string delimiters, so normalize before any parse strategy.
    """
    return text.replace("“", '"').replace("”", '"')


def _extract_json_fences(raw: str) -> str | None:
    """Try to extract JSON from various code-fence styles.

    Returns the inner content (without fences) if found, None otherwise.
    """
    # Standard markdown fences
    m = FENCE_RE.search(raw)
    if m:
        return m.group(1).strip()

    # Alternative fences
    m = ALT_FENCE_RE.search(raw)
    if m:
        return m.group(1).strip()

    return None


def _extract_json_regex(raw: str) -> str | None:
    """Find the largest balanced JSON object in the raw text.

    Uses a character-by-character brace counter to find valid JSON blocks,
    which is far more robust than regex for arbitrary nesting.
    """
    # Find all { positions
    candidates = []
    i = 0
    while i < len(raw):
        if raw[i] == "{":
            depth = 0
            j = i
            while j < len(raw):
                ch = raw[j]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidates.append(raw[i : j + 1])
                        break
                elif ch == '"':
                    # Skip string contents
                    j += 1
                    while j < len(raw) and raw[j] != '"':
                        if raw[j] == "\\":
                            j += 1  # skip escaped char
                        j += 1
                j += 1
        i += 1

    if not candidates:
        return None

    # Return the longest valid candidate (most likely the actual JSON)
    # Sort by length descending, then try to parse
    candidates.sort(key=len, reverse=True)
    for cand in candidates:
        try:
            json.loads(cand)
            return cand
        except json.JSONDecodeError:
            continue

    # If none parse cleanly, return the longest anyway for repair attempts
    return candidates[0]


def _repair_json(raw: str) -> str | None:
    """Attempt to repair common JSON syntax errors.

    Only applies safe, unambiguous repairs. Returns repaired string
    or None if repair would be too risky.
    """
    repaired = raw.strip()

    # Remove Python-style booleans/None (only outside strings — simple approach)
    # We do safer replacements: only when they appear as standalone tokens
    repaired = PYTHON_TRUE_RE.sub("true", repaired)
    repaired = PYTHON_FALSE_RE.sub("false", repaired)
    repaired = PYTHON_BOOL_RE.sub("null", repaired)

    # Remove trailing commas (safe — always invalid in JSON)
    repaired = TRAILING_COMMA_RE.sub(r"\1", repaired)

    # Fix unquoted keys: {key: ...} → {"key": ...}
    # Only apply if we see unquoted keys (this is risky, do it last)
    if UNQUOTED_KEY_RE.search(repaired):
        repaired = UNQUOTED_KEY_RE.sub(r'\1"\2":', repaired)

    try:
        json.loads(repaired)
        return repaired
    except json.JSONDecodeError:
        pass

    # Try stripping comments (// and /* */ — common in LLM outputs)
    # Remove // comments (but not URLs)
    lines = repaired.split("\n")
    cleaned = []
    for line in lines:
        # Find // that isn't part of ://
        in_string = False
        for i, ch in enumerate(line):
            if ch == '"' and (i == 0 or line[i - 1] != "\\"):
                in_string = not in_string
            if not in_string and i < len(line) - 1 and line[i : i + 2] == "//":
                # Check it's not ://
                if i == 0 or line[i - 1] != ":":
                    line = line[:i]
                    break
        cleaned.append(line)
    repaired = "\n".join(cleaned)

    try:
        json.loads(repaired)
        return repaired
    except json.JSONDecodeError:
        return None


def _has_react_content(raw: str) -> bool:
    """Check if the raw text contains ReAct-style model-thinking content."""
    return any(re.search(p, raw, re.IGNORECASE) for p in REACT_PATTERNS)


def parse_json_response(
    raw: str,
    *,
    context: str = "",
    log_raw_on_failure: bool = True,
) -> ParseResult:
    """Parse JSON from an LLM response using multi-strategy extraction.

    Strategies are tried in order of reliability. The FIRST strategy that
    yields a non-empty dict wins.

    Args:
        raw: The raw text output from the model.
        context: Human-readable label for log messages (e.g. "orchestrator",
                 "verifier-round-2", "scorer").
        log_raw_on_failure: If True, log the full raw text on parse failure
                            (may be noisy for long outputs).

    Returns:
        ParseResult with .data, .success, and .strategy metadata.
    """
    raw_preview = raw[:300] if len(raw) > 300 else raw
    errors: list[str] = []

    if not raw or not raw.strip():
        logger.warning("[%s] Empty input to parse_json_response", context)
        return ParseResult(
            data={},
            success=False,
            strategy="empty_input",
            raw_preview="",
            errors=["Input was empty or whitespace-only"],
        )

    raw = raw.strip()
    raw = _normalize_smart_quotes(raw)

    # ── Strategy 1: Direct JSON parse ──────────────────────────────────
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data:
            logger.debug("[%s] Strategy 1 (direct parse) succeeded", context)
            return ParseResult(
                data=data,
                success=True,
                strategy="direct_json",
                raw_preview=raw_preview,
            )
        elif isinstance(data, dict):
            errors.append("Direct parse produced empty dict")
        else:
            errors.append(f"Direct parse produced {type(data).__name__}, not dict")
    except json.JSONDecodeError as e:
        errors.append(f"Direct parse failed: {e}")

    # ── Strategy 2: Markdown/alternative fence extraction ──────────────
    inner = _extract_json_fences(raw)
    if inner:
        try:
            data = json.loads(inner)
            if isinstance(data, dict):
                logger.debug("[%s] Strategy 2 (fence extraction) succeeded", context)
                return ParseResult(
                    data=data,
                    success=True,
                    strategy="fence_extraction",
                    raw_preview=raw_preview,
                )
            errors.append("Fence extraction produced non-dict result")
        except json.JSONDecodeError as e:
            errors.append(f"Fence extraction parse failed: {e}")

    # ── Strategy 3: Regex-based JSON object finder ─────────────────────
    extracted = _extract_json_regex(raw)
    if extracted:
        try:
            data = json.loads(extracted)
            if isinstance(data, dict):
                logger.debug("[%s] Strategy 3 (regex extraction) succeeded", context)
                return ParseResult(
                    data=data,
                    success=True,
                    strategy="regex_extraction",
                    raw_preview=raw_preview,
                )
            errors.append("Regex extraction produced non-dict result")
        except json.JSONDecodeError as e:
            errors.append(f"Regex extraction parse failed: {e}")
    else:
        errors.append("No JSON object found by regex extraction")

    # ── Strategy 4: Repair common JSON errors ──────────────────────────
    # Try repair on the best candidate we have so far
    candidate = extracted if extracted else inner if inner else raw
    repaired = _repair_json(candidate)
    if repaired:
        try:
            data = json.loads(repaired)
            if isinstance(data, dict):
                logger.debug("[%s] Strategy 4 (json repair) succeeded", context)
                return ParseResult(
                    data=data,
                    success=True,
                    strategy="json_repair",
                    raw_preview=raw_preview,
                )
            errors.append("Repair produced non-dict result")
        except json.JSONDecodeError as e:
            errors.append(f"Repair parse failed: {e}")
    else:
        errors.append("JSON repair did not produce valid JSON")

    # ── All strategies exhausted ───────────────────────────────────────
    if log_raw_on_failure:
        logger.error(
            "[%s] ALL parse strategies failed. Raw (first 1000 chars): %s",
            context,
            raw[:1000],
        )

    return ParseResult(
        data={},
        success=False,
        strategy="all_failed",
        raw_preview=raw_preview,
        errors=errors,
    )


def detect_react_text(raw: str) -> bool:
    """Check if the raw output contains model-thinking/ReAct patterns.

    Unlike the old binary check, this returns True even for non-English
    variants and partial matches, AND we still try to extract JSON from
    mixed output rather than rejecting wholesale.
    """
    return _has_react_content(raw)
