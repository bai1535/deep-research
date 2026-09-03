"""Search tools built on BuildTool."""

from __future__ import annotations

import asyncio
import base64
import re
from html import unescape
from typing import Any
from urllib.parse import quote_plus

import httpx

from deep_research.config import get_config
from deep_research.core.tool import (
    BuildTool,
    RATE_LIMIT_COOLDOWN,
    _is_rate_limited,
    in_backend_cooldown,
    set_backend_cooldown,
)
from deep_research.tools.firecrawl_bridge import firecrawl_search

_BING_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Full browser header set — Baidu's anti-bot scores header completeness
# (datacenter IPs trip the challenge with minimal headers).
_BAIDU_HEADERS = {
    "User-Agent": _BING_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.baidu.com/",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Upgrade-Insecure-Requests": "1",
}

_BING_RESULT_RE = re.compile(r'<li class="b_algo".*?</li>', re.DOTALL)
_BING_TITLE_RE = re.compile(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
_BING_SNIPPET_RE = re.compile(r'<p[^>]*>(.*?)</p>', re.DOTALL)

# Baidu result parsing
_BAIDU_TITLE_RE = re.compile(r'<h3[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
_BAIDU_ABSTRACT_RE = re.compile(r'<div class="c-abstract[^"]*"[^>]*>(.*?)</div>', re.DOTALL)


def _parse_baidu_results(html: str, max_results: int) -> list[dict]:
    """Extract (title, url, body) from Baidu search results HTML.

    Baidu wraps links as http://www.baidu.com/link?url=... (redirect
    wrappers) — kept as-is; web_fetch follows redirects.  Anti-bot pages
    are detected by the caller, not here.
    """
    results: list[dict] = []
    for href, title_raw in _BAIDU_TITLE_RE.findall(html):
        title = re.sub(r"<[^>]+>", " ", title_raw)
        title = re.sub(r"\s+", " ", title).strip()
        if not title:
            continue
        body = ""
        # snippet lives in a c-abstract div near the title — first match
        m = _BAIDU_ABSTRACT_RE.search(html[html.find(title_raw):html.find(title_raw) + 4000])
        if m:
            body = re.sub(r"<[^>]+>", " ", m.group(1))
            body = re.sub(r"\s+", " ", body).strip()[:300]
        results.append({"title": title, "url": href, "body": body})
        if len(results) >= max_results:
            break
    return results


_BING_CITE_RE = re.compile(r"<cite[^>]*>(.*?)</cite>", re.DOTALL)


def _clean_html_fragment(raw: str) -> str:
    """Strip tags, decode HTML entities and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _bing_cite_url(block: str) -> str:
    """Fallback: read the visible cite/domain when redirect decoding fails."""
    m = _BING_CITE_RE.search(block)
    if not m:
        return ""
    text = _clean_html_fragment(m.group(1))
    if not text:
        return ""
    # <strong>https://</strong>example.com becomes "https:// example.com"
    # after tag stripping — remove the space introduced around the scheme.
    text = re.sub(r"(https?://)\s+", r"\1", text)
    if text.startswith(("http://", "https://")):
        return text
    return "https://" + text


def _unpack_bing_url(href: str) -> str:
    """Decode Bing's /ck/ redirect wrapper back to the real URL.

    Bing wraps result links as https://www.bing.com/ck/a?...&u=a1<base64>
    where the base64 is the target URL (a1/a2 prefix = encoding version).
    The HTML also escapes every ``&`` as ``&amp;``, so unescape first or
    the ``u=`` parameter is never found.
    Falls back to the (unescaped) original href when decoding fails.
    """
    href = unescape(href)
    if "bing.com/ck" not in href and "bing.com/cc" not in href:
        return href
    m = re.search(r"[?&]u=([^&]+)", href)
    if not m:
        return href
    try:
        b64 = m.group(1)
        # Bing prefixes the payload with a version marker ("a1"/"a2")
        # that is NOT part of the base64 data — strip it before decoding.
        if b64[:2] in ("a1", "a2"):
            b64 = b64[2:]
        padded = b64 + "=" * (-len(b64) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8", "replace")
        if decoded.startswith("http"):
            return decoded
    except Exception:
        pass
    return href


def _parse_bing_results(html: str, max_results: int) -> list[dict]:
    """Extract (title, url, body) from cn.bing.com search results HTML."""
    results: list[dict] = []
    for block in _BING_RESULT_RE.findall(html):
        m = _BING_TITLE_RE.search(block)
        if not m:
            continue
        url = _unpack_bing_url(m.group(1))
        # If the redirect wrapper could not be decoded, fall back to the
        # visible cite/domain so downstream web_fetch still has a usable URL.
        if "bing.com/ck" in url or "bing.com/cc" in url:
            fallback = _bing_cite_url(block)
            if fallback:
                url = fallback
        title = _clean_html_fragment(m.group(2))
        if not title:
            continue
        pm = _BING_SNIPPET_RE.search(block)
        snippet = _clean_html_fragment(pm.group(1))[:300] if pm else ""
        results.append({"title": title, "url": url, "body": snippet})
        if len(results) >= max_results:
            break
    return results


def _looks_english(text: str) -> bool:
    """Heuristic: a query is probably English if most chars are ASCII."""
    if not text:
        return False
    ascii_chars = sum(1 for ch in text if ord(ch) < 128)
    return ascii_chars / len(text) > 0.8


class FirecrawlSearchTool(BuildTool):
    name = "firecrawl_search"
    description = "Search the web using Firecrawl API. Returns structured results with title, URL, and content."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "description": "Max results (default 5)"},
        },
        "required": ["query"],
    }

    async def validate_input(self, args: dict) -> dict:
        args.setdefault("limit", 5)
        return args

    async def execute(self, args: dict) -> Any:
        config = get_config()
        # Keyless Firecrawl free tier (borrowed from ModSearch): works even
        # without FIRECRAWL_API_KEY and is reachable from CN servers.
        if not config.firecrawl_api_key:
            try:
                return await firecrawl_search(query=args["query"], limit=args["limit"])
            except Exception as exc:
                return [{"error": f"firecrawl_search keyless failed: {exc}"}]

        # Shared Firecrawl backend cooldown (429 rate limit) — web_fetch's
        # Firecrawl scrape and this search tool hit the SAME API, so they
        # back off together rather than each agent re-hitting the limit.
        if in_backend_cooldown("firecrawl"):
            return [{"error": "firecrawl_search rate-limit cooldown — retry later"}]

        try:
            from firecrawl import Firecrawl
        except ImportError:
            return [{"error": "firecrawl-py not installed"}]

        def _sync_search():
            app = Firecrawl(api_key=config.firecrawl_api_key)
            return app.search(query=args["query"], limit=args["limit"])

        try:
            return await asyncio.to_thread(_sync_search)
        except Exception as exc:
            if _is_rate_limited(exc):
                set_backend_cooldown("firecrawl", RATE_LIMIT_COOLDOWN)
                return [{"error": f"firecrawl_search rate-limited: {exc}"}]
            raise

    def format_result(self, raw: Any) -> str:
        if isinstance(raw, list):
            if not raw:
                return "No results found."
            if isinstance(raw[0], dict) and "error" in raw[0]:
                return f"ERROR: {raw[0]['error']}"
        if hasattr(raw, "data"):
            results = raw.data or []
            if not results:
                return "No results found."
            lines = []
            for i, r in enumerate(results, 1):
                title = getattr(r, "title", "") or getattr(r, "name", "") or "No title"
                url = getattr(r, "url", "") or getattr(r, "link", "") or "N/A"
                content = getattr(r, "description", "") or getattr(r, "content", "") or ""
                lines.append(f"{i}. {title}")
                lines.append(f"   URL: {url}")
                lines.append(f"   {content[:300]}")
                lines.append("")
            return "\n".join(lines)
        return str(raw)


class BingSearchTool(BuildTool):
    """Search via cn.bing.com — the entry Chinese users reach directly.

    Free, no API key, works from mainland China (DuckDuckGo's backend is
    www.bing.com, which is unreachable/blocked from CN networks — this
    tool hits cn.bing.com instead, same index, same browser entry point).
    """

    name = "bing_search"
    description = (
        "Search the web via Bing China (cn.bing.com). Free, no API key. "
        "First choice for English queries, official docs, GitHub, and "
        "papers. Returns title, URL, and snippet."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Max results (default 5)"},
        },
        "required": ["query"],
    }

    async def validate_input(self, args: dict) -> dict:
        args.setdefault("max_results", 5)
        args["max_results"] = min(int(args.get("max_results", 5)), 10)
        return args

    async def execute(self, args: dict) -> Any:
        query = args["query"]
        max_results = args["max_results"]
        # For English-heavy queries, ask Bing China for English-market results.
        # This still uses cn.bing.com (the only Bing endpoint reachable from
        # CN datacenter IPs) but switches the result language/market so niche
        # English academic/historical facts are not drowned by Chinese pages.
        if _looks_english(query):
            url = (
                f"https://cn.bing.com/search?q={quote_plus(query)}"
                f"&count={max_results}&mkt=en-US&setlang=en&ensearch=1"
            )
            accept_language = "en-US,en;q=0.9,zh-CN;q=0.8"
        else:
            url = (
                f"https://cn.bing.com/search?q={quote_plus(query)}"
                f"&count={max_results}&mkt=zh-CN&setlang=zh-hans"
            )
            accept_language = "zh-CN,zh;q=0.9,en;q=0.8"
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(
                    url,
                    headers={
                        "User-Agent": _BING_UA,
                        "Accept-Language": accept_language,
                    },
                )
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            return [{"error": f"bing_search failed: {exc}"}]
        return _parse_bing_results(html, max_results)

    def format_result(self, raw: Any) -> str:
        if isinstance(raw, list):
            if not raw:
                return "No results found."
            if isinstance(raw[0], dict) and "error" in raw[0]:
                return f"ERROR: {raw[0]['error']}"
            lines = []
            for i, r in enumerate(raw, 1):
                lines.append(f"{i}. {r.get('title', 'No title')}")
                lines.append(f"   URL: {r.get('url', 'N/A')}")
                lines.append(f"   {r.get('body', '')[:300]}")
                lines.append("")
            return "\n".join(lines)
        return str(raw)


class BaiduSearchTool(BuildTool):
    """Search via Baidu — mainland-China native, no region-split index.

    cn.bing.com serves DIFFERENT indexes by client IP: datacenter IPs
    (Tencent Cloud) get a stale/regional index that misses brand-new
    models (verified: Qwen3.6-35B-A3B not found via cn.bing from the
    server, found from residential IPs).  Baidu is a mainland service —
    same results regardless of IP, and its index covers new Chinese
    content well.
    """

    name = "baidu_search"
    description = (
        "Search the web via Baidu (www.baidu.com). Free, no API key. "
        "First choice for Chinese queries and brand-new China-released "
        "products/content. Returns title, URL, and snippet."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Max results (default 5)"},
        },
        "required": ["query"],
    }

    async def validate_input(self, args: dict) -> dict:
        args.setdefault("max_results", 5)
        args["max_results"] = min(int(args.get("max_results", 5)), 10)
        return args

    async def execute(self, args: dict) -> Any:
        query = args["query"]
        max_results = args["max_results"]
        url = f"https://www.baidu.com/s?wd={quote_plus(query)}&rn={max_results}&ie=utf-8"
        try:
            async with httpx.AsyncClient(
                timeout=15, follow_redirects=True, headers=_BAIDU_HEADERS
            ) as client:
                # Warm-up: land on baidu.com first so the BAIDUID cookie
                # is set before the search request — datacenter IPs get
                # the anti-bot page far more often without it.
                try:
                    await client.get("https://www.baidu.com/")
                except Exception:
                    pass  # warm-up failure is not fatal
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            return [{"error": f"baidu_search failed: {exc}"}]
        # Anti-bot challenge pages must not be returned as "results"
        if "百度安全验证" in html or "wappass" in html:
            return [{"error": "baidu_search anti-bot challenge — retry later"}]
        return _parse_baidu_results(html, max_results)

    def format_result(self, raw: Any) -> str:
        if isinstance(raw, list):
            if not raw:
                return "No results found."
            if isinstance(raw[0], dict) and "error" in raw[0]:
                return f"ERROR: {raw[0]['error']}"
            lines = []
            for i, r in enumerate(raw, 1):
                lines.append(f"{i}. {r.get('title', 'No title')}")
                lines.append(f"   URL: {r.get('url', 'N/A')}")
                if r.get("body"):
                    lines.append(f"   {r['body']}")
                lines.append("")
            return "\n".join(lines)
        return str(raw)


class TavilySearchTool(BuildTool):
    name = "tavily_search"
    description = "Search the web using Tavily API. Structured results with title, URL, and content."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Max results (default 5)"},
        },
        "required": ["query"],
    }

    async def validate_input(self, args: dict) -> dict:
        args.setdefault("max_results", 5)
        return args

    async def execute(self, args: dict) -> Any:
        config = get_config()
        if not config.tavily_api_key:
            return [{"error": "TAVILY_API_KEY not set"}]

        try:
            from tavily import TavilyClient
        except ImportError:
            return [{"error": "tavily-python not installed"}]

        client = TavilyClient(api_key=config.tavily_api_key)
        response = client.search(query=args["query"], max_results=args["max_results"], search_depth="advanced")
        return response.get("results", [])

    def format_result(self, raw: Any) -> str:
        if isinstance(raw, list):
            if not raw:
                return "No results found."
            if isinstance(raw[0], dict) and "error" in raw[0]:
                return f"ERROR: {raw[0]['error']}"
            lines = []
            for i, r in enumerate(raw, 1):
                lines.append(f"{i}. {r.get('title', 'No title')}")
                lines.append(f"   URL: {r.get('url', 'N/A')}")
                lines.append(f"   {r.get('content', '')[:300]}")
                lines.append("")
            return "\n".join(lines)
        return str(raw)
