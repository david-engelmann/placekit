//! Typed errors for the Places API core.
//!
//! Every failure mode of the client maps to one variant here. The Python
//! bindings translate these into a matching Python exception hierarchy using
//! [`Error::kind`].

/// Errors returned by every `placekit-core` operation.
#[derive(Debug, thiserror::Error)]
pub enum Error {
    /// The API key was rejected or lacks permission (HTTP 401/403,
    /// `UNAUTHENTICATED`, `PERMISSION_DENIED`).
    #[error("authentication failed (HTTP {status}): {message}")]
    Auth {
        status: u16,
        google_status: String,
        message: String,
        code: Option<i64>,
        details: Vec<serde_json::Value>,
        retry_after: Option<u64>,
    },
    /// Quota exhausted or rate limit hit (HTTP 429, `RESOURCE_EXHAUSTED`).
    #[error("rate limit or quota exceeded (HTTP {status}): {message}")]
    RateLimit {
        status: u16,
        google_status: String,
        message: String,
        code: Option<i64>,
        details: Vec<serde_json::Value>,
        retry_after: Option<u64>,
    },
    /// The requested resource does not exist (HTTP 404, `NOT_FOUND`).
    #[error("not found (HTTP {status}): {message}")]
    NotFound {
        status: u16,
        google_status: String,
        message: String,
        code: Option<i64>,
        details: Vec<serde_json::Value>,
        retry_after: Option<u64>,
    },
    /// The request itself was malformed (HTTP 400, `INVALID_ARGUMENT`
    /// or `FAILED_PRECONDITION`).
    #[error("invalid request (HTTP {status}): {message}")]
    InvalidRequest {
        status: u16,
        google_status: String,
        message: String,
        code: Option<i64>,
        details: Vec<serde_json::Value>,
        retry_after: Option<u64>,
    },
    /// Any other error response from the API.
    #[error("places API error (HTTP {status} {google_status}): {message}")]
    Api {
        status: u16,
        google_status: String,
        message: String,
        code: Option<i64>,
        details: Vec<serde_json::Value>,
        retry_after: Option<u64>,
    },
    /// The request never produced an HTTP response (DNS, connect, TLS,
    /// timeout, or a dropped connection).
    #[error("network error: {detail}")]
    Network {
        detail: String,
        /// The underlying transport error, kept typed as the source
        /// instead of being flattened into the message (R4-16). Absent
        /// when there is no concrete cause or when the cause's own
        /// rendering would leak a secret (see `network_redacted`).
        #[source]
        source: Option<Box<dyn std::error::Error + Send + Sync>>,
    },
    /// The API returned a success status with a body that did not decode
    /// into the expected shape. `status` carries the HTTP status of that
    /// response when there was one.
    #[error("failed to decode response: {detail}")]
    Decode {
        detail: String,
        status: Option<u16>,
        /// The underlying decode failure, kept typed as the source
        /// (R4-16), when a concrete one exists.
        #[source]
        source: Option<Box<dyn std::error::Error + Send + Sync>>,
    },
    /// The client itself was configured or called incorrectly. This is a
    /// programming error, detected before any network traffic.
    #[error("invalid client configuration or call: {detail}")]
    Config { detail: String },
}

