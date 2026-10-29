from typing import Optional

class PlacesError(Exception):
    kind: str
    message: str
    status_code: Optional[int]
    google_status: Optional[str]
    error_code: Optional[int]
    details: list
    field_violations: list
    quota_violations: list
    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = ...,
        google_status: Optional[str] = ...,
        error_code: Optional[int] = ...,
        details: Optional[list] = ...,
        field_violations: Optional[list] = ...,
        quota_violations: Optional[list] = ...,
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
