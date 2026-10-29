from types import TracebackType
from typing import Any, Iterable, Optional

from .fields import FieldsLike
from .models import (
    AutocompleteResult,
    LatLng,
    NearbySearchResult,
    PhotoMedia,
    PhotoUriResult,
    Place,
    TextSearchResult,
)

class Client:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: Optional[str] = ...,
        timeout: Optional[float] = ...,
    ) -> None: ...
    def close(self) -> None: ...
    def __enter__(self) -> "Client": ...
    def __exit__(
        self,
        exc_type: Optional[type[BaseException]] = ...,
        exc_value: Optional[BaseException] = ...,
        traceback: Optional[TracebackType] = ...,
    ) -> None: ...
    def text_search(
        self,
        query: str,
        *,
        fields: FieldsLike = ...,
        max_results: Optional[int] = ...,
        page_token: Optional[str] = ...,
        language: Optional[str] = ...,
        region: Optional[str] = ...,
        rank_preference: Optional[str] = ...,
        open_now: Optional[bool] = ...,
        price_levels: Optional[Iterable[str]] = ...,
        strict_type_filtering: Optional[bool] = ...,
        included_type: Optional[str] = ...,
        location_bias: Optional[dict[str, Any]] = ...,
        location_restriction: Optional[dict[str, Any]] = ...,
        page_size: Optional[int] = ...,
        min_rating: Optional[float] = ...,
        ev_options: Optional[dict[str, Any]] = ...,
        search_along_route: Optional[dict[str, Any]] = ...,
        routing_parameters: Optional[dict[str, Any]] = ...,
        include_pure_service_area_businesses: Optional[bool] = ...,
        include_future_opening_businesses: Optional[bool] = ...,
    ) -> TextSearchResult: ...
    def nearby_search(
        self,
        location: LatLng | tuple[float, float],
        radius_m: float,
        *,
        fields: FieldsLike = ...,
        included_types: Optional[Iterable[str]] = ...,
        excluded_types: Optional[Iterable[str]] = ...,
        max_results: Optional[int] = ...,
        language: Optional[str] = ...,
        region: Optional[str] = ...,
        rank_preference: Optional[str] = ...,
        included_primary_types: Optional[Iterable[str]] = ...,
        excluded_primary_types: Optional[Iterable[str]] = ...,
        routing_parameters: Optional[dict[str, Any]] = ...,
        include_future_opening_businesses: Optional[bool] = ...,
    ) -> NearbySearchResult: ...
    def place_details(
        self,
        place_id: str,
        *,
        fields: FieldsLike = ...,
        language: Optional[str] = ...,
        region: Optional[str] = ...,
        session_token: Optional[str] = ...,
    ) -> Place: ...
    def autocomplete(
        self,
        input_text: str,
        *,
        fields: FieldsLike = ...,
        language: Optional[str] = ...,
        region: Optional[str] = ...,
        session_token: Optional[str] = ...,
        included_region_codes: Optional[Iterable[str]] = ...,
        include_query_predictions: Optional[bool] = ...,
        location_bias: Optional[dict[str, Any]] = ...,
        location_restriction: Optional[dict[str, Any]] = ...,
        origin: Optional[LatLng | tuple[float, float]] = ...,
        input_offset: Optional[int] = ...,
        included_primary_types: Optional[Iterable[str]] = ...,
        include_pure_service_area_businesses: Optional[bool] = ...,
        include_future_opening_businesses: Optional[bool] = ...,
    ) -> AutocompleteResult: ...
    def place_photo(
        self,
        photo_name: str,
        *,
        max_width_px: Optional[int] = ...,
        max_height_px: Optional[int] = ...,
        skip_http_redirect: bool = ...,
    ) -> PhotoMedia | PhotoUriResult: ...

class AsyncClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: Optional[str] = ...,
        timeout: Optional[float] = ...,
    ) -> None: ...
    def close(self) -> None: ...
    async def __aenter__(self) -> "AsyncClient": ...
    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]] = ...,
        exc_value: Optional[BaseException] = ...,
        traceback: Optional[TracebackType] = ...,
    ) -> None: ...
    async def text_search(
        self,
        query: str,
        *,
        fields: FieldsLike = ...,
        max_results: Optional[int] = ...,
        page_token: Optional[str] = ...,
        language: Optional[str] = ...,
        region: Optional[str] = ...,
        rank_preference: Optional[str] = ...,
        open_now: Optional[bool] = ...,
        price_levels: Optional[Iterable[str]] = ...,
        strict_type_filtering: Optional[bool] = ...,
        included_type: Optional[str] = ...,
        location_bias: Optional[dict[str, Any]] = ...,
        location_restriction: Optional[dict[str, Any]] = ...,
        page_size: Optional[int] = ...,
        min_rating: Optional[float] = ...,
        ev_options: Optional[dict[str, Any]] = ...,
        search_along_route: Optional[dict[str, Any]] = ...,
        routing_parameters: Optional[dict[str, Any]] = ...,
        include_pure_service_area_businesses: Optional[bool] = ...,
        include_future_opening_businesses: Optional[bool] = ...,
    ) -> TextSearchResult: ...
    async def nearby_search(
        self,
        location: LatLng | tuple[float, float],
        radius_m: float,
        *,
        fields: FieldsLike = ...,
        included_types: Optional[Iterable[str]] = ...,
        excluded_types: Optional[Iterable[str]] = ...,
        max_results: Optional[int] = ...,
        language: Optional[str] = ...,
        region: Optional[str] = ...,
        rank_preference: Optional[str] = ...,
        included_primary_types: Optional[Iterable[str]] = ...,
        excluded_primary_types: Optional[Iterable[str]] = ...,
        routing_parameters: Optional[dict[str, Any]] = ...,
        include_future_opening_businesses: Optional[bool] = ...,
    ) -> NearbySearchResult: ...
    async def place_details(
        self,
        place_id: str,
        *,
        fields: FieldsLike = ...,
        language: Optional[str] = ...,
        region: Optional[str] = ...,
        session_token: Optional[str] = ...,
    ) -> Place: ...
    async def autocomplete(
        self,
        input_text: str,
        *,
        fields: FieldsLike = ...,
        language: Optional[str] = ...,
        region: Optional[str] = ...,
        session_token: Optional[str] = ...,
        included_region_codes: Optional[Iterable[str]] = ...,
        include_query_predictions: Optional[bool] = ...,
        location_bias: Optional[dict[str, Any]] = ...,
        location_restriction: Optional[dict[str, Any]] = ...,
        origin: Optional[LatLng | tuple[float, float]] = ...,
        input_offset: Optional[int] = ...,
        included_primary_types: Optional[Iterable[str]] = ...,
        include_pure_service_area_businesses: Optional[bool] = ...,
        include_future_opening_businesses: Optional[bool] = ...,
    ) -> AutocompleteResult: ...
    async def place_photo(
        self,
        photo_name: str,
        *,
        max_width_px: Optional[int] = ...,
        max_height_px: Optional[int] = ...,
        skip_http_redirect: bool = ...,
    ) -> PhotoMedia | PhotoUriResult: ...
