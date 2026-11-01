"""Address helpers over the typed place models.

The helpers in this module read the structured address a Place
already carries, its address components and its postal address,
and answer the questions those two carrier sets raise. Which
carrier holds the city changes by country, and in two recorded
countries the carriers disagree on the same place, so a resolved
city here always travels with the carrier it came from and a
confidence grade in the open.

Three countries carry a stated answer built from recorded places
and every other country follows one generic fallback chain whose
results are capped at the heuristic grade. The Japan precedence
rests on one Asakusa query in Tokyo and its places sit inside one
special ward set. The Emirates precedence rests on one Downtown
Dubai search set. The British two value answer rests on one
village set at Bourton-on-the-Water. A primary grade means the
value came from the stated table for the sampled region of its
country and it does not mean a surveyed national rule, and the
module does not promise that a stated precedence holds beyond
the sampled locality it rests on. The United States carries no
stated precedence in this version, so American places run under
the generic chain at heuristic grade. The country code that
routes a place to a stated answer or to the generic chain is
matched without regard to letter case, while the code a helper
returns and a result carries stays the value as sent.

The surface is deliberately narrower than the address problem.
No helper parses formatted text and no helper composes a display
address or renders an envelope. No helper assembles a postal
code from prefix and suffix pieces and no helper reads a sorting
code, because the recorded corpus holds no instance of either
form. Formatting and envelope rendering belong to the guide,
which points at libaddressinput metadata instead.

A result from this module is a reading of one response and its
confidence grade is part of that reading. The module does not
promise deliverability of any address and it does not promise
stability of any reading across requests for the same place and
it does not promise completeness of the political chain behind
any place. It does not promise cross script identity between
names for one place and the place ID remains the only join key
across scripts. It does not promise disputed territory truth and
it does not promise freshness of any value it returns. No
resolved city from this module is a fact of the same kind as a
place ID.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from . import types
from .exceptions import ConfigError
from .models import AddressComponent, Place, PlusCode, PostalAddress

# Component carriers assign from the types module constants so one
# wire string lives in one home. The postal set carriers and the
# both carriers marker are new values with no types module home.
CARRIER_LOCALITY = types.TYPE_LOCALITY
CARRIER_POSTAL_TOWN = types.TYPE_POSTAL_TOWN
CARRIER_SUBLOCALITY_LEVEL_1 = types.TYPE_SUBLOCALITY_LEVEL_1
CARRIER_SUBLOCALITY_LEVEL_2 = types.TYPE_SUBLOCALITY_LEVEL_2
CARRIER_SUBLOCALITY_LEVEL_3 = types.TYPE_SUBLOCALITY_LEVEL_3
CARRIER_SUBLOCALITY_LEVEL_4 = types.TYPE_SUBLOCALITY_LEVEL_4
CARRIER_SUBLOCALITY_LEVEL_5 = types.TYPE_SUBLOCALITY_LEVEL_5
CARRIER_NEIGHBORHOOD = types.TYPE_NEIGHBORHOOD
CARRIER_ADMINISTRATIVE_AREA_LEVEL_1 = types.TYPE_ADMINISTRATIVE_AREA_LEVEL_1
CARRIER_ADMINISTRATIVE_AREA_LEVEL_2 = types.TYPE_ADMINISTRATIVE_AREA_LEVEL_2
CARRIER_POSTAL_CODE_COMPONENT = types.TYPE_POSTAL_CODE
CARRIER_COUNTRY_COMPONENT = types.TYPE_COUNTRY
CARRIER_POSTAL_ADDRESS_LOCALITY = "postal_address_locality"
CARRIER_POSTAL_ADDRESS_SUBLOCALITY = "postal_address_sublocality"
CARRIER_POSTAL_ADDRESS_ADMINISTRATIVE_AREA = "postal_address_administrative_area"
CARRIER_POSTAL_ADDRESS_POSTAL_CODE = "postal_address_postal_code"
CARRIER_POSTAL_ADDRESS_REGION_CODE = "postal_address_region_code"
CARRIER_BOTH_POSTAL = "both_postal_carriers"

CONFIDENCE_PRIMARY = "primary"
CONFIDENCE_FALLBACK = "fallback"
CONFIDENCE_CONTESTED = "contested"
CONFIDENCE_HEURISTIC = "heuristic"
CONFIDENCE_NONE = "none"
CONFIDENCE_GRADES: frozenset[str] = frozenset(
    {
        CONFIDENCE_PRIMARY,
        CONFIDENCE_FALLBACK,
        CONFIDENCE_CONTESTED,
        CONFIDENCE_HEURISTIC,
        CONFIDENCE_NONE,
    }
)

POSTAL_PRESENT = "present"
POSTAL_ABSENT = "absent"

#: Countries with a stated city precedence, built from recorded
#: places inside one sampled locality of each country.
PRECEDENCE_COUNTRIES: frozenset[str] = frozenset({"JP", "AE"})

#: Countries with a stated two value city answer instead of a
#: precedence, because the two carriers disagree on every
#: recorded place.
CONTESTED_COUNTRIES: frozenset[str] = frozenset({"GB"})


@dataclass(frozen=True, slots=True)
class CityResolution:
    """One city reading with its carrier and confidence grade.

    The competing fields carry a value only on a contested
    result, where they hold the rival value and its carrier.
    The type carries no raw field because a reading is derived
    from the typed models rather than decoded from a payload,
    and the raw of a reading stays reachable through the Place
    the caller passed.
    """

    value: Optional[str]
    carrier: Optional[str]
    confidence: str
    country_code: Optional[str] = None
    competing_value: Optional[str] = None
    competing_carrier: Optional[str] = None


@dataclass(frozen=True, slots=True)
class DistrictResolution:
    """One district reading with its carrier and confidence grade."""

    value: Optional[str]
    carrier: Optional[str]
    confidence: str
    country_code: Optional[str] = None


@dataclass(frozen=True, slots=True)
class PostalCodeResult:
    """One postal code reading with its carrier and status.

    The status keeps presence and absence distinct outcomes.
    The competing fields carry a value only when the component
    carrier and the postal carrier both hold a code and the two
    codes differ, and they hold the postal value and its carrier
    while the headline carries the component value.
    """

    value: Optional[str]
    carrier: Optional[str]
    status: str
    country_code: Optional[str] = None
    competing_value: Optional[str] = None
    competing_carrier: Optional[str] = None


@dataclass(frozen=True, slots=True)
class PlusCodeParts:
    """The two halves of a compound plus code, split at its space."""

    code_part: str
    locality_text: Optional[str]


@dataclass(frozen=True, slots=True)
class AddressFlags:
    """Presence flags for one place, computed in one snapshot."""

    has_street_number: bool
    has_route: bool
    has_premise: bool
    has_subpremise: bool
    is_premise_level: bool
    spans_multiple_routes: bool
    has_no_street_level: bool
    has_postal_code: bool
    has_postal_address: bool
    has_country: bool
    has_city_carrier: bool


def _checked_components(
    components: Sequence[AddressComponent],
) -> Sequence[AddressComponent]:
    if isinstance(components, (str, bytes)):
        raise ConfigError(
            "components must be a sequence of AddressComponent values "
            "and not a bare string or bytes"
        )
    return components


# Routing into a stated answer or the generic chain matches the
# country code without regard to letter case, so a lowercase or
# mixed case signal still reaches the answer its country carries.
# The normalisation serves the match only and the code a helper
# returns or a result carries stays the value as sent.
def _routing_country(country: Optional[str]) -> Optional[str]:
    if country is None:
        return None
    return country.upper()


def _checked_type_name(type_name: str) -> str:
    if not isinstance(type_name, str):
        raise ConfigError("type_name must be a string naming a component type")
    if not type_name:
        raise ConfigError("type_name must not be empty")
    return type_name


def find_component(
    components: Sequence[AddressComponent], type_name: str
) -> Optional[AddressComponent]:
    """Return the first component whose types contain the name.

    List order is the only order rule. The helper returns None
    when no component matches, and it returns a matching
    component even when that component carries empty text.
    """
    matches = find_components(components, type_name)
    return matches[0] if matches else None


def find_components(
    components: Sequence[AddressComponent], type_name: str
) -> tuple[AddressComponent, ...]:
    """Return every component whose types contain the name.

    Matches come back in list order and an empty tuple means
    nothing matched. Matching is exact membership in the types
    list, so the bare sublocality name matches every levelled
    component that carries it as a companion type.
    """
    _checked_type_name(type_name)
    return tuple(
        component
        for component in _checked_components(components)
        if type_name in component.types
    )


def component_long_text(
    components: Sequence[AddressComponent], type_name: str
) -> Optional[str]:
    """Return the first nonempty long text among the matches.

    A match whose long text is empty is skipped and the scan
    keeps going, so this form never returns an empty string.
    """
    for component in find_components(components, type_name):
        if component.long_text:
            return component.long_text
    return None


def component_short_text(
    components: Sequence[AddressComponent], type_name: str
) -> Optional[str]:
    """Return the first nonempty short text among the matches.

    A match whose short text is empty is skipped and the scan
    keeps going, so this form never returns an empty string.
    """
    for component in find_components(components, type_name):
        if component.short_text:
            return component.short_text
    return None


def component_long_texts(
    components: Sequence[AddressComponent], type_name: str
) -> tuple[str, ...]:
    """Return the nonempty long texts of every match in order."""
    return tuple(
        component.long_text
        for component in find_components(components, type_name)
        if component.long_text
    )


def component_short_texts(
    components: Sequence[AddressComponent], type_name: str
) -> tuple[str, ...]:
    """Return the nonempty short texts of every match in order."""
    return tuple(
        component.short_text
        for component in find_components(components, type_name)
        if component.short_text
    )


def untyped_components(
    components: Sequence[AddressComponent],
) -> tuple[AddressComponent, ...]:
    """Return every component whose types list is empty.

    Typeless components carry no type to match, so type keyed
    lookup walks past them even when one holds the most specific
    text on its place. This bucket surfaces them in list order
    and no helper guesses a type for them.
    """
    return tuple(
        component
        for component in _checked_components(components)
        if not component.types
    )


def country_code_from_components(
    components: Sequence[AddressComponent],
) -> Optional[str]:
    """Return the short text of the country component.

    The scan takes the first country component with a nonempty
    short text and returns None when no such component exists.
    The value comes back as sent and is never uppercased or
    mapped to another code.
    """
    for component in find_components(components, types.TYPE_COUNTRY):
        if component.short_text:
            return component.short_text
    return None


def country_code(place: Place) -> Optional[str]:
    """Return the region code for a place from either carrier set.

    The country component answers first. When no country
    component with a nonempty short text exists, the read falls
    back to the region code of the postal address, and it
    returns None when neither carrier yields a value.
    """
    code = country_code_from_components(place.address_components)
    if code is not None:
        return code
    return postal_region_code(place.postal_address)


def administrative_area(place: Place) -> Optional[str]:
    """Return the level 1 administrative area long text.

    The read never falls back to the postal administrative area,
    because the recorded sets show the postal spelling changing
    across request languages while the component text stayed
    stable.
    """
    return component_long_text(
        place.address_components, types.TYPE_ADMINISTRATIVE_AREA_LEVEL_1
    )


def postal_code_from_components(
    components: Sequence[AddressComponent],
) -> Optional[str]:
    """Return the first nonempty postal code component text."""
    return component_long_text(components, types.TYPE_POSTAL_CODE)


def postal_code_from_postal_address(
    postal_address: Optional[PostalAddress],
) -> Optional[str]:
    """Return the postal code field of a postal address.

    A None postal address and a missing or empty field both
    read as None under the field reader rule.
    """
    if postal_address is None:
        return None
    return postal_address.postal_code or None


def postal_code(place: Place) -> PostalCodeResult:
    """Return the postal code reading for a place.

    When both carriers hold the same code the carrier reports
    both of them. When they hold different codes the headline
    carries the component value, because the component list is
    the fuller record and the postal address is a derived
    summary of it, and the postal value stays visible in the
    competing fields. When neither carrier holds a code the
    status reports absence, which the recorded Dubai set proves
    can be a property of a country rather than a gap.
    """
    country = country_code(place)
    component_value = postal_code_from_components(place.address_components)
    postal_value = postal_code_from_postal_address(place.postal_address)
    if component_value is not None and postal_value is not None:
        if component_value == postal_value:
            return PostalCodeResult(
                component_value, CARRIER_BOTH_POSTAL, POSTAL_PRESENT, country
            )
        return PostalCodeResult(
            component_value,
            CARRIER_POSTAL_CODE_COMPONENT,
            POSTAL_PRESENT,
            country,
            competing_value=postal_value,
            competing_carrier=CARRIER_POSTAL_ADDRESS_POSTAL_CODE,
        )
    if component_value is not None:
        return PostalCodeResult(
            component_value, CARRIER_POSTAL_CODE_COMPONENT, POSTAL_PRESENT, country
        )
    if postal_value is not None:
        return PostalCodeResult(
            postal_value, CARRIER_POSTAL_ADDRESS_POSTAL_CODE, POSTAL_PRESENT, country
        )
    return PostalCodeResult(None, None, POSTAL_ABSENT, country)


def _no_city(country: Optional[str]) -> CityResolution:
    return CityResolution(None, None, CONFIDENCE_NONE, country)


def _british_resolutions(place: Place, country: Optional[str]) -> tuple[CityResolution, ...]:
    components = place.address_components
    locality = component_long_text(components, types.TYPE_LOCALITY)
    town = component_long_text(components, types.TYPE_POSTAL_TOWN)
    if locality is not None and town is not None:
        if locality != town:
            return (
                CityResolution(
                    locality,
                    CARRIER_LOCALITY,
                    CONFIDENCE_CONTESTED,
                    country,
                    competing_value=town,
                    competing_carrier=CARRIER_POSTAL_TOWN,
                ),
                CityResolution(
                    town,
                    CARRIER_POSTAL_TOWN,
                    CONFIDENCE_CONTESTED,
                    country,
                    competing_value=locality,
                    competing_carrier=CARRIER_LOCALITY,
                ),
            )
        return (CityResolution(locality, CARRIER_LOCALITY, CONFIDENCE_PRIMARY, country),)
    if locality is not None:
        return (CityResolution(locality, CARRIER_LOCALITY, CONFIDENCE_PRIMARY, country),)
    if town is not None:
        return (CityResolution(town, CARRIER_POSTAL_TOWN, CONFIDENCE_FALLBACK, country),)
    return (_no_city(country),)


def city_resolutions(place: Place) -> tuple[CityResolution, ...]:
    """Return every city reading the applicable rules produce.

    The tuple holds one element in every country except the
    United Kingdom on a place where the civil place and the
    mailing town differ, where it holds both values in that
    order and each carries the other in its competing fields.
    """
    country = country_code(place)
    route = _routing_country(country)
    components = place.address_components
    if route in CONTESTED_COUNTRIES:
        return _british_resolutions(place, country)
    if route in PRECEDENCE_COUNTRIES:
        locality = component_long_text(components, types.TYPE_LOCALITY)
        if locality is not None:
            return (
                CityResolution(locality, CARRIER_LOCALITY, CONFIDENCE_PRIMARY, country),
            )
        if route == "AE":
            postal_value = postal_locality(place.postal_address)
            if postal_value is not None:
                return (
                    CityResolution(
                        postal_value,
                        CARRIER_POSTAL_ADDRESS_LOCALITY,
                        CONFIDENCE_FALLBACK,
                        country,
                    ),
                )
        return (_no_city(country),)
    generic_chain = (
        (types.TYPE_LOCALITY, CARRIER_LOCALITY),
        (types.TYPE_POSTAL_TOWN, CARRIER_POSTAL_TOWN),
        (types.TYPE_SUBLOCALITY_LEVEL_1, CARRIER_SUBLOCALITY_LEVEL_1),
        (types.TYPE_SUBLOCALITY_LEVEL_2, CARRIER_SUBLOCALITY_LEVEL_2),
    )
    for type_name, carrier in generic_chain:
        value = component_long_text(components, type_name)
        if value is not None:
            return (CityResolution(value, carrier, CONFIDENCE_HEURISTIC, country),)
    postal_value = postal_locality(place.postal_address)
    if postal_value is not None:
        return (
            CityResolution(
                postal_value,
                CARRIER_POSTAL_ADDRESS_LOCALITY,
                CONFIDENCE_HEURISTIC,
                country,
            ),
        )
    return (_no_city(country),)


def resolve_city(place: Place) -> CityResolution:
    """Return the headline city reading for a place.

    The result carries its value with the carrier it came from
    and a confidence grade in the open. The grade is primary
    when the value came from the primary row of a stated table,
    fallback when the chain fell past that row, heuristic for
    every result of the generic chain, and none when no carrier
    yielded a value. On a contested British place the headline
    is the civil place and the mailing town rides in the
    competing fields, and contested names that live rivalry
    rather than a step in the confidence ordering.
    """
    return city_resolutions(place)[0]


def resolve_district(place: Place) -> DistrictResolution:
    """Return the district reading for a place.

    Japan reads its district from sublocality level 2, which is
    the district carrier in the recorded Tokyo special ward
    geometry, and the Emirates read theirs from sublocality
    level 1. Every other country returns a none grade result
    because no other district carrier is stated, and the postal
    sublocality is never a district source under any
    circumstance.
    """
    country = country_code(place)
    route = _routing_country(country)
    if route == "JP":
        type_name = types.TYPE_SUBLOCALITY_LEVEL_2
        carrier = CARRIER_SUBLOCALITY_LEVEL_2
    elif route == "AE":
        type_name = types.TYPE_SUBLOCALITY_LEVEL_1
        carrier = CARRIER_SUBLOCALITY_LEVEL_1
    else:
        return DistrictResolution(None, None, CONFIDENCE_NONE, country)
    value = component_long_text(place.address_components, type_name)
    if value is None:
        return DistrictResolution(None, None, CONFIDENCE_NONE, country)
    return DistrictResolution(value, carrier, CONFIDENCE_PRIMARY, country)


def has_street_number(components: Sequence[AddressComponent]) -> bool:
    """Return whether a street number component exists.

    The flag trusts the type and never the text, because the
    recorded corpus holds a street number carrying a floor label
    and a unit label.
    """
    return find_component(components, types.TYPE_STREET_NUMBER) is not None


def has_route(components: Sequence[AddressComponent]) -> bool:
    """Return whether a route component exists in the list."""
    return find_component(components, types.TYPE_ROUTE) is not None


def has_premise(components: Sequence[AddressComponent]) -> bool:
    """Return whether a premise component exists in the list."""
    return find_component(components, types.TYPE_PREMISE) is not None


def has_subpremise(components: Sequence[AddressComponent]) -> bool:
    """Return whether a subpremise component exists in the list."""
    return find_component(components, types.TYPE_SUBPREMISE) is not None


def spans_multiple_routes(components: Sequence[AddressComponent]) -> bool:
    """Return whether two or more route components carry text.

    Only route components with a nonempty long text count, so
    one named route beside one empty route reads as one route.
    """
    routes = [
        component
        for component in find_components(components, types.TYPE_ROUTE)
        if component.long_text
    ]
    return len(routes) >= 2


def has_no_street_level(components: Sequence[AddressComponent]) -> bool:
    """Return whether no street level component exists.

    Street level means a street number or a route or a premise
    or a subpremise component, and the flag is true only when
    none of the four exists.
    """
    checked = _checked_components(components)
    return not (
        has_street_number(checked)
        or has_route(checked)
        or has_premise(checked)
        or has_subpremise(checked)
    )


def is_premise_level(place: Place) -> bool:
    """Return whether a place sits at premise level addressing.

    The flag is true when a premise component exists and no
    street number component and no route component exists,
    which is the Japanese block addressing shape the recorded
    corpus holds.
    """
    components = place.address_components
    return (
        has_premise(components)
        and not has_street_number(components)
        and not has_route(components)
    )


def address_flags(place: Place) -> AddressFlags:
    """Return every presence flag for a place in one snapshot.

    Each flag follows its own helper rule on the same place.
    The postal code flag is true exactly when the postal code
    reading reports present, the country flag is true exactly
    when a country read yields a value, and the city carrier
    flag is true exactly when city resolution yields a value.
    """
    components = place.address_components
    return AddressFlags(
        has_street_number=has_street_number(components),
        has_route=has_route(components),
        has_premise=has_premise(components),
        has_subpremise=has_subpremise(components),
        is_premise_level=is_premise_level(place),
        spans_multiple_routes=spans_multiple_routes(components),
        has_no_street_level=has_no_street_level(components),
        has_postal_code=postal_code(place).status == POSTAL_PRESENT,
        has_postal_address=place.postal_address is not None,
        has_country=country_code(place) is not None,
        has_city_carrier=resolve_city(place).value is not None,
    )


def split_compound_code(compound_code: Optional[str]) -> Optional[PlusCodeParts]:
    """Split a compound plus code into its code and locality text.

    The helper returns None when the input is None or empty or
    holds no space after the code token or holds nothing after
    that space, so a locality text is never an empty string. A
    global code alone is not a compound code and returns None,
    and that None means no compound form was present rather
    than no plus code at all. The locality text is reference
    text as sent and no helper feeds it into city resolution.
    """
    if not compound_code:
        return None
    code_part, separator, rest = compound_code.partition(" ")
    locality_text = rest.strip()
    if not separator or not code_part or not locality_text:
        return None
    return PlusCodeParts(code_part=code_part, locality_text=locality_text)


def split_plus_code(plus_code: Optional[PlusCode]) -> Optional[PlusCodeParts]:
    """Split the compound form of a plus code, when it carries one."""
    if plus_code is None:
        return None
    return split_compound_code(plus_code.compound_code)


def postal_locality(postal_address: Optional[PostalAddress]) -> Optional[str]:
    """Return the locality field of a postal address.

    A None postal address and a missing or empty field both
    read as None, and any other value returns as sent.
    """
    if postal_address is None:
        return None
    return postal_address.locality or None


def postal_sublocality(postal_address: Optional[PostalAddress]) -> Optional[str]:
    """Return the sublocality field of a postal address.

    The field returns as sent and is never aligned with the
    sublocality level 1 component, because the recorded Dubai
    set shows it copying the neighborhood value instead.
    """
    if postal_address is None:
        return None
    return postal_address.sublocality or None


def postal_administrative_area(
    postal_address: Optional[PostalAddress],
) -> Optional[str]:
    """Return the administrative area field of a postal address."""
    if postal_address is None:
        return None
    return postal_address.administrative_area or None


def postal_region_code(postal_address: Optional[PostalAddress]) -> Optional[str]:
    """Return the region code field of a postal address.

    This read is the single home of the region code rule. A
    None postal address and a missing or empty region code both
    read as None, and any other value returns as sent.
    """
    if postal_address is None:
        return None
    return postal_address.region_code or None


__all__ = [
    "CARRIER_ADMINISTRATIVE_AREA_LEVEL_1",
    "CARRIER_ADMINISTRATIVE_AREA_LEVEL_2",
    "CARRIER_BOTH_POSTAL",
    "CARRIER_COUNTRY_COMPONENT",
    "CARRIER_LOCALITY",
    "CARRIER_NEIGHBORHOOD",
    "CARRIER_POSTAL_ADDRESS_ADMINISTRATIVE_AREA",
    "CARRIER_POSTAL_ADDRESS_LOCALITY",
    "CARRIER_POSTAL_ADDRESS_POSTAL_CODE",
    "CARRIER_POSTAL_ADDRESS_REGION_CODE",
    "CARRIER_POSTAL_ADDRESS_SUBLOCALITY",
    "CARRIER_POSTAL_CODE_COMPONENT",
    "CARRIER_POSTAL_TOWN",
    "CARRIER_SUBLOCALITY_LEVEL_1",
    "CARRIER_SUBLOCALITY_LEVEL_2",
    "CARRIER_SUBLOCALITY_LEVEL_3",
    "CARRIER_SUBLOCALITY_LEVEL_4",
    "CARRIER_SUBLOCALITY_LEVEL_5",
    "CONFIDENCE_CONTESTED",
    "CONFIDENCE_FALLBACK",
    "CONFIDENCE_GRADES",
    "CONFIDENCE_HEURISTIC",
    "CONFIDENCE_NONE",
    "CONFIDENCE_PRIMARY",
    "CONTESTED_COUNTRIES",
    "POSTAL_ABSENT",
    "POSTAL_PRESENT",
    "PRECEDENCE_COUNTRIES",
    "AddressFlags",
    "CityResolution",
    "DistrictResolution",
    "PlusCodeParts",
    "PostalCodeResult",
    "address_flags",
    "administrative_area",
    "city_resolutions",
    "component_long_text",
    "component_long_texts",
    "component_short_text",
    "component_short_texts",
    "country_code",
    "country_code_from_components",
    "find_component",
    "find_components",
    "has_no_street_level",
    "has_premise",
    "has_route",
    "has_street_number",
    "has_subpremise",
    "is_premise_level",
    "postal_administrative_area",
    "postal_code",
    "postal_code_from_components",
    "postal_code_from_postal_address",
    "postal_locality",
    "postal_region_code",
    "postal_sublocality",
    "resolve_city",
    "resolve_district",
    "spans_multiple_routes",
    "split_compound_code",
    "split_plus_code",
    "untyped_components",
]
