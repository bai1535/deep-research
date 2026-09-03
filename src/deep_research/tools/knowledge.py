"""Knowledge-base tools: Wikipedia search + Wikidata entity lookup.

These complement the general-purpose search engines with structured,
curated fact sources.  They are free and need no API key, but the
public endpoints may be unreachable from some networks (CN datacenter
IPs); failures are returned as normal tool errors so the agent can
fall back to bing/baidu/web_fetch.

Both tools follow the same contract as search.py:
    success -> [{"title"/"label", "url", ...}, ...]
    failure -> [{"error": "..."}]
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote

from deep_research.core.tool import BuildTool
from deep_research.tools.firecrawl_bridge import firecrawl_search, firecrawl_scrape_json

_MAX_RESULTS = 5

# Common Wikidata properties whose labels are stable and useful to an LLM.
# This is intentionally a small curated map; raw property IDs are still
# available through key_facts for less common properties.
_WIKIDATA_PROPERTY_LABELS: dict[str, str] = {
    "P31": "instance of",
    "P279": "subclass of",
    "P17": "country",
    "P131": "located in the administrative territorial entity",
    "P569": "date of birth",
    "P570": "date of death",
    "P571": "inception",
    "P576": "dissolved, abolished or demolished",
    "P580": "start time",
    "P582": "end time",
    "P856": "official website",
    "P106": "occupation",
    "P108": "employer",
    "P69": "educated at",
    "P19": "place of birth",
    "P20": "place of death",
    "P21": "sex or gender",
    "P27": "country of citizenship",
    "P36": "capital",
    "P37": "official language",
    "P38": "currency",
    "P39": "position held",
    "P40": "child",
    "P50": "author",
    "P57": "director",
    "P58": "screenwriter",
    "P161": "cast member",
    "P175": "performer",
    "P577": "publication date",
    "P407": "language of work or name",
    "P112": "founded by",
    "P138": "named after",
    "P170": "creator",
    "P178": "operator",
    "P159": "headquarters location",
    "P176": "manufacturer",
    "P413": "position played on team",
    "P54": "member of sports team",
    "P641": "sport",
    "P625": "coordinate location",
    "P2048": "height",
    "P2049": "width",
    "P1082": "population",
    "P2044": "elevation above sea level",
    "P1448": "official name",
    "P361": "part of",
    "P527": "has part(s)",
    "P749": "parent organization",
    "P155": "follows",
    "P156": "followed by",
}

_SUPPORTED_WIKI_LANGS = {"en", "zh", "simple", "de", "fr", "es", "ru", "ja"}


def _looks_english(text: str) -> bool:
    """Heuristic: a query is probably English if most chars are ASCII."""
    if not text:
        return False
    ascii_chars = sum(1 for ch in text if ord(ch) < 128)
    return ascii_chars / len(text) > 0.8


def _strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or "")).strip()


class WikipediaSearchTool(BuildTool):
    """Search Wikipedia and return article titles, URLs, and intros.

    Uses Firecrawl's keyless search/scrape as a transport bridge so it
    works from CN servers where direct wikipedia.org is blocked.
    """

    name = "wikipedia_search"
    description = (
        "Search Wikipedia (default English, auto-switches to Chinese for Chinese queries) "
        "and return article titles, URLs, and introductory extracts. "
        "Free, no API key. Best for entity facts, official names, dates, people, places, "
        "and background knowledge. Returns title, URL, snippet, and extract."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query or article title"},
            "lang": {"type": "string", "description": "Wikipedia language code: en, zh, simple, de, fr, es, ru, ja (default auto)"},
            "limit": {"type": "integer", "description": "Max results (default 3, max 5)"},
        },
        "required": ["query"],
    }

    async def validate_input(self, args: dict) -> dict:
        args.setdefault("limit", 3)
        args["limit"] = min(max(int(args.get("limit", 3)), 1), _MAX_RESULTS)
        return args

    async def execute(self, args: dict) -> Any:
        query = args["query"]
        limit = args["limit"]
        lang = str(args.get("lang") or "").strip() or ("zh" if not _looks_english(query) else "en")
        if lang not in _SUPPORTED_WIKI_LANGS:
            lang = "en"

        try:
            search_items = await firecrawl_search(
                f"site:{lang}.wikipedia.org {query}",
                limit=limit,
            )
        except Exception as exc:
            detail = str(exc) or repr(exc)
            return [{"error": f"wikipedia_search failed: {type(exc).__name__}: {detail}"}]

        wiki_items = [
            it for it in search_items
            if "wikipedia.org" in (it.get("url") or "")
        ] or search_items

        results: list[dict] = []
        for item in wiki_items[:limit]:
            title = _strip_html(item.get("title", ""))[:300]
            url = item.get("url", "")
            snippet = _strip_html(item.get("snippet", ""))[:300]
            extract = ""
            if url and "wikipedia.org" in url:
                try:
                    page_title = title.replace(" ", "_")
                    rest_url = (
                        f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
                        f"{quote(page_title, safe=':()')}"
                    )
                    summary = await firecrawl_scrape_json(rest_url)
                    title = _strip_html(summary.get("title") or title)[:300]
                    extract = _strip_html(summary.get("extract") or "")[:600]
                    if not snippet:
                        snippet = _strip_html(summary.get("description") or "")[:300]
                    desktop = (summary.get("content_urls") or {}).get("desktop") or {}
                    url = desktop.get("page") or url
                except Exception:
                    pass
            results.append({
                "title": title,
                "url": url,
                "snippet": snippet,
                "extract": extract,
            })
        return results

    def format_result(self, raw: Any) -> str:
        if isinstance(raw, list):
            if not raw:
                return "No Wikipedia results found."
            if isinstance(raw[0], dict) and "error" in raw[0]:
                return f"ERROR: {raw[0]['error']}"
            lines = []
            for i, r in enumerate(raw, 1):
                lines.append(f"{i}. {r.get('title', 'No title')}")
                lines.append(f"   URL: {r.get('url', 'N/A')}")
                if r.get("extract"):
                    lines.append(f"   {r['extract']}")
                elif r.get("snippet"):
                    lines.append(f"   {r['snippet']}")
                lines.append("")
            return "\n".join(lines)
        return str(raw)


def _wikidata_claim_value(mainsnak: dict) -> str:
    """Render a Wikidata mainsnak's value as a short human-readable string."""
    if not mainsnak:
        return ""
    datavalue = mainsnak.get("datavalue") or {}
    value = datavalue.get("value")
    datatype = mainsnak.get("datatype", "")

    if datatype == "wikibase-item" and isinstance(value, dict):
        return str(value.get("id") or "")
    if datatype == "time" and isinstance(value, dict):
        t = str(value.get("time") or "")
        m = re.match(r"[+-](\d{4,})-(\d{2})-(\d{2})", t)
        if m:
            year, month, day = m.groups()
            return f"{int(year)}-{month}-{day}"
        return t
    if datatype == "quantity" and isinstance(value, dict):
        amount = str(value.get("amount") or "")
        if amount.startswith("+"):
            amount = amount[1:]
        unit = str(value.get("unit") or "")
        qid = unit.rsplit("/", 1)[-1] if unit else ""
        if qid and qid not in ("1", "Q1"):
            return f"{amount} {qid}"
        return amount
    if datatype == "monolingualtext" and isinstance(value, dict):
        return str(value.get("text") or "")
    if datatype in ("string", "external-id", "url"):
        return str(value or "")
    if isinstance(value, dict):
        if "latitude" in value and "longitude" in value:
            return f"{value.get('latitude')},{value.get('longitude')}"
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value)
    return str(value) if value is not None else ""


