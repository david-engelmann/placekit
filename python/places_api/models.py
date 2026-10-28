"""Typed response models for places_api.

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

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Photo":
        return cls(
            name=data.get("name", ""),
            width_px=int(data.get("widthPx", 0)),
            height_px=int(data.get("heightPx", 0)),
            author_attributions=[
                AuthorAttribution.from_api(a) for a in data.get("authorAttributions", [])
            ],
        )


@dataclass(slots=True)
class OpeningHours:
    """Regular opening hours of a place."""

    open_now: Optional[bool] = None
    weekday_descriptions: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "OpeningHours":
        return cls(
            open_now=data.get("openNow"),
            weekday_descriptions=list(data.get("weekdayDescriptions", [])),
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
        place_id = data.get("id") or str(data.get("name", "")).removeprefix("places/")
        return cls(
            id=place_id,
            name=data.get("name", ""),
            display_name=LocalizedText.from_api(display) if display else None,
            formatted_address=data.get("formattedAddress"),
            short_formatted_address=data.get("shortFormattedAddress"),
            location=LatLng.from_api(location) if location else None,
            types=list(data.get("types", [])),
            primary_type=data.get("primaryType"),
            rating=data.get("rating"),
            user_rating_count=data.get("userRatingCount"),
            price_level=data.get("priceLevel"),
            business_status=data.get("businessStatus"),
            national_phone_number=data.get("nationalPhoneNumber"),
            international_phone_number=data.get("internationalPhoneNumber"),
            website_uri=data.get("websiteUri"),
            google_maps_uri=data.get("googleMapsUri"),
            opening_hours=OpeningHours.from_api(hours) if hours else None,
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
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "TextSearchResult":
        return cls(
            places=[Place.from_api(p) for p in data.get("places", [])],
            next_page_token=data.get("nextPageToken"),
            raw=data,
        )


@dataclass(slots=True)
class NearbySearchResult:
    """Nearby Search results (the API returns at most one page)."""

    places: list[Place]
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "NearbySearchResult":
        return cls(places=[Place.from_api(p) for p in data.get("places", [])], raw=data)


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
