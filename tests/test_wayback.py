"""Tests for Wayback lookup tool (offline: formatting/validation)."""

import pytest

from deep_research.tools.wayback import WaybackLookupTool


@pytest.mark.asyncio
async def test_validate_defaults():
    args = await WaybackLookupTool().validate_input({"url": "qau.edu.ye"})
    assert args["timestamp"] == ""
    assert args["fetch_content"] is False
    assert args["limit"] == 1


@pytest.mark.asyncio
async def test_validate_clamps_limit():
    tool = WaybackLookupTool()
    assert (await tool.validate_input({"url": "x", "limit": 99}))["limit"] == 3
    assert (await tool.validate_input({"url": "x", "limit": 0}))["limit"] == 1


def test_format_error():
    out = WaybackLookupTool().format_result([{"error": "boom"}])
    assert out.startswith("ERROR:")


def test_format_success():
    out = WaybackLookupTool().format_result([
        {"timestamp": "20090508074158", "url": "http://web.archive.org/web/20090508074158/http://www.qau.edu.ye/", "status": "200", "content": "old page"},
    ])
    assert "20090508074158" in out
    assert "web.archive.org" in out
