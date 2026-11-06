"""Pins for the Round 53 repair pass over the address port.

The port of the placekit.address readings into the Rust core
kept the ordinary corpus identical and diverged on three
families of hostile input the red team drove against both
implementations. These pins hold the repaired behaviour over
the public API, one per driven shape.

A text carrying a lone surrogate passed every Python funnel
and worked in the pre port module, and the ported crossing
refused it, failing whole readings on fields the reading never
touched. The crossing now carries texts as byte strings under
a codec that round trips lone surrogates exactly, and the
first pins hold each reading the red team named.

The port also ran one wide exercise pass at every site, where
the pre port scans were shaped per helper, early exit at the
first landed match and blind to needles the helper never
tested. The middle pins hold the per scan shape, that a
component past a landed match is never tested, that the
postal read tests no sublocality needle and never routes, and
that the composite flags report the first error in the old
composition order. One pin holds the read count of the
validation funnel itself, which the conversion no longer adds
to.

The last pins hold the two sites where an operation answer is
the behaviour, the truthiness of the caller types object in
the untyped bucket and the partition and strip calls in the
compound code split, and the two readings that hand back the
caller string object itself.
"""

from __future__ import annotations

import pytest

from placekit import ConfigError, address
from placekit.models import AddressComponent, Place, PostalAddress


def _comp(long_text="", short_text="", types=()):
    return AddressComponent(
        long_text=long_text, short_text=short_text, types=list(types)
    )


def _comp_with_types(long_text, short_text, types_obj):
    comp = AddressComponent(long_text=long_text, short_text=short_text)
    object.__setattr__(comp, "types", types_obj)
    return comp


def _place(comps, postal=None):
    return Place(
        id="round-53-pin", address_components=comps, postal_address=postal
    )


class RaiseContains(list):
    """A types list whose contains raises for chosen needles."""

    def __init__(self, items, needles=None):
        super().__init__(items)
        self._needles = needles

    def __contains__(self, item):
        if self._needles is None or item in self._needles:
            raise RuntimeError("contains boom")
        return super().__contains__(item)


class UpperRaiseStr(str):
    def upper(self):
        raise RuntimeError("upper boom")


class LenLieList(list):
    def __len__(self):
        return 0


class BoolRaiseList(list):
    def __bool__(self):
        raise RuntimeError("bool boom")


class PartitionRaiseStr(str):
    def partition(self, sep):
        raise RuntimeError("partition boom")


class StripLieStr(str):
    def strip(self, chars=None):
        return "Lied Locality"


class PartitionLieStr(str):
    def partition(self, sep):
        code, found, rest = str.partition(self, sep)
        return code, found, StripLieStr(rest)


class SubStr(str):
    pass


# ----------------------------------------------------------------
# Lone surrogates cross the boundary and behave as before.
# ----------------------------------------------------------------


def test_surrogate_locality_text_resolves_the_city():
    comps = [
        _comp("Tok\ud800yo", "", ["locality", "political"]),
        _comp("United States", "US", ["country", "political"]),
    ]
    result = address.resolve_city(_place(comps))
    assert result.value == "Tok\ud800yo"
    assert result.country_code == "US"


def test_surrogate_in_untouched_fields_leaves_the_reading_alone():
    comps = [
        _comp("Bavaria", "B\udfffY", ["administrative_area_level_1", "political"]),
        _comp("Odd", "X\ud800", ["route"]),
        _comp("Germany", "DE", ["country", "political"]),
    ]
    assert address.administrative_area(_place(comps)) == "Bavaria"


def test_surrogate_type_item_matches_no_needle():
    comps = [_comp("Thing", "", ["rou\ud800te"])]
    assert address.find_components(comps, "route") == ()


def test_surrogate_type_name_argument_matches_nothing():
    comps = [_comp("Thing", "", ["route"])]
    assert address.find_components(comps, "rou\ud800te") == ()


def test_surrogate_locality_text_survives_the_compound_split():
    parts = address.split_compound_code("8FVC9G \ud800Town")
    assert parts is not None
    assert parts.code_part == "8FVC9G"
    assert parts.locality_text == "\ud800Town"


def test_surrogate_postal_value_stands_as_sent():
    place = _place([], PostalAddress(postal_code="123\ud800"))
    result = address.postal_code(place)
    assert result.value == "123\ud800"
    assert result.status == address.POSTAL_PRESENT


