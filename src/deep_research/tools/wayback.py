"""Wayback Machine lookup tool — historical snapshots via Firecrawl bridge.

Direct web.archive.org is unreachable from CN datacenter IPs, but
Firecrawl keyless can fetch the archive.org availability JSON.  This
tool is intentionally small: given a URL and an optional year, it finds
the closest archived snapshot and can fetch that snapshot's content.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

from deep_research.core.tool import BuildTool
from deep_research.tools.firecrawl_bridge import firecrawl_scrape, firecrawl_scrape_json

_AVAILABILITY_URL = "http://archive.org/wayback/available"


class WaybackLookupTool(BuildTool):
    """Look up a historical snapshot of a URL on the Wayback Machine."""

    name = "wayback_lookup"
    description = (
        "Look up a historical snapshot of a URL on the Wayback Machine. "
        "Use for old pages, old news, old graduation pages, archived official sites. "
        "Pass a URL and optionally a year/timestamp (e.g. 2002). "
        "Returns the closest archived snapshot; set fetch_content=true to also fetch the page text."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL or domain to look up, e.g. qau.edu.ye/news"},
            "timestamp": {"type": "string", "description": "Optional year or timestamp, e.g. 2002 or 20030601"},
            "fetch_content": {"type": "boolean", "description": "Whether to fetch the archived page content (default false)"},
            "limit": {"type": "integer", "description": "Max snapshots to return (default 1, max 3)"},
        },
        "required": ["url"],
    }

    async def validate_input(self, args: dict) -> dict:
        args.setdefault("timestamp", "")
        args.setdefault("fetch_content", False)
        args.setdefault("limit", 1)
        args["limit"] = min(max(int(args.get("limit", 1)), 1), 3)
        return args

    async def execute(self, args: dict) -> Any:
        url = args["url"]
        timestamp = str(args.get("timestamp") or "").strip()
        fetch_content = bool(args.get("fetch_content", False))
        limit = args["limit"]

        params = {"url": url}
        if timestamp:
            params["timestamp"] = timestamp

        query_url = f"{_AVAILABILITY_URL}?{urlencode(params)}"
        try:
            data = await firecrawl_scrape_json(
                query_url,
                timeout_ms=25000,
            )
        except Exception as exc:
            detail = str(exc) or repr(exc)
            return [{"error": f"wayback_lookup failed: {type(exc).__name__}: {detail}"}]

        snapshots = data.get("archived_snapshots") or {}
        closest = snapshots.get("closest") or {}
        if not closest or not closest.get("available"):
            return []

        results: list[dict] = []
        snap_url = closest.get("url", "")
        snap_ts = closest.get("timestamp", "")
        status = closest.get("status", "")
        if not snap_url:
            return []

        item = {
            "timestamp": snap_ts,
            "url": snap_url,
            "status": status,
            "original_url": url,
        }
        if fetch_content:
            try:
                page = await firecrawl_scrape(snap_url, timeout_ms=30000)
                item["content"] = (page.get("markdown") or "")[:5000]
            except Exception as exc:
                item["content_error"] = str(exc)[:200]
        results.append(item)
        return results[:limit]

    def format_result(self, raw: Any) -> str:
        if isinstance(raw, list):
            if not raw:
                return "No Wayback snapshot found."
            if isinstance(raw[0], dict) and "error" in raw[0]:
                return f"ERROR: {raw[0]['error']}"
            lines = []
            for i, r in enumerate(raw, 1):
                lines.append(f"{i}. Wayback snapshot")
                lines.append(f"   Timestamp: {r.get('timestamp', '?')}")
                lines.append(f"   URL: {r.get('url', 'N/A')}")
                if r.get("status"):
                    lines.append(f"   Status: {r['status']}")
                if r.get("content"):
                    lines.append(f"   Content: {r['content'][:1200]}")
                elif r.get("content_error"):
                    lines.append(f"   Content error: {r['content_error']}")
                lines.append("")
            return "\n".join(lines)
        return str(raw)


__all__ = ["WaybackLookupTool"]
