"""Conformance tests for the placekit.address helper module.

Every pin below names its recorded fixture and states its expected
output as literals in this file, taken from the cassettes and never
read back out of the helper under test. The pins follow the Round 14
design record as amended, and the synthesized A11 pin is a survival
pin only, asserting that the helpers raise nothing on the authored
empty shapes and never a precedence claim.

Some stated rules cannot be pinned from recorded evidence yet and
are named here instead of being invented as tests. The postal code
disagreement cell has no pin because no recorded fixture carries
two postal carriers holding different values. The country code
postal fallback has no pin because no shipped fixture excerpt
isolates a place whose components hold no country component while
its postal address holds a region code. A duplicate premise pin
needs a recorded excerpt of one Japanese place carrying two
premise components, which the cassettes hold in aggregate but no
excerpt isolates. A British postal cross reading pin cannot be
written because no British postal address was ever requested, and
the British cells off the recorded geometry are stated in the
record and unpinned for the same reason. A prefix and suffix
assembly pin and a sorting code pin cannot be written because no
prefix or suffix component and no sorting code exists anywhere in
the corpus. A United States primary grade pin stays unwritten
while the stated United States table stays held. A change between
requests pin and a colloquial area pin and an intersection pin
cannot be written because those cases hold no recorded components.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

import placekit
from placekit import ConfigError, address
from placekit.models import Place

FIXTURES = Path(__file__).parent / "fixtures"
RECORDED = FIXTURES / "recorded"
SYNTHESIZED = FIXTURES / "synthesized"


def recorded_payload(name: str):
    data = json.loads((RECORDED / name).read_bytes())
    assert "fixtureMark" not in data
    return data


def recorded_place(name: str, index: int = 0) -> Place:
    payload = recorded_payload(name)
    places = payload["places"] if "places" in payload else [payload]
    return Place.from_api(places[index])


def synthesized_place(name: str, index: int = 0) -> Place:
    data = json.loads((SYNTHESIZED / name).read_bytes())
    assert set(data) == {"fixtureMark", "payload"}
    assert data["fixtureMark"].get("origin") == "synthesized"
    payload = data["payload"]
    places = payload["places"] if "places" in payload else [payload]
    return Place.from_api(places[index])


# ---------------------------------------------------------------------------
# Japan, stated precedence


def test_jp_city_primary_english():
    place = recorded_place("recorded_A8_tokyo_english.json")
    assert place.display_text == "FUGLEN ASAKUSA"
    assert address.resolve_city(place) == address.CityResolution(
        value="Taito City",
        carrier=address.CARRIER_LOCALITY,
        confidence=address.CONFIDENCE_PRIMARY,
        country_code="JP",
    )


def test_jp_city_primary_japanese():
    place = recorded_place("recorded_A8_tokyo_japanese.json")
    english = recorded_place("recorded_A8_tokyo_english.json")
    assert address.resolve_city(place) == address.CityResolution(
        value="台東区",
        carrier=address.CARRIER_LOCALITY,
        confidence=address.CONFIDENCE_PRIMARY,
        country_code="JP",
    )
    # The type sequence matches the English pin while the text differs.
    assert [tuple(c.types) for c in place.address_components] == [
        tuple(c.types) for c in english.address_components
    ]
    assert place.address_components[4].long_text != english.address_components[4].long_text


def test_jp_district_and_barred_fragments():
    place = recorded_place("recorded_A5_sublocality_chains.json")
    assert address.resolve_district(place) == address.DistrictResolution(
        value="浅草",
        carrier=address.CARRIER_SUBLOCALITY_LEVEL_2,
        confidence=address.CONFIDENCE_PRIMARY,
        country_code="JP",
    )
    fragment = address.find_component(
        place.address_components, "sublocality_level_4"
    )
    assert fragment is not None
    assert fragment.long_text == "６"
    # The fragment is never a city output on this place.
    assert address.resolve_city(place).value == "台東区"


def test_bare_sublocality_chain_trap():
    place = recorded_place("recorded_A5_sublocality_chains.json")
    matches = address.find_components(place.address_components, "sublocality")
    assert [component.long_text for component in matches] == ["６", "２丁目", "浅草"]
    first = address.find_component(place.address_components, "sublocality")
    assert first is not None
    assert first.long_text == "６"


def test_jp_postal_silence():
    place = recorded_place("recorded_A6_japanese_block_addressing.json")
    assert address.postal_locality(place.postal_address) is None
    assert address.postal_sublocality(place.postal_address) is None
    assert address.resolve_city(place).value == "台東区"
    assert address.resolve_city(place).confidence == address.CONFIDENCE_PRIMARY
    assert address.postal_code(place) == address.PostalCodeResult(
        value="111-0032",
        carrier=address.CARRIER_BOTH_POSTAL,
        status=address.POSTAL_PRESENT,
        country_code="JP",
    )


def test_jp_premise_duplication_shape():
    place = recorded_place("recorded_A13_premise_and_subpremise.json")
    components = place.address_components
    assert len(address.find_components(components, "subpremise")) == 1
    assert address.has_premise(components) is True
    assert address.is_premise_level(place) is True
    assert components[0].types == []
    untyped = address.untyped_components(components)
    assert untyped == (components[0],)
    assert untyped[0].long_text == "1 Asakusa, Taito-ku"


# ---------------------------------------------------------------------------
# United Arab Emirates, stated precedence


def test_ae_city_primary():
    place = recorded_place("recorded_A7_rtl_script_address.json", 0)
    assert address.resolve_city(place) == address.CityResolution(
        value="دبي",
        carrier=address.CARRIER_LOCALITY,
        confidence=address.CONFIDENCE_PRIMARY,
        country_code="AE",
    )


def test_ae_district_and_postal_substitution():
    place = recorded_place("recorded_A9_country_without_postal_codes.json")
    district = address.resolve_district(place)
    assert district == address.DistrictResolution(
        value="المركز التجاري الثانية",
        carrier=address.CARRIER_SUBLOCALITY_LEVEL_1,
        confidence=address.CONFIDENCE_PRIMARY,
        country_code="AE",
    )
    postal_value = address.postal_sublocality(place.postal_address)
    assert postal_value == "وسط مدينة دبي"
    neighborhood = address.component_long_text(
        place.address_components, "neighborhood"
    )
    assert postal_value == neighborhood
    assert district.value != postal_value


def test_ae_postal_absence_of_a_code():
    place = recorded_place("recorded_A9_country_without_postal_codes.json")
    assert place.postal_address is not None
    assert address.postal_code(place) == address.PostalCodeResult(
        value=None,
        carrier=None,
        status=address.POSTAL_ABSENT,
        country_code="AE",
    )


def test_ae_postal_admin_dropout():
    place = recorded_place("recorded_A7_rtl_script_address.json", 1)
    assert address.administrative_area(place) == "دبي"
    assert address.postal_administrative_area(place.postal_address) is None


def test_ae_typeless_most_specific_text():
    place = recorded_place("recorded_A7_rtl_script_address.json", 1)
    untyped = address.untyped_components(place.address_components)
    assert [component.long_text for component in untyped] == [
        "Level 3, Armani Hotel Dubai"
    ]
    for type_name in ("premise", "route", "locality", "country"):
        assert untyped[0] not in address.find_components(
            place.address_components, type_name
        )


def test_lying_labels():
    place = recorded_place("recorded_A7_rtl_script_address.json", 0)
    assert (
        address.component_long_text(place.address_components, "route")
        == "122nd Floor"
    )
    assert address.has_route(place.address_components) is True
    assert address.resolve_city(place).value == "دبي"
    assert address.resolve_district(place).value == "برج خليفة"


# ---------------------------------------------------------------------------
# United Kingdom, stated two value answer


def test_gb_two_value_answer():
    place = recorded_place("recorded_A4_locality_postal_town_disagree.json")
    assert address.city_resolutions(place) == (
        address.CityResolution(
            value="Bourton-on-the-Water",
            carrier=address.CARRIER_LOCALITY,
            confidence=address.CONFIDENCE_CONTESTED,
            country_code="GB",
            competing_value="Cheltenham",
            competing_carrier=address.CARRIER_POSTAL_TOWN,
        ),
        address.CityResolution(
            value="Cheltenham",
            carrier=address.CARRIER_POSTAL_TOWN,
            confidence=address.CONFIDENCE_CONTESTED,
            country_code="GB",
            competing_value="Bourton-on-the-Water",
            competing_carrier=address.CARRIER_LOCALITY,
        ),
    )


def test_gb_headline_interim():
    place = recorded_place("recorded_A3_postal_town_carries_city.json")
    assert address.resolve_city(place) == address.CityResolution(
        value="Bourton-on-the-Water",
        carrier=address.CARRIER_LOCALITY,
        confidence=address.CONFIDENCE_CONTESTED,
        country_code="GB",
        competing_value="Cheltenham",
        competing_carrier=address.CARRIER_POSTAL_TOWN,
    )


def test_gb_postal_unobserved():
    place = recorded_place("recorded_A3_postal_town_carries_city.json")
    assert place.postal_address is None
    assert address.postal_locality(place.postal_address) is None


# ---------------------------------------------------------------------------
# Country signal letter case


def with_country_signal(place: Place, short_text: str) -> Place:
    """Return the decoded place with its country signal rewritten.

    The signal is the short text of the country component, and the
    rewrite happens on the decoded place so the recorded geometry
    of the fixture stays exactly as recorded.
    """
    components = [
        replace(component, short_text=short_text)
        if "country" in component.types
        else component
        for component in place.address_components
    ]
    return replace(place, address_components=components)


def test_gb_lowercase_signal_keeps_the_contested_answer():
    place = with_country_signal(
        recorded_place("recorded_A4_locality_postal_town_disagree.json"), "gb"
    )
    # The carried code stays the value as sent while the routing
    # match reads it without regard to letter case, so the recorded
    # rivalry survives instead of falling to the generic chain.
    assert address.country_code(place) == "gb"
    assert address.city_resolutions(place) == (
        address.CityResolution(
            value="Bourton-on-the-Water",
            carrier=address.CARRIER_LOCALITY,
            confidence=address.CONFIDENCE_CONTESTED,
            country_code="gb",
            competing_value="Cheltenham",
            competing_carrier=address.CARRIER_POSTAL_TOWN,
        ),
        address.CityResolution(
            value="Cheltenham",
            carrier=address.CARRIER_POSTAL_TOWN,
            confidence=address.CONFIDENCE_CONTESTED,
            country_code="gb",
            competing_value="Bourton-on-the-Water",
            competing_carrier=address.CARRIER_LOCALITY,
        ),
    )
    headline = address.resolve_city(place)
    assert headline.confidence == address.CONFIDENCE_CONTESTED
    assert headline.competing_value == "Cheltenham"


def test_jp_lowercase_signal_takes_the_stated_table():
    place = with_country_signal(
        recorded_place("recorded_A8_tokyo_english.json"), "jp"
    )
    assert address.country_code(place) == "jp"
    assert address.resolve_city(place) == address.CityResolution(
        value="Taito City",
        carrier=address.CARRIER_LOCALITY,
        confidence=address.CONFIDENCE_PRIMARY,
        country_code="jp",
    )
    assert address.resolve_district(place) == address.DistrictResolution(
        value="Asakusa",
        carrier=address.CARRIER_SUBLOCALITY_LEVEL_2,
        confidence=address.CONFIDENCE_PRIMARY,
        country_code="jp",
    )


# ---------------------------------------------------------------------------
# Generic chain countries


def test_us_rescue_under_the_generic_chain():
    place = recorded_place("recorded_A2_no_locality_sublocality_city.json")
    assert address.resolve_city(place) == address.CityResolution(
        value="Brooklyn",
        carrier=address.CARRIER_SUBLOCALITY_LEVEL_1,
        confidence=address.CONFIDENCE_HEURISTIC,
        country_code="US",
    )
    assert address.component_long_text(place.address_components, "locality") is None
    assert address.postal_locality(place.postal_address) == "Brooklyn"


def test_us_plain_locality_under_the_generic_chain():
    # Fork dependent pin. A shipped United States table would
    # rewrite this grade to primary.
    place = recorded_place("recorded_P15_richest_mall_store.json")
    assert address.resolve_city(place) == address.CityResolution(
        value="Santa Clara",
        carrier=address.CARRIER_LOCALITY,
        confidence=address.CONFIDENCE_HEURISTIC,
        country_code="US",
    )


def test_us_barred_neighborhood():
    place = recorded_place("recorded_P15_richest_mall_store.json")
    assert address.resolve_city(place).value != "Central San Jose"
    assert address.address_flags(place).has_city_carrier is True


def test_us_bridge_absence():
    place = recorded_place("recorded_A1_no_street_number.json")
    assert address.resolve_city(place) == address.CityResolution(
        value="New York",
        carrier=address.CARRIER_LOCALITY,
        confidence=address.CONFIDENCE_HEURISTIC,
        country_code="US",
    )
    result = address.postal_code(place)
    assert result.status == address.POSTAL_ABSENT
    assert place.postal_address is None
    assert address.has_street_number(place.address_components) is False
    assert address.has_no_street_level(place.address_components) is False


def test_vn_inversion_guard():
    place = recorded_place("recorded_P15_details_depth_saigon.json")
    resolution = address.resolve_city(place)
    assert resolution == address.CityResolution(
        value="Thành phố Hồ Chí Minh",
        carrier=address.CARRIER_LOCALITY,
        confidence=address.CONFIDENCE_HEURISTIC,
        country_code="VN",
    )
    assert resolution.value != "Tan Son Hoa"
    assert address.postal_locality(place.postal_address) == "Tan Son Hoa"


def test_il_thin_generic():
    place = recorded_place("recorded_A10_jerusalem_no_region_code.json")
    assert address.resolve_city(place) == address.CityResolution(
        value="Jerusalem",
        carrier=address.CARRIER_LOCALITY,
        confidence=address.CONFIDENCE_HEURISTIC,
        country_code="IL",
    )
    assert address.country_code(place) == "IL"


def test_il_pair_stability():
    first = recorded_place("recorded_A10_jerusalem_no_region_code.json")
    second = recorded_place("recorded_A10_jerusalem_region_ps.json")
    place_helpers = (
        address.country_code,
        address.resolve_city,
        address.resolve_district,
        address.postal_code,
        address.address_flags,
    )
    for helper in place_helpers:
        assert helper(first) == helper(second), helper.__name__
    assert address.split_plus_code(first.plus_code) == address.split_plus_code(
        second.plus_code
    )
    postal_helpers = (
        address.postal_locality,
        address.postal_sublocality,
        address.postal_administrative_area,
        address.postal_region_code,
    )
    for helper in postal_helpers:
        assert helper(first.postal_address) == helper(
            second.postal_address
        ), helper.__name__


# ---------------------------------------------------------------------------
# Absence shapes


def test_everest_absence():
    place = recorded_place("recorded_P1_no_address_natural_feature.json")
    assert address.resolve_city(place) == address.CityResolution(
        value=None,
        carrier=None,
        confidence=address.CONFIDENCE_NONE,
        country_code=None,
    )
    assert address.country_code(place) is None
    assert address.postal_code(place).status == address.POSTAL_ABSENT
    assert address.split_plus_code(place.plus_code) is None


def test_everest_global_code_only():
    place = recorded_place("recorded_V5_plus_code_global_only.json")
    assert address.split_plus_code(place.plus_code) is None
    assert place.plus_code is not None
    assert place.plus_code.global_code == "7MV8XWQG+74"


def test_no_carrier_set_at_all():
    place = recorded_place("recorded_A12_long_village_name.json")
    assert place.address_components == []
    assert place.postal_address is None
    assert address.resolve_city(place).confidence == address.CONFIDENCE_NONE
    assert address.resolve_city(place).value is None
    assert address.country_code(place) is None
    assert address.postal_code(place).status == address.POSTAL_ABSENT


# ---------------------------------------------------------------------------
# Plus code splitting


def test_plus_code_split_brooklyn():
    place = recorded_place("recorded_A2_no_locality_sublocality_city.json")
    assert address.split_plus_code(place.plus_code) == address.PlusCodeParts(
        code_part="P27Q+Q9", locality_text="Brooklyn, NY, USA"
    )


def test_plus_code_split_santa_clara():
    place = recorded_place("recorded_P15_richest_mall_store.json")
    assert address.split_plus_code(place.plus_code) == address.PlusCodeParts(
        code_part="83G4+2P", locality_text="Santa Clara, CA, USA"
    )


def test_plus_code_split_saigon():
    place = recorded_place("recorded_P15_details_depth_saigon.json")
    parts = address.split_plus_code(place.plus_code)
    assert parts is not None
    assert parts.code_part == "QMX9+V7"
    assert parts.locality_text == "Tan Son Hoa, Ho Chi Minh, Vietnam"
    # The split text never feeds city resolution on the same place.
    assert address.resolve_city(place).value == "Thành phố Hồ Chí Minh"


def test_split_compound_code_edges():
    assert address.split_compound_code(None) is None
    assert address.split_compound_code("") is None
    assert address.split_compound_code("87G8P27Q+Q9") is None
    assert address.split_compound_code("P27Q+Q9 ") is None
    assert address.split_plus_code(None) is None


# ---------------------------------------------------------------------------
# Synthesized survival


def test_synthesized_a11_survival():
    empty_text = synthesized_place(
        "synthesized_A11_component_present_but_empty.json", 0
    )
    empty_list = synthesized_place(
        "synthesized_A11_component_present_but_empty.json", 1
    )
    for place in (empty_text, empty_list):
        assert address.resolve_city(place).confidence == address.CONFIDENCE_NONE
        assert address.resolve_district(place).confidence == address.CONFIDENCE_NONE
        assert address.country_code(place) is None
        assert address.postal_code(place).status == address.POSTAL_ABSENT
        assert address.address_flags(place).has_city_carrier is False
        assert address.split_plus_code(place.plus_code) is None
    assert (
        address.component_long_text(empty_text.address_components, "route") is None
    )
    route = address.find_component(empty_text.address_components, "route")
    assert route is not None
    assert route.long_text == ""
    assert address.has_route(empty_text.address_components) is True
    assert address.has_no_street_level(empty_list.address_components) is True


# ---------------------------------------------------------------------------
# Error posture


def test_bare_string_components_raise_config_error():
    with pytest.raises(ConfigError):
        address.find_component("route", "route")
    with pytest.raises(ConfigError):
        address.find_components(b"route", "route")
    with pytest.raises(ConfigError):
        address.untyped_components("route")


def test_none_components_raise_config_error():
    with pytest.raises(ConfigError):
        address.find_components(None, "route")
    with pytest.raises(ConfigError):
        address.untyped_components(None)
    with pytest.raises(ConfigError):
        address.has_no_street_level(None)
    with pytest.raises(ConfigError):
        address.postal_code_from_components(None)


def test_bad_type_name_raises_config_error():
    with pytest.raises(ConfigError):
        address.find_components([], 3)
    with pytest.raises(ConfigError):
        address.component_long_text([], "")


def test_package_attribute_access():
    assert placekit.address is address
    assert "address" in placekit.__all__
    assert placekit.address.CARRIER_LOCALITY == "locality"
