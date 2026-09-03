"""Web fetch tool — multi-backend page extraction with source labels.

Reads URL content via a BACKEND CASCADE, matching the search layer's
"load by key" philosophy — no single vendor lock-in:

    1. Firecrawl scrape(url, formats=["markdown"])  — JS rendering, reads
       SPA/React pages that plain HTTP misses. 45s timeout.
    2. Tavily extract(urls=[url])                    — second backend when
       a Tavily key is configured; reads results[0].raw_content (markdown).
       30s timeout.
    3. httpx + real browser UA                      — last-resort raw HTML
       fetch (tags stripped in format_result).

Each backend is INDEPENDENT: Firecrawl failing never blocks Tavily,
Tavily failing never blocks httpx.  Every backend try/excepts itself and
returns None on failure; a missing API key skips the backend silently.
The source-credibility tag ([来源: xxx ★★★★]) is still injected by
execute; format_result only cleans the body text.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time

import httpx

from deep_research.config import get_config
from deep_research.core.tool import (
    BuildTool,
    RATE_LIMIT_COOLDOWN,
    _is_rate_limited,
    _is_unrecoverable,
    disable_tool_key,
    in_backend_cooldown,
    is_tool_key_disabled,
    set_backend_cooldown,
)
from deep_research.tools.firecrawl_bridge import firecrawl_scrape

logger = logging.getLogger("deep_research.tools.web_fetch")

_TAG_RE = re.compile(r"<[^>]+>")
# Blocks whose CONTENT is noise, not content — strip these BEFORE the
# tag-removal pass, otherwise `<script>var x=…</script>` would leave the
# JS text in the "body".  Applied to the httpx fallback path only
# (Firecrawl/Tavily already produce clean markdown).
_BLOCK_RE = re.compile(
    r"<(script|style|noscript|template|svg|nav|header|footer|aside|iframe|form)"
    r"[^>]*>.*?</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# Source-tag prefix injected by execute ("[来源: 学术论文 ★★★★ | firecrawl]\n")
_PREFIX_RE = re.compile(r"^\[来源: [^\]]+\]\n")

# Real-ish browser UA — some sites 403 plain bot UAs; this is only a
# last-resort backend, so a modest UA is the right trade.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

FIRECRAWL_TIMEOUT = 45   # seconds, wrapped around asyncio.to_thread
TAVILY_TIMEOUT = 30
HTTPX_TIMEOUT = 30


# ── URL credibility classification ─────────────────────────────────
# Ordered by priority — first match wins.
_SOURCE_PATTERNS: list[tuple[str, str, str]] = [
    # (regex pattern, label, credibility stars)
    # Academic / peer-reviewed
    (r"(arxiv\.org|eprint\.iacr\.org)", "学术论文", "★★★★"),
    (r"(\.edu|\.ac\.[a-z]{2})/(~|pub|research|papers|thesis)", "学术机构", "★★★★"),
    (r"(scholar\.google\.|semanticscholar\.org|researchgate\.net)", "学术索引", "★★★"),
    (r"(dl\.acm\.org|ieeexplore\.ieee\.org|link\.springer\.com|sciencedirect\.com|nature\.com|science\.org|cell\.com|pnas\.org)", "学术期刊/会议", "★★★★"),
    (r"proceedings\.(neurips\.cc|mlr\.press|aclanthology\.org)", "学术会议论文集", "★★★★"),
    # Government / standards
    (r"\.gov\.(cn|uk|au|ca|jp|de|fr|eu|us)", "政府机构", "★★★★"),
    (r"(\.gov|\.mil)(/|$)", "政府机构", "★★★★"),
    (r"(fipa\.org|w3\.org|ietf\.org|rfc-editor\.org|iso\.org|ieee\.org/standards)", "国际标准组织", "★★★★"),
    # Official documentation
    (r"(docs\.|documentation\.|readthedocs\.io|readthedocs\.org|devdocs\.io)", "官方文档", "★★★★"),
    (r"github\.com/[^/]+/[^/]+/(wiki|blob|tree)/", "项目文档/源码", "★★★"),
    # GitHub repos — BEFORE the .com catch-all, which would otherwise
    # bucket github.com/org/repo into "商业网站 ★★" (order bug found in test)
    (r"github\.com/[^/]+/[^/]+$", "开源仓库", "★★★"),
    # Industry / analyst reports
    (r"(gartner\.com|forrester\.com|mckinsey\.com|deloitte\.com|pwc\.com|bcg\.com|accenture\.com)", "行业分析报告", "★★★"),
    (r"(aws\.amazon\.com/blogs|cloud\.google\.com/blog|azure\.microsoft\.com/blog|engineering\.(meta|netflix|uber|spotify|airbnb)\.com)", "科技公司工程博客", "★★★"),
    # Major news outlets — placed BEFORE the generic .com catch-all, which
    # otherwise buckets any unmatched .com into "商业网站 ★★" (that rule is
    # intentionally broad; it is the last resort, not the norm).
    (r"(reuters\.com|bloomberg\.com|apnews\.com|ft\.com|nytimes\.com|washingtonpost\.com|theguardian\.com|economist\.com|wsj\.com|bbc\.com/news|cnn\.com|techcrunch\.com|theverge\.com|wired\.com|ars technica|arstechnica\.com)", "权威媒体", "★★★"),
    # Community / social — BEFORE the .com catch-all, which would otherwise
    # bucket reddit/ycombinator/stackoverflow into "商业网站 ★★"
    (r"(reddit\.com|news\.ycombinator\.com|stackoverflow\.com|stackexchange\.com|quora\.com)", "社区讨论", "★★"),
    (r"(medium\.com|substack\.com|dev\.to|hashnode\.dev|towardsdatascience\.com)", "个人/自媒体", "★★"),
    (r"(wikipedia\.org|wiki\.|britannica\.com)", "百科", "★★★"),
    # Product / company pages — the generic .com catch-all (last resort)
    (r"(\.com|\.cn|\.io|\.ai)(/|$)", "商业网站/产品页", "★★"),
]


def _classify_url(url: str) -> tuple[str, str]:
    """Classify a URL's source type and credibility.

    Returns (source_label, stars_string).
    """
    for pattern, label, stars in _SOURCE_PATTERNS:
        if re.search(pattern, url):
            return label, stars
    return "未知来源", "★"


def classify_url(url: str) -> str:
    """Return a human-readable source-credibility tag, e.g. "[学术论文 ★★★★]".

    Public wrapper around _classify_url — used by the scorer/verifier to
    surface source grading alongside the bare URLs stored on each research
    card (web_fetch injects this tag into fetched pages, but the researcher
    only persists the URL).
    """
    label, stars = _classify_url(url)
    return f"[{label} {stars}]"


# Extra markers beyond core._is_unrecoverable — SDK billing wording varies
# ("insufficient credits", "key expired", "payment required").  NOTE:
# "rate limit" is deliberately NOT here — 429 is transient (fix #B), it
# must degrade for that call and retry next time, not trip the breaker.
_UNRECOVERABLE_EXTRA = ("expired", "credit", "payment")


def _extract_status(result: object) -> int | None:
    """Firecrawl SDK HTTP status, across version AND type shapes.

    Top-level .statusCode (newer SDKs); .metadata.statusCode where
    metadata may be a dict OR a Pydantic/dataclass object (fix #2) —
    `getattr` handles both.
    """
    try:
        s = getattr(result, "statusCode", None)
        if s is not None:
            return int(s)
        meta = getattr(result, "metadata", None)
        if meta is not None:
            s = getattr(meta, "statusCode", None)  # object-shaped metadata
            if s is None and isinstance(meta, dict):
                s = meta.get("statusCode")
            if s is not None:
                return int(s)
    except (TypeError, ValueError):
        pass
    return None


def _decode_content(content: bytes, charset: str | None) -> str:
    """Decode page bytes without mangling Chinese encodings.

    Order: declared charset (if any) → utf-8 → gb18030 (GBK superset,
    decodes essentially every Chinese encoding).  `replace` only as a
    last resort so garbage bytes never raise.
    """
    try:
        return content.decode(charset or "utf-8")
    except (UnicodeDecodeError, LookupError):
        return content.decode("gb18030", errors="replace")


class WebFetchTool(BuildTool):
    name = "web_fetch"

    # Circuit breakers per INSTANCE, not per class (fix #A round 2):
    # with the web API running parallel runs, a class-level breaker meant
    # one run's Firecrawl quota error skipped Firecrawl for every other
    # run too.  registry.create_agent deep-copies tools per agent, so each
    # agent's WebFetchTool carries its own breaker state and one run's
    # failure cannot pollute another.
    # Semantics: opens on UNRECOVERABLE failure (quota/auth/invalid key),
    # stays open for _breaker_cooldown, then HALF-OPENS — the next call
    # probes again with a SHORT timeout (fix #B: a dead key must not hold
    # a thread-pool slot for 45s every 5 minutes).  Success resets it;
    # failure re-opens it.  Transient errors (5xx/timeout/DNS/429) never
    # trip it — degrade this call, retry next.
    _breaker_cooldown = 300.0   # seconds; after this the breaker half-opens
    _probe_timeout = 15.0       # half-open probes use a short timeout
    _empty_result_limit = 5     # SAME url empty N× (fix #1) → trip (page-level)
    _service_empty_limit = 15   # ANY url empty N× total (fix round-6/7) → trip
                                # (service-level: a degraded Firecrawl
                                # returns empty for every url — the per-url
                                # streak never fires because urls keep
                                # changing, so a second, url-agnostic
                                # counter covers that failure mode.
                                # Round-7: page-level statuses (403/404
                                # login walls) are EXCLUDED from the total,
                                # so 15 is reachable only by genuine
                                # service degradation, not academic
                                # login-wall diversity.)

    def __init__(self) -> None:
        self._firecrawl_breaker_open_at: float | None = None
        self._tavily_breaker_open_at: float | None = None
        # Fix #1: empty-result streaks are PER-URL — different URLs being
        # empty (login walls, PDFs, JS redirects) is page diversity, not
        # service degradation.  Only the SAME url coming back empty
        # repeatedly counts toward the breaker.
        self._firecrawl_empty_url: str | None = None
        self._firecrawl_empty_streak = 0
        self._tavily_empty_url: str | None = None
        self._tavily_empty_streak = 0
        # Fix round-6: TOTAL empty counter (url-agnostic, only reset by
        # SUCCESS) — catches service-level degradation that the per-url
        # streak structurally misses (every url empty → urls keep
        # changing → per-url streak never accumulates).
        self._firecrawl_total_empty = 0
        self._tavily_total_empty = 0

    # ── breaker helpers (instance-scoped) ─────────────────────────

    def _breaker_open(self, attr: str) -> bool:
        """True while the breaker's cooldown is still running."""
        t = getattr(self, attr, None)
        return t is not None and (time.time() - t) < self._breaker_cooldown

    def _breaker_trip(self, attr: str) -> None:
        """Open the breaker (record the trip timestamp)."""
        setattr(self, attr, time.time())

    def _breaker_close(self, attr: str) -> None:
        """Reset the breaker after a successful HALF-OPEN probe.

        Fix #2: only a probe that started AFTER the cooldown elapsed may
        close the breaker.  A concurrent probe B succeeding while probe A
        just tripped (timestamp=now) must NOT erase A's trip — without
        this check, close() would unconditionally clear the other
        probe's fresh trip and the failure would go unreported.
        """
        t = getattr(self, attr, None)
        if t is None:
            return  # already closed — nothing to do
        if (time.time() - t) >= self._breaker_cooldown:
            setattr(self, attr, None)

    def _record_backend_failure(self, backend: str, exc: Exception) -> None:
        """Classify a backend failure; disable or cooldown the backend.

        Unrecoverable (quota/auth/invalid key) → PERMANENT process-wide
        disable — every agent's instance stops trying this backend, so a
        dead key isn't re-probed by each of the parallel researchers.
        Rate limit (429) → short process-wide cooldown so parallel agents
        back off together instead of each re-hitting the limit.  Other
        transient (5xx/timeout/DNS) → warning only, degrade this call.
        """
        msg = str(exc).lower()
        if _is_unrecoverable(exc) or any(m in msg for m in _UNRECOVERABLE_EXTRA):
            disable_tool_key(backend, str(exc)[:120])
            logger.error("%s UNRECOVERABLE — disabled process-wide: %s", backend, exc)
        elif _is_rate_limited(exc):
            set_backend_cooldown(backend, RATE_LIMIT_COOLDOWN)
            logger.warning(
                "%s rate-limited — cooldown %.0fs (process-wide): %s",
                backend, RATE_LIMIT_COOLDOWN, exc,
            )
        else:
            logger.warning("%s failed: %s", backend, exc)

    # ── empty-result state helpers ────────────────────────────────

    def _reset_firecrawl_empty(self) -> None:
        self._firecrawl_empty_streak = 0
        self._firecrawl_empty_url = None
        self._firecrawl_total_empty = 0

    def _reset_tavily_empty(self) -> None:
        self._tavily_empty_streak = 0
        self._tavily_empty_url = None
        self._tavily_total_empty = 0
    description = (
        "Fetch and read the text content of a web page by URL. "
        "Results include a source credibility tag."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
        },
        "required": ["url"],
    }

    async def validate_input(self, args: dict) -> dict:
        url = args.get("url", "")
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL scheme: {url}")
        return args

    async def execute(self, args: dict) -> str:
        url = args["url"]
        label, stars = _classify_url(url)

        content, backend = "", ""
        for fn, name in (
            (self._fetch_firecrawl, "firecrawl"),
            (self._fetch_tavily, "tavily"),
            (self._fetch_httpx, "httpx"),
        ):
            try:
                result = await fn(url)
            except Exception as exc:  # defensive: a backend must never kill the chain
                # Fix #D: unrecaught backend exceptions go through the
                # same classifier — never silently absorbed
                self._record_backend_failure(name, exc)
                result = None
            if result:
                content, backend = result, name
                logger.info("web_fetch %s ok (%d chars) for %s", name, len(content), url)
                break

        if not content:
            return f"[来源: {label} {stars}]\nERROR: all fetch backends failed for {url}"

        # Source credibility tag first — the LLM sees it before the body.
        return f"[来源: {label} {stars} | {backend}]\n{content}"

    # ── backend 1: Firecrawl scrape (JS-rendered markdown) ─────────

    async def _fetch_firecrawl(self, url: str) -> str | None:
        if is_tool_key_disabled("firecrawl") or in_backend_cooldown("firecrawl"):
            return None  # process-wide disable/cooldown — logged at classification time
        if self._breaker_open("_firecrawl_breaker_open_at"):
            return None  # cooldown running — already logged at ERROR
        config = get_config()
        if not config.firecrawl_api_key:
            # Keyless Firecrawl free tier (ModSearch approach): reachable
            # from CN servers without any API key.
            try:
                page = await firecrawl_scrape(url, timeout_ms=FIRECRAWL_TIMEOUT * 1000)
            except Exception as exc:
                self._record_backend_failure("firecrawl", exc)
                return None
            md = (page.get("markdown") or "").strip()
            if md:
                return md
            return None

        try:
            from firecrawl import Firecrawl
        except ImportError:
            return None

        def _sync() -> object:
            # Constructor + call both inside the thread (a slow/key-checking
            # constructor must not block the event loop).
            app = Firecrawl(api_key=config.firecrawl_api_key)
            return app.scrape(url=url, formats=["markdown"])

        # Fix #B: half-open probes use a SHORT timeout — a dead key must
        # not hold a thread-pool slot for 45s every cooldown period.
        timeout = self._probe_timeout if self._firecrawl_breaker_open_at is not None else FIRECRAWL_TIMEOUT
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_sync), timeout=timeout
            )
        except Exception as exc:
            self._record_backend_failure("firecrawl", exc)
            return None

        # SDK shapes vary by version: top-level .markdown or .data.markdown
        md = getattr(result, "markdown", "") or ""
        if not md and hasattr(result, "data"):
            md = getattr(result.data, "markdown", "") or ""
        if md:
            self._reset_firecrawl_empty()  # service recovered
            self._breaker_close("_firecrawl_breaker_open_at")  # half-open probe OK
            return str(md).strip()
        # Fix #C + #1 + round-7/10: SDK answered but EMPTY.
        # (a) Half-open probe: page-level statuses (login walls 200+empty,
        #     403/404) are NOT probe failures — the page is the problem,
        #     the service may well be back.  Only a 5xx or status-less
        #     empty body means the service is still down → re-trip.
        #     (fix #2: exclusion must run BEFORE the probe re-trip, else
        #     probing a login wall would mis-trip the breaker.)
        if self._firecrawl_breaker_open_at is not None:
            status = _extract_status(result)
            if status is not None:
                # page-level (target site responded — incl. 5xx target
                # pages: a dead TARGET is not a dead Firecrawl) — keep
                # half-open, probe next time.
                logger.debug(
                    "firecrawl half-open probe: target status %s for %s — keeping half-open",
                    status, url,
                )
                return None
            logger.error("firecrawl half-open probe EMPTY — re-tripping")
            self._reset_firecrawl_empty()
            self._breaker_trip("_firecrawl_breaker_open_at")
            return None
        # (b) Page-level statuses (fix #1 round-9/11): scrape()'s
        # statusCode is the TARGET PAGE's HTTP status (Firecrawl is a
        # fetching proxy), so ANY status — 200+empty login walls, 403,
        # 404, even a 500 from a dead target site — means the target
        # responded; that's a page problem, not a service problem.
        # Firecrawl API failures (401/429/5xx of the API itself) come
        # back as exceptions → _record_backend_failure (visible there).
        # Only a body with NO status at all (service blackhole / old SDK
        # shape) feeds the service-level counter.
        if _extract_status(result) is not None:
            return None
        # (c) Signal 1 — per-URL streak: only the SAME url keeps coming
        #     back empty (page-level failure).
        if url == self._firecrawl_empty_url:
            self._firecrawl_empty_streak += 1
        else:
            self._firecrawl_empty_url = url
            self._firecrawl_empty_streak = 1
        # (d) Signal 2 — total empty count (url-agnostic): a degraded
        #     service returns empty for EVERY url (no page-level status,
        #     just an empty body); urls keep changing so the per-url
        #     streak never accumulates.  Only resets on success.
        self._firecrawl_total_empty += 1
        if (self._firecrawl_empty_streak >= self._empty_result_limit
                or self._firecrawl_total_empty >= self._service_empty_limit):
            logger.error(
                "firecrawl EMPTY results — same-url streak=%d, total=%d — breaker open for %.0fs",
                self._firecrawl_empty_streak, self._firecrawl_total_empty,
                self._breaker_cooldown,
            )
            self._reset_firecrawl_empty()
            self._breaker_trip("_firecrawl_breaker_open_at")
        return None

    # ── backend 2: Tavily extract (raw_content markdown) ───────────

    async def _fetch_tavily(self, url: str) -> str | None:
        if is_tool_key_disabled("tavily") or in_backend_cooldown("tavily"):
            return None  # process-wide disable/cooldown — logged at classification time
        if self._breaker_open("_tavily_breaker_open_at"):
            return None  # cooldown running — already logged at ERROR
        config = get_config()
        if not config.tavily_api_key:
            return None
        try:
            from tavily import TavilyClient
        except ImportError:
            return None

        def _sync() -> dict:
            # Fix #2: construct INSIDE the thread — TavilyClient() may
            # make network calls; doing it in the async body would block
            # the event loop.
            client = TavilyClient(api_key=config.tavily_api_key)
            return client.extract(urls=[url])

        # Fix #B: half-open probes use a SHORT timeout
        timeout = self._probe_timeout if self._tavily_breaker_open_at is not None else TAVILY_TIMEOUT
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(_sync), timeout=timeout
            )
        except Exception as exc:
            self._record_backend_failure("tavily", exc)
            return None

        # Fix #3 (round-7): a MALFORMED response (not a dict) is still an
        # empty result — count it, otherwise Tavily's degradation path
        # has a permanent blind spot while Firecrawl's counts.
        if not isinstance(response, dict):
            if self._tavily_breaker_open_at is not None:
                logger.error("tavily half-open probe returned malformed response — re-tripping")
                self._reset_tavily_empty()
                self._breaker_trip("_tavily_breaker_open_at")
            else:
                self._tavily_total_empty += 1
                if self._tavily_total_empty >= self._service_empty_limit:
                    logger.error(
                        "tavily %d malformed/empty responses — breaker open for %.0fs",
                        self._tavily_total_empty, self._breaker_cooldown,
                    )
                    self._reset_tavily_empty()
                    self._breaker_trip("_tavily_breaker_open_at")
            return None
        results = response.get("results") or []
        if results:
            raw = results[0].get("raw_content") or ""
            if raw:
                self._reset_tavily_empty()  # service recovered
                self._breaker_close("_tavily_breaker_open_at")  # half-open probe OK
                return str(raw).strip()
        # Fix #C + #1 + round-6/9/10: per-URL streak + service-level total.
        # Page-level failures first: Tavily extract reports pages it could
        # not fetch in failed_results (login walls, PDFs).  Those are PAGE
        # problems, not service degradation.
        failed = response.get("failed_results") or []
        if failed:
            # (fix #2 round-10): a half-open probe hitting a failed page
            # is not a probe failure either — keep half-open, probe next.
            return None
        # Half-open probe: truly empty response → service still down,
        # re-trip immediately (fix #2).
        if self._tavily_breaker_open_at is not None:
            logger.error("tavily half-open probe EMPTY — re-tripping")
            self._reset_tavily_empty()
            self._breaker_trip("_tavily_breaker_open_at")
            return None
        if url == self._tavily_empty_url:
            self._tavily_empty_streak += 1
        else:
            self._tavily_empty_url = url
            self._tavily_empty_streak = 1
        self._tavily_total_empty += 1
        if (self._tavily_empty_streak >= self._empty_result_limit
                or self._tavily_total_empty >= self._service_empty_limit):
            logger.error(
                "tavily EMPTY results — same-url streak=%d, total=%d — breaker open for %.0fs",
                self._tavily_empty_streak, self._tavily_total_empty,
                self._breaker_cooldown,
            )
            self._reset_tavily_empty()
            self._breaker_trip("_tavily_breaker_open_at")
        return None

    # ── backend 3: plain httpx (real browser UA) ───────────────────

    async def _fetch_httpx(self, url: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": _BROWSER_UA})
                resp.raise_for_status()
                # Fix #3: explicit decode — resp.text silently falls back
                # to utf-8 when the page declares no charset, which mangles
                # GBK pages (common on Chinese sites).  Decode from bytes
                # with charset-hint → utf-8 → gb18030 (GBK superset).
                charset = getattr(resp, "charset_encoding", None)
                return _decode_content(resp.content, charset)
        except Exception as exc:
            logger.warning("httpx fetch failed: %s", exc)
            return None

    def format_result(self, raw: object) -> str:
        text = str(raw)
        # Fix #3: peel off the "[来源: ...]" prefix BEFORE cleaning and
        # truncation — it must not eat into the 8000-char body budget,
        # and it is re-attached unchanged at the end.
        prefix = ""
        m = _PREFIX_RE.match(text)
        if m:
            prefix = m.group(0)
            text = text[len(prefix):]
        # Fix #1: drop comment + script/style/nav blocks BEFORE tag removal,
        # so their inner text doesn't leak into the "body".  Harmless for
        # clean markdown (no such tags) — only the httpx HTML path benefits.
        text = _COMMENT_RE.sub(" ", text)
        text = _BLOCK_RE.sub(" ", text)
        text = _TAG_RE.sub(" ", text)
        if _TAG_RE.search(text):
            # Still contains tags → raw HTML soup: collapse everything.
            text = re.sub(r"\s+", " ", text).strip()
        else:
            # Clean markdown (Firecrawl/Tavily): collapse spaces but KEEP
            # newlines — paragraphs/lists are structure, not noise.
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text) > 8000:
            # Fix #3: keep head + tail — conclusions live at the END of
            # long articles, and a hard head-cut made researchers guess.
            head = text[:5500]
            tail = text[-2000:]
            omitted = len(text) - len(head) - len(tail)
            text = head + f"\n\n… [中间 {omitted} 字符省略] …\n\n" + tail
        return prefix + text
