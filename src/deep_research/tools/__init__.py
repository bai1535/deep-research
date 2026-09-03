from .search import TavilySearchTool, FirecrawlSearchTool, BingSearchTool, BaiduSearchTool
from .knowledge import WikipediaSearchTool, WikidataLookupTool
from .wayback import WaybackLookupTool
from .web_fetch import WebFetchTool
from .db_tools import SQLiteReadTool
from deep_research.config import get_config
from deep_research.core.tool import BuildTool


def get_free_search_tools() -> list[BuildTool]:
    """Return truly free, no-Firecrawl-quota search tools.

    These are the default for normal research:
      - Baidu: mainland-native, no region-split index.
      - Bing (cn.bing.com): free EN-leaning engine.
    Wikipedia/Wikidata are NOT here because they are bridged through
    Firecrawl keyless and would consume Firecrawl quota.
    """
    return [BaiduSearchTool(), BingSearchTool()]


def get_quality_search_tools() -> list[BuildTool]:
    """Return free tools + Firecrawl/Tavily for quality-gate re-search.

    Used when the Reflector decides the normal research quality is not
    good enough.  Firecrawl is always available (keyless free tier);
    Tavily joins only when a key is configured.
    """
    config = get_config()
    tools = get_free_search_tools()
    # Knowledge-base tools consume Firecrawl keyless quota, so they are
    # reserved for quality-gate re-search too.
    tools.extend([WikipediaSearchTool(), WikidataLookupTool(), WaybackLookupTool()])
    tools.append(FirecrawlSearchTool())
    if config.tavily_api_key:
        tools.append(TavilySearchTool())
    return tools


def get_search_tools() -> list[BuildTool]:
    """Default search tools — free only, to save Firecrawl quota."""
    return get_free_search_tools()


def get_refuter_tools() -> list[BuildTool]:
    """Return search tools for the Refuter agent (free only by default)."""
    return get_search_tools()


__all__ = [
    "TavilySearchTool",
    "FirecrawlSearchTool",
    "BingSearchTool",
    "BaiduSearchTool",
    "WikipediaSearchTool",
    "WikidataLookupTool",
    "WaybackLookupTool",
    "WebFetchTool",
    "SQLiteReadTool",
    "get_free_search_tools",
    "get_quality_search_tools",
    "get_search_tools",
    "get_refuter_tools",
]
