"""Proof tests for NORMALIZATION.md, the normalization guide.

The guide is a promise, so the suite executes it. Every example in
the guide is run here in the same call shapes against the recorded
fixtures, with expected values stated as literals taken from the
cassettes and never read back out of the helpers under test, and
the boundary sentences are pinned as text so a later edit cannot
quietly soften them away. A structural test keeps the claim tags
and the travelling scope sentences where the guide design puts
them, so a draft that drops the tags or lets a scope sentence
wander out of its section fails here rather than in a reader.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from placekit import ConfigError, address, types
from placekit.models import Place

REPO_ROOT = Path(__file__).resolve().parents[1]
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


def synthesized_payload(name: str):
    data = json.loads((SYNTHESIZED / name).read_bytes())
    assert set(data) == {"fixtureMark", "payload"}
    assert data["fixtureMark"].get("origin") == "synthesized"
    return data["payload"]


def synthesized_place(name: str, index: int = 0) -> Place:
    payload = synthesized_payload(name)
    places = payload["places"] if "places" in payload else [payload]
    return Place.from_api(places[index])


# ---------------------------------------------------------------------------
# Example 1. Component lookup and the scanning text forms


def test_guide_example_1_lookup_and_scanning_text_forms():
    place = recorded_place("recorded_A5_sublocality_chains.json")
    components = place.address_components
    chain = address.find_components(components, types.TYPE_SUBLOCALITY)
    # The bare sublocality lookup returns the levelled chain in list
    # order with the level 4 fragment first, because every levelled
    # component carries the bare type as a companion.
    assert len(chain) == 3
    assert [component.long_text for component in chain] == [
        "６",
        "２丁目",
        "浅草",
    ]
    assert address.component_long_texts(
        components, types.TYPE_SUBLOCALITY
    ) == ("６", "２丁目", "浅草")
    assert (
        address.component_long_text(
            components, types.TYPE_SUBLOCALITY_LEVEL_2
        )
        == "浅草"
    )
    assert (
        address.component_long_text(
            components, types.TYPE_SUBLOCALITY_LEVEL_4
        )
        == "６"
    )


# ---------------------------------------------------------------------------
# Example 2. The typeless bucket


def test_guide_example_2_untyped_components():
    place = recorded_place("recorded_A13_premise_and_subpremise.json")
    components = place.address_components
    untyped = address.untyped_components(components)
    assert len(untyped) == 1
    assert untyped[0] is components[0]
    assert untyped[0].long_text == "1 Asakusa, Taito-ku"
    # No type keyed lookup on the same list returns that component.
    type_names = {name for component in components for name in component.types}
    for type_name in type_names:
        assert untyped[0] not in address.find_components(
            components, type_name
        )

    dubai = recorded_place("recorded_A7_rtl_script_address.json", 1)
    dubai_untyped = address.untyped_components(dubai.address_components)
    assert len(dubai_untyped) == 1
    assert dubai_untyped[0] is dubai.address_components[0]
    assert dubai_untyped[0].long_text == "Level 3, Armani Hotel Dubai"
    premise = address.find_component(
        dubai.address_components, types.TYPE_PREMISE
    )
    assert premise is not None
    assert premise is not dubai_untyped[0]


# ---------------------------------------------------------------------------
# Example 3. Presence flags trust types and a route can hold a floor label


def test_guide_example_3_lying_route_label_and_flags():
    place = recorded_place("recorded_A7_rtl_script_address.json", 0)
    components = place.address_components
    assert (
        address.component_long_text(components, types.TYPE_ROUTE)
        == "122nd Floor"
    )
    assert address.has_route(components) is True
    flags = address.address_flags(place)
    assert flags.has_route is True
    # No city or district output on the place uses the route text.
    assert address.resolve_city(place).value != "122nd Floor"
    assert address.resolve_district(place).value != "122nd Floor"
    assert address.resolve_city(place).carrier == address.CARRIER_LOCALITY


# ---------------------------------------------------------------------------
# Example 4. Country and administrative area reads


def test_guide_example_4_country_and_administrative_area():
    place = recorded_place("recorded_A10_jerusalem_no_region_code.json")
    assert address.country_code(place) == "IL"
    assert (
        address.country_code_from_components(place.address_components)
        == "IL"
    )
    assert address.administrative_area(place) == "Jerusalem District"
    assert address.postal_administrative_area(place.postal_address) is None

    # The postal administrative dropout. The component read returns
    # a value while the postal read returns None on the same place.
    dubai = recorded_place("recorded_A7_rtl_script_address.json", 1)
    assert address.administrative_area(dubai) == "دبي"
    assert address.postal_administrative_area(dubai.postal_address) is None


# ---------------------------------------------------------------------------
# Example 5. Postal field readers and the postal code status


def test_guide_example_5_postal_readers_and_status():
    # The present case loads the A6 name of the A5 and A6 pair, one
    # evidence item under two case names.
    japan = recorded_place("recorded_A6_japanese_block_addressing.json")
    result = address.postal_code(japan)
    assert result.status == address.POSTAL_PRESENT
    assert result.status == "present"
    assert result.carrier == address.CARRIER_BOTH_POSTAL
    assert result.carrier == "both_postal_carriers"
    assert result.value == "111-0032"

    dubai = recorded_place("recorded_A9_country_without_postal_codes.json")
    absent = address.postal_code(dubai)
    assert absent.status == address.POSTAL_ABSENT
    assert absent.status == "absent"
    assert absent.value is None
    assert address.postal_locality(dubai.postal_address) == "دبي"
    assert address.postal_sublocality(dubai.postal_address) == "وسط مدينة دبي"
    district = address.resolve_district(dubai)
    assert district.value == "المركز التجاري الثانية"
    assert address.postal_sublocality(dubai.postal_address) != district.value


# ---------------------------------------------------------------------------
# Example 6. Reading a city with its grade and acting on the grade


def _guide_city_label(city) -> str:
    """The branch the guide block takes for one city result."""
    if city.value is None:
        return "no recorded city"
    return city.value


def test_guide_example_6_city_grades_and_branching():
    tokyo = recorded_place("recorded_A8_tokyo_english.json")
    city = address.resolve_city(tokyo)
    assert (city.value, city.carrier, city.confidence) == (
        "Taito City",
        address.CARRIER_LOCALITY,
        address.CONFIDENCE_PRIMARY,
    )

    brooklyn = recorded_place("recorded_A2_no_locality_sublocality_city.json")
    city = address.resolve_city(brooklyn)
    assert (city.value, city.carrier, city.confidence) == (
        "Brooklyn",
        address.CARRIER_SUBLOCALITY_LEVEL_1,
        address.CONFIDENCE_HEURISTIC,
    )

    everest = recorded_place("recorded_P1_no_address_natural_feature.json")
    city = address.resolve_city(everest)
    assert (city.value, city.carrier, city.confidence) == (
        None,
        None,
        address.CONFIDENCE_NONE,
    )
    # The branch the guide takes for the none result renders a no
    # recorded city outcome rather than an empty string.
    assert _guide_city_label(city) == "no recorded city"


# ---------------------------------------------------------------------------
# Example 7. District readings for the two stated countries


def test_guide_example_7_district_readings():
    japan = recorded_place("recorded_A5_sublocality_chains.json")
    district = address.resolve_district(japan)
    assert (district.value, district.carrier, district.confidence) == (
        "浅草",
        address.CARRIER_SUBLOCALITY_LEVEL_2,
        address.CONFIDENCE_PRIMARY,
    )

    dubai = recorded_place("recorded_A9_country_without_postal_codes.json")
    district = address.resolve_district(dubai)
    assert (district.value, district.carrier, district.confidence) == (
        "المركز التجاري الثانية",
        address.CARRIER_SUBLOCALITY_LEVEL_1,
        address.CONFIDENCE_PRIMARY,
    )

    uncovered = recorded_place("recorded_A2_no_locality_sublocality_city.json")
    district = address.resolve_district(uncovered)
    assert district.value is None
    assert district.confidence == address.CONFIDENCE_NONE


# ---------------------------------------------------------------------------
# Example 8. The British two value handling


def test_guide_example_8_british_two_values():
    # This test pins one place under two case names. The A3 and A4
    # fixtures are byte identical and count as one evidence item,
    # and the 20 of 20 prevalence stays a cassette claim outside
    # this test.
    place = recorded_place("recorded_A4_locality_postal_town_disagree.json")
    twin = recorded_place("recorded_A3_postal_town_carries_city.json")
    resolutions = address.city_resolutions(place)
    assert address.city_resolutions(twin) == resolutions
    assert len(resolutions) == 2
    civil, mailing = resolutions
    assert (civil.value, civil.carrier, civil.confidence) == (
        "Bourton-on-the-Water",
        address.CARRIER_LOCALITY,
        address.CONFIDENCE_CONTESTED,
    )
    assert civil.competing_value == "Cheltenham"
    assert civil.competing_carrier == address.CARRIER_POSTAL_TOWN
    assert (mailing.value, mailing.carrier, mailing.confidence) == (
        "Cheltenham",
        address.CARRIER_POSTAL_TOWN,
        address.CONFIDENCE_CONTESTED,
    )
    assert mailing.competing_value == "Bourton-on-the-Water"
    assert mailing.competing_carrier == address.CARRIER_LOCALITY
    headline = address.resolve_city(place)
    assert headline == civil
    assert headline.value == resolutions[0].value
    assert headline.competing_value == "Cheltenham"


# ---------------------------------------------------------------------------
# Example 9. The generic chain on American places and the barred neighborhood


def test_guide_example_9_generic_chain_american_places():
    mall = recorded_place("recorded_P15_richest_mall_store.json")
    city = address.resolve_city(mall)
    assert (city.value, city.carrier, city.confidence) == (
        "Santa Clara",
        address.CARRIER_LOCALITY,
        address.CONFIDENCE_HEURISTIC,
    )
    assert city.value != "Central San Jose"
    assert (
        address.component_long_text(
            mall.address_components, types.TYPE_NEIGHBORHOOD
        )
        == "Central San Jose"
    )

    bridge = recorded_place("recorded_A1_no_street_number.json")
    city = address.resolve_city(bridge)
    assert (city.value, city.carrier, city.confidence) == (
        "New York",
        address.CARRIER_LOCALITY,
        address.CONFIDENCE_HEURISTIC,
    )
    assert address.postal_code(bridge).status == address.POSTAL_ABSENT
    flags = address.address_flags(bridge)
    assert flags.has_no_street_level is False
    assert flags.has_street_number is False


# ---------------------------------------------------------------------------
# Example 10. The Saigon inversion guard


def test_guide_example_10_saigon_inversion_guard():
    place = recorded_place("recorded_P15_details_depth_saigon.json")
    city = address.resolve_city(place)
    assert city.value == "Thành phố Hồ Chí Minh"
    assert city.carrier == address.CARRIER_LOCALITY
    assert city.confidence == address.CONFIDENCE_HEURISTIC
    assert city.value != "Tan Son Hoa"
    assert address.postal_locality(place.postal_address) == "Tan Son Hoa"


# ---------------------------------------------------------------------------
# Example 11. Comparing language readings and keeping them apart


def test_guide_example_11_language_pair_kept_apart():
    stored = recorded_place("recorded_A8_tokyo_japanese.json")
    display = recorded_place("recorded_A8_tokyo_english.json")
    assert stored.id == display.id
    stored_types = [tuple(c.types) for c in stored.address_components]
    display_types = [tuple(c.types) for c in display.address_components]
    assert stored_types == display_types
    assert address.component_long_text(
        stored.address_components, types.TYPE_LOCALITY
    ) == "台東区"
    assert address.component_long_text(
        display.address_components, types.TYPE_LOCALITY
    ) == "Taito City"
    assert stored.formatted_address != display.formatted_address
    assert stored.formatted_address.startswith("日本")
    assert display.formatted_address.startswith("2-chōme")


# ---------------------------------------------------------------------------
# Example 12. Comparing region readings on the Jerusalem pair


def test_guide_example_12_region_pair_localised_comparison():
    first = recorded_place("recorded_A10_jerusalem_no_region_code.json")
    second = recorded_place("recorded_A10_jerusalem_region_ps.json")
    place_level = (
        "country_code",
        "resolve_city",
        "resolve_district",
        "postal_code",
        "address_flags",
    )
    for name in place_level:
        helper = getattr(address, name)
        assert helper(first) == helper(second), (
            f"{name} moved between the two region settings"
        )
    postal_level = (
        "postal_locality",
        "postal_sublocality",
        "postal_administrative_area",
        "postal_region_code",
    )
    for name in postal_level:
        helper = getattr(address, name)
        assert helper(first.postal_address) == helper(
            second.postal_address
        ), f"{name} moved between the two region settings"
    assert address.split_plus_code(first.plus_code) == address.split_plus_code(
        second.plus_code
    ), "split_plus_code moved between the two region settings"


# ---------------------------------------------------------------------------
# Example 13. No street level and no components at all


def test_guide_example_13_no_street_level_and_no_components():
    # The premise level place loads the A6 name of the A5 and A6
    # pair, one evidence item under two case names.
    japan = recorded_place("recorded_A6_japanese_block_addressing.json")
    assert address.is_premise_level(japan) is True

    welsh = recorded_place("recorded_A12_long_village_name.json")
    city = address.resolve_city(welsh)
    assert (city.value, city.carrier, city.confidence) == (
        None,
        None,
        address.CONFIDENCE_NONE,
    )
    assert address.country_code(welsh) is None
    assert address.postal_code(welsh).status == address.POSTAL_ABSENT


# ---------------------------------------------------------------------------
# Example 14. Splitting a compound plus code and the global only case


def test_guide_example_14_plus_code_splits():
    brooklyn = recorded_place("recorded_A2_no_locality_sublocality_city.json")
    parts = address.split_plus_code(brooklyn.plus_code)
    assert parts is not None
    assert (parts.code_part, parts.locality_text) == (
        "P27Q+Q9",
        "Brooklyn, NY, USA",
    )

    mall = recorded_place("recorded_P15_richest_mall_store.json")
    parts = address.split_plus_code(mall.plus_code)
    assert parts is not None
    assert (parts.code_part, parts.locality_text) == (
        "83G4+2P",
        "Santa Clara, CA, USA",
    )

    saigon = recorded_place("recorded_P15_details_depth_saigon.json")
    parts = address.split_plus_code(saigon.plus_code)
    assert parts is not None
    assert (parts.code_part, parts.locality_text) == (
        "QMX9+V7",
        "Tan Son Hoa, Ho Chi Minh, Vietnam",
    )

    # The global only place loads the V5 name of the P1 and V5
    # pair, one evidence item under two case names.
    everest = recorded_place("recorded_V5_plus_code_global_only.json")
    assert address.split_plus_code(everest.plus_code) is None
    assert everest.plus_code is not None
    assert everest.plus_code.global_code == "7MV8XWQG+74"


# ---------------------------------------------------------------------------
# Example 15. Assembling a display line by hand without inventing fields


def test_guide_example_15_hand_assembly_without_invented_fields():
    place = recorded_place("recorded_A7_rtl_script_address.json", 1)
    components = place.address_components
    untyped = address.untyped_components(components)
    lost = [
        component.long_text for component in untyped if component.long_text
    ]
    assert lost == ["Level 3, Armani Hotel Dubai"]
    premise_texts = address.component_long_texts(
        components, types.TYPE_PREMISE
    )
    assert premise_texts == ("برج خليفة",)
    assert len(address.find_components(components, types.TYPE_ROUTE)) == 1
    line = ", ".join(
        component.long_text for component in components if component.long_text
    )
    assert "Level 3, Armani Hotel Dubai" in line


# ---------------------------------------------------------------------------
# Example 16. Deduplication on the place ID and nothing else


def test_guide_example_16_dedup_on_place_id():
    japanese = recorded_place("recorded_A8_tokyo_japanese.json")
    english = recorded_place("recorded_A8_tokyo_english.json")
    assert japanese.id == english.id
    japanese_texts = tuple(
        c.long_text for c in japanese.address_components
    )
    english_texts = tuple(c.long_text for c in english.address_components)
    assert japanese_texts != english_texts

    place = recorded_place("recorded_A13_premise_and_subpremise.json")
    premise = address.find_component(
        place.address_components, types.TYPE_PREMISE
    )
    level_4 = address.find_component(
        place.address_components, types.TYPE_SUBLOCALITY_LEVEL_4
    )
    assert premise is not None and level_4 is not None
    assert premise.long_text == level_4.long_text == "３７"
    assert premise is not level_4


# ---------------------------------------------------------------------------
# Example 17. Survival on the synthesized empty shapes


def test_guide_example_17_synthesized_empty_shapes_survival():
    empty_text = synthesized_place(
        "synthesized_A11_component_present_but_empty.json", 0
    )
    route = address.find_component(
        empty_text.address_components, types.TYPE_ROUTE
    )
    assert route is not None
    assert (
        address.component_long_text(
            empty_text.address_components, types.TYPE_ROUTE
        )
        is None
    )
    assert (
        address.resolve_city(empty_text).confidence
        == address.CONFIDENCE_NONE
    )

    empty_list = synthesized_place(
        "synthesized_A11_component_present_but_empty.json", 1
    )
    assert empty_list.address_components == []
    assert (
        address.resolve_city(empty_list).confidence
        == address.CONFIDENCE_NONE
    )


# ---------------------------------------------------------------------------
# Example 18. Caller argument errors raise ConfigError


def test_guide_example_18_caller_errors_raise_config_error():
    with pytest.raises(ConfigError):
        address.find_component("route,locality", types.TYPE_ROUTE)
    with pytest.raises(ConfigError):
        address.find_component([], 5)
    with pytest.raises(ConfigError):
        address.find_component([], "")


# ---------------------------------------------------------------------------
# Boundary sentence pins

PIN_1 = (
    "Google states that the response format is not guaranteed to "
    "remain the same between requests."
)
PIN_2 = (
    "The address component array does not necessarily include all "
    "the political entities that contain an address."
)
PIN_3 = (
    "The corpus behind this guide was recorded in October 2026 and "
    "this guide makes no claim about current API behaviour."
)
PIN_4 = (
    "A prevalence claim in this guide rests on cassette counts and "
    "never on a one place or two place fixture excerpt."
)
PIN_5 = (
    "The Japan precedence rests on one Asakusa query in Tokyo and "
    "its places sit inside one special ward set with 40 observations "
    "over 22 distinct places in two request language sets over that "
    "same query and the district row claims recorded special ward "
    "geometry and no wider Japanese geometry."
)
PIN_6 = (
    "The Emirates precedence rests on one Downtown Dubai search set "
    "in Arabic with 20 distinct places and it claims that sampled "
    "locality and no wider Emirates geometry."
)
PIN_7 = (
    "The British answer rests on one village set at "
    "Bourton-on-the-Water with 20 distinct places in one search set "
    "and it claims that sampled village geometry and no wider "
    "British geometry."
)
PIN_8 = (
    "The United States reading rests on 3 details places across 2 "
    "states with 3 different geometries and no American search set "
    "with components exists and every American claim in the guide "
    "must carry this thin warning in the same paragraph."
)
PIN_9 = (
    "The Vietnam reading rests on 1 distinct place seen twice in "
    "two details calls under English and German requests and it "
    "must be presented as single place status wherever it appears."
)
PIN_10 = (
    "The Israel reading rests on 1 distinct place seen twice under "
    "two region settings and it must be presented as single place "
    "status wherever it appears."
)
PIN_11 = (
    "A primary grade means the value came from the stated table for "
    "the sampled region of its country and it does not mean a "
    "surveyed national rule."
)
PIN_12 = (
    "Contested reports a live rivalry rather than a confidence "
    "level and a consumer must not sort a contested result as "
    "weaker than a fallback result."
)
PIN_13 = (
    "The British headline in resolve_city is an interim rule and "
    "not a finding of this guide."
)
PIN_14 = (
    "placekit.address ships no formatter and no display composer "
    "and no envelope renderer."
)
PIN_15 = "The place ID remains the only join key across scripts."
PIN_16 = (
    "The locality text of a compound plus code is reference text "
    "as sent and no helper feeds it into city resolution."
)
PIN_17 = (
    "No recorded instance of an empty text component or an empty "
    "component list exists anywhere in the corpus."
)
PIN_18 = "Places components cannot carry a deliverability verdict."
PIN_19 = (
    "A result from this module is a reading of one response and "
    "its confidence grade is part of that reading."
)
PIN_20 = (
    "No resolved city in this guide is a fact of the same kind as "
    "a place ID."
)

ALL_PINS = (
    PIN_1,
    PIN_2,
    PIN_3,
    PIN_4,
    PIN_5,
    PIN_6,
    PIN_7,
    PIN_8,
    PIN_9,
    PIN_10,
    PIN_11,
    PIN_12,
    PIN_13,
    PIN_14,
    PIN_15,
    PIN_16,
    PIN_17,
    PIN_18,
    PIN_19,
    PIN_20,
)


def _normalised(text: str) -> str:
    return " ".join(text.split())


def test_guide_file_exists_and_names_the_boundaries():
    guide = (REPO_ROOT / "NORMALIZATION.md").read_text()
    # Whitespace is normalised before the substring checks, so a
    # rewrap that changes no wording cannot fail these pins while
    # a wording softening still does.
    guide = _normalised(guide)
    for pin in ALL_PINS:
        assert _normalised(pin) in guide


# ---------------------------------------------------------------------------
# Structural test. Scope placement and claim tags

TAGS = (
    "[Recorded]",
    "[Cassette reported]",
    "[Synthesized]",
    "[Stated rule]",
    "[Heuristic]",
    "[Recipe]",
    "[Research]",
    "[Cannot promise]",
)


def _units(guide: str):
    """Split the guide into section and subsection units.

    Sections split on level 2 headings and subsections on level 3
    headings. A section unit holds its whole text including its
    subsections, and a subsection unit holds its own text, so a
    scope sentence can be asserted inside the unit it must travel
    with.
    """
    sections: dict[str, str] = {}
    subsections: dict[str, str] = {}
    section_name = ""
    subsection_name = ""
    section_lines: list[str] = []
    subsection_lines: list[str] = []

    def flush() -> None:
        if section_name:
            sections[section_name] = "\n".join(section_lines)
        if subsection_name:
            subsections[subsection_name] = "\n".join(subsection_lines)

    for line in guide.splitlines():
        if line.startswith("## "):
            flush()
            section_name = line[3:].strip()
            subsection_name = ""
            section_lines = [line]
            subsection_lines = []
        elif line.startswith("### "):
            if subsection_name:
                subsections[subsection_name] = "\n".join(subsection_lines)
            subsection_name = line[4:].strip()
            subsection_lines = [line]
            section_lines.append(line)
        else:
            section_lines.append(line)
            if subsection_name:
                subsection_lines.append(line)
    flush()
    return sections, subsections


def _section(sections: dict[str, str], number: int) -> str:
    for name, text in sections.items():
        if name.startswith(f"{number}."):
            return text
    raise AssertionError(f"guide section {number} not found")


def _recipe(subsections: dict[str, str], number: int) -> str:
    for name, text in subsections.items():
        if name.startswith(f"Recipe {number}."):
            return text
    raise AssertionError(f"recipe {number} not found")


def _subsection(subsections: dict[str, str], name: str) -> str:
    if name in subsections:
        return subsections[name]
    raise AssertionError(f"guide subsection {name} not found")


def _claim_units(text: str):
    """Yield the claim bearing units of one guide section.

    A unit is a prose paragraph, a table row, or a list item,
    outside fenced code blocks and headings. Table header rows and
    separator rows are furniture and are skipped.
    """
    blocks: list[list[str]] = []
    block: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.startswith("```"):
            if block:
                blocks.append(block)
                block = []
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not line.strip():
            if block:
                blocks.append(block)
                block = []
            continue
        block.append(line)
    if block:
        blocks.append(block)

    for block in blocks:
        first = block[0].lstrip()
        if first.startswith("#"):
            continue
        if first.startswith("|"):
            rows = [row for row in block if row.lstrip().startswith("|")]
            for index, row in enumerate(rows):
                cells = [
                    cell.strip() for cell in row.strip().strip("|").split("|")
                ]
                if all(cell and set(cell) <= set("-: ") for cell in cells):
                    continue
                if index == 0:
                    continue
                yield cells[0] if cells else ""
            continue
        if first.startswith("- "):
            item: list[str] = []
            for line in block:
                if line.lstrip().startswith("- "):
                    if item:
                        yield " ".join(item)
                    item = [line.lstrip()[2:]]
                else:
                    item.append(line.strip())
            if item:
                yield " ".join(item)
            continue
        yield " ".join(line.strip() for line in block)


def _opens_with_tag(unit: str) -> bool:
    unit = unit.strip()
    for tag in TAGS:
        if unit == tag or unit.startswith(tag + " "):
            return True
    return False


def test_guide_structure_keeps_scope_with_its_claims():
    guide = (REPO_ROOT / "NORMALIZATION.md").read_text()
    sections, subsections = _units(guide)

    section_5 = _normalised(_section(sections, 5))
    section_6 = _normalised(_section(sections, 6))
    recipe_1 = _normalised(_recipe(subsections, 1))
    recipe_4 = _normalised(_recipe(subsections, 4))
    recipe_8 = _normalised(_recipe(subsections, 8))

    # Placement, not mere presence. A scope sentence that survives
    # only in the marking key section or only in the boundary
    # index fails these assertions by construction.
    for pin in (PIN_5, PIN_6, PIN_7):
        assert _normalised(pin) in section_5
    assert _normalised(PIN_8) in section_5
    assert _normalised(PIN_8) in recipe_1
    assert _normalised(PIN_9) in section_5
    assert _normalised(PIN_9) in section_6
    assert _normalised(PIN_9) in recipe_8
    assert _normalised(PIN_10) in section_5
    assert _normalised(PIN_10) in recipe_4
    assert _normalised(PIN_19) in section_6
    assert _normalised(PIN_20) in recipe_1

    # Every boundary pin also sits inside its designed home
    # section, so a sentence drifted into the boundary index as
    # its only home fails here even though the flat presence pin
    # still finds its words somewhere in the file.
    home_sections = (
        (PIN_1, 1),
        (PIN_2, 1),
        (PIN_3, 1),
        (PIN_4, 2),
        (PIN_5, 5),
        (PIN_6, 5),
        (PIN_7, 5),
        (PIN_8, 5),
        (PIN_9, 5),
        (PIN_10, 5),
        (PIN_11, 6),
        (PIN_12, 6),
        (PIN_13, 7),
        (PIN_14, 3),
        (PIN_15, 6),
        (PIN_16, 6),
        (PIN_17, 4),
        (PIN_18, 1),
        (PIN_19, 6),
        (PIN_20, 7),
    )
    for pin, number in home_sections:
        assert _normalised(pin) in _normalised(
            _section(sections, number)
        ), f"a boundary pin sits outside its home section {number}"

    # The country scope pins travel inside their own country
    # subsection, not merely inside the country section, so a
    # scope sentence parked under a neighbouring country leaves
    # its own claims unbounded and fails here.
    country_subsections = (
        (PIN_5, "Japan"),
        (PIN_6, "United Arab Emirates"),
        (PIN_7, "United Kingdom"),
        (PIN_8, "United States"),
        (PIN_9, "Vietnam"),
        (PIN_10, "Israel"),
    )
    for pin, name in country_subsections:
        assert _normalised(pin) in _normalised(
            _subsection(subsections, name)
        ), f"a scope pin sits outside its {name} subsection"

    recipe_2 = _normalised(_recipe(subsections, 2))
    recipe_6 = _normalised(_recipe(subsections, 6))
    assert _normalised(PIN_13) in recipe_2
    assert _normalised(PIN_15) in recipe_6
    assert _normalised(PIN_16) in recipe_8

    # Every claim bearing paragraph, table row, and list item in
    # the claim bearing sections opens with exactly one tag. The
    # front matter and guide section 2 are the named apparatus
    # exemptions and are not scanned.
    for number in (1, 3, 4, 5, 6, 7, 8, 9):
        text = _section(sections, number)
        for unit in _claim_units(text):
            assert _opens_with_tag(unit), (
                f"guide section {number} has a claim bearing unit "
                f"with no opening tag: {unit[:80]}"
            )

    # The example 15 no formatter check, as text. The calls in the
    # recipe 3 code block are only the named reader functions plus
    # a string join, so a formatter call appearing in the block
    # fails here rather than as behaviour.
    recipe_3 = _recipe(subsections, 3)
    blocks = []
    current: list[str] = []
    in_fence = False
    for line in recipe_3.splitlines():
        if line.startswith("```"):
            if in_fence:
                blocks.append("\n".join(current))
                current = []
            in_fence = not in_fence
            continue
        if in_fence:
            current.append(line)
    assert blocks, "recipe 3 carries no code block"
    calls: set[str] = set()
    for node in ast.walk(ast.parse(blocks[0])):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.add(func.id)
            elif isinstance(func, ast.Attribute):
                calls.add(func.attr)
    allowed = {
        "component_long_texts",
        "find_components",
        "untyped_components",
        "join",
    }
    assert calls <= allowed, f"example 15 calls outside the readers: {calls}"
    assert "join" in calls
