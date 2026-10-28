"""Exception hierarchy for placekit.

Every error raised by the Rust core is translated into one of these types,
so callers can catch precisely the failure they care about. All of them
carry the HTTP ``status_code`` and the Google RPC ``google_status`` when
the error came from an API response.
"""

from __future__ import annotations

from typing import Optional


class PlacesError(Exception):
    """Base class for every error raised by placekit."""

    kind = "error"

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        google_status: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.google_status = google_status


class AuthenticationError(PlacesError):
    """The API key was rejected or lacks permission (HTTP 401/403)."""

    kind = "auth"


class RateLimitError(PlacesError):
    """Quota exhausted or rate limit hit (HTTP 429)."""

    kind = "rate_limit"


#: Alias for callers who think in quota terms.
QuotaError = RateLimitError


class NotFoundError(PlacesError):
    """The requested resource does not exist (HTTP 404)."""

    kind = "not_found"


class InvalidRequestError(PlacesError):
    """The request itself was malformed (HTTP 400)."""

    kind = "invalid_request"


class NetworkError(PlacesError):
    """The request never produced an HTTP response."""

    kind = "network"


class DecodeError(PlacesError):
    """A success response body did not decode into the expected shape."""

    kind = "decode"


class ApiError(PlacesError):
    """Any other error response from the Places API."""

    kind = "api"


class ConfigError(PlacesError, ValueError):
    """The client was configured or called incorrectly.

    Raised before any network traffic happens, for problems such as an
    out-of-range photo size or a malformed place id. Also a ``ValueError``
    so existing ``except ValueError`` handlers catch it.
    """

    kind = "config"


_KIND_TO_ERROR = {
    "auth": AuthenticationError,
    "rate_limit": RateLimitError,
    "not_found": NotFoundError,
    "invalid_request": InvalidRequestError,
    "network": NetworkError,
    "decode": DecodeError,
    "api": ApiError,
    "config": ConfigError,
}


def raise_translated(exc: BaseException) -> None:
    """Translate a Rust-core ``PlacesError`` into the hierarchy above.

    Always raises; never returns.
    """
    kind = getattr(exc, "kind", "api")
    error_type = _KIND_TO_ERROR.get(kind, ApiError)
    raise error_type(
        str(exc),
        status_code=getattr(exc, "status_code", None),
        google_status=getattr(exc, "google_status", None),
    ) from exc
