from pathlib import Path
from typing import Any, Optional

class LocalizedText:
    text: str
    language_code: Optional[str]
    def __init__(
        self, text: str, language_code: Optional[str] = ...
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "LocalizedText": ...

class LatLng:
    latitude: float
    longitude: float
    def __init__(self, latitude: float, longitude: float) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "LatLng": ...
    def to_api(self) -> dict[str, float]: ...

class AuthorAttribution:
    display_name: str
    uri: str
    photo_uri: str
    def __init__(
        self, display_name: str = ..., uri: str = ..., photo_uri: str = ...
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "AuthorAttribution": ...

class Attribution:
    provider: str
    provider_uri: str
    def __init__(self, provider: str = ..., provider_uri: str = ...) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Attribution": ...

class Photo:
    name: str
    width_px: int
    height_px: int
    author_attributions: list[AuthorAttribution]
    def __init__(
        self,
        name: str,
        width_px: int = ...,
        height_px: int = ...,
        author_attributions: list[AuthorAttribution] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Photo": ...

class OpeningHours:
    open_now: Optional[bool]
    weekday_descriptions: list[str]
    def __init__(
        self,
        open_now: Optional[bool] = ...,
        weekday_descriptions: list[str] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "OpeningHours": ...

class Place:
    id: str
    name: str
    display_name: Optional[LocalizedText]
    formatted_address: Optional[str]
    short_formatted_address: Optional[str]
    location: Optional[LatLng]
    types: list[str]
    primary_type: Optional[str]
    rating: Optional[float]
    user_rating_count: Optional[int]
    price_level: Optional[str]
    business_status: Optional[str]
    national_phone_number: Optional[str]
    international_phone_number: Optional[str]
    website_uri: Optional[str]
    google_maps_uri: Optional[str]
    opening_hours: Optional[OpeningHours]
    photos: list[Photo]
    attributions: list[Attribution]
    raw: dict[str, Any]
    @property
    def display_text(self) -> Optional[str]: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Place": ...

class TextSearchResult:
    places: list[Place]
    next_page_token: Optional[str]
    raw: dict[str, Any]
    def __init__(
        self,
        places: list[Place],
        next_page_token: Optional[str] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "TextSearchResult": ...

class NearbySearchResult:
    places: list[Place]
    raw: dict[str, Any]
    def __init__(
        self, places: list[Place], raw: dict[str, Any] = ...
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "NearbySearchResult": ...

class StringMatch:
    start_offset: int
    end_offset: int
    def __init__(self, start_offset: int = ..., end_offset: int = ...) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "StringMatch": ...

class FormattedText:
    text: str
    matches: list[StringMatch]
    def __init__(
        self, text: str = ..., matches: list[StringMatch] = ...
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "FormattedText": ...

class PlacePrediction:
    place_id: str
    text: Optional[FormattedText]
    main_text: Optional[FormattedText]
    secondary_text: Optional[FormattedText]
    types: list[str]
    distance_meters: Optional[int]
    raw: dict[str, Any]
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "PlacePrediction": ...

class Suggestion:
    place_prediction: Optional[PlacePrediction]
    raw: dict[str, Any]
    def __init__(
        self,
        place_prediction: Optional[PlacePrediction] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Suggestion": ...

class AutocompleteResult:
    suggestions: list[Suggestion]
    raw: dict[str, Any]
    def __init__(
        self, suggestions: list[Suggestion], raw: dict[str, Any] = ...
    ) -> None: ...
    @property
    def place_predictions(self) -> list[PlacePrediction]: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "AutocompleteResult": ...

class PhotoMedia:
    content: bytes
    content_type: Optional[str]
    def __init__(
        self, content: bytes, content_type: Optional[str] = ...
    ) -> None: ...
    def save(self, path: str | Path) -> Path: ...
