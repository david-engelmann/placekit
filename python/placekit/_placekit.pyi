"""Type stubs for the compiled Rust extension module.

End users do not call this module directly; ``placekit.client`` wraps it.
The request body arguments are the camelCase JSON bodies of the Places API,
deserialized into typed Rust structs on the other side.
"""

from typing import Any, Optional

__version__: str

class PlacesError(Exception):
    kind: str
    status_code: Optional[int]
    google_status: Optional[str]
    error_code: Optional[int]
    details: list[Any]
    field_violations: list[dict[str, Any]]
    quota_violations: list[dict[str, Any]]

class Client:
    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = ...,
        timeout: Optional[float] = ...,
    ) -> None: ...
    def text_search(
        self, body: dict[str, Any], fields: Optional[list[str]]
    ) -> dict[str, Any]: ...
    def text_search_async(
        self, body: dict[str, Any], fields: Optional[list[str]]
    ) -> Any: ...
    def nearby_search(
        self, body: dict[str, Any], fields: Optional[list[str]]
    ) -> dict[str, Any]: ...
    def nearby_search_async(
        self, body: dict[str, Any], fields: Optional[list[str]]
    ) -> Any: ...
    def place_details(
        self,
        place_id: str,
        fields: Optional[list[str]] = ...,
        language_code: Optional[str] = ...,
        region_code: Optional[str] = ...,
        session_token: Optional[str] = ...,
    ) -> dict[str, Any]: ...
    def place_details_async(
        self,
        place_id: str,
        fields: Optional[list[str]] = ...,
        language_code: Optional[str] = ...,
        region_code: Optional[str] = ...,
        session_token: Optional[str] = ...,
    ) -> Any: ...
    def autocomplete(
        self, body: dict[str, Any], fields: Optional[list[str]]
    ) -> dict[str, Any]: ...
    def autocomplete_async(
        self, body: dict[str, Any], fields: Optional[list[str]]
    ) -> Any: ...
    def place_photo(
        self,
        photo_name: str,
        max_width_px: Optional[int] = ...,
        max_height_px: Optional[int] = ...,
        skip_http_redirect: bool = ...,
    ) -> tuple[str, Any, Any]: ...
    def place_photo_async(
        self,
        photo_name: str,
        max_width_px: Optional[int] = ...,
        max_height_px: Optional[int] = ...,
        skip_http_redirect: bool = ...,
    ) -> Any: ...
