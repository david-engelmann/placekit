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
empty on a second pass. The components a Place carries face a
stricter rule and must be a list or tuple, because a Place is
reused across calls and a one shot iterable stored on it would
be spent by the first reading and read empty by every later
one. A model field of the wrong type on a hand built Place,
component or postal address raises at the reading that touches
it instead of flowing into a result under a type it does not
have, and a value that raises while it is being read or used,
an instance built without its constructor or a property
getter or method that raises, surfaces as the same
ConfigError with the original failure chained.

The readings themselves are computed in the Rust core, in
crates/placekit-core/src/address.rs, since Round 53. This
module is the delegation layer over that core. It validates
every argument through the funnels below, converts the checked
components into the plain shapes the core accepts, reads each
postal field at exactly the point the reading that touches it
always read it, and wraps the core answers back into the
result types this module has always returned. Validation
stays here because it is a property of the caller supplied
Python values, and the core never sees a Python object. One
boundary travels with the delegation and is stated here
rather than left to surprise. Where a caller supplied
operation returns a wrong answer instead of raising, the
readings follow the values as sent to the core rather than
the answer the operation gave.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Optional, Sequence

from . import _placekit, types
from .exceptions import ConfigError
from .fields import MAX_MATERIALIZED_ITEMS, _materialize_bounded, _safe_repr
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


