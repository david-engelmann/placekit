"""Type stubs for the compiled Rust extension module.

End users do not call this module directly; ``placekit.client`` wraps it.
The request body arguments are the camelCase JSON bodies of the Places API,
deserialized into typed Rust structs on the other side.
"""

from typing import Any, Optional, final

__version__: str
__all__ = ["CallHandle", "Client", "PlacesError", "__version__"]

@final
class CallHandle:
    """Handle to one in flight async call (Round 30).

    The call runs on the process runtime and completes into Rust
    state only. The Python layer polls ``is_done`` from its event
    loop thread and collects a finished call with ``take_result``,
    which builds the same result tuple the sync methods return or
    raises the call's ``PlacesError``.
    """

    def is_done(self) -> bool: ...
    def take_result(self) -> Any: ...
    def abort(self) -> None: ...

class PlacesError(Exception):
    kind: str
    status_code: Optional[int]
    google_status: Optional[str]
    error_code: Optional[int]
    details: list[Any]
    field_violations: list[Any]
    quota_violations: list[dict[str, Any]]
    status_mismatch: bool
    retryable: bool
    retry_after: Optional[float]

@final
class Client:
    def __new__(
        cls,
        api_key: str,
        base_url: Optional[str] = ...,
        timeout: Optional[float] = ...,
    ) -> "Client": ...
    def text_search(
        self, body: dict[str, Any], fields: Optional[list[str]] = ...
    ) -> tuple[dict[str, Any], str, int]: ...
    def text_search_async(
        self, body: dict[str, Any], fields: Optional[list[str]] = ...
    ) -> CallHandle: ...
    def nearby_search(
        self, body: dict[str, Any], fields: Optional[list[str]] = ...
    ) -> tuple[dict[str, Any], str, int]: ...
    def nearby_search_async(
        self, body: dict[str, Any], fields: Optional[list[str]] = ...
    ) -> CallHandle: ...
    def place_details(
        self,
        place_id: str,
        fields: Optional[list[str]] = ...,
        language_code: Optional[str] = ...,
        region_code: Optional[str] = ...,
        session_token: Optional[str] = ...,
    ) -> tuple[dict[str, Any], str, int]: ...
    def place_details_async(
        self,
        place_id: str,
        fields: Optional[list[str]] = ...,
        language_code: Optional[str] = ...,
        region_code: Optional[str] = ...,
        session_token: Optional[str] = ...,
    ) -> CallHandle: ...
    def autocomplete(
        self, body: dict[str, Any], fields: Optional[list[str]] = ...
    ) -> tuple[dict[str, Any], str, int]: ...
    def autocomplete_async(
        self, body: dict[str, Any], fields: Optional[list[str]] = ...
    ) -> CallHandle: ...
    def place_photo(
        self,
        photo_name: str,
        max_width_px: Optional[int] = ...,
        max_height_px: Optional[int] = ...,
        skip_http_redirect: bool = ...,
    ) -> tuple[str, Any, Any, int]: ...
    def place_photo_async(
        self,
        photo_name: str,
        max_width_px: Optional[int] = ...,
        max_height_px: Optional[int] = ...,
        skip_http_redirect: bool = ...,
    ) -> CallHandle: ...
