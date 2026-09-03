"""Tests for Wikipedia/Wikidata knowledge tools (offline: parsers/formatters)."""

import pytest

from deep_research.tools.knowledge import (
    WikipediaSearchTool,
    WikidataLookupTool,
    _wikidata_claim_value,
)


@pytest.mark.asyncio
async def test_wikipedia_validate_defaults():
    args = await WikipediaSearchTool().validate_input({"query": "Python"})
    assert args["limit"] == 3
    assert args["query"] == "Python"


@pytest.mark.asyncio
async def test_wikipedia_validate_clamps_limit():
    tool = WikipediaSearchTool()
    assert (await tool.validate_input({"query": "x", "limit": 99}))["limit"] == 5
    assert (await tool.validate_input({"query": "x", "limit": 0}))["limit"] == 1


def test_wikipedia_format_error():
    out = WikipediaSearchTool().format_result([{"error": "boom"}])
    assert out.startswith("ERROR:")


def test_wikipedia_format_success():
    out = WikipediaSearchTool().format_result([
        {"title": "Python (programming language)", "url": "https://en.wikipedia.org/wiki/Python_(programming_language)", "extract": "Python is a language."},
    ])
    assert "Python (programming language)" in out
    assert "https://en.wikipedia.org" in out


@pytest.mark.asyncio
async def test_wikidata_validate_defaults():
    args = await WikidataLookupTool().validate_input({"query": "Ada Lovelace"})
    assert args["limit"] == 3


def test_wikidata_claim_value_time():
    snak = {"datatype": "time", "datavalue": {"value": {"time": "+1815-12-10T00:00:00Z"}}}
    assert _wikidata_claim_value(snak) == "1815-12-10"


def test_wikidata_claim_value_quantity():
    snak = {"datatype": "quantity", "datavalue": {"value": {"amount": "+42", "unit": "http://www.wikidata.org/entity/Q1"}}}
    assert _wikidata_claim_value(snak) == "42"


def test_wikidata_claim_value_item():
    snak = {"datatype": "wikibase-item", "datavalue": {"value": {"id": "Q5"}}}
    assert _wikidata_claim_value(snak) == "Q5"


def test_wikidata_format_entity_key_facts():
    entity = {
        "id": "Q7259",
        "labels": {"en": {"value": "Ada Lovelace"}, "zh": {"value": "阿达·洛夫莱斯"}},
        "descriptions": {"en": {"value": "English mathematician and writer"}},
        "claims": {
            "P569": [{"mainsnak": {"datatype": "time", "datavalue": {"value": {"time": "+1815-12-10T00:00:00Z"}}}}],
            "P31": [{"mainsnak": {"datatype": "wikibase-item", "datavalue": {"value": {"id": "Q5"}}}}],
        },
        "sitelinks": {"en": {"title": "Ada Lovelace"}, "zh": {"title": "阿达·洛夫莱斯"}},
    }
    out = WikidataLookupTool._format_entity(entity, "en")
    assert out["label"] == "Ada Lovelace"
    assert out["sitelinks"]["zh"] == "阿达·洛夫莱斯"
    facts = {f["property"]: f["values"] for f in out["key_facts"]}
    assert facts["P569"] == ["1815-12-10"]
    assert facts["P31"] == ["Q5"]


def test_wikidata_format_error():
    out = WikidataLookupTool().format_result([{"error": "boom"}])
    assert out.startswith("ERROR:")