def _entry_guard(fn):
    """Run one public helper under the module entry guard.

    The funnels validate the values a caller hands in, but a
    validated value can still raise while it is being read or
    used. An instance built without its constructor has no
    attributes to read, a subclass property getter can raise
    at the read itself, and a string or list subclass can
    raise inside the method or membership test the reading
    performs. The client layer wraps exactly this class
    around its argument phase, and every public helper here
    runs under the same discipline, so an Exception a caller
    supplied value raises surfaces as a ConfigError with the
    original chained. A ConfigError raised deliberately
    inside passes through with its wording unchanged, and a
    BaseException passes through untouched, the standing
    posture everywhere in the library (Round 24 repair, red
    team F1 and F2).

    The guard also sets the exception context to this helper's
    public name when the error carries none yet (Round 25,
    Minor 4), so an address failure names the helper that
    raised it in the attribute callers log, the way a client
    failure names its method. The caught exception is named
    through the safe repr, so an exception whose own repr
    raises cannot break the guard itself (Round 65).
    """

    @functools.wraps(fn)
    def guarded(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ConfigError as exc:
            if exc.context is None:
                exc.context = fn.__name__
            raise
        except Exception as exc:
            raise ConfigError(
                f"an argument for {fn.__name__} raised while it "
                f"was being read: {_safe_repr(exc)}",
                context=fn.__name__,
            ) from exc

    return guarded


def _checked_components(
    components: Sequence[AddressComponent],
) -> tuple[AddressComponent, ...]:
    """Validate one caller supplied component list and return it
    materialised as a tuple.

    The plain capture the core conversion consumes rides out
    through _checked_components_and_plain, and this form keeps
    the tuple only shape the helpers that hand components back
    have always used.
    """
    checked, _plain = _checked_components_and_plain(components)
    return checked


def _checked_components_and_plain(
    components: Sequence[AddressComponent],
) -> tuple[
    tuple[AddressComponent, ...],
    list[tuple[Optional[str], Optional[str], tuple[Optional[str], ...]]],
]:
    """Validate one caller supplied component list and return it
    materialised as a tuple, with the plain field values the
    validation read captured beside it.

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
    plain = []
    for component in items:
        if not isinstance(component, AddressComponent):
            raise ConfigError(
                "components must hold AddressComponent values, "
                f"got {_safe_repr(component)}"
            )
        # The field values are captured as the validation reads
        # them, at exactly the reads the funnel has always made,
        # so the conversion further down never reads a caller
        # text again. A field a caller reads through a counting
        # or raising getter therefore sees the same read count
        # the pre port funnel produced.
        long_text = component.long_text
        if long_text is not None:
            long_text = component.long_text
            if not isinstance(long_text, str):
                raise ConfigError(
                    "component long_text must be a string, "
                    f"got {_safe_repr(component.long_text)}"
                )
        short_text = component.short_text
        if short_text is not None:
            short_text = component.short_text
            if not isinstance(short_text, str):
                raise ConfigError(
                    "component short_text must be a string, "
                    f"got {_safe_repr(component.short_text)}"
                )
        types_value = component.types
        if not isinstance(types_value, (list, tuple)):
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
        type_items = []
        for item in component.types:
            if item is not None and not isinstance(item, str):
                raise ConfigError(
                    "component types must hold strings, "
                    f"got {_safe_repr(item)}"
                )
            type_items.append(item)
        plain.append((long_text, short_text, tuple(type_items)))
    return tuple(items), plain


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


def _checked_place_and_plain(
    place: Place,
) -> tuple[
    tuple[AddressComponent, ...],
    list[tuple[Optional[str], Optional[str], tuple[Optional[str], ...]]],
]:
    """Validate one Place argument and return its components
    checked and materialised, with the plain capture beside
    them.

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

    The components themselves must be a list or tuple here,
    stricter than the components funnel, which accepts any
    iterable once for the call that receives it. A Place is a
    durable object its caller reads across many calls, so a
    one shot iterable stored in its components field would be
    spent by the first helper that touched the place and read
    empty for every later one, silently flipping answers
    between calls on an unchanged place (Round 24 repair, red
    team F3). The field is annotated as a list on the model,
    and this is that annotation enforced at the reading.
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
    components = place.address_components
    if not isinstance(components, (list, tuple)):
        raise ConfigError(
            "place address_components must be a list or tuple, "
            f"got {_safe_repr(components)}"
        )
    return _checked_components_and_plain(components)


def _encode_text(text: Optional[str]) -> Optional[bytes]:
    """Encode one checked text for the core crossing.

    The core works on byte strings, and the surrogatepass codec
    carries a lone surrogate as its three byte form and back,
    so a text holding one crosses exactly and returns exactly,
    where an encoding that refuses surrogates would fail the
    whole reading on a value every funnel accepts.
    """
    if text is None:
        return None
    return text.encode("utf-8", "surrogatepass")


def _decode_text(data: Optional[bytes]) -> Optional[str]:
    """Decode one text the core hands back, on the same codec
    terms as _encode_text, so a surrogate it carried returns as
    the surrogate the caller sent."""
    if data is None:
        return None
    return data.decode("utf-8", "surrogatepass")


def _core_components(
    plain: Sequence[
        tuple[Optional[str], Optional[str], tuple[Optional[str], ...]]
    ],
) -> list[tuple[Optional[bytes], Optional[bytes], tuple[Optional[bytes], ...]]]:
    """Convert the plain capture into the core shape.

    The core works on one triple per component, its long text,
    its short text and its type names, encoded as byte strings,
    so no Python object crosses the boundary. The conversion
    works only from the values the validation funnel captured
    while it read each field, so it adds no read of any caller
    field, and it runs inside the entry guard of the helper
    that owns the call.
    """
    return [
        (
            _encode_text(long_text),
            _encode_text(short_text),
            tuple(_encode_text(item) for item in type_items),
        )
        for long_text, short_text, type_items in plain
    ]


def _exercise_membership(
    checked: Sequence[AddressComponent], type_name: str
) -> None:
    """Run one membership test per component on the caller types.

    The core scan compares extracted type values, so the test
    the old scan ran on the caller supplied types objects, a
    list subclass contains or an item equality, no longer runs
    there. A types value that raises inside that test is part
    of this module's documented discipline, a value that raises
    while it is being used surfaces as a ConfigError, so each
    delegation site runs the test on the original objects, in
    scan order, before it calls the core, and a raise lands
    exactly where the old scan raised. The results are the
    core's to compute and are discarded here.
    """
    for component in checked:
        type_name in component.types


def _exercise_first_match(
    checked: Sequence[AddressComponent], type_name: str
) -> bool:
    """Run the membership test the way the old first match scan
    ran it, and report whether a match landed.

    The old scan stopped at the first component whose types
    hold the name, so a component past the landing one was
    never tested. The exercise walks in scan order and stops
    at the same component, and the landing report drives the
    exercise order at the composite flag sites, where the old
    composition short circuited from one scan to the next. The
    results are the core's to compute and are discarded beyond
    that ordering.
    """
    for component in checked:
        if type_name in component.types:
            return True
    return False


def _exercise_text_scan(
    checked: Sequence[AddressComponent], type_name: str
) -> bool:
    """Run the tests the way the old long text scan ran them,
    and report whether a reading landed.

    The old scan tested membership component by component and
    stopped at the first match whose long text is nonempty, so
    a component past the landing one was never tested, and a
    match with an empty text was tested and passed over. The
    exercise walks the same order with the same two tests and
    stops at the same component. The results are the core's to
    compute and are discarded beyond that ordering.
    """
    for component in checked:
        if type_name in component.types and component.long_text:
            return True
    return False


def _first_text_index(
    plain: Sequence[
        tuple[Optional[str], Optional[str], tuple[Optional[str], ...]]
    ],
    type_name: str,
) -> Optional[int]:
    """Return the index of the component the first nonempty long
    text scan for the name lands on, computed over the plain
    capture.

    The comparison runs on the encoded forms of the captured
    values, so the scan performs no test on a caller object,
    and it lands where the core lands on the same capture, the
    first component whose captured types hold the name and
    whose captured long text is nonempty. The city and district
    readings use the index to read the landing component's own
    long text object live at the point the old scan returned
    it, which is the read the return of a text scan consists
    of. When the exercise on the caller objects and this scan
    of the capture disagree, which only an unstable value can
    cause, the reading falls back to the core value.
    """
    needle = _encode_text(type_name)
    for index, (long_text, _short_text, type_items) in enumerate(plain):
        encoded_items = tuple(_encode_text(item) for item in type_items)
        if needle in encoded_items and _encode_text(long_text):
            return index
    return None


def _exercise_route_texts(
    checked: Sequence[AddressComponent],
    plain: Sequence[
        tuple[Optional[str], Optional[str], tuple[Optional[str], ...]]
    ],
) -> None:
    """Read the long text of every route match once, in match
    order.

    The old spans composition walked its route matches after a
    full membership scan and read each match's long text for
    its truthiness count, a live read of every match whether
    the count landed or not. The core counts from the captured
    values, so that filter read has no counterpart in the
    delegation unless it runs here, beside the membership
    exercise the spans sites already run. The matches are
    named over the plain capture on encoded forms, so naming
    them performs no test on a caller object, and the read
    itself runs on the caller component, in match order, so a
    text that raises on the read surfaces where the old filter
    raised. The values are the core's to count and are
    discarded here.
    """
    needle = _encode_text(types.TYPE_ROUTE)
    for index, (_long_text, _short_text, type_items) in enumerate(plain):
        encoded_items = tuple(_encode_text(item) for item in type_items)
        if needle in encoded_items:
            checked[index].long_text


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


@_entry_guard
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


@_entry_guard
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
    checked, plain = _checked_components_and_plain(components)
    _exercise_membership(checked, type_name)
    indices = _placekit.address_matching_indices(
        _core_components(plain), _encode_text(type_name)
    )
    return tuple(checked[index] for index in indices)


@_entry_guard
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


@_entry_guard
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


@_entry_guard
def component_long_texts(
    components: Sequence[AddressComponent], type_name: str
) -> tuple[str, ...]:
    """Return the nonempty long texts of every match in order."""
    return tuple(
        component.long_text
        for component in find_components(components, type_name)
        if component.long_text
    )


@_entry_guard
def component_short_texts(
    components: Sequence[AddressComponent], type_name: str
) -> tuple[str, ...]:
    """Return the nonempty short texts of every match in order."""
    return tuple(
        component.short_text
        for component in find_components(components, type_name)
        if component.short_text
    )


@_entry_guard
def untyped_components(
    components: Sequence[AddressComponent],
) -> tuple[AddressComponent, ...]:
    """Return every component whose types list is empty.

    Typeless components carry no type to match, so type keyed
    lookup walks past them even when one holds the most specific
    text on its place. This bucket surfaces them in list order
    and no helper guesses a type for them.
    """
    checked = _checked_components(components)
    # The old bucket test is the truthiness of the caller types
    # object itself, a test no core reading over extracted
    # values can stand in for, so the bucket is decided here on
    # the caller objects, the way the pre port helper decided
    # it. A types list whose length lies at zero lands in the
    # bucket and a types list whose truth test raises surfaces
    # here, both as the old helper answered.
    return tuple(
        component for component in checked if not component.types
    )


def _country_code_from_components(
    checked: Sequence[AddressComponent],
    plain: Sequence[
        tuple[Optional[str], Optional[str], tuple[Optional[str], ...]]
    ],
) -> Optional[str]:
    _exercise_membership(checked, types.TYPE_COUNTRY)
    indices = _placekit.address_matching_indices(
        _core_components(plain), _encode_text(types.TYPE_COUNTRY)
    )
    for index in indices:
        if checked[index].short_text:
            return checked[index].short_text
    return None


@_entry_guard
def country_code_from_components(
    components: Sequence[AddressComponent],
) -> Optional[str]:
    """Return the short text of the country component.

    The scan takes the first country component with a nonempty
    short text and returns None when no such component exists.
    The value comes back as sent and is never uppercased or
    mapped to another code.
    """
    checked, plain = _checked_components_and_plain(components)
    return _country_code_from_components(checked, plain)


def _country_code(
    place: Place,
    checked: Sequence[AddressComponent],
    plain: Sequence[
        tuple[Optional[str], Optional[str], tuple[Optional[str], ...]]
    ],
) -> Optional[str]:
    code = _country_code_from_components(checked, plain)
    if code is not None:
        return code
    return postal_region_code(place.postal_address)


@_entry_guard
def country_code(place: Place) -> Optional[str]:
    """Return the region code for a place from either carrier set.

    The country component answers first. When no country
    component with a nonempty short text exists, the read falls
    back to the region code of the postal address, and it
    returns None when neither carrier yields a value.
    """
    checked, plain = _checked_place_and_plain(place)
    return _country_code(place, checked, plain)


@_entry_guard
def administrative_area(place: Place) -> Optional[str]:
    """Return the level 1 administrative area long text.

    The read never falls back to the postal administrative area,
    because the recorded sets show the postal spelling changing
    across request languages while the component text stayed
    stable.
    """
    checked, plain = _checked_place_and_plain(place)
    _exercise_text_scan(checked, types.TYPE_ADMINISTRATIVE_AREA_LEVEL_1)
    index = _placekit.address_first_long_text_index(
        _core_components(plain),
        _encode_text(types.TYPE_ADMINISTRATIVE_AREA_LEVEL_1),
    )
    if index is None:
        return None
    # The reading hands back the matched component's own long
    # text object, the way the old scan returned it untouched.
    return checked[index].long_text


@_entry_guard
def postal_code_from_components(
    components: Sequence[AddressComponent],
) -> Optional[str]:
    """Return the first nonempty postal code component text."""
    return component_long_text(components, types.TYPE_POSTAL_CODE)


@_entry_guard
def postal_code_from_postal_address(
    postal_address: Optional[PostalAddress],
) -> Optional[str]:
    """Return the postal code field of a postal address.

    A None postal address and a missing or empty field both
    read as None under the field reader rule.
    """
    return _postal_field(postal_address, "postal_code")


def _postal_code(
    place: Place,
    checked: Sequence[AddressComponent],
    plain: Sequence[
        tuple[Optional[str], Optional[str], tuple[Optional[str], ...]]
    ],
) -> PostalCodeResult:
    country = _country_code(place, checked, plain)
    # The old postal read never routed and never tested a
    # sublocality needle, so no routing read and no district
    # exercise stands here. Its own scan is the postal code
    # long text scan, exercised on its own terms.
    _exercise_text_scan(checked, types.TYPE_POSTAL_CODE)
    index = _placekit.address_first_long_text_index(
        _core_components(plain), _encode_text(types.TYPE_POSTAL_CODE)
    )
    component_text = plain[index][0] if index is not None else None
    component_object = checked[index].long_text if index is not None else None
    postal_value = postal_code_from_postal_address(place.postal_address)
    if component_object is not None and postal_value is not None:
        # The old composition compared its two carrier values
        # at this point, a call on the caller supplied text
        # objects themselves that no reading over the extracted
        # values performs. The comparison still runs here, so
        # an equality that raises surfaces where the old
        # composition raised, and its answer is left unused.
        # The core composes the result from the values as sent,
        # which is the boundary the module states for an
        # operation that returns a wrong answer.
        bool(component_object == postal_value)
    row = _placekit.address_postal_code_result(
        _encode_text(country),
        _encode_text(component_text),
        _encode_text(postal_value),
    )
    # The result carries the caller supplied objects themselves
    # wherever the old composition carried them. The headline
    # value is the component object when a component value
    # stands and the postal object otherwise, the competing
    # value is the postal object when the core reports one,
    # and the country slot carries the code as sent.
    value = component_object if component_text is not None else postal_value
    competing = postal_value if row[4] is not None else None
    return PostalCodeResult(value, row[1], row[2], country, competing, row[5])


@_entry_guard
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
    checked, plain = _checked_place_and_plain(place)
    return _postal_code(place, checked, plain)


def _city_resolutions(
    place: Place,
    checked: Sequence[AddressComponent],
    plain: Sequence[
        tuple[Optional[str], Optional[str], tuple[Optional[str], ...]]
    ],
) -> tuple[CityResolution, ...]:
    country = _country_code(place, checked, plain)
    route = _routing_country(country)
    # Each chain exercises the scans the old chain ran, on
    # their own terms. The British chain ran both of its text
    # scans in full, the precedence chains ran the locality
    # scan alone, and the generic chain ran its scans in order
    # and stopped exercising further needles at the first scan
    # that landed, because the old chain returned there.
    #
    # A landed scan also read its landing text again as the
    # value it returned, and that return read is a live read of
    # the caller object, at the point the scan landed. Each
    # chain therefore reads the landing component's own long
    # text object as its scan lands, in scan order, and the
    # rows below carry that object wherever the old chain
    # carried its returned text. The index that names the
    # landing component is computed over the plain capture, so
    # naming it performs no test on a caller object. When the
    # exercise and the capture disagree, which only an unstable
    # value can cause, no live object stands for the carrier
    # and the row keeps the core value.
    live: dict[str, str] = {}

    def land(type_name: str, carrier: str) -> bool:
        if not _exercise_text_scan(checked, type_name):
            return False
        index = _first_text_index(plain, type_name)
        if index is not None:
            live[carrier] = checked[index].long_text
        return True

    if route in CONTESTED_COUNTRIES:
        land(types.TYPE_LOCALITY, CARRIER_LOCALITY)
        land(types.TYPE_POSTAL_TOWN, CARRIER_POSTAL_TOWN)
        if CARRIER_LOCALITY in live and CARRIER_POSTAL_TOWN in live:
            # The old British composition compared its two
            # landed texts before it built its rows, a call on
            # the caller supplied text objects themselves. The
            # comparison still runs here, so an equality that
            # raises surfaces where the old composition raised,
            # and its answer is left unused, on the same terms
            # as the postal comparison in _postal_code.
            bool(live[CARRIER_LOCALITY] != live[CARRIER_POSTAL_TOWN])
    elif route in PRECEDENCE_COUNTRIES:
        land(types.TYPE_LOCALITY, CARRIER_LOCALITY)
    else:
        for type_name, carrier in (
            (types.TYPE_LOCALITY, CARRIER_LOCALITY),
            (types.TYPE_POSTAL_TOWN, CARRIER_POSTAL_TOWN),
            (types.TYPE_SUBLOCALITY_LEVEL_1, CARRIER_SUBLOCALITY_LEVEL_1),
            (types.TYPE_SUBLOCALITY_LEVEL_2, CARRIER_SUBLOCALITY_LEVEL_2),
        ):
            if land(type_name, carrier):
                break
    encoded = _core_components(plain)
    needs_postal, rows = _placekit.address_city_resolutions(
        encoded, False, _encode_text(country), None
    )
    locality = None
    if needs_postal:
        # The chain reached the postal locality carrier, so the
        # field is read here, at exactly the point the chain
        # touches it, and the chain runs again with it in hand.
        locality = postal_locality(place.postal_address)
        needs_postal, rows = _placekit.address_city_resolutions(
            encoded, True, _encode_text(country), _encode_text(locality)
        )

    def carried(value: Optional[bytes], carrier: Optional[str]):
        # A row whose carrier a landed scan read live carries
        # that caller object, and a row on the postal locality
        # carrier carries the postal field object the chain
        # read, the way the old chains returned both untouched.
        # Any other row keeps the value the core composed.
        if carrier in live:
            return live[carrier]
        if carrier == CARRIER_POSTAL_ADDRESS_LOCALITY and locality is not None:
            return locality
        return _decode_text(value)

    # The core echoes the country code it was handed as a plain
    # value. Each result carries the code as sent, so the caller
    # supplied object itself goes back into every row.
    return tuple(
        CityResolution(
            carried(row[0], row[1]),
            row[1],
            row[2],
            country,
            carried(row[4], row[5]),
            row[5],
        )
        for row in rows
    )


@_entry_guard
def city_resolutions(place: Place) -> tuple[CityResolution, ...]:
    """Return every city reading the applicable rules produce.

    The tuple holds one element in every country except the
    United Kingdom on a place where the civil place and the
    mailing town differ, where it holds both values in that
    order and each carries the other in its competing fields.
    """
    checked, plain = _checked_place_and_plain(place)
    return _city_resolutions(place, checked, plain)


@_entry_guard
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
    place: Place,
    checked: Sequence[AddressComponent],
    plain: Sequence[
        tuple[Optional[str], Optional[str], tuple[Optional[str], ...]]
    ],
) -> DistrictResolution:
    country = _country_code(place, checked, plain)
    route = _routing_country(country)
    type_name = None
    carrier = None
    if route == "JP":
        type_name = types.TYPE_SUBLOCALITY_LEVEL_2
        carrier = CARRIER_SUBLOCALITY_LEVEL_2
    if route == "AE":
        type_name = types.TYPE_SUBLOCALITY_LEVEL_1
        carrier = CARRIER_SUBLOCALITY_LEVEL_1
    # A routed chain ran one text scan, and a landed scan read
    # its landing text again as the value it returned. When the
    # scan lands here, the landing component's own long text
    # object is read live at the same point, on the terms the
    # city readings state, and the result carries that object.
    live_value = None
    if type_name is not None and _exercise_text_scan(checked, type_name):
        index = _first_text_index(plain, type_name)
        if index is not None:
            live_value = checked[index].long_text
    row = _placekit.address_district_resolution(
        _core_components(plain), _encode_text(country)
    )
    # The core echoes the country code as a plain value and the
    # result carries the code as sent, as in the city reading.
    value = live_value if row[1] == carrier else _decode_text(row[0])
    return DistrictResolution(value, row[1], row[2], country)


