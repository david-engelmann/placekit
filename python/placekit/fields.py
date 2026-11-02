"""Field masks, a first-class part of the Places API (New) protocol.

Every response field must be requested through the ``X-Goog-FieldMask``
header, and billing follows the fields you ask for. Pass a ``FieldMask`` (or
any iterable of path strings) as the ``fields`` argument of search and
details calls. When ``fields`` is omitted, curated defaults are used.

Billing note: the curated defaults include fields from the Enterprise
billing tier (among them rating, userRatingCount, priceLevel and, on
Place Details, the phone numbers, websiteUri and regularOpeningHours),
so a default search call is billed at that tier. Place Details is the
exception: its default mask requests every modelled field, including
currentOpeningHours from the Enterprise plus Atmosphere tier, because
the method promises full details. The search defaults are a curated
subset; modelled attributes beyond them (among them addressComponents,
plusCode, viewport, postalAddress and currentOpeningHours) are only
populated when a caller requests them through ``fields``. Pass a
narrower ``fields`` set to control billing. The mask also decides
what can be populated at all. An attribute outside the mask reads
as not returned on the result, in the sense the models
documentation defines, whether or not the API holds a value for it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Tuple, Union

from .exceptions import ConfigError

#: The universal ceiling on caller iterables the client materialises
#: (field masks here, list and mapping parameters in the client).
#: Slots whose API documentation states a smaller maximum enforce
#: that maximum instead; this ceiling is the bound for every other
#: slot, so an endless or absurd iterable is refused with a
#: ConfigError after this many items instead of being consumed
#: until memory runs out (R20-F01 and F02).
MAX_MATERIALIZED_ITEMS = 1000


def _materialize_bounded(
    name: str,
    iterable: Iterable[Any],
    limit: int,
    *,
    documented_maximum: bool = False,
) -> list:
    """Materialise one caller iterable under a bound, in one place.

    This is the single bounded read loop behind the field mask
    builder and the client's list and mapping parameters, with
    one error wording for every slot. Items are counted as they
    are consumed, never by any container they land in, so a
    stream that never ends is refused after the limit even when
    it cycles over values it already yielded. Anything the
    iterable raises while being read surfaces as a ConfigError
    with the original exception chained. ``documented_maximum``
    marks a limit the API documentation states for the slot,
    which words the refusal as the slot's own maximum; every
    other limit is the universal ceiling and words it as one.
    """
    try:
        iterator = iter(iterable)
    except Exception as exc:
        raise ConfigError(
            f"{name} could not be read as an iterable: {exc!r}"
        ) from exc
    items: list = []
    while True:
        try:
            item = next(iterator)
        except StopIteration:
            break
        except Exception as exc:
            raise ConfigError(
                f"{name} raised while being read: {exc!r}"
            ) from exc
        items.append(item)
        if len(items) > limit:
            if documented_maximum:
                raise ConfigError(
                    f"{name} takes at most {limit} items, got more"
                )
            raise ConfigError(
                f"{name} materialised past the ceiling of "
                f"{limit} items; refusing to consume an "
                "unbounded iterable"
            )
    return items

#: Default paths requested by text_search when no fields are given.
TEXT_SEARCH_FIELDS: Tuple[str, ...] = (
    "places.id",
    "places.name",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.rating",
    "places.userRatingCount",
    "places.types",
    "places.primaryType",
    "places.priceLevel",
    "places.businessStatus",
    "places.photos",
    "nextPageToken",
)

#: Default paths requested by nearby_search when no fields are given.
NEARBY_SEARCH_FIELDS: Tuple[str, ...] = (
    "places.id",
    "places.name",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.rating",
    "places.userRatingCount",
    "places.types",
    "places.primaryType",
    "places.priceLevel",
    "places.businessStatus",
    "places.photos",
)

#: Default paths requested by place_details when no fields are given.
#: This is every field the models carry, because the method promises
#: full details; anything less would leave modelled attributes
#: permanently empty with no signal that they were never requested.
PLACE_DETAILS_FIELDS: Tuple[str, ...] = (
    "id",
    "name",
    "displayName",
    "formattedAddress",
    "shortFormattedAddress",
    "location",
    "rating",
    "userRatingCount",
    "types",
    "primaryType",
    "priceLevel",
    "businessStatus",
    "photos",
    "nationalPhoneNumber",
    "internationalPhoneNumber",
    "websiteUri",
    "googleMapsUri",
    "regularOpeningHours",
    "currentOpeningHours",
    "currentSecondaryOpeningHours",
    "regularSecondaryOpeningHours",
    "addressComponents",
    "adrFormatAddress",
    "plusCode",
    "postalAddress",
    "primaryTypeDisplayName",
    "viewport",
    "attributions",
    "googleMapsTypeLabel",
    "editorialSummary",
    "iconMaskBaseUri",
    "iconBackgroundColor",
    "openingDate",
    "utcOffsetMinutes",
    "pureServiceAreaBusiness",
    "movedPlace",
    "movedPlaceId",
    "reviews",
    "takeout",
    "delivery",
    "dineIn",
    "curbsidePickup",
    "reservable",
    "servesBreakfast",
    "servesLunch",
    "servesDinner",
    "servesBeer",
    "servesWine",
    "servesBrunch",
    "servesVegetarianFood",
    "outdoorSeating",
    "liveMusic",
    "menuForChildren",
    "servesCocktails",
    "servesDessert",
    "servesCoffee",
    "goodForChildren",
    "allowsDogs",
    "restroom",
    "goodForGroups",
    "goodForWatchingSports",
    "paymentOptions",
    "parkingOptions",
    "accessibilityOptions",
    "timeZone",
    "generativeSummary",
    "reviewSummary",
    "consumerAlert",
    "googleMapsLinks",
    "priceRange",
    "evChargeOptions",
    "addressDescriptor",
)

#: One segment of a field path. Wire field names are camelCase
#: identifiers of at least two characters; the two character floor is
#: what keeps a shredded one-character path out even when a caller
#: materializes a string into a list themselves.
_SEGMENT = re.compile(r"[A-Za-z][A-Za-z0-9]+")


def _safe_repr(value: Any) -> str:
    """The repr of a caller supplied value for an error message.

    A member whose own repr raises must not escape through the
    message that reports it, so a repr failure falls back to the
    type name and the ConfigError exists before any hostile
    value is formatted into it (Round 24, RT4).
    """
    try:
        return repr(value)
    except Exception:
        return f"<{type(value).__name__} whose repr raised>"


def _set_sort_key(value: Any) -> tuple[int, str]:
    """A sort key for set members that cannot raise.

    String members sort among themselves exactly as a plain
    sort orders them, so a set of paths keeps its deterministic
    header order. A member of any other type sorts after the
    strings by its safe repr and is then refused by the
    constructor as a ConfigError, instead of the comparison
    itself escaping as a bare TypeError (Round 24, RT4).
    """
    if isinstance(value, str):
        return (0, value)
    return (1, _safe_repr(value))


@dataclass(frozen=True, slots=True)
class FieldMask:
    """An immutable, validated set of field paths for one request.

    >>> mask = FieldMask("places.displayName", "places.rating")
    >>> mask.header_value
    'places.displayName,places.rating'

    The mask is a frozen dataclass, so assigning to ``paths`` after
    construction raises ``dataclasses.FrozenInstanceError``; build a
    new mask instead of editing one (A23).

    A mask carries at most ``MAX_MATERIALIZED_ITEMS`` paths, the
    same ceiling ``FieldMask.of`` enforces on the iterables it
    reads, so the two public doors into the type refuse the same
    absurd sizes (Round 24 repair).
    """

    paths: Tuple[str, ...]

    def __init__(self, *paths: str) -> None:
        if not paths:
            raise ConfigError(
                "FieldMask requires at least one field path",
                context="FieldMask",
            )
        if len(paths) > MAX_MATERIALIZED_ITEMS:
            raise ConfigError(
                f"FieldMask takes at most {MAX_MATERIALIZED_ITEMS} "
                f"field paths, got {len(paths)}",
                context="FieldMask",
            )
        for path in paths:
            if not isinstance(path, str) or not _valid_path(path):
                raise ConfigError(
                    f"invalid field mask path: {_safe_repr(path)}",
                    context="FieldMask",
                )
        # A mask is a set of paths; duplicates are dropped keeping
        # first seen order so the header is stable for a given input.
        object.__setattr__(self, "paths", tuple(dict.fromkeys(paths)))

    @property
    def header_value(self) -> str:
        """The value sent in the X-Goog-FieldMask header."""
        return ",".join(self.paths)

    @classmethod
    def of(cls, paths: "FieldMask | Iterable[str]") -> "FieldMask":
        """Build a mask from any iterable of paths.

        A FieldMask passes through unchanged, so a mask can be
        rebuilt from itself the way the client methods already
        accept one in the ``fields`` argument (Round 24, the one
        genuine defect inside the composition finding).

        A single string is not an iterable of paths for this purpose;
        it is rejected rather than shredded into one-character paths.
        Sets are sorted first so the header order is deterministic.

        The iterable is materialised under the universal ceiling
        (``MAX_MATERIALIZED_ITEMS``), and anything it raises while
        being read surfaces as a ConfigError with the original
        exception chained, so a hostile or endless iterable fails
        the way every other local misuse fails (R20-F01 and F10).
        """
        if isinstance(paths, FieldMask):
            return paths
        if isinstance(paths, (str, bytes)):
            raise ConfigError(
                "FieldMask.of expects an iterable of field paths, "
                f"not a single string: {_safe_repr(paths)}",
                context="FieldMask",
            )
        from_set = isinstance(paths, (set, frozenset))
        try:
            items = _materialize_bounded(
                "field paths", paths, MAX_MATERIALIZED_ITEMS
            )
        except ConfigError as exc:
            # A mask construction failure carries the mask as its
            # context (Round 25, Minor 4), set here rather than in
            # the shared materialiser, whose other callers are
            # client parameters the client annotates itself.
            if exc.context is None:
                exc.context = "FieldMask"
            raise
        if from_set:
            items = sorted(items, key=_set_sort_key)
        return cls(*items)

    @classmethod
    def text_search(cls) -> "FieldMask":
        """The curated Text Search default mask."""
        return cls(*TEXT_SEARCH_FIELDS)

    @classmethod
    def nearby_search(cls) -> "FieldMask":
        """The curated Nearby Search default mask."""
        return cls(*NEARBY_SEARCH_FIELDS)

    @classmethod
    def place_details(cls) -> "FieldMask":
        """The curated Place Details default mask."""
        return cls(*PLACE_DETAILS_FIELDS)


#: Accepted shapes for the ``fields`` argument of client methods.
FieldsLike = Union[FieldMask, Iterable[str], None]


def _valid_path(path: str) -> bool:
    """Whether one path matches the wire grammar: dot separated
    camelCase segments, no empty segments, whitespace, commas or
    wildcards. Semantic errors (snake_case names, stray punctuation)
    fail here, locally, instead of at the API."""
    if not path or path.strip() != path or "," in path:
        return False
    return all(_SEGMENT.fullmatch(segment) for segment in path.split("."))


def normalize_fields(fields: FieldsLike) -> list[str] | None:
    """Normalize a fields argument into a plain list of paths, or None."""
    if fields is None:
        return None
    if isinstance(fields, FieldMask):
        return list(fields.paths)
    if isinstance(fields, (str, bytes)):
        raise ConfigError(
            "fields must be an iterable of field paths or a FieldMask, "
            f"not a single string: {_safe_repr(fields)}",
            context="FieldMask",
        )
    return list(FieldMask.of(fields).paths)


__all__ = [
    "MAX_MATERIALIZED_ITEMS",
    "NEARBY_SEARCH_FIELDS",
    "PLACE_DETAILS_FIELDS",
    "TEXT_SEARCH_FIELDS",
    "FieldMask",
    "FieldsLike",
    "normalize_fields",
]