def test_surrogate_country_code_flows_through_the_readings():
    comps = [
        _comp("LocCity", "", ["locality", "political"]),
        AddressComponent(
            long_text="Nowhere",
            short_text="J\ud800",
            types=["country", "political"],
        ),
    ]
    result = address.resolve_city(_place(comps))
    assert result.value == "LocCity"
    assert result.country_code == "J\ud800"


# ----------------------------------------------------------------
# The exercise is shaped per scan, the way the old scans ran.
# ----------------------------------------------------------------


def test_administrative_area_never_tests_trailing_components():
    comps = [
        _comp("Bavaria", "BY", ["administrative_area_level_1", "political"]),
        _comp_with_types("Boom", "", RaiseContains(["route"])),
        _comp("Germany", "DE", ["country", "political"]),
    ]
    assert address.administrative_area(_place(comps)) == "Bavaria"


def test_generic_city_chain_stops_exercising_at_the_landed_scan():
    comps = [
        _comp("LocCity", "", ["locality", "political"]),
        _comp_with_types(
            "Boom",
            "",
            RaiseContains(
                ["route"],
                {"postal_town", "sublocality_level_1", "sublocality_level_2"},
            ),
        ),
        _comp("Country", "US", ["country", "political"]),
    ]
    assert address.resolve_city(_place(comps)).value == "LocCity"


def test_british_city_chain_stops_both_scans_at_the_landing():
    comps = [
        _comp("Same", "", ["locality", "postal_town"]),
        _comp_with_types("Boom", "", RaiseContains(["x"], {"postal_town"})),
        _comp("Country", "GB", ["country", "political"]),
    ]
    rows = address.city_resolutions(_place(comps))
    assert rows[0].value == "Same"


def test_postal_read_never_tests_the_japanese_sublocality_needle():
    comps = [
        _comp_with_types("Boom", "", RaiseContains(["x"], {"sublocality_level_2"})),
        _comp("111-0032", "", ["postal_code"]),
        _comp("Japan", "JP", ["country", "political"]),
    ]
    place = _place(
        comps, PostalAddress(region_code="JP", postal_code="111-0032")
    )
    assert address.postal_code(place).value == "111-0032"


def test_postal_read_never_tests_the_emirates_sublocality_needle():
    comps = [
        _comp_with_types("Boom", "", RaiseContains(["x"], {"sublocality_level_1"})),
        _comp("UAE", "AE", ["country", "political"]),
    ]
    place = _place(comps, PostalAddress(region_code="AE", postal_code="999"))
    assert address.postal_code(place).value == "999"


def test_postal_read_never_uppercases_the_country_text():
    comps = [
        _comp("111-0032", "", ["postal_code"]),
        AddressComponent(
            long_text="Japan",
            short_text=UpperRaiseStr("JP"),
            types=["country", "political"],
        ),
    ]
    place = _place(comps, PostalAddress(postal_code="111-0032"))
    assert address.postal_code(place).value == "111-0032"


def test_spans_multiple_routes_tests_no_other_needle():
    comps = [
        _comp("Route One", "", ["route"]),
        _comp("Route Two", "", ["route"]),
        _comp_with_types("Boom", "", RaiseContains(["z"], {"premise"})),
    ]
    assert address.spans_multiple_routes(comps) is True


def test_no_street_level_stops_at_the_first_landed_needle():
    comps = [
        _comp("42", "", ["street_number"]),
        _comp_with_types("Boom", "", RaiseContains(["z"], {"country"})),
    ]
    assert address.has_no_street_level(comps) is False


def test_premise_level_tests_no_postal_needle():
    comps = [
        _comp("Block", "", ["premise"]),
        _comp_with_types("Boom", "", RaiseContains(["z"], {"postal_code"})),
    ]
    assert address.is_premise_level(_place(comps)) is True


def test_address_flags_reports_the_postal_error_before_the_needle():
    comps = [
        _comp_with_types("Boom", "", RaiseContains(["z"], {"locality"})),
        _comp("Japan", "JP", ["country", "political"]),
    ]
    place = _place(comps, PostalAddress(postal_code=123))
    with pytest.raises(ConfigError) as caught:
        address.address_flags(place)
    chain = str(caught.value) + str(caught.value.__cause__)
    assert "postal_code" in chain
    assert "contains boom" not in chain