@_entry_guard
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
    checked, plain = _checked_place_and_plain(place)
    return _resolve_district(place, checked, plain)


@_entry_guard
def has_street_number(components: Sequence[AddressComponent]) -> bool:
    """Return whether a street number component exists.

    The flag trusts the type and never the text, because the
    recorded corpus holds a street number carrying a floor label
    and a unit label.
    """
    return find_component(components, types.TYPE_STREET_NUMBER) is not None


@_entry_guard
def has_route(components: Sequence[AddressComponent]) -> bool:
    """Return whether a route component exists in the list."""
    return find_component(components, types.TYPE_ROUTE) is not None


@_entry_guard
def has_premise(components: Sequence[AddressComponent]) -> bool:
    """Return whether a premise component exists in the list."""
    return find_component(components, types.TYPE_PREMISE) is not None


@_entry_guard
def has_subpremise(components: Sequence[AddressComponent]) -> bool:
    """Return whether a subpremise component exists in the list."""
    return find_component(components, types.TYPE_SUBPREMISE) is not None


def _flags_core(
    plain: Sequence[
        tuple[Optional[str], Optional[str], tuple[Optional[str], ...]]
    ],
) -> tuple[bool, ...]:
    """Ask the core for the component flag row over the plain
    capture.

    The exercise at each site runs over the caller objects on
    that site's own scan terms, and the core then computes the
    flags over the extracted type names. The row runs from
    street number presence through the no street level flag,
    in the order the AddressFlags fields consume them.
    """
    return _placekit.address_component_flags(_core_components(plain))