impl Error {
    /// Stable machine-readable kind, used by language bindings to select an
    /// exception type. One of `auth`, `rate_limit`, `not_found`,
    /// `invalid_request`, `api`, `network`, `decode`, `config`.
    pub fn kind(&self) -> &'static str {
        match self {
            Error::Auth { .. } => "auth",
            Error::RateLimit { .. } => "rate_limit",
            Error::NotFound { .. } => "not_found",
            Error::InvalidRequest { .. } => "invalid_request",
            Error::Api { .. } => "api",
            Error::Network { .. } => "network",
            Error::Decode { .. } => "decode",
            Error::Config { .. } => "config",
        }
    }

    /// HTTP status code, when the error came from an API response.
    pub fn status_code(&self) -> Option<u16> {
        match self {
            Error::Auth { status, .. }
            | Error::RateLimit { status, .. }
            | Error::NotFound { status, .. }
            | Error::InvalidRequest { status, .. }
            | Error::Api { status, .. } => Some(*status),
            Error::Decode { status, .. } => *status,
            _ => None,
        }
    }

    /// The Google RPC status string (for example `INVALID_ARGUMENT`), when
    /// the error came from an API response. `None` when the response
    /// carried no parseable envelope status, never an empty string.
    pub fn google_status(&self) -> Option<&str> {
        let raw = match self {
            Error::Auth { google_status, .. }
            | Error::RateLimit { google_status, .. }
            | Error::NotFound { google_status, .. }
            | Error::InvalidRequest { google_status, .. }
            | Error::Api { google_status, .. } => google_status.as_str(),
            _ => return None,
        };
        if raw.is_empty() {
            None
        } else {
            Some(raw)
        }
    }

    /// True when the envelope `code` and the HTTP status disagree. The
    /// exception class follows the envelope status while `status_code`
    /// follows HTTP; this flag makes that split visible instead of
    /// silent.
    pub fn status_mismatch(&self) -> bool {
        match (self.error_code(), self.status_code()) {
            (Some(code), Some(status)) => code != i64::from(status),
            _ => false,
        }
    }

    /// Whether a caller side retry can plausibly succeed. The rule is
    /// status based, not variant based (R4-13): any error carrying a
    /// retryable HTTP status (429, 500, 502, 503, 504) reports true,
    /// whichever variant carries it; quota errors report true; a plain
    /// API error whose Google status is a server side one reports true.
    /// Errors carrying no status keep the conservative default, false.
    /// No retry is attempted by the client itself.
    pub fn retryable(&self) -> bool {
        if let Some(status) = self.status_code() {
            if matches!(status, 429 | 500 | 502 | 503 | 504) {
                return true;
            }
        }
        match self {
            Error::RateLimit { .. } => true,
            Error::Api { google_status, .. } => matches!(
                google_status.as_str(),
                "UNAVAILABLE" | "INTERNAL" | "DEADLINE_EXCEEDED"
            ),
            _ => false,
        }
    }

    /// The value of a `Retry-After` response header in whole seconds,
    /// when the failing response carried one.
    pub fn retry_after(&self) -> Option<u64> {
        match self {
            Error::Auth { retry_after, .. }
            | Error::RateLimit { retry_after, .. }
            | Error::NotFound { retry_after, .. }
            | Error::InvalidRequest { retry_after, .. }
            | Error::Api { retry_after, .. } => *retry_after,
            _ => None,
        }
    }

    /// Attach a parsed `Retry-After` value to an API error. Other
    /// variants have nowhere to carry it and are returned unchanged.
    pub(crate) fn with_retry_after(mut self, retry_after: Option<u64>) -> Error {
        match &mut self {
            Error::Auth {
                retry_after: slot, ..
            }
            | Error::RateLimit {
                retry_after: slot, ..
            }
            | Error::NotFound {
                retry_after: slot, ..
            }
            | Error::InvalidRequest {
                retry_after: slot, ..
            }
            | Error::Api {
                retry_after: slot, ..
            } => *slot = retry_after,
            _ => {}
        }
        self
    }

    /// Append a parenthesised note to an API error's message, for facts
    /// learned outside the body (an unreadable body, the content type,
    /// which host actually answered). Other variants are unchanged.
    pub(crate) fn with_note(mut self, note: &str) -> Error {
        match &mut self {
            Error::Auth { message, .. }
            | Error::RateLimit { message, .. }
            | Error::NotFound { message, .. }
            | Error::InvalidRequest { message, .. }
            | Error::Api { message, .. } => {
                message.push_str(" (");
                message.push_str(note);
                message.push(')');
            }
            _ => {}
        }
        self
    }

    /// The `code` field of the Google error envelope, when the response
    /// carried one. Cross checked against the HTTP status by callers; a
    /// mismatch is visible here rather than silently trusted.
    pub fn error_code(&self) -> Option<i64> {
        match self {
            Error::Auth { code, .. }
            | Error::RateLimit { code, .. }
            | Error::NotFound { code, .. }
            | Error::InvalidRequest { code, .. }
            | Error::Api { code, .. } => *code,
            _ => None,
        }
    }

    /// The parsed `details` array of the Google error envelope (the
    /// `google.rpc` detail objects), empty when the response carried none.
    pub fn details(&self) -> &[serde_json::Value] {
        match self {
            Error::Auth { details, .. }
            | Error::RateLimit { details, .. }
            | Error::NotFound { details, .. }
            | Error::InvalidRequest { details, .. }
            | Error::Api { details, .. } => details,
            _ => &[],
        }
    }

    /// Field violations from a `google.rpc.BadRequest` detail, as
    /// (field, description) pairs. Field names are the wire (JSON) names,
    /// for example `textQuery`.
    pub fn field_violations(&self) -> Vec<(String, String)> {
        let mut out = Vec::new();
        for detail in self.details() {
            let type_url = detail.get("@type").and_then(|v| v.as_str());
            if !matches!(type_url, Some(t) if t.ends_with("google.rpc.BadRequest")) {
                continue;
            }
            if let Some(violations) = detail.get("fieldViolations").and_then(|v| v.as_array()) {
                for violation in violations {
                    let field = violation
                        .get("field")
                        .and_then(|v| v.as_str())
                        .unwrap_or_default()
                        .to_owned();
                    let description = violation
                        .get("description")
                        .and_then(|v| v.as_str())
                        .unwrap_or_default()
                        .to_owned();
                    out.push((field, description));
                }
            }
        }
        out
    }

    /// Violation objects from a `google.rpc.QuotaFailure` detail.
    pub fn quota_violations(&self) -> Vec<serde_json::Value> {
        let mut out = Vec::new();
        for detail in self.details() {
            let type_url = detail.get("@type").and_then(|v| v.as_str());
            if !matches!(type_url, Some(t) if t.ends_with("google.rpc.QuotaFailure")) {
                continue;
            }
            if let Some(violations) = detail.get("violations").and_then(|v| v.as_array()) {
                out.extend(violations.iter().cloned());
            }
        }
        out
    }

    /// Build an error from a non-success HTTP response. Parses the
    /// standard Google error envelope (`{"error": {"code", "message",
    /// "status", "details"}}`) and classifies it. The full rule set, in
    /// the order applied (R4-26):
    ///
    /// 1. The envelope is read field by field (R4-09): a field that is
    ///    present and rightly typed is used, a mistyped field is
    ///    skipped, and the rest of the envelope still counts. Only a
    ///    body with no usable envelope field at all falls back to the
    ///    bare HTTP classification with the body echoed as the message.
    /// 2. A Google status string decides the class first:
    ///    `UNAUTHENTICATED` and `PERMISSION_DENIED` are auth errors,
    ///    `RESOURCE_EXHAUSTED` is a rate limit, `NOT_FOUND` is not
    ///    found, `INVALID_ARGUMENT` and `FAILED_PRECONDITION` are
    ///    invalid requests, and the server side statuses `UNAVAILABLE`,
    ///    `INTERNAL` and `DEADLINE_EXCEEDED` are plain API errors,
    ///    which never fall through to the client side HTTP classes.
    /// 3. With no status string, an envelope numeric `code` classifies
    ///    the error in place of the HTTP status.
    /// 4. Otherwise the HTTP status decides (401/403 auth, 429 rate
    ///    limit, 404 not found, 400 invalid request, anything else a
    ///    plain API error).
    ///
    /// The stored `status_code` is always the HTTP status, whichever
    /// rule classified the error; the envelope `code` is kept
    /// separately for cross checking (see `status_mismatch`).
    ///
    /// Hybrid bodies: a body carrying both a result shape and an error
    /// envelope is classified purely as an error (R4-19). An envelope
    /// is an explicit failure signal from the server; silently
    /// returning the result half would hide it.
    pub fn from_response(status: u16, body: &str) -> Error {
        Self::from_response_detailed(status, body, None)
    }

    /// [`Error::from_response`] with the response content type, used to
    /// describe non-envelope bodies in the error message.
    pub(crate) fn from_response_detailed(
        status: u16,
        body: &str,
        content_type: Option<&str>,
    ) -> Error {
        let parsed = parse_envelope(body);
        let (google_status, message, code, details, class_status) = match parsed {
            Some(parts) => {
                // Classification follows the envelope status first.
                // With no status string, an envelope that still carries
                // a numeric code classifies by that code (an off-spec
                // but observed shape); otherwise the HTTP status
                // decides. The stored status stays the HTTP one below
                // either way.
                let class_status = if parts.status.is_none() {
                    parts
                        .code
                        .and_then(|c| u16::try_from(c).ok())
                        .unwrap_or(status)
                } else {
                    status
                };
                (
                    parts.status.unwrap_or_default(),
                    parts
                        .message
                        .map(|m| m.chars().take(500).collect())
                        .unwrap_or_else(|| format!("HTTP {status}")),
                    parts.code,
                    parts.details,
                    class_status,
                )
            }
            None => (
                String::new(),
                non_envelope_message(status, body, content_type),
                None,
                Vec::new(),
                status,
            ),
        };

        match google_status.as_str() {
            "UNAUTHENTICATED" | "PERMISSION_DENIED" => Error::Auth {
                status,
                google_status,
                message,
                code,
                details,
                retry_after: None,
            },
            "RESOURCE_EXHAUSTED" => Error::RateLimit {
                status,
                google_status,
                message,
                code,
                details,
                retry_after: None,
            },
            "NOT_FOUND" => Error::NotFound {
                status,
                google_status,
                message,
                code,
                details,
                retry_after: None,
            },
            "INVALID_ARGUMENT" | "FAILED_PRECONDITION" => Error::InvalidRequest {
                status,
                google_status,
                message,
                code,
                details,
                retry_after: None,
            },
            // A canonical server side status classifies as a plain API
            // error whatever the HTTP code says; it must never fall
            // through to the client side HTTP classes below.
            "UNAVAILABLE" | "INTERNAL" | "DEADLINE_EXCEEDED" => Error::Api {
                status,
                google_status,
                message,
                code,
                details,
                retry_after: None,
            },
            _ => match class_status {
                401 | 403 => Error::Auth {
                    status,
                    google_status,
                    message,
                    code,
                    details,
                    retry_after: None,
                },
                429 => Error::RateLimit {
                    status,
                    google_status,
                    message,
                    code,
                    details,
                    retry_after: None,
                },
                404 => Error::NotFound {
                    status,
                    google_status,
                    message,
                    code,
                    details,
                    retry_after: None,
                },
                400 => Error::InvalidRequest {
                    status,
                    google_status,
                    message,
                    code,
                    details,
                    retry_after: None,
                },
                _ => Error::Api {
                    status,
                    google_status,
                    message,
                    code,
                    details,
                    retry_after: None,
                },
            },
        }
    }

    /// Build the error for a response whose error body could not be
    /// read at all. The HTTP status is the one fact that survives, so
    /// the class comes from the HTTP fallback and the read failure is
    /// recorded in the message rather than dropped.
    pub(crate) fn from_unreadable_body(
        status: u16,
        read_error: &str,
        content_type: Option<&str>,
    ) -> Error {
        Self::from_response_detailed(status, "", content_type)
            .with_note(&format!("error body unreadable: {read_error}"))
    }

    /// True when a body parses as a Google error envelope: an `error`
    /// object carrying a status string, or a numeric code or a message
    /// even without one. Used to catch error envelopes that arrive on
    /// a success HTTP status, where they would otherwise decode as an
    /// empty or defaulted success value.
    pub(crate) fn has_error_envelope(body: &str) -> bool {
        parse_envelope(body)
            .map(|parts| parts.status.is_some() || parts.code.is_some() || parts.message.is_some())
            .unwrap_or(false)
    }

    pub(crate) fn network(err: reqwest::Error) -> Error {
        // Prefix the detail with a stable class token so callers can
        // branch on the transport cause without matching reqwest prose;
        // a timeout in particular must not read as a decode failure.
        // The reqwest error itself is kept as the typed source (R4-16).
        let class = transport_class(&err);
        Error::Network {
            detail: format!("{class}: {err}"),
            source: Some(Box::new(err)),
        }
    }

    /// Like [`Error::network`], but for request paths whose URL carries
    /// a secret (R4-07): the photo media URL carries the API key as a
    /// query parameter, and a reqwest error's Display embeds the full
    /// URL, so the transport failure is classified without formatting
    /// the error, and the cause is dropped rather than kept as a
    /// source that would render the same URL to anyone printing the
    /// chain. The class token and the HTTP status, when the failure
    /// carried one, are the diagnostics that remain.
    pub(crate) fn network_redacted(err: reqwest::Error) -> Error {
        let class = transport_class(&err);
        let detail = match err.status() {
            Some(status) => format!("{class}: transport error (HTTP {})", status.as_u16()),
            None => format!("{class}: transport error"),
        };
        Error::Network {
            detail,
            source: None,
        }
    }

    pub(crate) fn network_detail(detail: String) -> Error {
        Error::Network {
            detail,
            source: None,
        }
    }

    pub(crate) fn config(detail: impl Into<String>) -> Error {
        Error::Config {
            detail: detail.into(),
        }
    }
}