def test_the_funnel_read_count_is_the_whole_read_count():
    class CountingComponent(AddressComponent):
        reads = 0

        @property
        def long_text(self):
            type(self).reads += 1
            if type(self).reads >= 3:
                raise RuntimeError("third read boom")
            return "Main Street"

    comp = object.__new__(CountingComponent)
    for field_name, value in (
        ("short_text", ""),
        ("types", ["route"]),
        ("language_code", None),
        ("raw", {}),
    ):
        vars(AddressComponent)[field_name].__set__(comp, value)
    vars(AddressComponent)["long_text"].__set__(comp, "Main Street")
    CountingComponent.reads = 0
    found = address.find_components([comp], "route")
    assert len(found) == 1
    assert CountingComponent.reads == 2


# ----------------------------------------------------------------
# The two sites where the operation answer is the behaviour.
# ----------------------------------------------------------------


def test_untyped_bucket_follows_the_types_object_truthiness():
    routey = _comp_with_types("Routey", "", LenLieList(["route"]))
    plain = _comp("Plain", "", [])
    assert address.untyped_components([routey, plain]) == (routey, plain)


def test_untyped_bucket_surfaces_a_raising_truth_test():
    comps = [_comp_with_types("Routey", "", BoolRaiseList(["route"]))]
    with pytest.raises(ConfigError):
        address.untyped_components(comps)


def test_compound_split_surfaces_a_raising_partition():
    with pytest.raises(ConfigError):
        address.split_compound_code(PartitionRaiseStr("8FVC9G+8X Toronto"))


def test_compound_split_keeps_a_lying_strip_answer():
    parts = address.split_compound_code(
        PartitionLieStr("8FVC9G+8X    Toronto   ")
    )
    assert parts is not None
    assert parts.code_part == "8FVC9G+8X"
    assert parts.locality_text == "Lied Locality"


# ----------------------------------------------------------------
# Two readings hand back the caller string object itself.
# ----------------------------------------------------------------


def test_administrative_area_returns_the_caller_text_object():
    comps = [
        AddressComponent(
            long_text=SubStr("Bavaria"),
            short_text=SubStr("BY"),
            types=["administrative_area_level_1"],
        ),
        AddressComponent(
            long_text=SubStr("Germany"),
            short_text=SubStr("DE"),
            types=["country", "political"],
        ),
    ]
    assert address.administrative_area(_place(comps)) is comps[0].long_text


def test_postal_value_returns_the_caller_text_object():
    comps = [
        AddressComponent(
            long_text=SubStr("Germany"),
            short_text=SubStr("DE"),
            types=["country", "political"],
        ),
        AddressComponent(
            long_text=SubStr("111"),
            short_text="",
            types=["postal_code"],
        ),
    ]
    result = address.postal_code(_place(comps))
    assert result.value is comps[1].long_text


# ----------------------------------------------------------------
# Repair pass 2, the read pattern of the text scans themselves.
#
# The delta red team found two loci where the repaired code
# read a caller text fewer times than the pre port scans did,
# so a raise on the missing read was silently swallowed, and
# the readings that still took their text from a core row
# handed back a plain string where the old readings returned
# the caller text object itself. The old text scan read its
# landing text twice, once as its truthiness test and once as
# the value it returned, and the old spans composition read
# every route match's text once more for its filter count.
# The pins below hold the restored reads, as totals on counting
# components, as raises on planned getters, and as identity on
# the caller objects, plus the two carrier comparisons the old
# compositions ran on the caller texts and the funnel error
# reads.
# ----------------------------------------------------------------


class _CountingComponent(AddressComponent):
    """A component whose three fields are counting properties,
    so a test can hold the exact read total a reading performs
    on each field, the way the pre port scans performed it."""

    @property
    def long_text(self):
        self._reads["long_text"] += 1
        return self._values["long_text"]

    @property
    def short_text(self):
        self._reads["short_text"] += 1
        return self._values["short_text"]

    @property
    def types(self):
        self._reads["types"] += 1
        return self._values["types"]


def _counting_comp(long_text, short_text, types):
    comp = object.__new__(_CountingComponent)
    object.__setattr__(
        comp,
        "_values",
        {
            "long_text": long_text,
            "short_text": short_text,
            "types": list(types),
        },
    )
    object.__setattr__(
        comp, "_reads", {"long_text": 0, "short_text": 0, "types": 0}
    )
    vars(AddressComponent)["language_code"].__set__(comp, None)
    vars(AddressComponent)["raw"].__set__(comp, {})
    return comp


