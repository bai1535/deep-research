"""Tests for Bing result parsing and URL unwrapping (no network)."""

from deep_research.tools.search import (
    _clean_html_fragment,
    _parse_bing_results,
    _unpack_bing_url,
)


def test_unpack_bing_url_decodes_html_escaped_redirect():
    href = (
        "https://www.bing.com/ck/a?!&&p=abc&ptn=3&ver=2&hsh=4"
        "&u=a1aHR0cHM6Ly9leGFtcGxlLmNvbS9wYXRo&ntb=1"
    )
    # The HTML page escapes every & as &amp;; this is what the regex sees.
    escaped = href.replace("&", "&amp;")
    assert _unpack_bing_url(escaped) == "https://example.com/path"


def test_unpack_bing_url_unescapes_non_redirect_href():
    href = "https://example.com/search?q=a&amp;b=1"
    assert _unpack_bing_url(href) == "https://example.com/search?q=a&b=1"


def test_unpack_bing_url_keeps_plain_url():
    href = "https://example.com/page"
    assert _unpack_bing_url(href) == href


def test_clean_html_fragment_removes_tags_and_unescapes():
    raw = "<b>Hello</b> &amp; <i>welcome</i>&nbsp;world"
    assert _clean_html_fragment(raw) == "Hello & welcome world"


def test_parse_bing_results_extracts_real_url_and_clean_text():
    html = """
    <li class="b_algo">
      <h2><a href="https://www.bing.com/ck/a?!&amp;&amp;p=abc&amp;u=a1aHR0cHM6Ly9leGFtcGxlLmNvbS9wYXRo&amp;ntb=1">
        Example &amp; Test
      </a></h2>
      <div class="b_caption"><p class="b_lineclamp2">Hello &amp; welcome <b>world</b></p></div>
    </li>
    """
    results = _parse_bing_results(html, max_results=5)
    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/path"
    assert results[0]["title"] == "Example & Test"
    assert results[0]["body"] == "Hello & welcome world"


def test_parse_bing_results_falls_back_to_cite_when_no_u_param():
    html = """
    <li class="b_algo">
      <div class="b_tpcn"><a href="https://www.bing.com/ck/a?!&amp;&amp;p=abc&amp;ntb=1">
        <cite><strong>https://</strong>example.com</cite>
      </a></div>
      <h2><a href="https://www.bing.com/ck/a?!&amp;&amp;p=abc&amp;ntb=1">Example</a></h2>
      <div class="b_caption"><p>Just a snippet</p></div>
    </li>
    """
    results = _parse_bing_results(html, max_results=5)
    assert len(results) == 1
    assert results[0]["url"] == "https://example.com"
