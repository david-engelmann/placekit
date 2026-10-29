"""Exception hierarchy for placekit.

Every error raised by the Rust core is translated into one of these types,
so callers can catch precisely the failure they care about. All of them
carry the HTTP ``status_code`` and the Google RPC ``google_status`` when
the error came from an API response.
"""

from __future__ import annotations

from typing import Any, NoReturn, Optional


class PlacesError(Exception):
    """Base class for every error raised by placekit."""

    kind = "error"

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        google_status: Optional[str] = None,
        error_code: Optional[int] = None,
        details: Optional[list[Any]] = None,
        field_violations: Optional[list[Any]] = None,
        quota_violations: Optional[list[Any]] = None,
        status_mismatch: bool = False,
        retryable: bool = False,
        retry_after: Optional[float] = None,
        context: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.google_status = google_status
        #: The ``code`` field of the Google error envelope, when present.
        self.error_code = error_code
        #: The parsed ``details`` array of the envelope (google.rpc detail
        #: objects as dicts), empty when the response carried none. The
        #: list is copied, so later mutation of the caller's list cannot
        #: rewrite a raised exception.
        self.details = list(details) if details is not None else []
        #: Field violations from a BadRequest detail, as dicts with
        #: ``field`` (the wire name, for example ``textQuery``) and
        #: ``description`` keys.
        self.field_violations = (
            list(field_violations) if field_violations is not None else []
        )
        #: Violation dicts from a QuotaFailure detail.
        self.quota_violations = (
            list(quota_violations) if quota_violations is not None else []
        )
        #: True when the envelope ``code`` and the HTTP status disagree.
        #: Classification follows the envelope status first and the HTTP
        #: code second, so the class and ``status_code`` can come from
        #: different sources; this flag makes that split visible.
        self.status_mismatch = status_mismatch
        #: True when a caller side retry can plausibly succeed (quota
        #: errors and server side failures). The client never retries
        #: on its own; this only informs the caller's policy.
        self.retryable = retryable
        #: Seconds from the response's ``Retry-After`` header, when the
        #: failing response carried one in integer form.
        self.retry_after = retry_after
        #: Which call failed, as an operation name plus its identifying
        #: argument where one exists (for example ``place_details
        #: place_id=...``), set by the client methods. Never a URL, so
        #: it cannot carry the API key.
        self.context = context

    def __str__(self) -> str:
        """The message plus the context the type collects, so logging
        an exception shows why it was raised, not just its text."""
        parts = []
        if self.context is not None:
            parts.append(f"context={self.context}")
        if self.status_code is not None:
            parts.append(f"status_code={self.status_code}")
        if self.google_status is not None:
            parts.append(f"google_status={self.google_status}")
        if self.retry_after is not None:
            parts.append(f"retry_after={self.retry_after}")
        if not parts:
            return self.message
        return f"{self.message} ({', '.join(parts)})"

    def __repr__(self) -> str:
        return f"{type(self).__name__}({str(self)!r})"


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


def raise_translated(exc: BaseException, context: Optional[str] = None) -> NoReturn:
    """Translate a Rust-core ``PlacesError`` into the hierarchy above.

    ``context`` names the call that failed; the client methods supply
    it so multi-request programs can tell which call an exception came
    from. Always raises; never returns.
    """
    kind = getattr(exc, "kind", "api")
    error_type = _KIND_TO_ERROR.get(kind, ApiError)
    raise error_type(
        str(exc),
        status_code=getattr(exc, "status_code", None),
        google_status=getattr(exc, "google_status", None),
        error_code=getattr(exc, "error_code", None),
        details=getattr(exc, "details", None),
        field_violations=getattr(exc, "field_violations", None),
        quota_violations=getattr(exc, "quota_violations", None),
        status_mismatch=getattr(exc, "status_mismatch", False),
        retryable=getattr(exc, "retryable", False),
        retry_after=getattr(exc, "retry_after", None),
        context=context,
    ) from exc