def _counts(comp):
    reads = comp._reads
    return (reads["long_text"], reads["short_text"], reads["types"])


def _probe_place():
    """The counting probe place, nine components and a postal
    address, shared by the read total pins."""
    comps = [
        _counting_comp("42", "", ["street_number"]),
        _counting_comp("Main Street", "Main St", ["route"]),
        _counting_comp("Second Street", "", ["route"]),
        _counting_comp("Springfield", "", ["locality", "political"]),
        _counting_comp(
            "Bavaria", "BY", ["administrative_area_level_1", "political"]
        ),
        _counting_comp("United States", "US", ["country", "political"]),
        _counting_comp("62701", "", ["postal_code"]),
        _counting_comp("Block 5", "", ["premise"]),
        _counting_comp("Typeless", "", []),
    ]
    place = Place(
        id="round-53-pass-2",
        address_components=comps,
        postal_address=PostalAddress(
            region_code="US", postal_code="62701", locality="Postal City"
        ),
    )
    return comps, place


class _PlannedComponent(AddressComponent):
    """A component whose long text answers from a per read
    plan. A plan entry is the value to return, or the string
    RAISE to raise on that read."""

    @property
    def long_text(self):
        state = self._state
        state["n"] += 1
        plan = state["plan"]
        step = plan[min(state["n"], len(plan)) - 1]
        if step == "RAISE":
            raise RuntimeError(f"read {state['n']} boom")
        return step


def _planned_comp(plan, short_text, types):
    comp = object.__new__(_PlannedComponent)
    object.__setattr__(comp, "_state", {"plan": list(plan), "n": 0})
    for field_name, value in (
        ("short_text", short_text),
        ("types", list(types)),
        ("language_code", None),
        ("raw", {}),
    ):
        vars(AddressComponent)[field_name].__set__(comp, value)
    return comp


class EqRaiseStr(str):
    def __eq__(self, other):
        raise RuntimeError("eq boom")

    def __ne__(self, other):
        raise RuntimeError("eq boom")

    __hash__ = str.__hash__


def test_spans_reads_the_long_text_of_every_route_match():
    comps, _place_unused = _probe_place()
    assert address.spans_multiple_routes(comps) is True
    # The funnel reads each text twice. The spans composition
    # then reads the long text of each route match once more
    # for its filter count, and no other text again.
    assert _counts(comps[1]) == (3, 2, 3)
    assert _counts(comps[2]) == (3, 2, 3)
    assert _counts(comps[0]) == (2, 2, 3)
    assert _counts(comps[3]) == (2, 2, 3)


def test_city_reads_the_landing_text_again_as_its_value():
    comps, place = _probe_place()
    rows = address.city_resolutions(place)
    assert rows[0].value == "Springfield"
    # The locality text is read twice by the funnel, once as
    # the scan truthiness test, and once again as the returned
    # value. The country short text pays the same four reads
    # through the country scan.
    assert _counts(comps[3]) == (4, 2, 4)
    assert _counts(comps[5]) == (2, 4, 3)


def test_flags_read_totals_match_the_pre_port_composition():
    comps, place = _probe_place()
    flags = address.address_flags(place)
    assert flags.spans_multiple_routes is True
    assert flags.has_city_carrier is True
    # Every field of every component, at the totals the pre
    # port composition produced on this place, the composed
    # scans paying their reads in field order over one funnel.
    expected = [
        (2, 2, 15),
        (3, 2, 12),
        (3, 2, 11),
        (4, 2, 11),
        (2, 2, 10),
        (2, 8, 10),
        (4, 2, 10),
        (2, 2, 9),
        (2, 2, 7),
    ]
    assert [_counts(comp) for comp in comps] == expected


def test_district_japan_reads_the_landing_text_again():
    ward = _counting_comp(
        "Taito City", "", ["sublocality_level_2", "sublocality"]
    )
    country = _counting_comp("Japan", "JP", ["country", "political"])
    result = address.resolve_district(_place([ward, country]))
    assert result.value == "Taito City"
    assert _counts(ward) == (4, 2, 4)
    assert _counts(country) == (2, 4, 3)


