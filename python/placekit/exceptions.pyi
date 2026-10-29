from typing import Any, NoReturn, Optional

class PlacesError(Exception):
    kind: str
    message: str
    status_code: Optional[int]
    google_status: Optional[str]
    error_code: Optional[int]
    details: list[Any]
    field_violations: list[Any]
    quota_violations: list[Any]
    status_mismatch: bool
    retryable: bool
    retry_after: Optional[float]
    context: Optional[str]
    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = ...,
        google_status: Optional[str] = ...,
        error_code: Optional[int] = ...,
        details: Optional[list[Any]] = ...,
        field_violations: Optional[list[Any]] = ...,
        quota_violations: Optional[list[Any]] = ...,
        status_mismatch: bool = ...,
        retryable: bool = ...,
        retry_after: Optional[float] = ...,
        context: Optional[str] = ...,
    ) -> None: ...

class AuthenticationError(PlacesError): ...
class RateLimitError(PlacesError): ...

QuotaError = RateLimitError

class NotFoundError(PlacesError): ...
class InvalidRequestError(PlacesError): ...
class NetworkError(PlacesError): ...
class DecodeError(PlacesError): ...
class ApiError(PlacesError): ...
class ConfigError(PlacesError, ValueError): ...

def raise_translated(
    exc: BaseException, context: Optional[str] = ...
) -> NoReturn: ...
