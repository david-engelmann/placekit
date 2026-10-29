"""Field masks, a first-class part of the Places API (New) protocol.

Every response field must be requested through the ``X-Goog-FieldMask``
header, and billing follows the fields you ask for. Pass a ``FieldMask`` (or
any iterable of path strings) as the ``fields`` argument of search and
details calls. When ``fields`` is omitted, curated defaults are used.

Billing note: the curated defaults include fields from the Enterprise
billing tier (among them rating, userRatingCount, priceLevel and, on
Place Details, the phone numbers, websiteUri and regularOpeningHours),
so a default call is billed at that tier. A higher Enterprise plus
Atmosphere tier exists above it, and the defaults do not reach it. Pass
a narrower ``fields`` set to control billing.
"""

from __future__ import annotations

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
    "attributions",
)


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
            if not path or path.strip() != path or "," in path:
                raise ConfigError(f"invalid field mask path: {path!r}")
        object.__setattr__(self, "paths", tuple(paths))

    @property
    def header_value(self) -> str:
        """The value sent in the X-Goog-FieldMask header."""
        return ",".join(self.paths)

    @classmethod
    def of(cls, paths: Iterable[str]) -> "FieldMask":
        """Build a mask from any iterable of paths."""
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


def normalize_fields(fields: FieldsLike) -> list[str] | None:
    """Normalize a fields argument into a plain list of paths, or None."""
    if fields is None:
        return None
    if isinstance(fields, FieldMask):
        return list(fields.paths)
    return list(FieldMask.of(fields).paths)