def test_district_emirates_reads_the_landing_text_again():
    district = _counting_comp(
        "Downtown Dubai", "", ["sublocality_level_1", "sublocality"]
    )
    country = _counting_comp(
        "United Arab Emirates", "AE", ["country", "political"]
    )
    result = address.resolve_district(_place([district, country]))
    assert result.value == "Downtown Dubai"
    assert _counts(district)[0] == 4


def test_british_chain_reads_both_landing_texts_again():
    locality = _counting_comp(
        "Bourton-on-the-Water", "", ["locality", "political"]
    )
    town = _counting_comp("Cheltenham", "", ["postal_town"])
    country = _counting_comp("United Kingdom", "GB", ["country", "political"])
    rows = address.city_resolutions(_place([locality, town, country]))
    assert rows[0].value == "Bourton-on-the-Water"
    assert rows[0].competing_value == "Cheltenham"
    assert _counts(locality)[0] == 4
    assert _counts(town)[0] == 4


def test_precedence_japan_reads_the_landing_text_again():
    locality = _counting_comp("Tokyo", "", ["locality", "political"])
    country = _counting_comp("Japan", "JP", ["country", "political"])
    result = address.resolve_city(_place([locality, country]))
    assert result.value == "Tokyo"
    assert _counts(locality)[0] == 4


def test_spans_surfaces_a_route_text_that_raises_on_the_filter_read():
    comps = [
        _comp("Main Street", "", ["route"]),
        _planned_comp(
            ["Second Street", "Second Street", "RAISE"], "", ["route"]
        ),
    ]
    with pytest.raises(ConfigError):
        address.spans_multiple_routes(comps)


def test_flags_surfaces_a_route_text_that_raises_on_the_filter_read():
    comps = [
        _comp("Springfield", "", ["locality", "political"]),
        _comp("Main Street", "", ["route"]),
        _planned_comp(
            ["Second Street", "Second Street", "RAISE"], "", ["route"]
        ),
        _comp("United States", "US", ["country", "political"]),
    ]
    with pytest.raises(ConfigError):
        address.address_flags(_place(comps))


def test_city_surfaces_a_landing_text_that_raises_on_the_return_read():
    comps = [
        _planned_comp(
            ["Springfield", "Springfield", "Springfield", "RAISE"],
            "",
            ["locality", "political"],
        ),
        _comp("United States", "US", ["country", "political"]),
    ]
    with pytest.raises(ConfigError):
        address.resolve_city(_place(comps))


def test_district_surfaces_a_landing_text_that_raises_on_the_return_read():
    comps = [
        _planned_comp(
            ["Taito City", "Taito City", "Taito City", "RAISE"],
            "",
            ["sublocality_level_2", "sublocality"],
        ),
        _comp("Japan", "JP", ["country", "political"]),
    ]
    with pytest.raises(ConfigError):
        address.resolve_district(_place(comps))


def test_british_chain_surfaces_a_town_text_that_raises_on_the_return_read():
    comps = [
        _comp("Bourton-on-the-Water", "", ["locality", "political"]),
        _planned_comp(
            ["Cheltenham", "Cheltenham", "Cheltenham", "RAISE"],
            "",
            ["postal_town"],
        ),
        _comp("United Kingdom", "GB", ["country", "political"]),
    ]
    with pytest.raises(ConfigError):
        address.city_resolutions(_place(comps))


def test_precedence_chain_surfaces_a_locality_that_raises_on_the_return_read():
    comps = [
        _planned_comp(
            ["Tokyo", "Tokyo", "Tokyo", "RAISE"],
            "",
            ["locality", "political"],
        ),
        _comp("Japan", "JP", ["country", "political"]),
    ]
    with pytest.raises(ConfigError):
        address.resolve_city(_place(comps))


def test_city_returns_the_word_the_return_read_answers():
    comps = [
        _planned_comp(
            ["Springfield", "Springfield", "Springfield", "Changed"],
            "",
            ["locality", "political"],
        ),
        _comp("United States", "US", ["country", "political"]),
    ]
    result = address.resolve_city(_place(comps))
    assert result.value == "Changed"


def test_city_value_is_the_caller_text_object():
    loc = SubStr("Springfield")
    comps = [
        AddressComponent(long_text=loc, short_text="", types=["locality"]),
        _comp("United States", "US", ["country", "political"]),
    ]
    result = address.resolve_city(_place(comps))
    assert result.value is loc


