from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Optional

@dataclass(frozen=True, slots=True)
class LocalizedText:
    __match_args__: ClassVar[tuple[str, ...]] = ('text', 'language_code', 'raw')
    text: str
    language_code: Optional[str]
    raw: dict[str, Any]
    def __init__(
        self, text: str, language_code: Optional[str] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "LocalizedText": ...

@dataclass(frozen=True, slots=True)
class LatLng:
    __match_args__: ClassVar[tuple[str, ...]] = ('latitude', 'longitude', 'raw')
    latitude: float
    longitude: float
    raw: dict[str, Any]
    def __init__(self, latitude: float, longitude: float, raw: dict[str, Any] = ...) -> None: ...
    def __post_init__(self) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "LatLng": ...
    def to_api(self) -> dict[str, float]: ...

@dataclass(frozen=True, slots=True)
class AuthorAttribution:
    __match_args__: ClassVar[tuple[str, ...]] = ('display_name', 'uri', 'photo_uri', 'raw')
    display_name: str
    uri: str
    photo_uri: str
    raw: dict[str, Any]
    def __init__(
        self, display_name: str = ..., uri: str = ..., photo_uri: str = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "AuthorAttribution": ...

@dataclass(frozen=True, slots=True)
class Attribution:
    __match_args__: ClassVar[tuple[str, ...]] = ('provider', 'provider_uri', 'raw')
    provider: str
    provider_uri: str
    raw: dict[str, Any]
    def __init__(self, provider: str = ..., provider_uri: str = ..., raw: dict[str, Any] = ...) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "Attribution": ...

@dataclass(frozen=True, slots=True)
class Photo:
    __match_args__: ClassVar[tuple[str, ...]] = ('name', 'width_px', 'height_px', 'author_attributions', 'flag_content_uri', 'google_maps_uri', 'raw')
    name: str
    width_px: int
    height_px: int
    author_attributions: list[AuthorAttribution]
    flag_content_uri: Optional[str]
    google_maps_uri: Optional[str]
    raw: dict[str, Any]
    def __init__(
        self,
        name: str,
        width_px: int = ...,
        height_px: int = ...,
        author_attributions: list[AuthorAttribution] = ...,
        flag_content_uri: Optional[str] = ...,
        google_maps_uri: Optional[str] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    def __post_init__(self) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "Photo": ...

@dataclass(frozen=True, slots=True)
class Date:
    __match_args__: ClassVar[tuple[str, ...]] = ('year', 'month', 'day', 'raw')
    year: int
    month: int
    day: int
    raw: dict[str, Any]
    def __init__(
        self, year: int = ..., month: int = ..., day: int = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "Date": ...

@dataclass(frozen=True, slots=True)
class OpeningPoint:
    __match_args__: ClassVar[tuple[str, ...]] = ('date', 'truncated', 'day', 'hour', 'minute', 'raw')
    date: Optional[Date]
    truncated: Optional[bool]
    day: Optional[int]
    hour: Optional[int]
    minute: Optional[int]
    raw: dict[str, Any]
    def __init__(
        self,
        date: Optional[Date] = ...,
        truncated: Optional[bool] = ...,
        day: Optional[int] = ...,
        hour: Optional[int] = ...,
        minute: Optional[int] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "OpeningPoint": ...

@dataclass(frozen=True, slots=True)
class Period:
    __match_args__: ClassVar[tuple[str, ...]] = ('open', 'close', 'raw')
    open: Optional[OpeningPoint]
    close: Optional[OpeningPoint]
    raw: dict[str, Any]
    def __init__(
        self,
        open: Optional[OpeningPoint] = ...,
        close: Optional[OpeningPoint] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "Period": ...

@dataclass(frozen=True, slots=True)
class SpecialDay:
    __match_args__: ClassVar[tuple[str, ...]] = ('date', 'raw')
    date: Optional[Date]
    raw: dict[str, Any]
    def __init__(self, date: Optional[Date] = ..., raw: dict[str, Any] = ...) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "SpecialDay": ...

@dataclass(frozen=True, slots=True)
class OpeningHours:
    __match_args__: ClassVar[tuple[str, ...]] = ('open_now', 'periods', 'weekday_descriptions', 'next_close_time', 'next_open_time', 'special_days', 'secondary_hours_type', 'raw')
    open_now: Optional[bool]
    periods: list[Period]
    weekday_descriptions: list[str]
    next_close_time: Optional[str]
    next_open_time: Optional[str]
    special_days: list[SpecialDay]
    secondary_hours_type: Optional[str]
    raw: dict[str, Any]
    def __init__(
        self,
        open_now: Optional[bool] = ...,
        periods: list[Period] = ...,
        weekday_descriptions: list[str] = ...,
        next_close_time: Optional[str] = ...,
        next_open_time: Optional[str] = ...,
        special_days: list[SpecialDay] = ...,
        secondary_hours_type: Optional[str] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    def __post_init__(self) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "OpeningHours": ...

@dataclass(frozen=True, slots=True)
class AddressComponent:
    __match_args__: ClassVar[tuple[str, ...]] = ('long_text', 'short_text', 'types', 'language_code', 'raw')
    long_text: str
    short_text: str
    types: list[str]
    language_code: Optional[str]
    raw: dict[str, Any]
    def __init__(
        self,
        long_text: str = ...,
        short_text: str = ...,
        types: list[str] = ...,
        language_code: Optional[str] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    def __post_init__(self) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "AddressComponent": ...

@dataclass(frozen=True, slots=True)
class PlusCode:
    __match_args__: ClassVar[tuple[str, ...]] = ('global_code', 'compound_code', 'raw')
    global_code: str
    compound_code: Optional[str]
    raw: dict[str, Any]
    def __init__(
        self, global_code: str = ..., compound_code: Optional[str] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "PlusCode": ...

@dataclass(frozen=True, slots=True)
class Viewport:
    __match_args__: ClassVar[tuple[str, ...]] = ('low', 'high', 'raw')
    low: LatLng
    high: LatLng
    raw: dict[str, Any]
    def __init__(self, low: LatLng, high: LatLng, raw: dict[str, Any] = ...) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "Viewport": ...

@dataclass(frozen=True, slots=True)
class PostalAddress:
    __match_args__: ClassVar[tuple[str, ...]] = ('region_code', 'language_code', 'postal_code', 'administrative_area', 'locality', 'address_lines', 'sublocality', 'organization', 'recipients', 'raw')
    region_code: Optional[str]
    language_code: Optional[str]
    postal_code: Optional[str]
    administrative_area: Optional[str]
    locality: Optional[str]
    address_lines: list[str]
    sublocality: Optional[str]
    organization: Optional[str]
    recipients: list[str]
    raw: dict[str, Any]
    def __init__(
        self,
        region_code: Optional[str] = ...,
        language_code: Optional[str] = ...,
        postal_code: Optional[str] = ...,
        administrative_area: Optional[str] = ...,
        locality: Optional[str] = ...,
        address_lines: list[str] = ...,
        sublocality: Optional[str] = ...,
        organization: Optional[str] = ...,
        recipients: list[str] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    def __post_init__(self) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "PostalAddress": ...

@dataclass(frozen=True, slots=True)
class Review:
    __match_args__: ClassVar[tuple[str, ...]] = ('name', 'relative_publish_time_description', 'text', 'original_text', 'rating', 'author_attribution', 'publish_time', 'flag_content_uri', 'google_maps_uri', 'visit_date', 'raw')
    name: str
    relative_publish_time_description: str
    text: Optional[LocalizedText]
    original_text: Optional[LocalizedText]
    rating: Optional[float]
    author_attribution: Optional[AuthorAttribution]
    publish_time: Optional[str]
    flag_content_uri: Optional[str]
    google_maps_uri: Optional[str]
    visit_date: Optional[Date]
    raw: dict[str, Any]
    def __init__(
        self,
        name: str = ...,
        relative_publish_time_description: str = ...,
        text: Optional[LocalizedText] = ...,
        original_text: Optional[LocalizedText] = ...,
        rating: Optional[float] = ...,
        author_attribution: Optional[AuthorAttribution] = ...,
        publish_time: Optional[str] = ...,
        flag_content_uri: Optional[str] = ...,
        google_maps_uri: Optional[str] = ...,
        visit_date: Optional[Date] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "Review": ...

@dataclass(frozen=True, slots=True)
class PaymentOptions:
    __match_args__: ClassVar[tuple[str, ...]] = ('accepts_credit_cards', 'accepts_debit_cards', 'accepts_cash_only', 'accepts_nfc', 'raw')
    accepts_credit_cards: Optional[bool]
    accepts_debit_cards: Optional[bool]
    accepts_cash_only: Optional[bool]
    accepts_nfc: Optional[bool]
    raw: dict[str, Any]
    def __init__(
        self,
        accepts_credit_cards: Optional[bool] = ...,
        accepts_debit_cards: Optional[bool] = ...,
        accepts_cash_only: Optional[bool] = ...,
        accepts_nfc: Optional[bool] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "PaymentOptions": ...

@dataclass(frozen=True, slots=True)
class ParkingOptions:
    __match_args__: ClassVar[tuple[str, ...]] = ('free_parking_lot', 'paid_parking_lot', 'free_street_parking', 'paid_street_parking', 'valet_parking', 'free_garage_parking', 'paid_garage_parking', 'raw')
    free_parking_lot: Optional[bool]
    paid_parking_lot: Optional[bool]
    free_street_parking: Optional[bool]
    paid_street_parking: Optional[bool]
    valet_parking: Optional[bool]
    free_garage_parking: Optional[bool]
    paid_garage_parking: Optional[bool]
    raw: dict[str, Any]
    def __init__(
        self,
        free_parking_lot: Optional[bool] = ...,
        paid_parking_lot: Optional[bool] = ...,
        free_street_parking: Optional[bool] = ...,
        paid_street_parking: Optional[bool] = ...,
        valet_parking: Optional[bool] = ...,
        free_garage_parking: Optional[bool] = ...,
        paid_garage_parking: Optional[bool] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "ParkingOptions": ...

@dataclass(frozen=True, slots=True)
class AccessibilityOptions:
    __match_args__: ClassVar[tuple[str, ...]] = ('wheelchair_accessible_parking', 'wheelchair_accessible_entrance', 'wheelchair_accessible_restroom', 'wheelchair_accessible_seating', 'raw')
    wheelchair_accessible_parking: Optional[bool]
    wheelchair_accessible_entrance: Optional[bool]
    wheelchair_accessible_restroom: Optional[bool]
    wheelchair_accessible_seating: Optional[bool]
    raw: dict[str, Any]
    def __init__(
        self,
        wheelchair_accessible_parking: Optional[bool] = ...,
        wheelchair_accessible_entrance: Optional[bool] = ...,
        wheelchair_accessible_restroom: Optional[bool] = ...,
        wheelchair_accessible_seating: Optional[bool] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "AccessibilityOptions": ...

@dataclass(frozen=True, slots=True)
class TimeZone:
    __match_args__: ClassVar[tuple[str, ...]] = ('id', 'raw')
    id: str
    raw: dict[str, Any]
    def __init__(self, id: str = ..., raw: dict[str, Any] = ...) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "TimeZone": ...

@dataclass(frozen=True, slots=True)
class GenerativeSummary:
    __match_args__: ClassVar[tuple[str, ...]] = ('overview', 'raw')
    overview: Optional[LocalizedText]
    raw: dict[str, Any]
    def __init__(self, overview: Optional[LocalizedText] = ..., raw: dict[str, Any] = ...) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "GenerativeSummary": ...

@dataclass(frozen=True, slots=True)
class ReviewSummary:
    __match_args__: ClassVar[tuple[str, ...]] = ('text', 'raw')
    text: Optional[LocalizedText]
    raw: dict[str, Any]
    def __init__(self, text: Optional[LocalizedText] = ..., raw: dict[str, Any] = ...) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "ReviewSummary": ...

@dataclass(frozen=True, slots=True)
class ConsumerAlert:
    __match_args__: ClassVar[tuple[str, ...]] = ('overview', 'language_code', 'raw')
    overview: str
    language_code: Optional[str]
    raw: dict[str, Any]
    def __init__(
        self, overview: str = ..., language_code: Optional[str] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "ConsumerAlert": ...

@dataclass(frozen=True, slots=True)
class GoogleMapsLinks:
    __match_args__: ClassVar[tuple[str, ...]] = ('directions_uri', 'place_uri', 'write_a_review_uri', 'reviews_uri', 'photos_uri', 'raw')
    directions_uri: Optional[str]
    place_uri: Optional[str]
    write_a_review_uri: Optional[str]
    reviews_uri: Optional[str]
    photos_uri: Optional[str]
    raw: dict[str, Any]
    def __init__(
        self,
        directions_uri: Optional[str] = ...,
        place_uri: Optional[str] = ...,
        write_a_review_uri: Optional[str] = ...,
        reviews_uri: Optional[str] = ...,
        photos_uri: Optional[str] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "GoogleMapsLinks": ...

@dataclass(frozen=True, slots=True)
class Money:
    __match_args__: ClassVar[tuple[str, ...]] = ('currency_code', 'units', 'nanos', 'raw')
    currency_code: str
    units: int
    nanos: int
    raw: dict[str, Any]
    def __init__(
        self, currency_code: str = ..., units: int = ..., nanos: int = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "Money": ...

@dataclass(frozen=True, slots=True)
class PriceRange:
    __match_args__: ClassVar[tuple[str, ...]] = ('start_price', 'end_price', 'raw')
    start_price: Optional[Money]
    end_price: Optional[Money]
    raw: dict[str, Any]
    def __init__(
        self,
        start_price: Optional[Money] = ...,
        end_price: Optional[Money] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "PriceRange": ...

@dataclass(frozen=True, slots=True)
class ConnectorAggregation:
    __match_args__: ClassVar[tuple[str, ...]] = ('type', 'max_charge_rate_kw', 'count', 'available_count', 'out_of_service_count', 'availability_last_update_time', 'raw')
    type: str
    max_charge_rate_kw: Optional[float]
    count: Optional[int]
    available_count: Optional[int]
    out_of_service_count: Optional[int]
    availability_last_update_time: Optional[str]
    raw: dict[str, Any]
    def __init__(
        self,
        type: str = ...,
        max_charge_rate_kw: Optional[float] = ...,
        count: Optional[int] = ...,
        available_count: Optional[int] = ...,
        out_of_service_count: Optional[int] = ...,
        availability_last_update_time: Optional[str] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "ConnectorAggregation": ...

@dataclass(frozen=True, slots=True)
class EvChargeOptions:
    __match_args__: ClassVar[tuple[str, ...]] = ('connector_count', 'connector_aggregation', 'raw')
    connector_count: Optional[int]
    connector_aggregation: list[ConnectorAggregation]
    raw: dict[str, Any]
    def __init__(
        self,
        connector_count: Optional[int] = ...,
        connector_aggregation: list[ConnectorAggregation] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    def __post_init__(self) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "EvChargeOptions": ...

@dataclass(frozen=True, slots=True)
class Landmark:
    __match_args__: ClassVar[tuple[str, ...]] = ('name', 'place_id', 'display_name', 'types', 'spatial_relationship', 'straight_line_distance_meters', 'travel_distance_meters', 'raw')
    name: str
    place_id: str
    display_name: Optional[LocalizedText]
    types: list[str]
    spatial_relationship: Optional[str]
    straight_line_distance_meters: Optional[float]
    travel_distance_meters: Optional[float]
    raw: dict[str, Any]
    def __init__(
        self,
        name: str = ...,
        place_id: str = ...,
        display_name: Optional[LocalizedText] = ...,
        types: list[str] = ...,
        spatial_relationship: Optional[str] = ...,
        straight_line_distance_meters: Optional[float] = ...,
        travel_distance_meters: Optional[float] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    def __post_init__(self) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "Landmark": ...

@dataclass(frozen=True, slots=True)
class Area:
    __match_args__: ClassVar[tuple[str, ...]] = ('name', 'place_id', 'display_name', 'containment', 'raw')
    name: str
    place_id: str
    display_name: Optional[LocalizedText]
    containment: Optional[str]
    raw: dict[str, Any]
    def __init__(
        self,
        name: str = ...,
        place_id: str = ...,
        display_name: Optional[LocalizedText] = ...,
        containment: Optional[str] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "Area": ...

@dataclass(frozen=True, slots=True)
class AddressDescriptor:
    __match_args__: ClassVar[tuple[str, ...]] = ('landmarks', 'areas', 'raw')
    landmarks: list[Landmark]
    areas: list[Area]
    raw: dict[str, Any]
    def __init__(
        self,
        landmarks: list[Landmark] = ...,
        areas: list[Area] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    def __post_init__(self) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "AddressDescriptor": ...

@dataclass(frozen=True, slots=True)
class Place:
    __match_args__: ClassVar[tuple[str, ...]] = ('id', 'name', 'display_name', 'formatted_address', 'short_formatted_address', 'location', 'types', 'primary_type', 'rating', 'user_rating_count', 'price_level', 'business_status', 'national_phone_number', 'international_phone_number', 'website_uri', 'google_maps_uri', 'opening_hours', 'current_opening_hours', 'current_secondary_opening_hours', 'regular_secondary_opening_hours', 'address_components', 'plus_code', 'viewport', 'postal_address', 'adr_format_address', 'primary_type_display_name', 'google_maps_type_label', 'editorial_summary', 'icon_mask_base_uri', 'icon_background_color', 'opening_date', 'utc_offset_minutes', 'pure_service_area_business', 'moved_place', 'moved_place_id', 'photos', 'attributions', 'reviews', 'takeout', 'delivery', 'dine_in', 'curbside_pickup', 'reservable', 'serves_breakfast', 'serves_lunch', 'serves_dinner', 'serves_beer', 'serves_wine', 'serves_brunch', 'serves_vegetarian_food', 'outdoor_seating', 'live_music', 'menu_for_children', 'serves_cocktails', 'serves_dessert', 'serves_coffee', 'good_for_children', 'allows_dogs', 'restroom', 'good_for_groups', 'good_for_watching_sports', 'payment_options', 'parking_options', 'accessibility_options', 'time_zone', 'generative_summary', 'review_summary', 'consumer_alert', 'google_maps_links', 'price_range', 'ev_charge_options', 'address_descriptor', 'raw')
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
    current_secondary_opening_hours: list[OpeningHours]
    regular_secondary_opening_hours: list[OpeningHours]
    address_components: list[AddressComponent]
    plus_code: Optional[PlusCode]
    viewport: Optional[Viewport]
    postal_address: Optional[PostalAddress]
    adr_format_address: Optional[str]
    primary_type_display_name: Optional[LocalizedText]
    google_maps_type_label: Optional[LocalizedText]
    editorial_summary: Optional[LocalizedText]
    icon_mask_base_uri: Optional[str]
    icon_background_color: Optional[str]
    opening_date: Optional[Date]
    utc_offset_minutes: Optional[int]
    pure_service_area_business: Optional[bool]
    moved_place: Optional[str]
    moved_place_id: Optional[str]
    photos: list[Photo]
    attributions: list[Attribution]
    reviews: list[Review]
    takeout: Optional[bool]
    delivery: Optional[bool]
    dine_in: Optional[bool]
    curbside_pickup: Optional[bool]
    reservable: Optional[bool]
    serves_breakfast: Optional[bool]
    serves_lunch: Optional[bool]
    serves_dinner: Optional[bool]
    serves_beer: Optional[bool]
    serves_wine: Optional[bool]
    serves_brunch: Optional[bool]
    serves_vegetarian_food: Optional[bool]
    outdoor_seating: Optional[bool]
    live_music: Optional[bool]
    menu_for_children: Optional[bool]
    serves_cocktails: Optional[bool]
    serves_dessert: Optional[bool]
    serves_coffee: Optional[bool]
    good_for_children: Optional[bool]
    allows_dogs: Optional[bool]
    restroom: Optional[bool]
    good_for_groups: Optional[bool]
    good_for_watching_sports: Optional[bool]
    payment_options: Optional[PaymentOptions]
    parking_options: Optional[ParkingOptions]
    accessibility_options: Optional[AccessibilityOptions]
    time_zone: Optional[TimeZone]
    generative_summary: Optional[GenerativeSummary]
    review_summary: Optional[ReviewSummary]
    consumer_alert: Optional[ConsumerAlert]
    google_maps_links: Optional[GoogleMapsLinks]
    price_range: Optional[PriceRange]
    ev_charge_options: Optional[EvChargeOptions]
    address_descriptor: Optional[AddressDescriptor]
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
        current_secondary_opening_hours: list[OpeningHours] = ...,
        regular_secondary_opening_hours: list[OpeningHours] = ...,
        address_components: list[AddressComponent] = ...,
        plus_code: Optional[PlusCode] = ...,
        viewport: Optional[Viewport] = ...,
        postal_address: Optional[PostalAddress] = ...,
        adr_format_address: Optional[str] = ...,
        primary_type_display_name: Optional[LocalizedText] = ...,
        google_maps_type_label: Optional[LocalizedText] = ...,
        editorial_summary: Optional[LocalizedText] = ...,
        icon_mask_base_uri: Optional[str] = ...,
        icon_background_color: Optional[str] = ...,
        opening_date: Optional[Date] = ...,
        utc_offset_minutes: Optional[int] = ...,
        pure_service_area_business: Optional[bool] = ...,
        moved_place: Optional[str] = ...,
        moved_place_id: Optional[str] = ...,
        photos: list[Photo] = ...,
        attributions: list[Attribution] = ...,
        reviews: list[Review] = ...,
        takeout: Optional[bool] = ...,
        delivery: Optional[bool] = ...,
        dine_in: Optional[bool] = ...,
        curbside_pickup: Optional[bool] = ...,
        reservable: Optional[bool] = ...,
        serves_breakfast: Optional[bool] = ...,
        serves_lunch: Optional[bool] = ...,
        serves_dinner: Optional[bool] = ...,
        serves_beer: Optional[bool] = ...,
        serves_wine: Optional[bool] = ...,
        serves_brunch: Optional[bool] = ...,
        serves_vegetarian_food: Optional[bool] = ...,
        outdoor_seating: Optional[bool] = ...,
        live_music: Optional[bool] = ...,
        menu_for_children: Optional[bool] = ...,
        serves_cocktails: Optional[bool] = ...,
        serves_dessert: Optional[bool] = ...,
        serves_coffee: Optional[bool] = ...,
        good_for_children: Optional[bool] = ...,
        allows_dogs: Optional[bool] = ...,
        restroom: Optional[bool] = ...,
        good_for_groups: Optional[bool] = ...,
        good_for_watching_sports: Optional[bool] = ...,
        payment_options: Optional[PaymentOptions] = ...,
        parking_options: Optional[ParkingOptions] = ...,
        accessibility_options: Optional[AccessibilityOptions] = ...,
        time_zone: Optional[TimeZone] = ...,
        generative_summary: Optional[GenerativeSummary] = ...,
        review_summary: Optional[ReviewSummary] = ...,
        consumer_alert: Optional[ConsumerAlert] = ...,
        google_maps_links: Optional[GoogleMapsLinks] = ...,
        price_range: Optional[PriceRange] = ...,
        ev_charge_options: Optional[EvChargeOptions] = ...,
        address_descriptor: Optional[AddressDescriptor] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    def __post_init__(self) -> None: ...
    @property
    def display_text(self) -> Optional[str]: ...
    @property
    def regular_opening_hours(self) -> Optional[OpeningHours]: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "Place": ...

@dataclass(frozen=True, slots=True)
class Leg:
    __match_args__: ClassVar[tuple[str, ...]] = ('duration', 'distance_meters', 'raw')
    duration: str
    distance_meters: Optional[int]
    raw: dict[str, Any]
    def __init__(
        self, duration: str = ..., distance_meters: Optional[int] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "Leg": ...

@dataclass(frozen=True, slots=True)
class RoutingSummary:
    __match_args__: ClassVar[tuple[str, ...]] = ('legs', 'directions_uri', 'raw')
    legs: list[Leg]
    directions_uri: Optional[str]
    raw: dict[str, Any]
    def __init__(
        self, legs: list[Leg] = ..., directions_uri: Optional[str] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    def __post_init__(self) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "RoutingSummary": ...

@dataclass(frozen=True, slots=True)
class TextSearchResult:
    __match_args__: ClassVar[tuple[str, ...]] = ('places', 'next_page_token', 'search_uri', 'routing_summaries', 'raw')
    places: list[Place]
    next_page_token: Optional[str]
    search_uri: Optional[str]
    routing_summaries: list[RoutingSummary]
    raw: dict[str, Any]
    def __init__(
        self,
        places: list[Place],
        next_page_token: Optional[str] = ...,
        search_uri: Optional[str] = ...,
        routing_summaries: list[RoutingSummary] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    def __post_init__(self) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "TextSearchResult": ...

@dataclass(frozen=True, slots=True)
class NearbySearchResult:
    __match_args__: ClassVar[tuple[str, ...]] = ('places', 'routing_summaries', 'raw')
    places: list[Place]
    routing_summaries: list[RoutingSummary]
    raw: dict[str, Any]
    def __init__(
        self,
        places: list[Place],
        routing_summaries: list[RoutingSummary] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    def __post_init__(self) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "NearbySearchResult": ...

@dataclass(frozen=True, slots=True)
class StringMatch:
    __match_args__: ClassVar[tuple[str, ...]] = ('start_offset', 'end_offset', 'raw')
    start_offset: Optional[int]
    end_offset: Optional[int]
    raw: dict[str, Any]
    def __init__(self, start_offset: Optional[int] = ..., end_offset: Optional[int] = ..., raw: dict[str, Any] = ...) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "StringMatch": ...

@dataclass(frozen=True, slots=True)
class FormattedText:
    __match_args__: ClassVar[tuple[str, ...]] = ('text', 'matches', 'raw')
    text: str
    matches: list[StringMatch]
    raw: dict[str, Any]
    def __init__(
        self, text: str = ..., matches: list[StringMatch] = ...,
        raw: dict[str, Any] = ...,
    ) -> None: ...
    def __post_init__(self) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "FormattedText": ...

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
    def __post_init__(self) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "PlacePrediction": ...

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
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "QueryPrediction": ...

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
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "Suggestion": ...

@dataclass(frozen=True, slots=True)
class AutocompleteResult:
    __match_args__: ClassVar[tuple[str, ...]] = ('suggestions', 'raw')
    suggestions: list[Suggestion]
    raw: dict[str, Any]
    def __init__(
        self, suggestions: list[Suggestion], raw: dict[str, Any] = ...
    ) -> None: ...
    def __post_init__(self) -> None: ...
    @property
    def place_predictions(self) -> list[PlacePrediction]: ...
    @property
    def query_predictions(self) -> list[QueryPrediction]: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "AutocompleteResult": ...

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
    __match_args__: ClassVar[tuple[str, ...]] = ('photo_uri', 'name', 'raw')
    photo_uri: str
    name: str
    raw: dict[str, Any]
    def __init__(
        self, photo_uri: str, name: str = ..., raw: dict[str, Any] = ...
    ) -> None: ...
    @classmethod
    def from_api(cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = ...) -> "PhotoUriResult": ...