class WikidataLookupTool(BuildTool):
    """Look up an entity on Wikidata and return structured factual claims.

    Uses Firecrawl's keyless search/scrape to reach Wikidata from CN
    servers, including the EntityData JSON endpoint.
    """

    name = "wikidata_lookup"
    description = (
        "Look up a factual entity on Wikidata and return its labels, description, "
        "common structured claims (instance of, dates, country, founder, official website, etc.) "
        "and linked Wikipedia titles. Free, no API key. Use for precise entity facts and "
        "cross-language identifiers before or after a regular web search."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Entity name, person, place, organization, or QID"},
            "lang": {"type": "string", "description": "Preferred label language: en, zh, de, fr, es (default auto)"},
            "limit": {"type": "integer", "description": "Max entities to return (default 3, max 5)"},
        },
        "required": ["query"],
    }

    async def validate_input(self, args: dict) -> dict:
        args.setdefault("limit", 3)
        args["limit"] = min(max(int(args.get("limit", 3)), 1), _MAX_RESULTS)
        return args

    async def execute(self, args: dict) -> Any:
        query = args["query"]
        limit = args["limit"]
        lang = str(args.get("lang") or "").strip() or ("zh" if not _looks_english(query) else "en")
        if lang not in _SUPPORTED_WIKI_LANGS:
            lang = "en"

        qids: list[str] = []
        m = re.fullmatch(r"[Qq]\d+", query.strip())
        if m:
            qids = [query.strip().upper()]
        else:
            try:
                search_items = await firecrawl_search(
                    f"site:wikidata.org/wiki/ {query}",
                    limit=limit,
                )
            except Exception as exc:
                detail = str(exc) or repr(exc)
                return [{"error": f"wikidata_lookup failed: {type(exc).__name__}: {detail}"}]
            for item in search_items:
                mm = re.search(r"/wiki/(Q\d+)", item.get("url", ""))
                if mm and mm.group(1) not in qids:
                    qids.append(mm.group(1))
                if len(qids) >= limit:
                    break

        if not qids:
            return []

        results: list[dict] = []
        errors: list[str] = []
        for qid in qids[:limit]:
            try:
                entity_data = await firecrawl_scrape_json(
                    f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
                )
                entity = ((entity_data or {}).get("entities") or {}).get(qid) or {}
                results.append(self._format_entity(entity, lang))
            except Exception as exc:
                detail = str(exc) or repr(exc)
                errors.append(f"wikidata_entity {qid} failed: {type(exc).__name__}: {detail}")

        if not results:
            return [{"error": errors[0] if errors else "wikidata_lookup returned no entity data"}]
        return results

    @staticmethod
    def _format_entity(entity: dict, lang: str) -> dict:
        eid = entity.get("id", "")
        labels = entity.get("labels") or {}
        descriptions = entity.get("descriptions") or {}
        label = (
            labels.get(lang, {}).get("value")
            or labels.get("en", {}).get("value")
            or labels.get("zh", {}).get("value")
            or ""
        )
        description = (
            descriptions.get(lang, {}).get("value")
            or descriptions.get("en", {}).get("value")
            or descriptions.get("zh", {}).get("value")
            or ""
        )

        claims_raw = entity.get("claims") or {}
        key_facts: list[dict[str, Any]] = []
        for prop, prop_label in _WIKIDATA_PROPERTY_LABELS.items():
            if prop not in claims_raw:
                continue
            values: list[str] = []
            for claim in claims_raw[prop]:
                v = _wikidata_claim_value(claim.get("mainsnak") or {})
                if v:
                    values.append(v)
                if len(values) >= 5:
                    break
            if values:
                key_facts.append({
                    "property": prop,
                    "property_label": prop_label,
                    "values": values,
                })

        sitelinks: dict[str, str] = {}
        for code in ("en", "zh", "simple", "fr", "de", "es"):
            sl = (entity.get("sitelinks") or {}).get(code)
            if sl:
                sitelinks[code] = sl.get("title", "")

        return {
            "id": eid,
            "label": label,
            "description": description,
            "url": f"https://www.wikidata.org/wiki/{eid}" if eid else "",
            "key_facts": key_facts,
            "sitelinks": sitelinks,
        }

    def format_result(self, raw: Any) -> str:
        if isinstance(raw, list):
            if not raw:
                return "No Wikidata results found."
            if isinstance(raw[0], dict) and "error" in raw[0]:
                return f"ERROR: {raw[0]['error']}"
            lines = []
            for i, r in enumerate(raw, 1):
                lines.append(f"{i}. {r.get('label') or r.get('id') or 'No title'}")
                if r.get("description"):
                    lines.append(f"   描述: {r['description']}")
                lines.append(f"   URL: {r.get('url', 'N/A')}")
                for fact in r.get("key_facts", []):
                    values = ", ".join(fact.get("values", [])[:5])
                    lines.append(f"   {fact.get('property_label') or fact.get('property')}: {values}")
                if r.get("sitelinks"):
                    links = ", ".join(f"{code}:{title}" for code, title in r["sitelinks"].items())
                    lines.append(f"   维基百科: {links}")
                lines.append("")
            return "\n".join(lines)
        return str(raw)


__all__ = ["WikipediaSearchTool", "WikidataLookupTool"]