def test_british_values_are_the_caller_text_objects():
    loc = SubStr("Bourton-on-the-Water")
    town = SubStr("Cheltenham")
    comps = [
        AddressComponent(long_text=loc, short_text="", types=["locality"]),
        AddressComponent(
            long_text=town, short_text="", types=["postal_town"]
        ),
        _comp("United Kingdom", "GB", ["country", "political"]),
    ]
    rows = address.city_resolutions(_place(comps))
    assert rows[0].value is loc
    assert rows[0].competing_value is town
    assert rows[1].value is town
    assert rows[1].competing_value is loc


def test_district_value_is_the_caller_text_object():
    ward = SubStr("Taito City")
    comps = [
        AddressComponent(
            long_text=ward, short_text="", types=["sublocality_level_2"]
        ),
        _comp("Japan", "JP", ["country", "political"]),
    ]
    result = address.resolve_district(_place(comps))
    assert result.value is ward


def test_emirates_postal_city_value_is_the_postal_field_object():
    loc = SubStr("Dubai")
    place = _place(
        [_comp("United Arab Emirates", "AE", ["country", "political"])],
        PostalAddress(region_code="AE", locality=loc),
    )
    result = address.resolve_city(place)
    assert result.value is loc


def test_generic_postal_city_value_is_the_postal_field_object():
    loc = SubStr("Postal City")
    place = _place(
        [_comp("United States", "US", ["country", "political"])],
        PostalAddress(region_code="US", locality=loc),
    )
    result = address.resolve_city(place)
    assert result.value is loc


def test_postal_comparison_surfaces_a_raising_equality():
    comps = [
        AddressComponent(
            long_text=EqRaiseStr("62701"),
            short_text="",
            types=["postal_code"],
        ),
        _comp("United States", "US", ["country", "political"]),
    ]
    place = _place(comps, PostalAddress(postal_code="62701"))
    with pytest.raises(ConfigError) as caught:
        address.postal_code(place)
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_british_comparison_surfaces_a_raising_equality():
    comps = [
        AddressComponent(
            long_text=EqRaiseStr("Bourton-on-the-Water"),
            short_text="",
            types=["locality"],
        ),
        _comp("Cheltenham", "", ["postal_town"]),
        _comp("United Kingdom", "GB", ["country", "political"]),
    ]
    with pytest.raises(ConfigError) as caught:
        address.city_resolutions(_place(comps))
    assert isinstance(caught.value.__cause__, RuntimeError)


class _FunnelPlanComponent(AddressComponent):
    """A component whose three fields answer from per read
    plans, so a test can place a value of the wrong type on the
    funnel's own reads and a raise on the read its error
    message performs."""

    @property
    def long_text(self):
        return _planned_read(self._plans, "long_text")

    @property
    def short_text(self):
        return _planned_read(self._plans, "short_text")

    @property
    def types(self):
        return _planned_read(self._plans, "types")


def _planned_read(plans, field):
    state = plans[field]
    state["n"] += 1
    step = state["plan"][min(state["n"], len(state["plan"])) - 1]
    if step == "RAISE":
        raise RuntimeError(f"{field} read {state['n']} boom")
    return step


def _funnel_comp(plans):
    comp = object.__new__(_FunnelPlanComponent)
    full = {
        "long_text": {"plan": [""], "n": 0},
        "short_text": {"plan": [""], "n": 0},
        "types": {"plan": [[]], "n": 0},
    }
    for field, plan in plans.items():
        full[field] = {"plan": list(plan), "n": 0}
    object.__setattr__(comp, "_plans", full)
    vars(AddressComponent)["language_code"].__set__(comp, None)
    vars(AddressComponent)["raw"].__set__(comp, {})
    return comp


def test_funnel_reads_the_long_text_again_for_its_type_error():
    comp = _funnel_comp({"long_text": [123, 123, "RAISE"]})
    with pytest.raises(ConfigError) as caught:
        address.find_components([comp], "route")
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_funnel_reads_the_short_text_again_for_its_type_error():
    comp = _funnel_comp({"short_text": [123, 123, "RAISE"]})
    with pytest.raises(ConfigError) as caught:
        address.find_components([comp], "route")
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_funnel_reads_the_types_again_for_its_type_error():
    comp = _funnel_comp({"types": [123, "RAISE"]})
    with pytest.raises(ConfigError) as caught:
        address.find_components([comp], "route")
    assert isinstance(caught.value.__cause__, RuntimeError)