def _exercise_flag_helpers(
    checked: Sequence[AddressComponent],
    plain: Sequence[
        tuple[Optional[str], Optional[str], tuple[Optional[str], ...]]
    ],
) -> None:
    """Run the flag scans' membership tests in the old
    composition order, on each scan's own terms.

    The composite reading runs the component helpers first, in
    field order, and the old composition short circuited inside
    the premise level sequence and inside the no street level
    chain, so the exercise mirrors those short circuits. The
    spans composition between them runs its route text pass
    over its matches, the filter read the old spans helper ran.
    The composed postal, country and city readings then
    exercise themselves in their own order.
    """
    _exercise_first_match(checked, types.TYPE_STREET_NUMBER)
    _exercise_first_match(checked, types.TYPE_ROUTE)
    _exercise_first_match(checked, types.TYPE_PREMISE)
    _exercise_first_match(checked, types.TYPE_SUBPREMISE)
    if _exercise_first_match(checked, types.TYPE_PREMISE):
        if not _exercise_first_match(checked, types.TYPE_STREET_NUMBER):
            _exercise_first_match(checked, types.TYPE_ROUTE)
    _exercise_membership(checked, types.TYPE_ROUTE)
    _exercise_route_texts(checked, plain)
    if not _exercise_first_match(checked, types.TYPE_STREET_NUMBER):
        if not _exercise_first_match(checked, types.TYPE_ROUTE):
            if not _exercise_first_match(checked, types.TYPE_PREMISE):
                _exercise_first_match(checked, types.TYPE_SUBPREMISE)


