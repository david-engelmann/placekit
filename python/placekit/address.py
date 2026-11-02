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
form. Formatting and envelope rendering belong to the
normalization guide at NORMALIZATION.md in the repository root,
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

Every helper validates its arguments at entry, and a caller
argument error raises ConfigError from placekit.exceptions,
the same discipline the client layer keeps. A component list
is materialised once per call, so a one shot iterable answers
with the contents it carried on that call rather than reading
empty on a second pass. A model field of the wrong type on a
hand built Place, component or postal address raises at the
reading that touches it instead of flowing into a result under
a type it does not have.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from . import types
from .exceptions import ConfigError
from .fields import MAX_MATERIALIZED_ITEMS, _materialize_bounded
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


def _safe_repr(value: object) -> str:
    """The repr of a caller supplied value for an error message.

    A value whose own repr raises must not escape through the
    message that reports it, so a repr failure falls back to the
    type name. The message is built only after the failure is
    known, and it never formats a hostile value unguarded
    (Round 24, the FieldMask lesson applied here too).
    """
    try:
        return repr(value)
    except Exception:
        return f"<{type(value).__name__} whose repr raised>"


def _checked_components(
    components: Sequence[AddressComponent],
) -> tuple[AddressComponent, ...]:
    """Validate one caller supplied component list and return it
    materialised as a tuple.

    The input is read exactly once, under the same bounded
    ceiling the client applies to caller iterables, and every
    helper works from the materialised tuple this returns. A
    one shot iterable (a generator above all) therefore answers
    with its real contents instead of the empty stream a second
    read would see, which was the silent wrong answer of the
    earlier shape, where validation consumed the input and the
    scan then read the exhausted original (Round 24, M2).

    Every caller shaped corruption raises ConfigError here, at
    entry, so no public helper can escape as a bare builtin or
    hand back a value of the wrong type. An element that is not
    an AddressComponent is refused, and so is a text field or a
    types item of the wrong type on an element that is one,
    because the helpers hand those values back and match on
    them. A null element inside the types list is a different
    shape and stays untouched: the model layer settlement lands
    one as None at its wire index, and membership reads past it
    without error.
    """
    if components is None or isinstance(components, (str, bytes)):
        raise ConfigError(
            "components must be a sequence of AddressComponent values "
            "and not None or a bare string or bytes"
        )
    items = _materialize_bounded(
        "components", components, MAX_MATERIALIZED_ITEMS
    )
    for component in items:
        if not isinstance(component, AddressComponent):
            raise ConfigError(
                "components must hold AddressComponent values, "
                f"got {_safe_repr(component)}"
            )
        if component.long_text is not None and not isinstance(
            component.long_text, str
        ):
            raise ConfigError(
                "component long_text must be a string, "
                f"got {_safe_repr(component.long_text)}"
            )
        if component.short_text is not None and not isinstance(
            component.short_text, str
        ):
            raise ConfigError(
                "component short_text must be a string, "
                f"got {_safe_repr(component.short_text)}"
            )
        if not isinstance(component.types, (list, tuple)):
            # The element posture matches the sequence posture
            # above. Construction refuses a bare string in the
            # types field and nothing else, so a hand built
            # component can still carry a types value that is not
            # a list at all, an integer or None, and the membership
            # test in the search then raised a bare TypeError.
            raise ConfigError(
                "component types must be a list of strings, "
                f"got {_safe_repr(component.types)}"
            )
        for item in component.types:
            if item is not None and not isinstance(item, str):
                raise ConfigError(
                    "component types must hold strings, "
                    f"got {_safe_repr(item)}"
                )
    return tuple(items)


def _checked_postal_address(
    postal_address: Optional[PostalAddress],
) -> Optional[PostalAddress]:
    """Validate the carrier type of a postal address argument.

    None is the documented absence and passes. Anything that is
    not a PostalAddress is a caller error and raises ConfigError
    here instead of a bare AttributeError at the field read.
    """
    if postal_address is None:
        return None
    if not isinstance(postal_address, PostalAddress):
        raise ConfigError(
            "postal_address must be a PostalAddress, "
            f"got {_safe_repr(postal_address)}"
        )
    return postal_address


def _postal_field(
    postal_address: Optional[PostalAddress], field_name: str
) -> Optional[str]:
    """Read one string field of a postal address under the field
    reader rule.

    A None postal address and a missing or empty field both read
    as None. A field holding a value of the wrong type is a
    caller error and raises ConfigError, because the readers
    hand the value back under a string promise and returning it
    unchecked made the result a lie about its own type
    (Round 24, RT1). Every postal field read in this module
    flows through here, so a corrupt field raises at the read
    that touches it and a field no reading touches stays
    unread.
    """
    checked = _checked_postal_address(postal_address)
    if checked is None:
        return None
    value = getattr(checked, field_name)
    if value is not None and not isinstance(value, str):
        raise ConfigError(
            f"postal_address {field_name} must be a string, "
            f"got {_safe_repr(value)}"
        )
    return value or None


