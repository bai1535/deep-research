"""Final-answer extractor.

The deep-research pipeline produces a long Markdown report.  For
benchmarks such as BrowseComp-Plus, and for quick user-facing answers,
we also want a short, self-contained final answer.  This module
deterministically extracts the most answer-like section from the
generated report and stores it in evidence.json.
"""

from __future__ import annotations

import re

# The editor template uses "## 1. 直接回答" as the most answer-like section.
# We also accept common variants.
_SECTION_HEADINGS = [
    re.compile(r"^##\s*1\.\s*直接回答\s*$", re.MULTILINE),
    re.compile(r"^##\s*直接回答\s*$", re.MULTILINE),
    re.compile(r"^##\s*1\.\s*Direct Answer\s*$", re.MULTILINE),
    re.compile(r"^##\s*执行摘要\s*$", re.MULTILINE),
    re.compile(r"^##\s*Executive Summary\s*$", re.MULTILINE),
]

_HEADING_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_MD_ITALIC_RE = re.compile(r"\*([^*]+)\*")
_WS_RE = re.compile(r"\s+")


def _clean_markdown(text: str) -> str:
    """Strip common Markdown formatting and collapse whitespace."""
    text = _MD_LINK_RE.sub(r"\1", text)
    text = _MD_BOLD_RE.sub(r"\1", text)
    text = _MD_ITALIC_RE.sub(r"\1", text)
    # Remove list markers, blockquote markers, and image syntax leftovers.
    text = re.sub(r"(?m)^\s*([-*+]|\d+\.)\s+", "", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def _section_text(report: str, heading: re.Pattern[str]) -> str:
    """Return text after a heading until the next Markdown heading."""
    m = heading.search(report)
    if not m:
        return ""
    start = m.end()
    nxt = _HEADING_RE.search(report, start)
    end = nxt.start() if nxt else len(report)
    return report[start:end].strip()


def extract_final_answer(report_text: str, max_chars: int = 800) -> str:
    """Extract a concise final answer from a Markdown report.

    Priority:
      1. "## 1. 直接回答" (the editor's mandated answer section)
      2. "## 直接回答" / "## 1. Direct Answer"
      3. "## 执行摘要" / "## Executive Summary"
      4. The first non-empty paragraph after the title.

    Returns cleaned plain text, truncated to *max_chars*.
    """
    if not report_text:
        return ""

    for pattern in _SECTION_HEADINGS:
        text = _section_text(report_text, pattern)
        if text:
            cleaned = _clean_markdown(text)
            if cleaned:
                return cleaned[:max_chars]

    # Fallback: first non-empty paragraph after the first heading.
    lines = [ln.strip() for ln in report_text.splitlines() if ln.strip()]
    if lines:
        # Skip the H1 title and any metadata line directly under it.
        body_start = 1 if lines[0].startswith("#") else 0
        for line in lines[body_start:]:
            if line.startswith("#"):
                continue
            cleaned = _clean_markdown(line)
            if cleaned:
                return cleaned[:max_chars]

    cleaned = _clean_markdown(report_text)
    return cleaned[:max_chars] if cleaned else ""


__all__ = ["extract_final_answer"]
