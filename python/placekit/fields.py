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
narrower ``fields`` set to control billing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Tuple, Union

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
    "addressComponents",
    "adrFormatAddress",
    "plusCode",
    "postalAddress",
    "primaryTypeDisplayName",
    "viewport",
    "attributions",
)

#: One segment of a field path. Wire field names are camelCase
#: identifiers of at least two characters; the two character floor is
#: what keeps a shredded one-character path out even when a caller
#: materializes a string into a list themselves.
_SEGMENT = re.compile(r"[A-Za-z][A-Za-z0-9]+")


@dataclass(frozen=True, slots=True)
class FieldMask:
    """An immutable, validated set of field paths for one request.

    >>> mask = FieldMask("places.displayName", "places.rating")
    >>> mask.header_value
    'places.displayName,places.rating'
    """

    paths: Tuple[str, ...]

    def __init__(self, *paths: str) -> None:
        if not paths:
            raise ConfigError("FieldMask requires at least one field path")
        for path in paths:
            if not isinstance(path, str) or not _valid_path(path):
                raise ConfigError(f"invalid field mask path: {path!r}")
        # A mask is a set of paths; duplicates are dropped keeping
        # first seen order so the header is stable for a given input.
        object.__setattr__(self, "paths", tuple(dict.fromkeys(paths)))

    @property
    def header_value(self) -> str:
        """The value sent in the X-Goog-FieldMask header."""
        return ",".join(self.paths)

    @classmethod
    def of(cls, paths: Iterable[str]) -> "FieldMask":
        """Build a mask from any iterable of paths.

        A single string is not an iterable of paths for this purpose;
        it is rejected rather than shredded into one-character paths.
        Sets are sorted first so the header order is deterministic.
        """
        if isinstance(paths, (str, bytes)):
            raise ConfigError(
                "FieldMask.of expects an iterable of field paths, "
                f"not a single string: {paths!r}"
            )
        if isinstance(paths, (set, frozenset)):
            paths = sorted(paths)
        return cls(*paths)

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
            f"not a single string: {fields!r}"
        )
    return list(FieldMask.of(fields).paths)
