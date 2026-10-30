"""Typed response models for placekit.

Responses arrive as dataclasses with attribute access, never raw dicts.
Fields this client version does not model yet are preserved verbatim on
``Place.raw`` so nothing the API returns is silently lost.

The models are frozen value objects. Attribute assignment on a
parsed result raises instead of silently rewriting it, so a result
can be shared without one holder rebinding another holder's fields.
The freeze is shallow by design. List fields and each ``raw`` dict
remain mutable in place, so a holder can still append to
``place.types`` or edit ``place.raw``; only rebinding is refused.
They stay unhashable where they carry list fields; ``LatLng``, the
one pure pair, is hashable. Every ``raw`` is a deep copy of the
payload it came from, so the caller's dict, a result's raw and a
child model's raw share no mutable state.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .exceptions import ConfigError, DecodeError


def _require(data: dict[str, Any], key: str, model: str) -> Any:
    """Fetch a required payload key or raise a DecodeError naming it.

    One strictness policy for every decoder (RC-18): a missing
    required key is a DecodeError with the key and model named, never
    a bare KeyError and never a fabricated empty object.
    """
    if key not in data:
        raise DecodeError(f"{model} payload is missing required key {key!r}")
    return data[key]


def _as_float(value: Any, model: str, key: str) -> float:
    if isinstance(value, bool):
        raise DecodeError(f"{model} payload key {key!r} is not a number: {value!r}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise DecodeError(
            f"{model} payload key {key!r} is not a number: {value!r}"
        ) from exc


def _as_int(value: Any, model: str, key: str) -> int:
    if isinstance(value, bool):
        raise DecodeError(f"{model} payload key {key!r} is not an integer: {value!r}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise DecodeError(
            f"{model} payload key {key!r} is not an integer: {value!r}"
        ) from exc


def _optional_int(value: Any, model: str, key: str) -> Optional[int]:
    return None if value is None else _as_int(value, model, key)


def _str_list(value: Any, model: str, key: str) -> list[str]:
    """Decode a list of strings; a bare string is a DecodeError, never
    shredded into one-character items."""
    if isinstance(value, (str, bytes)):
        raise DecodeError(
            f"{model} payload key {key!r} is a single string, not a list"
        )
    try:
        return list(value)
    except TypeError as exc:
        raise DecodeError(
            f"{model} payload key {key!r} is not a list: {value!r}"
        ) from exc


def _reject_bare_string(model: str, field_name: str, value: Any) -> None:
    """Direct construction guard (RT5-L3): a list-typed field handed
    a bare string or bytes value would otherwise store it unchecked,
    and iterating the field later would yield one-character items,
    the shred the decoders already refuse on the response side."""
    if isinstance(value, (str, bytes)):
        raise ConfigError(
            f"{model} field {field_name!r} must be a list, not a "
            f"single string: {value!r}"
        )


@dataclass(frozen=True, slots=True)
class LocalizedText:
    """A text value paired with its language."""

    text: str
    language_code: Optional[str] = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "LocalizedText":
        return cls(text=data.get("text", ""), language_code=data.get("languageCode"))


@dataclass(frozen=True, slots=True)
class LatLng:
    """A latitude/longitude pair.

    Construction validates the values are real, finite numbers
    (bools and strings are not coordinates). Range is a request-side
    rule enforced by the client at call time, so a LatLng decoded
    from a response is preserved exactly as the API sent it.
    """

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        for name, value in (
            ("latitude", self.latitude),
            ("longitude", self.longitude),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                raise ConfigError(
                    f"LatLng {name} must be a finite real number, got {value!r}"
                )

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "LatLng":
        return cls(
            latitude=_as_float(_require(data, "latitude", "LatLng"), "LatLng", "latitude"),
            longitude=_as_float(
                _require(data, "longitude", "LatLng"), "LatLng", "longitude"
            ),
        )

    def to_api(self) -> dict[str, float]:
        return {"latitude": float(self.latitude), "longitude": float(self.longitude)}


@dataclass(frozen=True, slots=True)
class AuthorAttribution:
    """Credit for a photo author."""

    display_name: str = ""
    uri: str = ""
    photo_uri: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "AuthorAttribution":
        return cls(
            display_name=data.get("displayName", ""),
            uri=data.get("uri", ""),
            photo_uri=data.get("photoUri", ""),
        )


@dataclass(frozen=True, slots=True)
class Attribution:
    """Provider attribution attached to a place."""

    provider: str = ""
    provider_uri: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Attribution":
        return cls(provider=data.get("provider", ""), provider_uri=data.get("providerUri", ""))


@dataclass(frozen=True, slots=True)
class Photo:
    """A photo attached to a place.

    Pass ``name`` to ``Client.place_photo`` to download the image.
    """

    name: str
    width_px: int = 0
    height_px: int = 0
    author_attributions: list[AuthorAttribution] = field(default_factory=list)
    #: Link where users can flag a problem with this photo.
    flag_content_uri: Optional[str] = None
    #: Link to view this photo on Google Maps.
    google_maps_uri: Optional[str] = None

    def __post_init__(self) -> None:
        _reject_bare_string("Photo", "author_attributions", self.author_attributions)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Photo":
        return cls(
            name=data.get("name", ""),
            width_px=_as_int(data.get("widthPx", 0), "Photo", "widthPx"),
            height_px=_as_int(data.get("heightPx", 0), "Photo", "heightPx"),
            author_attributions=[
                AuthorAttribution.from_api(a) for a in data.get("authorAttributions", [])
            ],
            flag_content_uri=data.get("flagContentUri"),
            google_maps_uri=data.get("googleMapsUri"),
        )


@dataclass(frozen=True, slots=True)
class Date:
    """A calendar date. A zero component means it was unset."""

    year: int = 0
    month: int = 0
    day: int = 0

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Date":
        return cls(
            year=_as_int(data.get("year", 0), "Date", "year"),
            month=_as_int(data.get("month", 0), "Date", "month"),
            day=_as_int(data.get("day", 0), "Date", "day"),
        )


@dataclass(frozen=True, slots=True)
class OpeningPoint:
    """One end of an opening period.

    ``day`` is 0 for Sunday through 6 for Saturday. The first period in a
    list does not start on any fixed day, and period order is independent
    of the weekday description order.
    """

    date: Optional[Date] = None
    truncated: Optional[bool] = None
    day: Optional[int] = None
    hour: Optional[int] = None
    minute: Optional[int] = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "OpeningPoint":
        date = data.get("date")
        return cls(
            date=Date.from_api(date) if date else None,
            truncated=data.get("truncated"),
            day=_optional_int(data.get("day"), "OpeningPoint", "day"),
            hour=_optional_int(data.get("hour"), "OpeningPoint", "hour"),
            minute=_optional_int(data.get("minute"), "OpeningPoint", "minute"),
        )


@dataclass(frozen=True, slots=True)
class Period:
    """A single open/close span within opening hours."""

    open: Optional[OpeningPoint] = None
    close: Optional[OpeningPoint] = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Period":
        open_point = data.get("open")
        close_point = data.get("close")
        return cls(
            open=OpeningPoint.from_api(open_point) if open_point else None,
            close=OpeningPoint.from_api(close_point) if close_point else None,
        )


@dataclass(frozen=True, slots=True)
class OpeningHours:
    """Regular opening hours of a place."""

    open_now: Optional[bool] = None
    periods: list[Period] = field(default_factory=list)
    weekday_descriptions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _reject_bare_string("OpeningHours", "periods", self.periods)
        _reject_bare_string(
            "OpeningHours", "weekday_descriptions", self.weekday_descriptions
        )

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "OpeningHours":
        return cls(
            open_now=data.get("openNow"),
            periods=[Period.from_api(p) for p in data.get("periods", [])],
            weekday_descriptions=_str_list(
                data.get("weekdayDescriptions", []),
                "OpeningHours",
                "weekdayDescriptions",
            ),
        )


@dataclass(frozen=True, slots=True)
class AddressComponent:
    """One component of a structured address."""

    long_text: str = ""
    short_text: str = ""
    types: list[str] = field(default_factory=list)
    language_code: Optional[str] = None

    def __post_init__(self) -> None:
        _reject_bare_string("AddressComponent", "types", self.types)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "AddressComponent":
        return cls(
            long_text=data.get("longText", ""),
            short_text=data.get("shortText", ""),
            types=_str_list(data.get("types", []), "AddressComponent", "types"),
            language_code=data.get("languageCode"),
        )


@dataclass(frozen=True, slots=True)
class PlusCode:
    """Plus code location reference for a place."""

    global_code: str = ""
    compound_code: Optional[str] = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "PlusCode":
        return cls(
            global_code=data.get("globalCode", ""),
            compound_code=data.get("compoundCode"),
        )


@dataclass(frozen=True, slots=True)
class Viewport:
    """A rectangular area bounded by its low and high corners."""

    low: LatLng
    high: LatLng

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Viewport":
        return cls(
            low=LatLng.from_api(_require(data, "low", "Viewport")),
            high=LatLng.from_api(_require(data, "high", "Viewport")),
        )


@dataclass(frozen=True, slots=True)
class PostalAddress:
    """A postal address in structured form."""

    region_code: Optional[str] = None
    language_code: Optional[str] = None
    postal_code: Optional[str] = None
    administrative_area: Optional[str] = None
    locality: Optional[str] = None
    address_lines: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _reject_bare_string("PostalAddress", "address_lines", self.address_lines)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "PostalAddress":
        return cls(
            region_code=data.get("regionCode"),
            language_code=data.get("languageCode"),
            postal_code=data.get("postalCode"),
            administrative_area=data.get("administrativeArea"),
            locality=data.get("locality"),
            address_lines=_str_list(
                data.get("addressLines", []), "PostalAddress", "addressLines"
            ),
        )


# Wire fidelity note (T19): public field names mirror the API's own
# names even where they shadow builtins (Place.id above all, and the
# various types fields). Renaming them would break the one-to-one
# mapping between model attributes and wire fields that callers rely
# on when reading raw payloads, so the shadowing is kept deliberately
# and no rename is planned.
@dataclass(frozen=True, slots=True)
class Place:
    """A single place, from search results or Place Details."""

    id: str
    name: str = ""
    display_name: Optional[LocalizedText] = None
    formatted_address: Optional[str] = None
    short_formatted_address: Optional[str] = None
    location: Optional[LatLng] = None
    types: list[str] = field(default_factory=list)
    primary_type: Optional[str] = None
    rating: Optional[float] = None
    user_rating_count: Optional[int] = None
    price_level: Optional[str] = None
    business_status: Optional[str] = None
    national_phone_number: Optional[str] = None
    international_phone_number: Optional[str] = None
    website_uri: Optional[str] = None
    google_maps_uri: Optional[str] = None
    opening_hours: Optional[OpeningHours] = None
    current_opening_hours: Optional[OpeningHours] = None
    address_components: list[AddressComponent] = field(default_factory=list)
    plus_code: Optional[PlusCode] = None
    viewport: Optional[Viewport] = None
    postal_address: Optional[PostalAddress] = None
    adr_format_address: Optional[str] = None
    primary_type_display_name: Optional[LocalizedText] = None
    photos: list[Photo] = field(default_factory=list)
    attributions: list[Attribution] = field(default_factory=list)
    #: The full response payload for this place, including any fields this
    #: client version does not model yet. A deep copy of the payload, so
    #: it shares no mutable state with the caller's dict. Excluded from
    #: repr and equality, which are about the modelled fields.
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("Place", "types", self.types)
        _reject_bare_string("Place", "address_components", self.address_components)
        _reject_bare_string("Place", "photos", self.photos)
        _reject_bare_string("Place", "attributions", self.attributions)

    @property
    def display_text(self) -> Optional[str]:
        """The display name as a plain string, when present."""
        return self.display_name.text if self.display_name else None

    @property
    def regular_opening_hours(self) -> Optional[OpeningHours]:
        """Alias for ``opening_hours`` under its wire name,
        ``regularOpeningHours``."""
        return self.opening_hours

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Place":
        data = copy.deepcopy(data)
        display = data.get("displayName")
        location = data.get("location")
        hours = data.get("regularOpeningHours")
        current_hours = data.get("currentOpeningHours")
        plus_code = data.get("plusCode")
        viewport = data.get("viewport")
        postal = data.get("postalAddress")
        type_display = data.get("primaryTypeDisplayName")
        place_id = data.get("id") or str(data.get("name", "")).removeprefix("places/")
        if not data:
            # An empty payload is a truncated or wrong response, not a
            # place; a payload that merely lacks an id (a field mask
            # that did not request one) still decodes, with id "".
            raise DecodeError(
                "Place payload is empty; refusing to fabricate an "
                "empty place from it"
            )
        rating = data.get("rating")
        user_rating_count = data.get("userRatingCount")
        return cls(
            id=place_id,
            name=data.get("name", ""),
            display_name=LocalizedText.from_api(display) if display else None,
            formatted_address=data.get("formattedAddress"),
            short_formatted_address=data.get("shortFormattedAddress"),
            location=LatLng.from_api(location) if location else None,
            types=_str_list(data.get("types", []), "Place", "types"),
            primary_type=data.get("primaryType"),
            rating=(
                _as_float(rating, "Place", "rating") if rating is not None else None
            ),
            user_rating_count=(
                _as_int(user_rating_count, "Place", "userRatingCount")
                if user_rating_count is not None
                else None
            ),
            price_level=data.get("priceLevel"),
            business_status=data.get("businessStatus"),
            national_phone_number=data.get("nationalPhoneNumber"),
            international_phone_number=data.get("internationalPhoneNumber"),
            website_uri=data.get("websiteUri"),
            google_maps_uri=data.get("googleMapsUri"),
            opening_hours=OpeningHours.from_api(hours) if hours else None,
            current_opening_hours=(
                OpeningHours.from_api(current_hours) if current_hours else None
            ),
            address_components=[
                AddressComponent.from_api(c)
                for c in data.get("addressComponents", [])
            ],
            plus_code=PlusCode.from_api(plus_code) if plus_code else None,
            viewport=Viewport.from_api(viewport) if viewport else None,
            postal_address=PostalAddress.from_api(postal) if postal else None,
            adr_format_address=data.get("adrFormatAddress"),
            primary_type_display_name=(
                LocalizedText.from_api(type_display) if type_display else None
            ),
            photos=[Photo.from_api(p) for p in data.get("photos", [])],
            attributions=[Attribution.from_api(a) for a in data.get("attributions", [])],
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class TextSearchResult:
    """One page of Text Search results."""

    places: list[Place]
    #: Pass back as ``page_token`` to fetch the next page, when present.
    next_page_token: Optional[str] = None
    #: Link to run the same query on Google Maps. Present only when the
    #: ``searchUri`` field was requested through the field mask.
    search_uri: Optional[str] = None
    #: Routing summaries, one per place, when requested through the field
    #: mask and routing parameters were supplied. Unmodeled entries are
    #: preserved as dicts.
    routing_summaries: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("TextSearchResult", "places", self.places)
        _reject_bare_string(
            "TextSearchResult", "routing_summaries", self.routing_summaries
        )

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "TextSearchResult":
        data = copy.deepcopy(data)
        return cls(
            places=[Place.from_api(p) for p in data.get("places", [])],
            next_page_token=data.get("nextPageToken"),
            search_uri=data.get("searchUri"),
            routing_summaries=list(data.get("routingSummaries", [])),
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class NearbySearchResult:
    """Nearby Search results (the API returns at most one page).

    There is deliberately no ``next_page_token`` here. The Places API
    does not paginate Nearby Search; the Rust response type is shared
    with Text Search, which is the only reason the field exists at the
    wire layer at all.
    """

    places: list[Place]
    #: Routing summaries, one per place, when requested through the field
    #: mask and routing parameters were supplied.
    routing_summaries: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("NearbySearchResult", "places", self.places)
        _reject_bare_string(
            "NearbySearchResult", "routing_summaries", self.routing_summaries
        )

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "NearbySearchResult":
        data = copy.deepcopy(data)
        return cls(
            places=[Place.from_api(p) for p in data.get("places", [])],
            routing_summaries=list(data.get("routingSummaries", [])),
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class StringMatch:
    """A substring match range inside an autocomplete text."""

    start_offset: int = 0
    end_offset: int = 0

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "StringMatch":
        return cls(
            start_offset=_as_int(data.get("startOffset", 0), "StringMatch", "startOffset"),
            end_offset=_as_int(data.get("endOffset", 0), "StringMatch", "endOffset"),
        )


@dataclass(frozen=True, slots=True)
class FormattedText:
    """Text with match ranges, as returned by Autocomplete."""

    text: str = ""
    matches: list[StringMatch] = field(default_factory=list)

    def __post_init__(self) -> None:
        _reject_bare_string("FormattedText", "matches", self.matches)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "FormattedText":
        return cls(
            text=data.get("text", ""),
            matches=[StringMatch.from_api(m) for m in data.get("matches", [])],
        )


@dataclass(frozen=True, slots=True)
class PlacePrediction:
    """A predicted place from Autocomplete."""

    place_id: str
    #: Resource name of the suggested place, for example
    #: ``places/ChIJrTLr-GyuEmsRBfy61i59si0``.
    place: str = ""
    text: Optional[FormattedText] = None
    main_text: Optional[FormattedText] = None
    secondary_text: Optional[FormattedText] = None
    types: list[str] = field(default_factory=list)
    distance_meters: Optional[int] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("PlacePrediction", "types", self.types)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "PlacePrediction":
        data = copy.deepcopy(data)
        text = data.get("text")
        structured = data.get("structuredFormat") or {}
        main = structured.get("mainText")
        secondary = structured.get("secondaryText")
        return cls(
            place_id=data.get("placeId", ""),
            place=data.get("place", ""),
            text=FormattedText.from_api(text) if text else None,
            main_text=FormattedText.from_api(main) if main else None,
            secondary_text=FormattedText.from_api(secondary) if secondary else None,
            types=_str_list(data.get("types", []), "PlacePrediction", "types"),
            distance_meters=_optional_int(
                data.get("distanceMeters"), "PlacePrediction", "distanceMeters"
            ),
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class QueryPrediction:
    """A predicted search query from Autocomplete, returned when
    ``include_query_predictions`` is set."""

    text: Optional[FormattedText] = None
    main_text: Optional[FormattedText] = None
    secondary_text: Optional[FormattedText] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "QueryPrediction":
        data = copy.deepcopy(data)
        text = data.get("text")
        structured = data.get("structuredFormat") or {}
        main = structured.get("mainText")
        secondary = structured.get("secondaryText")
        return cls(
            text=FormattedText.from_api(text) if text else None,
            main_text=FormattedText.from_api(main) if main else None,
            secondary_text=FormattedText.from_api(secondary) if secondary else None,
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class Suggestion:
    """One autocomplete suggestion.

    ``place_prediction`` is set for place suggestions and
    ``query_prediction`` for query suggestions; the full payload is
    preserved on ``raw`` either way.
    """

    place_prediction: Optional[PlacePrediction] = None
    query_prediction: Optional[QueryPrediction] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Suggestion":
        data = copy.deepcopy(data)
        prediction = data.get("placePrediction")
        query = data.get("queryPrediction")
        return cls(
            place_prediction=PlacePrediction.from_api(prediction) if prediction else None,
            query_prediction=QueryPrediction.from_api(query) if query else None,
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class AutocompleteResult:
    """Autocomplete suggestions for one input."""

    suggestions: list[Suggestion]
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("AutocompleteResult", "suggestions", self.suggestions)

    @property
    def place_predictions(self) -> list[PlacePrediction]:
        """Just the place predictions, skipping any other suggestion kinds."""
        return [s.place_prediction for s in self.suggestions if s.place_prediction]

    @property
    def query_predictions(self) -> list[QueryPrediction]:
        """Just the query predictions, skipping any other suggestion kinds."""
        return [s.query_prediction for s in self.suggestions if s.query_prediction]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "AutocompleteResult":
        data = copy.deepcopy(data)
        return cls(
            suggestions=[Suggestion.from_api(s) for s in data.get("suggestions", [])],
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class PhotoMedia:
    """Downloaded photo bytes from the photo media endpoint."""

    #: The image bytes; excluded from repr so printing a result does
    #: not dump the payload.
    content: bytes = field(repr=False)
    content_type: Optional[str] = None

    def save(self, path: str | Path) -> Path:
        """Write the photo to ``path`` and return the path.

        An existing file at ``path`` is overwritten. The parent
        directory must already exist.
        """
        target = Path(path)
        target.write_bytes(self.content)
        return target


@dataclass(frozen=True, slots=True)
class PhotoUriResult:
    """The photo media endpoint's JSON form, returned on request instead
    of following its redirect.

    Returned by ``place_photo`` when ``skip_http_redirect`` is set.
    ``photo_uri`` is short lived; render or fetch it promptly.
    """

    photo_uri: str
    name: str = ""
