"""Tests for the constants modules (types, lang and ranking).

The counts and sample values asserted here come from the official
Place Types page and the Google Maps Platform FAQ supported languages
table, as recorded in the Round 7 fixes spec. They are pinned against
those sources, not read back out of the generated modules, so a value
dropped, doubled or mistyped by a later edit fails here.
"""

from __future__ import annotations

import json

import pytest

import placekit
from placekit import Client, lang, ranking, types


@pytest.fixture()
def client(api_key, base_url) -> Client:
    return Client(api_key, base_url=base_url)


def test_constants_counts():
    assert len(types.TABLE_A_TYPES) == 478
    assert len(types.TABLE_B_TYPES) == 36
    assert len(types.ADDRESS_COMPONENT_TYPES) == 4
    assert len(types.ALL_TYPES) == 518
    # The union carries no duplicates across the three sets, so the
    # parts sum to the whole instead of overlapping silently.
    parts = (
        len(types.TABLE_A_TYPES)
        + len(types.TABLE_B_TYPES)
        + len(types.ADDRESS_COMPONENT_TYPES)
    )
    assert parts == len(types.ALL_TYPES)
    assert types.ALL_TYPES == (
        types.TABLE_A_TYPES | types.TABLE_B_TYPES | types.ADDRESS_COMPONENT_TYPES
    )
    type_constants = [n for n in types.__all__ if n.startswith("TYPE_")]
    assert len(type_constants) == 518
    assert {getattr(types, n) for n in type_constants} == types.ALL_TYPES
    # The collections are not types and stay out of the union.
    assert types.COLLECTION_REGIONS not in types.ALL_TYPES
    assert types.COLLECTION_CITIES not in types.ALL_TYPES
    lang_constants = [n for n in lang.__all__ if n != "ALL_CODES"]
    assert len(lang_constants) == 82
    assert len(lang.ALL_CODES) == 82
    assert {getattr(lang, n) for n in lang_constants} == lang.ALL_CODES


def test_constants_wire_values_character_for_character():
    # One granular restaurant value, the longest tail of Table A.
    assert types.TYPE_SOUTHWESTERN_US_RESTAURANT == "southwestern_us_restaurant"
    assert types.TYPE_JAPANESE_IZAKAYA_RESTAURANT == "japanese_izakaya_restaurant"
    assert types.TYPE_EBIKE_CHARGING_STATION == "ebike_charging_station"
    assert types.TYPE_GEOCODE == "geocode"
    assert types.TYPE_STREET_NUMBER == "street_number"
    # The one mixed case value in the language module.
    assert lang.SERBIAN_LATIN == "sr-Latn"
    # The source table lists iw for Hebrew and the table is the authority.
    assert lang.HEBREW == "iw"
    assert lang.CHINESE_SIMPLIFIED == "zh-CN"
    assert lang.SPANISH_LATIN_AMERICA == "es-419"
    assert lang.FILIPINO == "fil"
    # Both parenthesised collections.
    assert types.COLLECTION_REGIONS == "(regions)"
    assert types.COLLECTION_CITIES == "(cities)"
    assert ranking.RELEVANCE == "RELEVANCE"
    assert ranking.DISTANCE == "DISTANCE"
    assert ranking.POPULARITY == "POPULARITY"


def test_legacy_dead_values_have_no_constant():
    # Type values the new vocabulary has no home for.
    for dead in ("address", "grocery_or_supermarket"):
        assert dead not in types.ALL_TYPES
        assert dead not in types.TABLE_A_TYPES
        assert dead not in types.TABLE_B_TYPES
    type_values = [
        getattr(types, n)
        for n in types.__all__
        if isinstance(getattr(types, n), str)
    ]
    assert "address" not in type_values
    assert "grocery_or_supermarket" not in type_values
    # Language codes dropped from the current supported table.
    for dead_code in ("nn", "or", "rm", "tl"):
        assert dead_code not in lang.ALL_CODES
    # The legacy misspellings are not carried under any name.
    for misspelled in ("GALICAIN", "GUJURATI", "UKRANIAN"):
        assert not hasattr(lang, misspelled)
    assert lang.GALICIAN == "gl"
    assert lang.GUJARATI == "gu"
    assert lang.UKRAINIAN == "uk"


def test_package_attribute_access():
    # A plain package import makes the submodule attribute form work.
    assert placekit.types.TYPE_CAFE == "cafe"
    assert placekit.lang.ENGLISH == "en"
    assert placekit.ranking.DISTANCE == "DISTANCE"
    assert "types" in placekit.__all__
    assert "lang" in placekit.__all__
    assert "ranking" in placekit.__all__


def test_ranking_values_match_the_core_vocabulary(client, stub_server):
    # Every member of each method set goes through the stub client
    # path for rank_preference and the request body must carry the
    # same string, so the module and the core cannot drift apart.
    for value in sorted(ranking.TEXT_SEARCH_VALUES):
        client.text_search("cafes", rank_preference=value)
        body = json.loads(stub_server.last_request["body"])
        assert body["rankPreference"] == value
    for value in sorted(ranking.NEARBY_SEARCH_VALUES):
        client.nearby_search((-33.8668, 151.2071), 800.0, rank_preference=value)
        body = json.loads(stub_server.last_request["body"])
        assert body["rankPreference"] == value
    assert ranking.TEXT_SEARCH_VALUES == {"RELEVANCE", "DISTANCE"}
    assert ranking.NEARBY_SEARCH_VALUES == {"DISTANCE", "POPULARITY"}