@_entry_guard
def spans_multiple_routes(components: Sequence[AddressComponent]) -> bool:
    """Return whether two or more route components carry text.

    Only route components with a nonempty long text count, so
    one named route beside one empty route reads as one route.
    """
    checked, plain = _checked_components_and_plain(components)
    _exercise_membership(checked, types.TYPE_ROUTE)
    _exercise_route_texts(checked, plain)
    return _flags_core(plain)[5]


@_entry_guard
def has_no_street_level(components: Sequence[AddressComponent]) -> bool:
    """Return whether no street level component exists.

    Street level means a street number or a route or a premise
    or a subpremise component, and the flag is true only when
    none of the four exists.
    """
    checked, plain = _checked_components_and_plain(components)
    if not _exercise_first_match(checked, types.TYPE_STREET_NUMBER):
        if not _exercise_first_match(checked, types.TYPE_ROUTE):
            if not _exercise_first_match(checked, types.TYPE_PREMISE):
                _exercise_first_match(checked, types.TYPE_SUBPREMISE)
    return _flags_core(plain)[6]


@_entry_guard
def is_premise_level(place: Place) -> bool:
    """Return whether a place sits at premise level addressing.

    The flag is true when a premise component exists and no
    street number component and no route component exists,
    which is the Japanese block addressing shape the recorded
    corpus holds.
    """
    checked, plain = _checked_place_and_plain(place)
    if _exercise_first_match(checked, types.TYPE_PREMISE):
        if not _exercise_first_match(checked, types.TYPE_STREET_NUMBER):
            _exercise_first_match(checked, types.TYPE_ROUTE)
    return _flags_core(plain)[4]


