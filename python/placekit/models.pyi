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
    flag_content_uri: Optional[str]
    google_maps_uri: Optional[str]
    def __init__(
        self,
        name: str,
        width_px: int = ...,
        height_px: int = ...,
        author_attributions: list[AuthorAttribution] = ...,
        flag_content_uri: Optional[str] = ...,
        google_maps_uri: Optional[str] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Photo": ...

class Date:
    year: int
    month: int
    day: int
    def __init__(
        self, year: int = ..., month: int = ..., day: int = ...
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Date": ...

class OpeningPoint:
    date: Optional[Date]
    truncated: Optional[bool]
    day: Optional[int]
    hour: Optional[int]
    minute: Optional[int]
    def __init__(
        self,
        date: Optional[Date] = ...,
        truncated: Optional[bool] = ...,
        day: Optional[int] = ...,
        hour: Optional[int] = ...,
        minute: Optional[int] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "OpeningPoint": ...

class Period:
    open: Optional[OpeningPoint]
    close: Optional[OpeningPoint]
    def __init__(
        self,
        open: Optional[OpeningPoint] = ...,
        close: Optional[OpeningPoint] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Period": ...

class OpeningHours:
    open_now: Optional[bool]
    periods: list[Period]
    weekday_descriptions: list[str]
    def __init__(
        self,
        open_now: Optional[bool] = ...,
        periods: list[Period] = ...,
        weekday_descriptions: list[str] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "OpeningHours": ...

class AddressComponent:
    long_text: str
    short_text: str
    types: list[str]
    language_code: Optional[str]
    def __init__(
        self,
        long_text: str = ...,
        short_text: str = ...,
        types: list[str] = ...,
        language_code: Optional[str] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "AddressComponent": ...

class PlusCode:
    global_code: str
    compound_code: Optional[str]
    def __init__(
        self, global_code: str = ..., compound_code: Optional[str] = ...
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "PlusCode": ...

class Viewport:
    low: LatLng
    high: LatLng
    def __init__(self, low: LatLng, high: LatLng) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Viewport": ...

class PostalAddress:
    region_code: Optional[str]
    language_code: Optional[str]
    postal_code: Optional[str]
    administrative_area: Optional[str]
    locality: Optional[str]
    address_lines: list[str]
    def __init__(
        self,
        region_code: Optional[str] = ...,
        language_code: Optional[str] = ...,
        postal_code: Optional[str] = ...,
        administrative_area: Optional[str] = ...,
        locality: Optional[str] = ...,
        address_lines: list[str] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "PostalAddress": ...

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
    current_opening_hours: Optional[OpeningHours]
    address_components: list[AddressComponent]
    plus_code: Optional[PlusCode]
    viewport: Optional[Viewport]
    postal_address: Optional[PostalAddress]
    adr_format_address: Optional[str]
    primary_type_display_name: Optional[LocalizedText]
    photos: list[Photo]
    attributions: list[Attribution]
    raw: dict[str, Any]
    def __init__(
        self,
        id: str,
        name: str = ...,
        display_name: Optional[LocalizedText] = ...,
        formatted_address: Optional[str] = ...,
        short_formatted_address: Optional[str] = ...,
        location: Optional[LatLng] = ...,
        types: list[str] = ...,
        primary_type: Optional[str] = ...,
        rating: Optional[float] = ...,
        user_rating_count: Optional[int] = ...,
        price_level: Optional[str] = ...,
        business_status: Optional[str] = ...,
        national_phone_number: Optional[str] = ...,
        international_phone_number: Optional[str] = ...,
        website_uri: Optional[str] = ...,
        google_maps_uri: Optional[str] = ...,
        opening_hours: Optional[OpeningHours] = ...,
        current_opening_hours: Optional[OpeningHours] = ...,
        address_components: list[AddressComponent] = ...,
        plus_code: Optional[PlusCode] = ...,
        viewport: Optional[Viewport] = ...,
        postal_address: Optional[PostalAddress] = ...,
        adr_format_address: Optional[str] = ...,
        primary_type_display_name: Optional[LocalizedText] = ...,
        photos: list[Photo] = ...,
        attributions: list[Attribution] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @property
    def display_text(self) -> Optional[str]: ...
    @property
    def regular_opening_hours(self) -> Optional[OpeningHours]: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Place": ...

class TextSearchResult:
    places: list[Place]
    next_page_token: Optional[str]
    search_uri: Optional[str]
    routing_summaries: list[dict[str, Any]]
    raw: dict[str, Any]
    def __init__(
        self,
        places: list[Place],
        next_page_token: Optional[str] = ...,
        search_uri: Optional[str] = ...,
        routing_summaries: list[dict[str, Any]] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "TextSearchResult": ...

class NearbySearchResult:
    places: list[Place]
    routing_summaries: list[dict[str, Any]]
    raw: dict[str, Any]
    def __init__(
        self,
        places: list[Place],
        routing_summaries: list[dict[str, Any]] = ...,
        raw: dict[str, Any] = ...,
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
    place: str
    text: Optional[FormattedText]
    main_text: Optional[FormattedText]
    secondary_text: Optional[FormattedText]
    types: list[str]
    distance_meters: Optional[int]
    raw: dict[str, Any]
    def __init__(
        self,
        place_id: str,
        place: str = ...,
        text: Optional[FormattedText] = ...,
        main_text: Optional[FormattedText] = ...,
        secondary_text: Optional[FormattedText] = ...,
        types: list[str] = ...,
        distance_meters: Optional[int] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "PlacePrediction": ...

class QueryPrediction:
    text: Optional[FormattedText]
    main_text: Optional[FormattedText]
    secondary_text: Optional[FormattedText]
    raw: dict[str, Any]
    def __init__(
        self,
        text: Optional[FormattedText] = ...,
        main_text: Optional[FormattedText] = ...,
        secondary_text: Optional[FormattedText] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "QueryPrediction": ...

class Suggestion:
    place_prediction: Optional[PlacePrediction]
    query_prediction: Optional[QueryPrediction]
    raw: dict[str, Any]
    def __init__(
        self,
        place_prediction: Optional[PlacePrediction] = ...,
        query_prediction: Optional[QueryPrediction] = ...,
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
    @property
    def query_predictions(self) -> list[QueryPrediction]: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "AutocompleteResult": ...

class PhotoMedia:
    content: bytes
    content_type: Optional[str]
    def __init__(
        self, content: bytes, content_type: Optional[str] = ...
    ) -> None: ...
    def save(self, path: str | Path) -> Path: ...

class PhotoUriResult:
    photo_uri: str
    name: str
    def __init__(self, photo_uri: str, name: str = ...) -> None: ...