/// The stable class token for a transport failure, shared by the
/// error mappings so the wording cannot drift between them.
fn transport_class(err: &reqwest::Error) -> &'static str {
    if err.is_timeout() {
        "timeout"
    } else if err.is_connect() {
        "connect"
    } else if err.is_redirect() {
        "redirect"
    } else if err.is_body() || err.is_decode() {
        "body"
    } else {
        "network"
    }
}
/// Message for an error response whose body is not a Google envelope.
/// The body text is the only diagnostic a proxy or load balancer
/// failure leaves, so it is echoed up to a cap; truncation is marked
/// with the total size and content type instead of being invisible.
fn non_envelope_message(status: u16, body: &str, content_type: Option<&str>) -> String {
    if body.trim().is_empty() {
        return format!("HTTP {status}");
    }
    let mut message: String = body.chars().take(500).collect();
    if body.chars().count() > 500 {
        message.push_str(&format!(
            "... [truncated, {} bytes, {}]",
            body.len(),
            content_type.unwrap_or("unknown content type")
        ));
    }
    message
}

/// One usable field set read from a Google error envelope. The parse
/// is field by field on purpose (R4-09): each field is taken when it is
/// present and rightly typed and skipped when it is not, so one
/// mistyped field cannot discard the status, message and details the
/// rest of the envelope carried.
struct EnvelopeParts {
    status: Option<String>,
    message: Option<String>,
    code: Option<i64>,
    details: Vec<serde_json::Value>,
}