@_entry_guard
def address_flags(place: Place) -> AddressFlags:
    """Return every presence flag for a place in one snapshot.

    Each flag follows its own helper rule on the same place.
    The postal code flag is true exactly when the postal code
    reading reports present, the country flag is true exactly
    when a country read yields a value, and the city carrier
    flag is true exactly when city resolution yields a value.
    """
    checked, plain = _checked_place_and_plain(place)
    _exercise_flag_helpers(checked, plain)
    (
        street_number,
        route,
        premise,
        subpremise,
        premise_level,
        spans,
        no_street_level,
    ) = _flags_core(plain)
    return AddressFlags(
        has_street_number=street_number,
        has_route=route,
        has_premise=premise,
        has_subpremise=subpremise,
        is_premise_level=premise_level,
        spans_multiple_routes=spans,
        has_no_street_level=no_street_level,
        has_postal_code=(
            _postal_code(place, checked, plain).status == POSTAL_PRESENT
        ),
        has_postal_address=place.postal_address is not None,
        has_country=_country_code(place, checked, plain) is not None,
        has_city_carrier=(
            _city_resolutions(place, checked, plain)[0].value is not None
        ),
    )


@_entry_guard
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
    # The split runs here on the caller string itself, the way
    # the pre port helper ran it, because its partition and its
    # strip are calls on that object and no core reading over
    # an extracted value can stand in for them. A partition
    # that raises surfaces from the caller object and a strip
    # that answers with other text shapes the answer, both as
    # the old helper behaved.
    code_part, separator, rest = compound_code.partition(" ")
    locality_text = rest.strip()
    if not separator or not code_part or not locality_text:
        return None
    return PlusCodeParts(code_part=code_part, locality_text=locality_text)


