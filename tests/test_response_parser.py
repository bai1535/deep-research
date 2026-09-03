"""Tests for the multi-strategy response parser."""

import pytest

from deep_research.response_parser import parse_json_response


def test_parse_normal_json():
    result = parse_json_response('{"a": 1, "b": "x"}', context="test")
    assert result.success
    assert result.data == {"a": 1, "b": "x"}


def test_parse_curly_double_quotes():
    raw = '{“entries”: [{“claim_index”: 0, “status”: “false”}]}'
    result = parse_json_response(raw, context="test")
    assert result.success
    assert result.data["entries"][0]["claim_index"] == 0
    assert result.data["entries"][0]["status"] == "false"


def test_parse_curly_quotes_inside_markdown_fence():
    raw = '```json\n{“a”: “中文内容”, “list”: [1, 2]}\n```'
    result = parse_json_response(raw, context="test")
    assert result.success
    assert result.data["a"] == "中文内容"
    assert result.data["list"] == [1, 2]


def test_parse_curly_single_quotes_inside_string_value():
    raw = '{"note": "他说‘你好’并且走了"}'
    result = parse_json_response(raw, context="test")
    assert result.success
    assert result.data["note"] == "他说‘你好’并且走了"


def test_parse_invalid_json_still_fails():
    raw = '{"a": }'
    result = parse_json_response(raw, context="test", log_raw_on_failure=False)
    assert not result.success