def _checked_place(place: Place) -> tuple[AddressComponent, ...]:
    """Validate one Place argument and return its components
    checked and materialised.

    Every Place taking helper enters through here, so a value
    that is not a Place at all raises ConfigError instead of a
    bare AttributeError naming an internal attribute, and the
    components are validated once through the components funnel
    and shared by every reading the helper composes (Round 24,
    M1). The formatted address is validated with them because
    every Place carries one under a string promise. The postal
    address is validated at its reads, through the postal
    readers, so a corrupt postal field raises exactly where a
    reading touches it.
    """
    if not isinstance(place, Place):
        raise ConfigError(f"place must be a Place, got {_safe_repr(place)}")
    if place.formatted_address is not None and not isinstance(
        place.formatted_address, str
    ):
        raise ConfigError(
            "place formatted_address must be a string, "
            f"got {_safe_repr(place.formatted_address)}"
        )
    return _checked_components(place.address_components)


# Scan cores over an already checked component list. Every public
# helper validates its list once through _checked_components and
# then works through these cores, so one public call pays the
# validation and the scans once no matter how many readings it
# composes. Before this sharing, address_flags alone revalidated
# the same list seventeen times and rescanned it sixteen times
# (Round 21 Finding 5). The cores assume the check has run and
# the type name is valid, and they answer in list order exactly
# as the helpers they sit under always have.
def _scan_components(
    checked: Sequence[AddressComponent], type_name: str
) -> tuple[AddressComponent, ...]:
    return tuple(
        component for component in checked if type_name in component.types
    )


def _scan_component(
    checked: Sequence[AddressComponent], type_name: str
) -> Optional[AddressComponent]:
    for component in checked:
        if type_name in component.types:
            return component
    return None


def _scan_long_text(
    checked: Sequence[AddressComponent], type_name: str
) -> Optional[str]:
    for component in checked:
        if type_name in component.types and component.long_text:
            return component.long_text
    return None


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


def _country_code_from_components(
    checked: Sequence[AddressComponent],
) -> Optional[str]:
    for component in _scan_components(checked, types.TYPE_COUNTRY):
        if component.short_text:
            return component.short_text
    return None


def country_code_from_components(
    components: Sequence[AddressComponent],
) -> Optional[str]:
    """Return the short text of the country component.

    The scan takes the first country component with a nonempty
    short text and returns None when no such component exists.
    The value comes back as sent and is never uppercased or
    mapped to another code.
    """
    return _country_code_from_components(_checked_components(components))


def _country_code(
    place: Place, checked: Sequence[AddressComponent]
) -> Optional[str]:
    code = _country_code_from_components(checked)
    if code is not None:
        return code
    return postal_region_code(place.postal_address)


def country_code(place: Place) -> Optional[str]:
    """Return the region code for a place from either carrier set.

    The country component answers first. When no country
    component with a nonempty short text exists, the read falls
    back to the region code of the postal address, and it
    returns None when neither carrier yields a value.
    """
    return _country_code(place, _checked_place(place))


