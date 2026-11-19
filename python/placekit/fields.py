"""Field masks, a first-class part of the Places API (New) protocol.

Every response field must be requested through the ``X-Goog-FieldMask``
header, and billing follows the fields you ask for. Pass a ``FieldMask`` (or
any iterable of path strings) as the ``fields`` argument of search and
details and autocomplete calls. When ``fields`` is omitted, the search
and details calls use curated defaults. Autocomplete has no curated
default, so the API default field set governs an autocomplete call
that passes no ``fields``. A mask is judged again when it is used in
a call, whatever its size at construction. The core refuses a mask
holding more than 100 paths, and a mask whose joined header value
runs past 4096 bytes, at call time.

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

Construction of a mask is computed in the Rust core since
Round 54. This module reads the caller supplied values through
the same guarded reads as before, converts the checked paths
into plain data, and lets the core grammar, the duplicate
dropping and the set ordering decide over those values, so the
class keeps its signature and its ConfigError discipline and no
caller code changes. The header value stays a join over the
stored paths in this module, so it keeps returning the objects
the old property returned. One boundary travels with the
delegation. Where a caller supplied operation returns a wrong
answer instead of raising, the construction follows the values
as sent to the core rather than the answer the operation gave.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Tuple, Union

from . import _placekit
from ._guarded import (
    MAX_MATERIALIZED_ITEMS,
    _materialize_bounded,
    _safe_repr,
    _safe_type_name,
)
from .exceptions import ConfigError

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

    Construction is not the operative bound. When a mask is used
    in a call, the core refuses a mask holding more than 100 paths
    and a mask whose joined header value runs past 4096 bytes, so
    a mask of a few hundred short paths constructs without
    complaint and then fails at call time with a ``ConfigError``
    naming the bound it crossed.
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
        encoded = []
        pending: list[tuple[int, bytes]] = []

        def flush_pending() -> None:
            # The verdicts of a run of plain string paths are
            # decided in one core pass (audit A50-149). A plain
            # string's own checks perform no caller visible
            # operation (its reads cannot be overridden and its
            # encoding is taken unbound), so deferring its
            # verdict across later plain string paths is
            # invisible to the caller. The flush therefore runs
            # at the first member that is not a plain string,
            # whose checks can be observed, and once after the
            # loop, so a refusal still surfaces ahead of every
            # observable read, exactly where the per path
            # crossing used to raise it.
            if not pending:
                return
            bad = _placekit.mask_first_invalid_path(
                [data for _index, data in pending]
            )
            if bad is not None:
                index = pending[bad][0]
                raise ConfigError(
                    f"invalid field mask path: {_safe_repr(paths[index])}",
                    context="FieldMask",
                )
            pending.clear()

        for index, path in enumerate(paths):
            if type(path) is not str:
                flush_pending()
            if not isinstance(path, str):
                raise ConfigError(
                    f"invalid field mask path: {_safe_repr(path)}",
                    context="FieldMask",
                )
            if type(path) is not str:
                try:
                    _valid_path(path)
                except Exception as exc:
                    # The path check reads the member (strip,
                    # membership, split), and a string subclass whose
                    # read raises used to escape construction as a
                    # bare builtin. The member is rendered safely, so
                    # the refusal itself cannot be the escaping read
                    # (Round 31, Caller Minor 3). The check now runs
                    # as the caller side exercise of the construction
                    # check, at the old site, so the raise still
                    # surfaces here, and the verdict that decides
                    # comes from the core over the value as sent
                    # (Round 54). An exact string member skips the
                    # exercise: its reads run on the string's own
                    # buffer, no caller code can run inside them,
                    # and the exercise's answer is discarded either
                    # way, so the skip is invisible (audit A50-209).
                    raise ConfigError(
                        f"invalid field mask path: {_safe_repr(path)}",
                        context="FieldMask",
                    ) from exc
            data = _encode_path(path)
            if type(path) is str:
                pending.append((index, data))
            elif not _placekit.mask_valid_path(data):
                raise ConfigError(
                    f"invalid field mask path: {_safe_repr(path)}",
                    context="FieldMask",
                )
            encoded.append(data)
        flush_pending()
        # A mask is a set of paths; duplicates are dropped keeping
        # first seen order so the header is stable for a given input.
        # The dedupe reads the members once more, hashing and
        # comparing them, past the guarded path check above, and a
        # member whose hash or equality raises used to escape here
        # as a bare builtin (Round 34, red team Minor 1). The
        # caller side pass below still performs those reads at
        # this site so a raise still surfaces here, and the core
        # picks the surviving members over the values as sent, so
        # the tuple stored holds the caller's own first seen
        # objects at the indices the core returns (Round 54).
        try:
            dict.fromkeys(paths)
        except Exception as exc:
            raise ConfigError(
                "a field mask path raised while its duplicates "
                "were being dropped",
                context="FieldMask",
            ) from exc
        unique = tuple(
            paths[index] for index in _placekit.mask_unique_indices(encoded)
        )
        object.__setattr__(self, "paths", unique)

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

        The mask this returns is still subject to the call time
        bounds the class docstring names, at most 100 paths and a
        4096 byte header, which the core enforces when the mask
        is sent.
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
            try:
                keys = [_set_sort_key(item) for item in items]
                # The sort key itself reads no member past its
                # type, but comparing the keys of two string
                # members reads the members themselves, and a
                # member whose comparison raises used to escape
                # here as a bare builtin (Round 34, red team
                # Minor 1). The caller side pass below still
                # performs those comparisons at this site, over
                # the keys the old sort computed, so a raise still
                # surfaces here, and the core then fixes the
                # order over the values as sent (Round 54).
                sorted(range(len(items)), key=keys.__getitem__)
            except Exception as exc:
                raise ConfigError(
                    "a field mask path raised while the set of "
                    "paths was being sorted",
                    context="FieldMask",
                ) from exc
            order = _placekit.mask_sorted_order(
                [(rank, _encode_path(text)) for rank, text in keys]
            )
            items = [items[index] for index in order]
        return cls(*items)

    @classmethod
    def text_search(cls) -> "FieldMask":
        """The curated Text Search default mask."""
        if cls is FieldMask:
            return _curated_default("text_search", TEXT_SEARCH_FIELDS)
        return cls(*TEXT_SEARCH_FIELDS)

    @classmethod
    def nearby_search(cls) -> "FieldMask":
        """The curated Nearby Search default mask."""
        if cls is FieldMask:
            return _curated_default("nearby_search", NEARBY_SEARCH_FIELDS)
        return cls(*NEARBY_SEARCH_FIELDS)

    @classmethod
    def place_details(cls) -> "FieldMask":
        """The curated Place Details default mask."""
        if cls is FieldMask:
            return _curated_default("place_details", PLACE_DETAILS_FIELDS)
        return cls(*PLACE_DETAILS_FIELDS)


#: The curated default masks, built once each. A mask is a
#: frozen dataclass over a tuple of paths, so a standing
#: instance is safe to share, and the core keeps its own
#: defaults the same way (audit A50-038). A caller who asks
#: for the same default on every request otherwise repays
#: the full construction, crossings included, every time
#: (audit A50-148).
_CURATED_DEFAULTS: dict[str, "FieldMask"] = {}


def _curated_default(name: str, fields: Tuple[str, ...]) -> "FieldMask":
    mask = _CURATED_DEFAULTS.get(name)
    if mask is None:
        mask = FieldMask(*fields)
        _CURATED_DEFAULTS[name] = mask
    return mask


#: Accepted shapes for the ``fields`` argument of client methods.
FieldsLike = Union[FieldMask, Iterable[str], None]


def _encode_path(path: str) -> bytes:
    """The byte form of one path for the core crossing.

    The core works on byte strings, and the surrogatepass codec
    carries a lone surrogate in a caller string across exactly,
    the crossing Round 53 settled for component texts. The
    unbound ``str.encode`` reads the string's own buffer, so the
    conversion performs no call on the caller's object, and a
    subclass that overrides ``encode`` can neither raise nor lie
    at a site the pre port code never called (Round 54).
    """
    return str.encode(path, "utf-8", "surrogatepass")


def _valid_path(path: str) -> bool:
    """Whether one path matches the wire grammar: dot separated
    camelCase segments, no empty segments, whitespace, commas or
    wildcards. Semantic errors (snake_case names, stray punctuation)
    fail here, locally, instead of at the API.

    Since Round 54 this function is the caller side exercise of
    the construction check. The constructor runs it at the old
    site so a member whose own reads raise surfaces the raise
    exactly where it always did, and its answer is no longer the
    verdict. The verdict comes from the core over the value as
    sent, which the module docstring states as the delegation
    boundary.
    """
    if not path or path.strip() != path or "," in path:
        return False
    return all(_SEGMENT.fullmatch(segment) for segment in path.split("."))


def _mask_paths(mask: FieldMask) -> list[str]:
    """The paths of a mask instance, read defensively.

    A mask is a frozen dataclass, but a caller can fabricate
    one past its constructor, so the state an instance carries
    is not trusted here. A mask missing its paths is refused
    as a ConfigError instead of escaping as a bare
    AttributeError, and every member is revalidated as a
    string at this layer, so a fabricated mask carrying a non
    string member is refused before any native call, whose
    conversion would otherwise refuse the member with a bare
    TypeError outside every wrap the client provides (Round
    31, Caller Minor 3 and red team Minor 1). An ordinary mask
    reads exactly as it did before.
    """
    try:
        paths = mask.paths
    except Exception as exc:
        raise ConfigError(
            "the FieldMask carries no readable paths",
            context="FieldMask",
        ) from exc
    if isinstance(paths, (str, bytes)) or not isinstance(paths, (tuple, list)):
        raise ConfigError(
            "the FieldMask paths must be a tuple of strings, "
            f"got {_safe_repr(paths)}",
            context="FieldMask",
        )
    try:
        items = _materialize_bounded(
            "field paths", paths, MAX_MATERIALIZED_ITEMS
        )
    except ConfigError as exc:
        if exc.context is None:
            exc.context = "FieldMask"
        raise
    for item in items:
        if not isinstance(item, str):
            raise ConfigError(
                f"invalid field mask path: {_safe_repr(item)}",
                context="FieldMask",
            )
    return items


def normalize_fields(fields: FieldsLike) -> list[str] | None:
    """Normalize a fields argument into a plain list of paths, or None."""
    if fields is None:
        return None
    if isinstance(fields, FieldMask):
        return _mask_paths(fields)
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
