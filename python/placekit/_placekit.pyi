"""Type stubs for the compiled Rust extension module.

End users do not call this module directly; ``placekit.client`` wraps it.
The request body arguments are the camelCase JSON bodies of the Places API,
deserialized into typed Rust structs on the other side.
"""

from typing import Any, Optional, Sequence, final

__version__: str
__all__ = [
    "CallHandle",
    "Client",
    "PlacesError",
    "__version__",
    "address_city_resolutions",
    "address_component_flags",
    "address_country_code",
    "address_district_resolution",
    "address_first_long_text",
    "address_first_long_text_index",
    "address_first_short_text",
    "address_long_texts",
    "address_matching_indices",
    "address_postal_code_result",
    "address_short_texts",
    "address_split_compound_code",
    "address_untyped_indices",
    "mask_sorted_order",
    "mask_unique_indices",
    "mask_valid_path",
]

def address_matching_indices(
    components: list[tuple[Optional[bytes], Optional[bytes], Sequence[Optional[bytes]]]],
    type_name: bytes,
) -> list[int]: ...
def address_untyped_indices(
    components: list[tuple[Optional[bytes], Optional[bytes], Sequence[Optional[bytes]]]]
) -> list[int]: ...
def address_first_long_text(
    components: list[tuple[Optional[bytes], Optional[bytes], Sequence[Optional[bytes]]]],
    type_name: bytes,
) -> Optional[bytes]: ...
def address_first_long_text_index(
    components: list[tuple[Optional[bytes], Optional[bytes], Sequence[Optional[bytes]]]],
    type_name: bytes,
) -> Optional[int]: ...
def address_first_short_text(
    components: list[tuple[Optional[bytes], Optional[bytes], Sequence[Optional[bytes]]]],
    type_name: bytes,
) -> Optional[bytes]: ...
def address_long_texts(
    components: list[tuple[Optional[bytes], Optional[bytes], Sequence[Optional[bytes]]]],
    type_name: bytes,
) -> list[bytes]: ...
def address_short_texts(
    components: list[tuple[Optional[bytes], Optional[bytes], Sequence[Optional[bytes]]]],
    type_name: bytes,
) -> list[bytes]: ...
def address_country_code(
    components: list[tuple[Optional[bytes], Optional[bytes], Sequence[Optional[bytes]]]]
) -> Optional[bytes]: ...
def address_city_resolutions(
    components: list[tuple[Optional[bytes], Optional[bytes], Sequence[Optional[bytes]]]],
    postal_locality_read: bool,
    country_code: Optional[bytes],
    postal_locality: Optional[bytes],
) -> tuple[
    bool,
    list[
        tuple[
            Optional[bytes], Optional[str], str, Optional[bytes], Optional[bytes], Optional[str]
        ]
    ],
]: ...
def address_district_resolution(
    components: list[tuple[Optional[bytes], Optional[bytes], Sequence[Optional[bytes]]]],
    country_code: Optional[bytes],
) -> tuple[Optional[bytes], Optional[str], str, Optional[bytes]]: ...
def address_postal_code_result(
    country_code: Optional[bytes],
    component_value: Optional[bytes],
    postal_value: Optional[bytes],
) -> tuple[
    Optional[bytes], Optional[str], str, Optional[bytes], Optional[bytes], Optional[str]
]: ...
def address_component_flags(
    components: list[tuple[Optional[bytes], Optional[bytes], Sequence[Optional[bytes]]]]
) -> tuple[bool, bool, bool, bool, bool, bool, bool]: ...
def address_split_compound_code(
    compound_code: bytes,
) -> Optional[tuple[bytes, bytes]]: ...
def mask_valid_path(path: bytes) -> bool: ...
def mask_unique_indices(paths: list[bytes]) -> list[int]: ...
def mask_sorted_order(keys: list[tuple[int, bytes]]) -> list[int]: ...

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
