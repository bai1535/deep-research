"""Tests for the Firecrawl keyless bridge helpers (offline)."""

import pytest

from deep_research.tools.firecrawl_bridge import extract_json_from_markdown


def test_extract_json_from_plain_json_block():
    md = "```json\n{\"a\": 1}\n```"
    assert extract_json_from_markdown(md) == {"a": 1}


def test_extract_json_from_json_fence_without_lang():
    md = "```\n{\"b\": [1, 2]}\n```"
    assert extract_json_from_markdown(md) == {"b": [1, 2]}


def test_extract_json_from_plain_text():
    md = '{"c": "x"}'
    assert extract_json_from_markdown(md) == {"c": "x"}


def test_extract_json_invalid_raises():
    with pytest.raises(Exception):
        extract_json_from_markdown("```json\nnot json\n```")
