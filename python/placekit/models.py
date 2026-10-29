"""Typed response models for placekit.

Responses arrive as dataclasses with attribute access, never raw dicts.
Fields this client version does not model yet are preserved verbatim on
``Place.raw`` so nothing the API returns is silently lost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass(slots=True)
class LocalizedText:
    """A text value paired with its language."""

    text: str
    language_code: Optional[str] = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "LocalizedText":
        return cls(text=data.get("text", ""), language_code=data.get("languageCode"))


@dataclass(slots=True)
class LatLng:
    """A latitude/longitude pair."""

    latitude: float
    longitude: float

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "LatLng":
        return cls(latitude=float(data["latitude"]), longitude=float(data["longitude"]))

    def to_api(self) -> dict[str, float]:
        return {"latitude": self.latitude, "longitude": self.longitude}


@dataclass(slots=True)
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


@dataclass(slots=True)
class Attribution:
    """Provider attribution attached to a place."""

    provider: str = ""
    provider_uri: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Attribution":
        return cls(provider=data.get("provider", ""), provider_uri=data.get("providerUri", ""))


@dataclass(slots=True)
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

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Photo":
        return cls(
            name=data.get("name", ""),
            width_px=int(data.get("widthPx", 0)),
            height_px=int(data.get("heightPx", 0)),
            author_attributions=[
                AuthorAttribution.from_api(a) for a in data.get("authorAttributions", [])
            ],
            flag_content_uri=data.get("flagContentUri"),
            google_maps_uri=data.get("googleMapsUri"),
        )


@dataclass(slots=True)
class Date:
    """A calendar date. A zero component means it was unset."""

    year: int = 0
    month: int = 0
    day: int = 0

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Date":
        return cls(
            year=int(data.get("year", 0)),
            month=int(data.get("month", 0)),
            day=int(data.get("day", 0)),
        )


@dataclass(slots=True)
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
            day=data.get("day"),
            hour=data.get("hour"),
            minute=data.get("minute"),
        )


@dataclass(slots=True)
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


@dataclass(slots=True)
class OpeningHours:
    """Regular opening hours of a place."""

    open_now: Optional[bool] = None
    periods: list[Period] = field(default_factory=list)
    weekday_descriptions: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "OpeningHours":
        return cls(
            open_now=data.get("openNow"),
            periods=[Period.from_api(p) for p in data.get("periods", [])],
            weekday_descriptions=list(data.get("weekdayDescriptions", [])),
        )


@dataclass(slots=True)
class AddressComponent:
    """One component of a structured address."""

    long_text: str = ""
    short_text: str = ""
    types: list[str] = field(default_factory=list)
    language_code: Optional[str] = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "AddressComponent":
        return cls(
            long_text=data.get("longText", ""),
            short_text=data.get("shortText", ""),
            types=list(data.get("types", [])),
            language_code=data.get("languageCode"),
        )


@dataclass(slots=True)
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


@dataclass(slots=True)
class Viewport:
    """A rectangular area bounded by its low and high corners."""

    low: LatLng
    high: LatLng

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Viewport":
        return cls(
            low=LatLng.from_api(data.get("low", {})),
            high=LatLng.from_api(data.get("high", {})),
        )


@dataclass(slots=True)
class PostalAddress:
    """A postal address in structured form."""

    region_code: Optional[str] = None
    language_code: Optional[str] = None
    postal_code: Optional[str] = None
    administrative_area: Optional[str] = None
    locality: Optional[str] = None
    address_lines: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "PostalAddress":
        return cls(
            region_code=data.get("regionCode"),
            language_code=data.get("languageCode"),
            postal_code=data.get("postalCode"),
            administrative_area=data.get("administrativeArea"),
            locality=data.get("locality"),
            address_lines=list(data.get("addressLines", [])),
        )


@dataclass(slots=True)
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
    #: client version does not model yet.
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def display_text(self) -> Optional[str]:
        """The display name as a plain string, when present."""
        return self.display_name.text if self.display_name else None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Place":
        display = data.get("displayName")
        location = data.get("location")
        hours = data.get("regularOpeningHours")
        current_hours = data.get("currentOpeningHours")
        plus_code = data.get("plusCode")
        viewport = data.get("viewport")
        postal = data.get("postalAddress")
        type_display = data.get("primaryTypeDisplayName")
        place_id = data.get("id") or str(data.get("name", "")).removeprefix("places/")
        rating = data.get("rating")
        user_rating_count = data.get("userRatingCount")
        return cls(
            id=place_id,
            name=data.get("name", ""),
            display_name=LocalizedText.from_api(display) if display else None,
            formatted_address=data.get("formattedAddress"),
            short_formatted_address=data.get("shortFormattedAddress"),
            location=LatLng.from_api(location) if location else None,
            types=list(data.get("types", [])),
            primary_type=data.get("primaryType"),
            rating=float(rating) if rating is not None else None,
            user_rating_count=(
                int(user_rating_count) if user_rating_count is not None else None
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


@dataclass(slots=True)
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
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "TextSearchResult":
        return cls(
            places=[Place.from_api(p) for p in data.get("places", [])],
            next_page_token=data.get("nextPageToken"),
            search_uri=data.get("searchUri"),
            routing_summaries=list(data.get("routingSummaries", [])),
            raw=data,
        )


@dataclass(slots=True)
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
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "NearbySearchResult":
        return cls(
            places=[Place.from_api(p) for p in data.get("places", [])],
            routing_summaries=list(data.get("routingSummaries", [])),
            raw=data,
        )


@dataclass(slots=True)
class StringMatch:
    """A substring match range inside an autocomplete text."""

    start_offset: int = 0
    end_offset: int = 0

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "StringMatch":
        return cls(
            start_offset=int(data.get("startOffset", 0)),
            end_offset=int(data.get("endOffset", 0)),
        )


@dataclass(slots=True)
class FormattedText:
    """Text with match ranges, as returned by Autocomplete."""

    text: str = ""
    matches: list[StringMatch] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "FormattedText":
        return cls(
            text=data.get("text", ""),
            matches=[StringMatch.from_api(m) for m in data.get("matches", [])],
        )


@dataclass(slots=True)
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
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "PlacePrediction":
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
            types=list(data.get("types", [])),
            distance_meters=data.get("distanceMeters"),
            raw=data,
        )


@dataclass(slots=True)
class Suggestion:
    """One autocomplete suggestion.

    ``place_prediction`` is set for place suggestions. Query predictions are
    not modeled yet; their payload is preserved on ``raw``.
    """

    place_prediction: Optional[PlacePrediction] = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Suggestion":
        prediction = data.get("placePrediction")
        return cls(
            place_prediction=PlacePrediction.from_api(prediction) if prediction else None,
            raw=data,
        )


@dataclass(slots=True)
class AutocompleteResult:
    """Autocomplete suggestions for one input."""

    suggestions: list[Suggestion]
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def place_predictions(self) -> list[PlacePrediction]:
        """Just the place predictions, skipping any other suggestion kinds."""
        return [s.place_prediction for s in self.suggestions if s.place_prediction]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "AutocompleteResult":
        return cls(
            suggestions=[Suggestion.from_api(s) for s in data.get("suggestions", [])],
            raw=data,
        )


@dataclass(slots=True)
class PhotoMedia:
    """Downloaded photo bytes from the photo media endpoint."""

    content: bytes
    content_type: Optional[str] = None

    def save(self, path: str | Path) -> Path:
        """Write the photo to ``path`` and return the path."""
        target = Path(path)
        target.write_bytes(self.content)
        return target


@dataclass(slots=True)
class PhotoUriResult:
    """The photo media endpoint's JSON form, returned on request instead
    of following its redirect.

    Returned by ``place_photo`` when ``skip_http_redirect`` is set.
    ``photo_uri`` is short lived; render or fetch it promptly.
    """

    photo_uri: str
    name: str = ""
