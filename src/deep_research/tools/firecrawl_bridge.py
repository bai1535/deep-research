"""Firecrawl bridge helpers — keyless-first search/scrape.

ModSearch's key insight is that Firecrawl has a keyless free tier
(`POST https://api.firecrawl.dev/v2/search` and `/v2/scrape` without an
API key).  From CN datacenter IPs this is often reachable even when
Wikipedia/Wikidata are not, so we use it as a transport bridge to those
knowledge bases.

These helpers are intentionally small and dependency-light (httpx only).
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

FIRECRAWL_DEFAULT_BASE = "https://api.firecrawl.dev"
DEFAULT_TIMEOUT_MS = 20_000

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def _headers(api_key: str | None = None) -> dict[str, str]:
    headers = {"content-type": "application/json"}
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    return headers


def extract_json_from_markdown(markdown: str) -> Any:
    """Extract a JSON object from a Firecrawl markdown code block."""
    text = (markdown or "").strip()
    m = _JSON_FENCE_RE.match(text)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


async def firecrawl_search(
    query: str,
    *,
    limit: int = 5,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    api_key: str | None = None,
    base_url: str = FIRECRAWL_DEFAULT_BASE,
) -> list[dict]:
    """Run Firecrawl search (keyless by default) and return web items."""
    url = f"{base_url.rstrip('/')}/v2/search"
    body = {
        "query": query,
        "limit": limit,
        "sources": ["web"],
        "timeout": timeout_ms,
    }
    async with httpx.AsyncClient(timeout=timeout_ms / 1000 + 5) as client:
        resp = await client.post(url, headers=_headers(api_key), json=body)
        if resp.status_code >= 400:
            detail = (resp.text or "").strip()[:300]
            raise RuntimeError(f"firecrawl search returned {resp.status_code}: {detail}")
        data = resp.json()

    items: list[dict] = []
    for r in (data.get("data", {}).get("web") or []):
        items.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("description", ""),
        })
    return items


async def firecrawl_scrape(
    url: str,
    *,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    api_key: str | None = None,
    base_url: str = FIRECRAWL_DEFAULT_BASE,
) -> dict:
    """Scrape one URL with Firecrawl (keyless by default), return markdown + metadata."""
    endpoint = f"{base_url.rstrip('/')}/v2/scrape"
    body = {
        "url": url,
        "formats": ["markdown", "links"],
        "onlyMainContent": True,
        "maxAge": 0,
        "storeInCache": False,
        "skipTlsVerification": False,
        "timeout": timeout_ms,
    }
    async with httpx.AsyncClient(timeout=timeout_ms / 1000 + 5) as client:
        resp = await client.post(endpoint, headers=_headers(api_key), json=body)
        if resp.status_code >= 400:
            detail = (resp.text or "").strip()[:300]
            raise RuntimeError(f"firecrawl scrape returned {resp.status_code}: {detail}")
        data = resp.json()

    page = data.get("data") or {}
    return {
        "markdown": page.get("markdown", ""),
        "metadata": page.get("metadata") or {},
        "links": page.get("links") or [],
    }


async def firecrawl_scrape_json(
    url: str,
    *,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    api_key: str | None = None,
    base_url: str = FIRECRAWL_DEFAULT_BASE,
) -> Any:
    """Scrape a URL that returns JSON and parse it from the markdown code block."""
    page = await firecrawl_scrape(
        url,
        timeout_ms=timeout_ms,
        api_key=api_key,
        base_url=base_url,
    )
    return extract_json_from_markdown(page["markdown"])


__all__ = [
    "firecrawl_search",
    "firecrawl_scrape",
    "firecrawl_scrape_json",
    "extract_json_from_markdown",
]