/// Read the envelope fields of a response body, or `None` when the
/// body carries no `error` object at all.
fn parse_envelope(body: &str) -> Option<EnvelopeParts> {
    let value: serde_json::Value = serde_json::from_str(body).ok()?;
    let error = value.get("error")?.as_object()?;
    Some(EnvelopeParts {
        status: error
            .get("status")
            .and_then(|v| v.as_str())
            .map(str::to_owned),
        message: error
            .get("message")
            .and_then(|v| v.as_str())
            .map(str::to_owned),
        code: error.get("code").and_then(serde_json::Value::as_i64),
        details: error
            .get("details")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn maps_invalid_argument() {
        let body = r#"{"error": {"code": 400, "message": "Missing textQuery", "status": "INVALID_ARGUMENT"}}"#;
        let err = Error::from_response(400, body);
        assert_eq!(err.kind(), "invalid_request");
        assert_eq!(err.status_code(), Some(400));
        assert_eq!(err.google_status(), Some("INVALID_ARGUMENT"));
        assert!(matches!(err, Error::InvalidRequest { .. }));
    }

    #[test]
    fn maps_resource_exhausted_to_rate_limit() {
        let body = r#"{"error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}}"#;
        let err = Error::from_response(429, body);
        assert_eq!(err.kind(), "rate_limit");
        assert!(matches!(err, Error::RateLimit { .. }));
    }

    #[test]
    fn maps_permission_denied_to_auth() {
        let body = r#"{"error": {"code": 403, "message": "API not enabled", "status": "PERMISSION_DENIED"}}"#;
        let err = Error::from_response(403, body);
        assert_eq!(err.kind(), "auth");
        assert!(matches!(err, Error::Auth { .. }));
    }

    #[test]
    fn maps_not_found() {
        let body = r#"{"error": {"code": 404, "message": "No such place", "status": "NOT_FOUND"}}"#;
        let err = Error::from_response(404, body);
        assert_eq!(err.kind(), "not_found");
        assert!(matches!(err, Error::NotFound { .. }));
    }

    #[test]
    fn falls_back_to_http_status_when_body_is_not_google_json() {
        let err = Error::from_response(429, "slow down");
        assert_eq!(err.kind(), "rate_limit");
        let err = Error::from_response(503, "");
        assert_eq!(err.kind(), "api");
        assert_eq!(err.status_code(), Some(503));
    }

    #[test]
    fn google_status_wins_over_http_code() {
        // A 400 carrying RESOURCE_EXHAUSTED is a quota problem, not a
        // malformed request.
        let body =
            r#"{"error": {"code": 400, "message": "Quota", "status": "RESOURCE_EXHAUSTED"}}"#;
        let err = Error::from_response(400, body);
        assert_eq!(err.kind(), "rate_limit");
    }

    #[test]
    fn parses_field_violations_from_fixture() {
        // The fixture field name is the wire form textQuery (finding A1);
        // this test fails if details stop being parsed or the fixture
        // regresses to the proto name.
        let body = include_str!("../../../tests/fixtures/error_invalid.json");
        let err = Error::from_response(400, body);
        assert_eq!(err.error_code(), Some(400));
        assert_eq!(err.details().len(), 1);
        assert_eq!(
            err.field_violations(),
            vec![(
                "textQuery".to_owned(),
                "Request contains an invalid argument.".to_owned()
            )]
        );
        assert!(err.quota_violations().is_empty());
    }

    #[test]
    fn parses_quota_violations_from_fixture() {
        let body = include_str!("../../../tests/fixtures/error_quota.json");
        let err = Error::from_response(429, body);
        assert_eq!(err.kind(), "rate_limit");
        assert_eq!(err.error_code(), Some(429));
        let violations = err.quota_violations();
        assert_eq!(violations.len(), 1);
        assert_eq!(
            violations[0]["quotaMetric"],
            "places.googleapis.com/default"
        );
        assert!(err.field_violations().is_empty());
    }

    #[test]
    fn envelope_code_is_kept_even_when_it_disagrees_with_http_status() {
        // Classification follows the Google status string, but the
        // envelope code stays available for the caller to cross check.
        let body =
            r#"{"error": {"code": 400, "message": "Quota", "status": "RESOURCE_EXHAUSTED"}}"#;
        let err = Error::from_response(429, body);
        assert_eq!(err.kind(), "rate_limit");
        assert_eq!(err.status_code(), Some(429));
        assert_eq!(err.error_code(), Some(400));
    }

    #[test]
    fn status_mismatch_flags_envelope_code_against_http_status() {
        let body =
            r#"{"error": {"code": 400, "message": "Quota", "status": "RESOURCE_EXHAUSTED"}}"#;
        assert!(Error::from_response(500, body).status_mismatch());
        assert!(!Error::from_response(400, body).status_mismatch());
        // No envelope code, no mismatch.
        assert!(!Error::from_response(503, "").status_mismatch());
    }

    #[test]
    fn google_status_is_none_without_an_envelope_status() {
        // The documented contract is None, not an empty string, when a
        // non-envelope body carried no Google status (case 6).
        let err = Error::from_response(500, "Internal Server Error: upstream exploded");
        assert_eq!(err.kind(), "api");
        assert_eq!(err.google_status(), None);
        assert_eq!(err.status_code(), Some(500));
    }

    #[test]
    fn envelope_message_is_capped() {
        let long = "x".repeat(5_000);
        let body = format!(
            r#"{{"error": {{"code": 400, "message": "{long}", "status": "INVALID_ARGUMENT"}}}}"#
        );
        let err = Error::from_response(400, &body);
        // The stored message is exactly 500 characters: the run of
        // 500 is present and a run of 501 is not, the same exact shape
        // as the Python test of this name, so cap drift fails here.
        let text = err.to_string();
        assert!(text.contains(&"x".repeat(500)), "{text}");
        assert!(!text.contains(&"x".repeat(501)), "{text}");
    }

    #[test]
    fn server_side_statuses_never_fall_to_http_classes() {
        for (http, google) in [
            (400, "DEADLINE_EXCEEDED"),
            (400, "UNAVAILABLE"),
            (404, "INTERNAL"),
        ] {
            let body =
                format!(r#"{{"error": {{"code": {http}, "message": "m", "status": "{google}"}}}}"#);
            let err = Error::from_response(http, &body);
            assert_eq!(err.kind(), "api", "{google} on HTTP {http}");
            assert_eq!(err.google_status(), Some(google));
            assert!(err.retryable(), "{google} must be retryable");
        }
    }

    #[test]
    fn retryable_classification() {
        assert!(Error::from_response(429, "").retryable());
        assert!(Error::from_response(503, "").retryable());
        assert!(!Error::from_response(404, "").retryable());
        assert!(!Error::from_response(400, "").retryable());
        assert!(!Error::from_response(403, "").retryable());
    }

    #[test]
    fn retry_after_round_trips() {
        let err = Error::from_response(429, "").with_retry_after(Some(7));
        assert_eq!(err.retry_after(), Some(7));
        let err = Error::from_response(429, "");
        assert_eq!(err.retry_after(), None);
    }

    #[test]
    fn non_envelope_truncation_is_marked() {
        let body = "y".repeat(600);
        let err = Error::from_response_detailed(503, &body, Some("text/html"));
        let text = err.to_string();
        assert!(text.contains("[truncated, 600 bytes, text/html]"), "{text}");
    }

    #[test]
    fn unreadable_body_keeps_the_http_class_and_the_failure() {
        let err = Error::from_unreadable_body(500, "connection closed", None);
        assert_eq!(err.kind(), "api");
        assert_eq!(err.status_code(), Some(500));
        assert!(err
            .to_string()
            .contains("error body unreadable: connection closed"));
        let err = Error::from_unreadable_body(429, "connection closed", None);
        assert_eq!(err.kind(), "rate_limit");
    }

    #[test]
    fn error_envelope_detection() {
        assert!(Error::has_error_envelope(
            r#"{"error": {"code": 403, "message": "m", "status": "PERMISSION_DENIED"}}"#
        ));
        assert!(!Error::has_error_envelope(r#"{"places": []}"#));
        assert!(!Error::has_error_envelope("not json"));
        // A code or a message makes the envelope an error signal even
        // without a status string; a bare error object carries neither
        // and is not one.
        assert!(Error::has_error_envelope(r#"{"error": {"code": 403}}"#));
        assert!(Error::has_error_envelope(
            r#"{"error": {"message": "denied"}}"#
        ));
        assert!(!Error::has_error_envelope(r#"{"error": {}}"#));
    }

    #[test]
    fn envelope_without_status_classifies_by_its_code() {
        // The red team's case: an envelope with a code and a message
        // but no status string, arriving on HTTP 200. The class comes
        // from the numeric code, the stored status stays the HTTP one,
        // and there is no Google status to report.
        let body = r#"{"error": {"code": 403, "message": "denied but no status field"}}"#;
        let err = Error::from_response(200, body);
        assert_eq!(err.kind(), "auth");
        assert_eq!(err.status_code(), Some(200));
        assert_eq!(err.google_status(), None);
        assert_eq!(err.error_code(), Some(403));
        assert!(err.to_string().contains("denied but no status field"));
    }

    #[test]
    fn decode_error_carries_its_http_status() {
        let err = Error::Decode {
            detail: "bad body".to_owned(),
            status: Some(200),
            source: None,
        };
        assert_eq!(err.status_code(), Some(200));
        assert_eq!(err.google_status(), None);
        let err = Error::Decode {
            detail: "local".to_owned(),
            status: None,
            source: None,
        };
        assert_eq!(err.status_code(), None);
    }

    #[test]
    fn mistyped_envelope_fields_are_skipped_not_fatal() {
        // R4-09: a string typed code used to discard the whole
        // envelope. The status, message and details survive; only the
        // mistyped field is skipped.
        let body = r#"{"error": {"code": "400", "message": "Missing textQuery", "status": "INVALID_ARGUMENT", "details": [{"@type": "type.googleapis.com/google.rpc.BadRequest", "fieldViolations": [{"field": "textQuery", "description": "bad"}]}]}}"#;
        let err = Error::from_response(400, body);
        assert_eq!(err.kind(), "invalid_request");
        assert_eq!(err.google_status(), Some("INVALID_ARGUMENT"));
        assert_eq!(err.error_code(), None);
        assert!(err.to_string().contains("Missing textQuery"));
        assert_eq!(err.details().len(), 1);
        // A mistyped status falls back to the code and HTTP rules,
        // and the message still survives.
        let body = r#"{"error": {"code": 429, "message": "Quota gone", "status": 7}}"#;
        let err = Error::from_response(429, body);
        assert_eq!(err.kind(), "rate_limit");
        assert_eq!(err.google_status(), None);
        assert!(err.to_string().contains("Quota gone"));
        // A mistyped details field drops only the details.
        let body = r#"{"error": {"code": 404, "message": "gone", "status": "NOT_FOUND", "details": "none"}}"#;
        let err = Error::from_response(404, body);
        assert_eq!(err.kind(), "not_found");
        assert!(err.details().is_empty());
        assert!(Error::has_error_envelope(
            r#"{"error": {"code": "x", "status": "NOT_FOUND"}}"#
        ));
    }

    #[test]
    fn retryable_follows_the_status_on_any_variant() {
        // R4-13: a retryable status reports retryable whichever
        // variant carries it, not only on the Api variant.
        let err = Error::Decode {
            detail: "body".to_owned(),
            status: Some(503),
            source: None,
        };
        assert!(err.retryable());
        let err = Error::Decode {
            detail: "body".to_owned(),
            status: Some(429),
            source: None,
        };
        assert!(err.retryable());
        let err = Error::Decode {
            detail: "body".to_owned(),
            status: Some(404),
            source: None,
        };
        assert!(!err.retryable());
        let err = Error::Decode {
            detail: "local".to_owned(),
            status: None,
            source: None,
        };
        assert!(!err.retryable());
    }

    #[test]
    fn sources_are_kept_typed() {
        // R4-16: a concrete cause is reachable through the standard
        // source chain instead of being flattened into the message.
        use std::error::Error as StdError;
        let cause = std::io::Error::new(std::io::ErrorKind::InvalidData, "boom");
        let err = Error::Decode {
            detail: "bad body".to_owned(),
            status: Some(200),
            source: Some(Box::new(cause)),
        };
        let source = StdError::source(&err).expect("a source is carried");
        assert!(source.to_string().contains("boom"));
        let err = Error::network_detail("plain".to_owned());
        assert!(StdError::source(&err).is_none());
    }
}