@_entry_guard
def split_plus_code(plus_code: Optional[PlusCode]) -> Optional[PlusCodeParts]:
    """Split the compound form of a plus code, when it carries one."""
    if plus_code is None:
        return None
    if not isinstance(plus_code, PlusCode):
        raise ConfigError(
            f"plus_code must be a PlusCode, got {_safe_repr(plus_code)}"
        )
    return split_compound_code(plus_code.compound_code)


@_entry_guard
def postal_locality(postal_address: Optional[PostalAddress]) -> Optional[str]:
    """Return the locality field of a postal address.

    A None postal address and a missing or empty field both
    read as None, and any other value returns as sent.
    """
    return _postal_field(postal_address, "locality")


@_entry_guard
def postal_sublocality(postal_address: Optional[PostalAddress]) -> Optional[str]:
    """Return the sublocality field of a postal address.

    The field returns as sent and is never aligned with the
    sublocality level 1 component, because the recorded Dubai
    set shows it copying the neighborhood value instead.
    """
    return _postal_field(postal_address, "sublocality")


@_entry_guard
def postal_administrative_area(
    postal_address: Optional[PostalAddress],
) -> Optional[str]:
    """Return the administrative area field of a postal address."""
    return _postal_field(postal_address, "administrative_area")


@_entry_guard
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
