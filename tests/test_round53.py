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
