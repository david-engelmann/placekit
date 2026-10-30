from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Optional

@dataclass(frozen=True, slots=True)
class LocalizedText:
    __match_args__: ClassVar[tuple[str, ...]] = ('text', 'language_code')
    text: str
    language_code: Optional[str]
    def __init__(
        self, text: str, language_code: Optional[str] = ...
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "LocalizedText": ...

@dataclass(frozen=True, slots=True)
class LatLng:
    __match_args__: ClassVar[tuple[str, ...]] = ('latitude', 'longitude')
    latitude: float
    longitude: float
    def __init__(self, latitude: float, longitude: float) -> None: ...
    def __post_init__(self) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "LatLng": ...
    def to_api(self) -> dict[str, float]: ...

@dataclass(frozen=True, slots=True)
class AuthorAttribution:
    __match_args__: ClassVar[tuple[str, ...]] = ('display_name', 'uri', 'photo_uri')
    display_name: str
    uri: str
    photo_uri: str
    def __init__(
        self, display_name: str = ..., uri: str = ..., photo_uri: str = ...
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "AuthorAttribution": ...

@dataclass(frozen=True, slots=True)
class Attribution:
    __match_args__: ClassVar[tuple[str, ...]] = ('provider', 'provider_uri')
    provider: str
    provider_uri: str
    def __init__(self, provider: str = ..., provider_uri: str = ...) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Attribution": ...

@dataclass(frozen=True, slots=True)
class Photo:
    __match_args__: ClassVar[tuple[str, ...]] = ('name', 'width_px', 'height_px', 'author_attributions', 'flag_content_uri', 'google_maps_uri')
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

@dataclass(frozen=True, slots=True)
class Date:
    __match_args__: ClassVar[tuple[str, ...]] = ('year', 'month', 'day')
    year: int
    month: int
    day: int
    def __init__(
        self, year: int = ..., month: int = ..., day: int = ...
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Date": ...

@dataclass(frozen=True, slots=True)
class OpeningPoint:
    __match_args__: ClassVar[tuple[str, ...]] = ('date', 'truncated', 'day', 'hour', 'minute')
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

@dataclass(frozen=True, slots=True)
class Period:
    __match_args__: ClassVar[tuple[str, ...]] = ('open', 'close')
    open: Optional[OpeningPoint]
    close: Optional[OpeningPoint]
    def __init__(
        self,
        open: Optional[OpeningPoint] = ...,
        close: Optional[OpeningPoint] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Period": ...

@dataclass(frozen=True, slots=True)
class OpeningHours:
    __match_args__: ClassVar[tuple[str, ...]] = ('open_now', 'periods', 'weekday_descriptions')
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

@dataclass(frozen=True, slots=True)
class AddressComponent:
    __match_args__: ClassVar[tuple[str, ...]] = ('long_text', 'short_text', 'types', 'language_code')
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

@dataclass(frozen=True, slots=True)
class PlusCode:
    __match_args__: ClassVar[tuple[str, ...]] = ('global_code', 'compound_code')
    global_code: str
    compound_code: Optional[str]
    def __init__(
        self, global_code: str = ..., compound_code: Optional[str] = ...
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "PlusCode": ...

@dataclass(frozen=True, slots=True)
class Viewport:
    __match_args__: ClassVar[tuple[str, ...]] = ('low', 'high')
    low: LatLng
    high: LatLng
    def __init__(self, low: LatLng, high: LatLng) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Viewport": ...

@dataclass(frozen=True, slots=True)
class PostalAddress:
    __match_args__: ClassVar[tuple[str, ...]] = ('region_code', 'language_code', 'postal_code', 'administrative_area', 'locality', 'address_lines')
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

@dataclass(frozen=True, slots=True)
class Place:
    __match_args__: ClassVar[tuple[str, ...]] = ('id', 'name', 'display_name', 'formatted_address', 'short_formatted_address', 'location', 'types', 'primary_type', 'rating', 'user_rating_count', 'price_level', 'business_status', 'national_phone_number', 'international_phone_number', 'website_uri', 'google_maps_uri', 'opening_hours', 'current_opening_hours', 'address_components', 'plus_code', 'viewport', 'postal_address', 'adr_format_address', 'primary_type_display_name', 'photos', 'attributions', 'raw')
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

@dataclass(frozen=True, slots=True)
class TextSearchResult:
    __match_args__: ClassVar[tuple[str, ...]] = ('places', 'next_page_token', 'search_uri', 'routing_summaries', 'raw')
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

@dataclass(frozen=True, slots=True)
class NearbySearchResult:
    __match_args__: ClassVar[tuple[str, ...]] = ('places', 'routing_summaries', 'raw')
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

@dataclass(frozen=True, slots=True)
class StringMatch:
    __match_args__: ClassVar[tuple[str, ...]] = ('start_offset', 'end_offset')
    start_offset: int
    end_offset: int
    def __init__(self, start_offset: int = ..., end_offset: int = ...) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "StringMatch": ...

@dataclass(frozen=True, slots=True)
class FormattedText:
    __match_args__: ClassVar[tuple[str, ...]] = ('text', 'matches')
    text: str
    matches: list[StringMatch]
    def __init__(
        self, text: str = ..., matches: list[StringMatch] = ...
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "FormattedText": ...

@dataclass(frozen=True, slots=True)
class PlacePrediction:
    __match_args__: ClassVar[tuple[str, ...]] = ('place_id', 'place', 'text', 'main_text', 'secondary_text', 'types', 'distance_meters', 'raw')
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

@dataclass(frozen=True, slots=True)
class QueryPrediction:
    __match_args__: ClassVar[tuple[str, ...]] = ('text', 'main_text', 'secondary_text', 'raw')
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

@dataclass(frozen=True, slots=True)
class Suggestion:
    __match_args__: ClassVar[tuple[str, ...]] = ('place_prediction', 'query_prediction', 'raw')
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

@dataclass(frozen=True, slots=True)
class AutocompleteResult:
    __match_args__: ClassVar[tuple[str, ...]] = ('suggestions', 'raw')
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

@dataclass(frozen=True, slots=True)
class PhotoMedia:
    __match_args__: ClassVar[tuple[str, ...]] = ('content', 'content_type')
    content: bytes
    content_type: Optional[str]
    def __init__(
        self, content: bytes, content_type: Optional[str] = ...
    ) -> None: ...
    def save(self, path: str | Path) -> Path: ...

@dataclass(frozen=True, slots=True)
class PhotoUriResult:
    __match_args__: ClassVar[tuple[str, ...]] = ('photo_uri', 'name')
    photo_uri: str
    name: str
    def __init__(self, photo_uri: str, name: str = ...) -> None: ...
