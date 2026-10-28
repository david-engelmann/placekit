from typing import Any, Iterable, Optional

from .fields import FieldsLike
from .models import (
    AutocompleteResult,
    LatLng,
    NearbySearchResult,
    PhotoMedia,
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
        language: Optional[str] = ...,
        region: Optional[str] = ...,
        session_token: Optional[str] = ...,
        included_region_codes: Optional[Iterable[str]] = ...,
        include_query_predictions: Optional[bool] = ...,
        location_bias: Optional[dict[str, Any]] = ...,
        location_restriction: Optional[dict[str, Any]] = ...,
    ) -> AutocompleteResult: ...
    def place_photo(
        self,
        photo_name: str,
        *,
        max_width_px: Optional[int] = ...,
        max_height_px: Optional[int] = ...,
    ) -> PhotoMedia: ...

class AsyncClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: Optional[str] = ...,
        timeout: Optional[float] = ...,
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
        language: Optional[str] = ...,
        region: Optional[str] = ...,
        session_token: Optional[str] = ...,
        included_region_codes: Optional[Iterable[str]] = ...,
        include_query_predictions: Optional[bool] = ...,
        location_bias: Optional[dict[str, Any]] = ...,
        location_restriction: Optional[dict[str, Any]] = ...,
    ) -> AutocompleteResult: ...
    async def place_photo(
        self,
        photo_name: str,
        *,
        max_width_px: Optional[int] = ...,
        max_height_px: Optional[int] = ...,
    ) -> PhotoMedia: ...