def administrative_area(place: Place) -> Optional[str]:
    """Return the level 1 administrative area long text.

    The read never falls back to the postal administrative area,
    because the recorded sets show the postal spelling changing
    across request languages while the component text stayed
    stable.
    """
    return _scan_long_text(
        _checked_place(place), types.TYPE_ADMINISTRATIVE_AREA_LEVEL_1
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
    return _postal_field(postal_address, "postal_code")


def _postal_code(
    place: Place, checked: Sequence[AddressComponent]
) -> PostalCodeResult:
    country = _country_code(place, checked)
    component_value = _scan_long_text(checked, types.TYPE_POSTAL_CODE)
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
    return _postal_code(place, _checked_place(place))


def _no_city(country: Optional[str]) -> CityResolution:
    return CityResolution(None, None, CONFIDENCE_NONE, country)


def _british_resolutions(
    country: Optional[str],
    checked: Sequence[AddressComponent],
) -> tuple[CityResolution, ...]:
    locality = _scan_long_text(checked, types.TYPE_LOCALITY)
    town = _scan_long_text(checked, types.TYPE_POSTAL_TOWN)
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


def _city_resolutions(
    place: Place, checked: Sequence[AddressComponent]
) -> tuple[CityResolution, ...]:
    country = _country_code(place, checked)
    route = _routing_country(country)
    if route in CONTESTED_COUNTRIES:
        return _british_resolutions(country, checked)
    if route in PRECEDENCE_COUNTRIES:
        locality = _scan_long_text(checked, types.TYPE_LOCALITY)
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
        value = _scan_long_text(checked, type_name)
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


def city_resolutions(place: Place) -> tuple[CityResolution, ...]:
    """Return every city reading the applicable rules produce.

    The tuple holds one element in every country except the
    United Kingdom on a place where the civil place and the
    mailing town differ, where it holds both values in that
    order and each carries the other in its competing fields.
    """
    return _city_resolutions(place, _checked_place(place))


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


def _resolve_district(
    place: Place, checked: Sequence[AddressComponent]
) -> DistrictResolution:
    country = _country_code(place, checked)
    route = _routing_country(country)
    if route == "JP":
        type_name = types.TYPE_SUBLOCALITY_LEVEL_2
        carrier = CARRIER_SUBLOCALITY_LEVEL_2
    elif route == "AE":
        type_name = types.TYPE_SUBLOCALITY_LEVEL_1
        carrier = CARRIER_SUBLOCALITY_LEVEL_1
    else:
        return DistrictResolution(None, None, CONFIDENCE_NONE, country)
    value = _scan_long_text(checked, type_name)
    if value is None:
        return DistrictResolution(None, None, CONFIDENCE_NONE, country)
    return DistrictResolution(value, carrier, CONFIDENCE_PRIMARY, country)


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
    return _resolve_district(place, _checked_place(place))


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


def _spans_multiple_routes(checked: Sequence[AddressComponent]) -> bool:
    routes = [
        component
        for component in _scan_components(checked, types.TYPE_ROUTE)
        if component.long_text
    ]
    return len(routes) >= 2


def spans_multiple_routes(components: Sequence[AddressComponent]) -> bool:
    """Return whether two or more route components carry text.

    Only route components with a nonempty long text count, so
    one named route beside one empty route reads as one route.
    """
    return _spans_multiple_routes(_checked_components(components))


def _has_no_street_level(checked: Sequence[AddressComponent]) -> bool:
    return not (
        _scan_component(checked, types.TYPE_STREET_NUMBER) is not None
        or _scan_component(checked, types.TYPE_ROUTE) is not None
        or _scan_component(checked, types.TYPE_PREMISE) is not None
        or _scan_component(checked, types.TYPE_SUBPREMISE) is not None
    )


def has_no_street_level(components: Sequence[AddressComponent]) -> bool:
    """Return whether no street level component exists.

    Street level means a street number or a route or a premise
    or a subpremise component, and the flag is true only when
    none of the four exists.
    """
    return _has_no_street_level(_checked_components(components))


def _is_premise_level(checked: Sequence[AddressComponent]) -> bool:
    return (
        _scan_component(checked, types.TYPE_PREMISE) is not None
        and _scan_component(checked, types.TYPE_STREET_NUMBER) is None
        and _scan_component(checked, types.TYPE_ROUTE) is None
    )


def is_premise_level(place: Place) -> bool:
    """Return whether a place sits at premise level addressing.

    The flag is true when a premise component exists and no
    street number component and no route component exists,
    which is the Japanese block addressing shape the recorded
    corpus holds.
    """
    return _is_premise_level(_checked_place(place))


def address_flags(place: Place) -> AddressFlags:
    """Return every presence flag for a place in one snapshot.

    Each flag follows its own helper rule on the same place.
    The postal code flag is true exactly when the postal code
    reading reports present, the country flag is true exactly
    when a country read yields a value, and the city carrier
    flag is true exactly when city resolution yields a value.
    """
    checked = _checked_place(place)
    return AddressFlags(
        has_street_number=_scan_component(checked, types.TYPE_STREET_NUMBER)
        is not None,
        has_route=_scan_component(checked, types.TYPE_ROUTE) is not None,
        has_premise=_scan_component(checked, types.TYPE_PREMISE) is not None,
        has_subpremise=_scan_component(checked, types.TYPE_SUBPREMISE)
        is not None,
        is_premise_level=_is_premise_level(checked),
        spans_multiple_routes=_spans_multiple_routes(checked),
        has_no_street_level=_has_no_street_level(checked),
        has_postal_code=_postal_code(place, checked).status == POSTAL_PRESENT,
        has_postal_address=place.postal_address is not None,
        has_country=_country_code(place, checked) is not None,
        has_city_carrier=(
            _city_resolutions(place, checked)[0].value is not None
        ),
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
    An input that is not a string at all is a caller error and
    raises ConfigError.
    """
    if compound_code is None:
        return None
    if not isinstance(compound_code, str):
        raise ConfigError(
            "compound_code must be a string, "
            f"got {_safe_repr(compound_code)}"
        )
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
    if not isinstance(plus_code, PlusCode):
        raise ConfigError(
            f"plus_code must be a PlusCode, got {_safe_repr(plus_code)}"
        )
    return split_compound_code(plus_code.compound_code)


def postal_locality(postal_address: Optional[PostalAddress]) -> Optional[str]:
    """Return the locality field of a postal address.

    A None postal address and a missing or empty field both
    read as None, and any other value returns as sent.
    """
    return _postal_field(postal_address, "locality")


def postal_sublocality(postal_address: Optional[PostalAddress]) -> Optional[str]:
    """Return the sublocality field of a postal address.

    The field returns as sent and is never aligned with the
    sublocality level 1 component, because the recorded Dubai
    set shows it copying the neighborhood value instead.
    """
    return _postal_field(postal_address, "sublocality")


def postal_administrative_area(
    postal_address: Optional[PostalAddress],
) -> Optional[str]:
    """Return the administrative area field of a postal address."""
    return _postal_field(postal_address, "administrative_area")


def postal_region_code(postal_address: Optional[PostalAddress]) -> Optional[str]:
    """Return the region code field of a postal address.

    This read is the single home of the region code rule. A
    None postal address and a missing or empty region code both
    read as None, and any other value returns as sent.
    """
    return _postal_field(postal_address, "region_code")


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
