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
        retry_after: Option<f64>,
    },
    /// Quota exhausted or rate limit hit (HTTP 429, `RESOURCE_EXHAUSTED`).
    #[error("rate limit or quota exceeded (HTTP {status}): {message}")]
    RateLimit {
        status: u16,
        google_status: String,
        message: String,
        code: Option<i64>,
        details: Vec<serde_json::Value>,
        retry_after: Option<f64>,
    },
    /// The requested resource does not exist (HTTP 404, `NOT_FOUND`).
    #[error("not found (HTTP {status}): {message}")]
    NotFound {
        status: u16,
        google_status: String,
        message: String,
        code: Option<i64>,
        details: Vec<serde_json::Value>,
        retry_after: Option<f64>,
    },
    /// The request itself was malformed (HTTP 400, `INVALID_ARGUMENT`,
    /// `FAILED_PRECONDITION` or `OUT_OF_RANGE`).
    #[error("invalid request (HTTP {status}): {message}")]
    InvalidRequest {
        status: u16,
        google_status: String,
        message: String,
        code: Option<i64>,
        details: Vec<serde_json::Value>,
        retry_after: Option<f64>,
    },
    /// Any other error response from the API.
    #[error(
        "places API error (HTTP {status}{}): {message}",
        google_status_segment(google_status)
    )]
    Api {
        status: u16,
        google_status: String,
        message: String,
        code: Option<i64>,
        details: Vec<serde_json::Value>,
        retry_after: Option<f64>,
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
    /// programming error, detected before any network traffic. The
    /// rendering is the specific detail alone (Round 25, Minor 8):
    /// a fixed prefix saying the configuration or call was invalid
    /// repeated the classification the type already carries into
    /// every message built from this variant.
    #[error("{detail}")]
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
    /// A network error whose transport failure was a timeout reports
    /// true (Round 25, Minor 11): the documented meaning of the flag
    /// is whether a caller side retry can plausibly succeed, and a
    /// timeout is the classic case where one can. Errors carrying no
    /// status and no such signal keep the conservative default, false.
    /// No retry is attempted by the client itself.
    pub fn retryable(&self) -> bool {
        if let Some(status) = self.status_code() {
            if matches!(status, 429 | 500 | 502 | 503 | 504) {
                return true;
            }
        }
        if self.is_timeout() {
            return true;
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

    /// True when this error is a network failure whose transport
    /// class is a timeout. Every network detail opens with its
    /// transport class token, so a timeout carries the token in
    /// text; the typed source, when one was kept, answers directly
    /// as the second check.
    fn is_timeout(&self) -> bool {
        match self {
            Error::Network { detail, source } => {
                detail.starts_with("timeout")
                    || source
                        .as_deref()
                        .and_then(|s| s.downcast_ref::<reqwest::Error>())
                        .is_some_and(|e| e.is_timeout())
            }
            _ => false,
        }
    }

    /// The value of a `Retry-After` response header in seconds, when
    /// the failing response carried one. Fractional header values keep
    /// their fraction (Round 24); the declared Python type is `float`.
    pub fn retry_after(&self) -> Option<f64> {
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
    pub(crate) fn with_retry_after(mut self, retry_after: Option<f64>) -> Error {
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
    ///    found, `INVALID_ARGUMENT`, `FAILED_PRECONDITION` and
    ///    `OUT_OF_RANGE` are invalid requests, and the server side
    ///    statuses `UNAVAILABLE`,
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

    /// [`Error::from_response`] with the response content type, which
    /// the callers read off the response on every error path. The
    /// value no longer shapes the message built from a non-envelope
    /// body (R18-A6); it stays on the signature so the construction
    /// paths keep one shape.
    pub(crate) fn from_response_detailed(
        status: u16,
        body: &str,
        content_type: Option<&str>,
    ) -> Error {
        Self::from_response_read(status, body, content_type, None)
    }

    /// [`Error::from_response_detailed`] for an error body whose read
    /// stopped at the read cap (Round 23). The body string is the
    /// capped prefix, not the body, so the message built from a
    /// non-envelope body must state that the read was capped rather
    /// than reporting the prefix length as the body size it used to
    /// claim. The envelope path is unaffected: a truncated envelope
    /// parses or fails on its own contents either way.
    pub(crate) fn from_capped_error_body(
        status: u16,
        body: &str,
        content_type: Option<&str>,
        read_cap: usize,
    ) -> Error {
        Self::from_response_read(status, body, content_type, Some(read_cap))
    }

    fn from_response_read(
        status: u16,
        body: &str,
        content_type: Option<&str>,
        read_cap: Option<usize>,
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
                    // The status truncates at the same bound as the
                    // message (Round 28, Finding 1). The cap lands
                    // before the classification match below and
                    // cannot move a classification: every canonical
                    // status is far shorter than the cap, and a
                    // status longer than the cap never matched one,
                    // padded or not, so it falls to the HTTP class
                    // exactly as it did whole.
                    parts
                        .status
                        .map(|s| s.chars().take(ENVELOPE_TEXT_CAP_CHARS).collect())
                        .unwrap_or_default(),
                    parts
                        .message
                        .map(|m| m.chars().take(ENVELOPE_TEXT_CAP_CHARS).collect())
                        .unwrap_or_else(|| {
                            // A message missing from a completely read
                            // envelope was genuinely not carried. A
                            // message missing from a partly read one
                            // (the tolerant head scan stopped before
                            // the error object closed) may only have
                            // been cut off by the read cap, and the
                            // text must not claim the envelope carried
                            // none (Round 25 landing repair).
                            if parts.partial {
                                "the error envelope message could not be read in full".to_owned()
                            } else {
                                "the error envelope carried no message".to_owned()
                            }
                        }),
                    parts.code,
                    parts.details,
                    class_status,
                )
            }
            None => (
                String::new(),
                non_envelope_message(status, body, content_type, read_cap),
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
            "INVALID_ARGUMENT" | "FAILED_PRECONDITION" | "OUT_OF_RANGE" => Error::InvalidRequest {
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

    /// The error for a response body read that timed out
    /// (Round 25, red team Minor 1). The HTTP class fallback used
    /// to mask that timeout in full: no attribute and no message
    /// token recorded that the caller's own deadline fired, and
    /// the masked form reported retryable false on client error
    /// statuses. The timeout is the fact a caller acts on, so it
    /// surfaces as the network error it is, carrying the timeout
    /// class token. The detail is a fixed string with no source
    /// because this constructor also serves the photo path, whose
    /// request URL carries the API key and whose transport
    /// failures are never formatted (R4-07). `label` names the
    /// body as the reading path names it: the error body on the
    /// error paths, the response or photo body on the success
    /// paths, whose reads give the timeout the same treatment
    /// (Round 25 landing repair).
    pub(crate) fn network_body_read_timeout_labelled(label: &str) -> Error {
        Error::Network {
            detail: format!("timeout: the {label} read timed out"),
            source: None,
        }
    }

    /// [`Error::network_body_read_timeout_labelled`] for an error
    /// response body, the original Round 25 shape.
    pub(crate) fn network_body_read_timeout() -> Error {
        Self::network_body_read_timeout_labelled("error body")
    }

    pub(crate) fn config(detail: impl Into<String>) -> Error {
        Error::Config {
            detail: detail.into(),
        }
    }
}

/// The Google status segment of the Api headline: a space and the
/// status when the envelope carried one, and nothing when it did
/// not, so a failure with no Google status never renders an empty
/// gap where the status would sit (Round 25, Minor 1).
fn google_status_segment(google_status: &str) -> String {
    if google_status.is_empty() {
        String::new()
    } else {
        format!(" {google_status}")
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
/// The body is not quoted (R18-A6). Error text is the surface callers
/// log most, and an unparsed body is wholly server chosen, so quoting
/// it would let a hostile or compromised endpoint place arbitrary
/// text into caller logs and echo request data back through the same
/// channel. The body size is the fact the message carries, or the
/// read cap when the read stopped there and the size is unknown; the
/// HTTP status is not repeated here because every variant's headline
/// already carries it (Round 25, Minor 1). A parsed envelope is a
/// different case and keeps its own message and attributes: those
/// are the API's structured diagnostic, not raw body text. The
/// status and content type are accepted so every error construction
/// path takes the same inputs; neither shapes the message.
fn non_envelope_message(
    _status: u16,
    body: &str,
    _content_type: Option<&str>,
    read_cap: Option<usize>,
) -> String {
    if body.trim().is_empty() {
        return "no error body".to_owned();
    }
    match read_cap {
        // The read stopped at the cap, so the prefix length is not
        // the body size and the message must not present it as one
        // (Round 23): the true size is unknown once reading stops.
        // The message opens with the fact rather than the HTTP
        // status (Round 25, Minor 1): every variant's headline
        // already carries the status, so a status here printed it
        // twice in one rendering.
        Some(cap) => format!(
            "error body read stopped at the {cap} byte cap, so the full size is unknown, not a Places error envelope"
        ),
        None => format!(
            "error body of {} bytes, not a Places error envelope",
            body.len()
        ),
    }
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
    /// True when these parts came from the tolerant head scan
    /// and the scan stopped before the error object closed, so
    /// a field read as absent may only be unread. Always false
    /// for the whole document parse, whose absent fields are
    /// genuinely absent.
    partial: bool,
}

/// The character bound on server supplied text carried into an
/// exception. The envelope status and message are truncated to
/// it when the error is built, and every string inside the
/// parsed details is truncated to it in the parse funnel (Round
/// 25, Minor 6; the status joined them in Round 28, Finding 1,
/// after the audit found it passing through whole while every
/// neighbouring field was capped). The caps are defined to be
/// one bound, so they read from this one constant rather than
/// from literals that only imply the coupling (Round 25 landing
/// repair).
const ENVELOPE_TEXT_CAP_CHARS: usize = 500;

/// Read the envelope fields of a response body, or `None` when the
/// body carries no `error` object at all.
///
/// The whole document parse is tried first and its field by field
/// posture is unchanged (R4-09). When the whole parse refuses the
/// body, the envelope head fields are recovered tolerantly instead
/// (Round 25, Major 1 and the red team depth finding): the parse is
/// all or nothing, so a body truncated by the error read cap, or
/// carrying a value nested past the parser depth limit anywhere
/// inside it, lost the status and message and code its head carried
/// complete, and classification fell back to the bare HTTP code. The
/// tolerant scan reads only the head, so neither body size nor
/// nesting anywhere in the body can defeat it. Details are not
/// recovered by the scan; they degrade to empty while the status,
/// message and class survive.
///
/// String values inside parsed details are capped at the same 500
/// character discipline as the envelope message (Round 25, Minor
/// 6). The message cap alone left the details beside it bounded
/// only by the body cap, and on a success status envelope that cap
/// is the 32 MiB success cap rather than the error read cap, so a
/// hostile or broken endpoint could park a details payload of that
/// size inside an exception callers routinely log or retain.
fn parse_envelope(body: &str) -> Option<EnvelopeParts> {
    let value: serde_json::Value = match serde_json::from_str(body) {
        Ok(value) => value,
        Err(_) => return parse_envelope_head(body),
    };
    let error = value.get("error")?.as_object()?;
    let mut details = error
        .get("details")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    for detail in &mut details {
        cap_detail_strings(detail);
    }
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
        details,
        partial: false,
    })
}

/// Truncate every string value inside one parsed detail at
/// [`ENVELOPE_TEXT_CAP_CHARS`] characters, the envelope message
/// discipline. The walk is
/// iterative, over the values of objects and the items of arrays;
/// object keys are names rather than values and keep their length.
fn cap_detail_strings(value: &mut serde_json::Value) {
    let mut stack: Vec<&mut serde_json::Value> = vec![value];
    while let Some(node) = stack.pop() {
        match node {
            serde_json::Value::String(text) => {
                if text.chars().count() > ENVELOPE_TEXT_CAP_CHARS {
                    *text = text.chars().take(ENVELOPE_TEXT_CAP_CHARS).collect();
                }
            }
            serde_json::Value::Array(items) => stack.extend(items.iter_mut()),
            serde_json::Value::Object(map) => stack.extend(map.values_mut()),
            _ => {}
        }
    }
}

/// Recover the envelope head fields from a body the whole document
/// parse refused. The scan walks the top level object to the
/// `error` key, then reads that object's scalar fields, skipping
/// every other value with an iterative depth walk that no nesting
/// can exhaust. A field whose value is not complete in the text is
/// read as absent, matching the field by field posture of the
/// whole parse, and a failure further into the error object never
/// discards head fields already read: the head is the
/// classification.
///
/// Duplicate keys resolve last wins, as the whole document parse
/// resolves them (Round 25 landing repair). The walk does not
/// stop at the first `error` key: a later error object replaces
/// an earlier one, and an `error` value that is not an object is
/// skipped like any other value rather than ending the scan. One
/// limit stands where the data runs out: a later error object
/// cut off before it yields a head field does not erase an
/// earlier complete one, because the first readable value is
/// the only data there is. A scan that recovers no head field
/// at all reports no envelope, the same verdict the whole parse
/// gives an error object with no usable field, so the caller
/// takes the bare HTTP fallback and its wording.
fn parse_envelope_head(body: &str) -> Option<EnvelopeParts> {
    let mut scan = HeadScan::new(body);
    scan.skip_ws();
    if !scan.eat(b'{') {
        return None;
    }
    let mut found: Option<EnvelopeParts> = None;
    loop {
        scan.skip_ws();
        if scan.at_end() || scan.eat(b'}') {
            break;
        }
        let Some(key) = scan.string() else {
            break;
        };
        scan.skip_ws();
        if !scan.eat(b':') {
            break;
        }
        scan.skip_ws();
        if key == "error" && scan.peek() == Some(b'{') {
            let (parts, closed) = scan.error_object();
            let usable = parts.status.is_some() || parts.message.is_some() || parts.code.is_some();
            if closed || usable {
                found = Some(parts);
            }
            if !closed {
                break;
            }
        } else if !scan.skip_value() {
            break;
        }
        scan.skip_ws();
        if scan.eat(b',') {
            continue;
        }
        break;
    }
    found.filter(|parts| parts.status.is_some() || parts.message.is_some() || parts.code.is_some())
}

/// A byte cursor over a response body for the tolerant head scan.
/// Only token boundaries are found by hand; string tokens are
/// decoded by serde_json itself, so escapes and unicode read
/// exactly as the whole parse would read them.
struct HeadScan<'a> {
    bytes: &'a [u8],
    pos: usize,
}

impl<'a> HeadScan<'a> {
    fn new(body: &'a str) -> Self {
        HeadScan {
            bytes: body.as_bytes(),
            pos: 0,
        }
    }

    fn at_end(&self) -> bool {
        self.pos >= self.bytes.len()
    }

    fn peek(&self) -> Option<u8> {
        self.bytes.get(self.pos).copied()
    }

    fn skip_ws(&mut self) {
        while matches!(self.peek(), Some(b' ' | b'\t' | b'\n' | b'\r')) {
            self.pos += 1;
        }
    }

    fn eat(&mut self, byte: u8) -> bool {
        if self.peek() == Some(byte) {
            self.pos += 1;
            true
        } else {
            false
        }
    }

    /// Read one JSON string at the cursor and decode it, or `None`
    /// when the text at the cursor is not a complete decodable
    /// string.
    fn string(&mut self) -> Option<String> {
        self.skip_ws();
        if self.peek() != Some(b'"') {
            return None;
        }
        let start = self.pos;
        self.pos += 1;
        loop {
            match self.peek()? {
                b'\\' => self.pos += 2,
                b'"' => {
                    self.pos += 1;
                    let token = std::str::from_utf8(&self.bytes[start..self.pos]).ok()?;
                    return serde_json::from_str(token).ok();
                }
                _ => self.pos += 1,
            }
        }
    }

    /// Skip the string token at the cursor without decoding it.
    /// Returns false when the token is not complete in the text.
    fn skip_string_raw(&mut self) -> bool {
        // The cursor is on the opening quote.
        self.pos += 1;
        loop {
            match self.peek() {
                None => return false,
                Some(b'\\') => self.pos += 2,
                Some(b'"') => {
                    self.pos += 1;
                    return true;
                }
                Some(_) => self.pos += 1,
            }
        }
    }

    /// Skip one JSON value at the cursor, however deeply nested.
    /// The depth walk is an explicit counter rather than recursion,
    /// so no nesting depth in the skipped value can exhaust it.
    /// Returns false when the value is not complete in the text
    /// (the read was capped) or is malformed.
    fn skip_value(&mut self) -> bool {
        self.skip_ws();
        match self.peek() {
            Some(b'"') => self.skip_string_raw(),
            Some(b'{' | b'[') => {
                let mut depth = 0usize;
                loop {
                    match self.peek() {
                        None => return false,
                        Some(b'"') => {
                            if !self.skip_string_raw() {
                                return false;
                            }
                        }
                        Some(b'{' | b'[') => {
                            depth += 1;
                            self.pos += 1;
                        }
                        Some(b'}' | b']') => {
                            depth -= 1;
                            self.pos += 1;
                            if depth == 0 {
                                return true;
                            }
                        }
                        Some(_) => self.pos += 1,
                    }
                }
            }
            Some(_) => {
                // A number or a true, false or null literal: the
                // token runs to the next structural character or
                // whitespace, neither of which its alphabet holds.
                while matches!(
                    self.peek(),
                    Some(b'0'..=b'9' | b'-' | b'+' | b'.' | b'e' | b'E' | b'a'..=b'z')
                ) {
                    self.pos += 1;
                }
                true
            }
            None => false,
        }
    }

    /// Read the error object's scalar head fields. The cursor is
    /// on the opening brace of the error value; the caller has
    /// already checked that shape, since an `error` value that
    /// is not an object is skipped by the caller rather than
    /// read here. Once the object opens, whatever head fields
    /// were fully read are the result, even when the rest of
    /// the object is truncated or unreadable. The returned flag
    /// says whether the object closed cleanly, which the caller
    /// needs twice over: only a cleanly closed object lets the
    /// top level walk continue on to a later `error` key, and
    /// a message missing from a partly read object was not
    /// shown to be absent.
    ///
    /// Duplicate head keys resolve last wins inside the object
    /// too, as the whole parse resolves them: a repeated field
    /// whose later value is mistyped clears the field, matching
    /// the whole parse reading the later value and skipping it
    /// as mistyped.
    fn error_object(&mut self) -> (EnvelopeParts, bool) {
        self.skip_ws();
        self.eat(b'{');
        let mut parts = EnvelopeParts {
            status: None,
            message: None,
            code: None,
            details: Vec::new(),
            partial: true,
        };
        loop {
            self.skip_ws();
            if self.at_end() {
                return (parts, false);
            }
            if self.eat(b'}') {
                parts.partial = false;
                return (parts, true);
            }
            let Some(key) = self.string() else {
                return (parts, false);
            };
            self.skip_ws();
            if !self.eat(b':') {
                return (parts, false);
            }
            self.skip_ws();
            match key.as_str() {
                "status" | "message" => {
                    let slot = if key == "status" {
                        &mut parts.status
                    } else {
                        &mut parts.message
                    };
                    if self.peek() == Some(b'"') {
                        match self.string() {
                            Some(value) => *slot = Some(value),
                            None => return (parts, false),
                        }
                    } else {
                        *slot = None;
                        if !self.skip_value() {
                            return (parts, false);
                        }
                    }
                }
                "code" => match self.peek() {
                    Some(b'0'..=b'9' | b'-') => {
                        let start = self.pos;
                        while matches!(
                            self.peek(),
                            Some(b'0'..=b'9' | b'-' | b'+' | b'.' | b'e' | b'E')
                        ) {
                            self.pos += 1;
                        }
                        let token = std::str::from_utf8(&self.bytes[start..self.pos]).unwrap_or("");
                        parts.code = serde_json::from_str::<serde_json::Value>(token)
                            .ok()
                            .and_then(|v| v.as_i64());
                    }
                    _ => {
                        parts.code = None;
                        if !self.skip_value() {
                            return (parts, false);
                        }
                    }
                },
                _ => {
                    if !self.skip_value() {
                        return (parts, false);
                    }
                }
            }
            self.skip_ws();
            if self.eat(b',') {
                continue;
            }
            // The object ends here when the next byte is its
            // closing brace, which is consumed so the caller's
            // walk resumes past the object; anything else is
            // malformed, and the fields read so far stand
            // either way.
            let closed = self.eat(b'}');
            if closed {
                parts.partial = false;
            }
            return (parts, closed);
        }
    }
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
    fn envelope_status_is_capped_on_the_whole_parse() {
        // Round 28, Finding 1: the status was the one envelope
        // string exempt from the cap the message and the detail
        // strings already honour. At exactly the cap it is kept
        // whole; one past it, it truncates to the cap.
        let at_cap = "s".repeat(500);
        let body = format!(r#"{{"error": {{"code": 400, "message": "m", "status": "{at_cap}"}}}}"#);
        let err = Error::from_response(400, &body);
        assert_eq!(err.google_status(), Some(at_cap.as_str()));

        let one_past = "s".repeat(501);
        let body =
            format!(r#"{{"error": {{"code": 400, "message": "m", "status": "{one_past}"}}}}"#);
        let err = Error::from_response(400, &body);
        assert_eq!(err.google_status(), Some("s".repeat(500).as_str()));
    }

    #[test]
    fn envelope_status_cap_cannot_move_classification() {
        // A known status padded far past the cap never matched
        // when it passed through whole, and truncation must not
        // start matching it: the HTTP class decides, exactly as
        // before the cap.
        let padded = format!("RESOURCE_EXHAUSTED{}", "s".repeat(5_000));
        let body = format!(r#"{{"error": {{"code": 400, "message": "m", "status": "{padded}"}}}}"#);
        let err = Error::from_response(400, &body);
        assert_eq!(err.google_status().map(str::len), Some(500));
        assert_eq!(err.kind(), "invalid_request");
    }

    #[test]
    fn envelope_status_is_capped_on_the_head_scan() {
        // A value nested past the parser depth limit defeats the
        // whole document parse, so the status is recovered by the
        // tolerant head scan instead; the cap holds on that path
        // too, fed by the same funnel.
        let status = "s".repeat(5_000);
        let nested = format!("{}{}", "[".repeat(200), "]".repeat(200));
        let body = format!(
            r#"{{"error": {{"code": 400, "message": "m", "status": "{status}", "details": [{nested}]}}}}"#
        );
        let err = Error::from_response(400, &body);
        assert_eq!(err.google_status().map(str::len), Some(500));
        assert_eq!(err.kind(), "invalid_request");
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
        let err = Error::from_response(429, "").with_retry_after(Some(7.0));
        assert_eq!(err.retry_after(), Some(7.0));
        let err = Error::from_response(429, "");
        assert_eq!(err.retry_after(), None);
    }

    #[test]
    fn non_envelope_body_is_not_quoted() {
        // R18-A6: an unparsed body reaches the message at no length;
        // the status and the body size are what it carries.
        let body = "y".repeat(600);
        let err = Error::from_response_detailed(503, &body, Some("text/html"));
        let text = err.to_string();
        assert!(text.contains("HTTP 503"), "{text}");
        assert!(text.contains("600 bytes"), "{text}");
        assert!(!text.contains("yyyy"), "{text}");
        // A short body is not quoted either; quoting was never a
        // property of length.
        let err = Error::from_response_detailed(500, "upstream exploded", Some("text/plain"));
        let text = err.to_string();
        assert!(!text.contains("upstream exploded"), "{text}");
        assert!(text.contains("HTTP 500"), "{text}");
    }

    #[test]
    fn capped_error_body_read_states_the_cap_not_a_size() {
        // Round 23: an over cap error body was reported with the
        // capped read length as if it were the body size. The capped
        // construction states that the read stopped at the cap and
        // the full size is unknown; the prefix length appears only
        // as the cap figure itself.
        let prefix = "y".repeat(256 * 1024);
        let err = Error::from_capped_error_body(500, &prefix, Some("text/html"), 256 * 1024);
        let text = err.to_string();
        assert!(text.contains("HTTP 500"), "{text}");
        assert!(text.contains("stopped at the 262144 byte cap"), "{text}");
        assert!(text.contains("full size is unknown"), "{text}");
        assert!(!text.contains("error body of 262144 bytes"), "{text}");
        assert!(!text.contains("yyyy"), "{text}");
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

    #[test]
    fn over_cap_envelope_still_classifies_by_its_status() {
        // Round 25, Major 1: the envelope fields sit complete at
        // the head of an over cap body, ahead of the detail bulk
        // that overflows the read cap. The capped prefix parse
        // cannot read the document whole, so the tolerant head
        // scan recovers the status, code and message, and the
        // classification follows the envelope rather than falling
        // back to the bare HTTP code.
        let body = format!(
            r#"{{"error": {{"code": 429, "message": "big quota", "status": "RESOURCE_EXHAUSTED", "details": [{{"@type": "type.googleapis.com/google.rpc.DebugInfo", "detail": "{}"}}]}}}}"#,
            "z".repeat(300_000)
        );
        let prefix = &body[..256 * 1024];
        let err = Error::from_capped_error_body(400, prefix, None, 256 * 1024);
        assert_eq!(err.kind(), "rate_limit");
        assert_eq!(err.google_status(), Some("RESOURCE_EXHAUSTED"));
        assert_eq!(err.error_code(), Some(429));
        assert!(err.to_string().contains("big quota"), "{err}");
        // The details sit past the truncation and degrade to
        // empty; the class and message survive without them.
        assert!(err.details().is_empty());
        // The mirror shape: an invalid argument envelope on a
        // rate limit HTTP code classifies by its status too.
        let body = format!(
            r#"{{"error": {{"code": 400, "message": "big invalid", "status": "INVALID_ARGUMENT", "details": [{{"@type": "type.googleapis.com/google.rpc.DebugInfo", "detail": "{}"}}]}}}}"#,
            "z".repeat(300_000)
        );
        let prefix = &body[..256 * 1024];
        let err = Error::from_capped_error_body(429, prefix, None, 256 * 1024);
        assert_eq!(err.kind(), "invalid_request");
        assert_eq!(err.google_status(), Some("INVALID_ARGUMENT"));
    }

    #[test]
    fn deeply_nested_value_still_classifies_by_its_status() {
        // Round 25, red team Major: a value nested past the JSON
        // parser depth limit anywhere in the body defeated the
        // whole document parse in full, on a body of about a
        // kilobyte. The tolerant head scan skips values with an
        // iterative walk, so the nesting depth cannot defeat it,
        // whether the deep value sits inside a detail or in an
        // unknown key beside the head fields.
        let mut deep = serde_json::json!("x");
        for _ in 0..200 {
            deep = serde_json::json!([deep]);
        }
        let body = serde_json::json!({
            "error": {
                "code": 429,
                "message": "nested quota",
                "status": "RESOURCE_EXHAUSTED",
                "details": [{"@type": "type.googleapis.com/google.rpc.DebugInfo", "detail": deep}],
            }
        })
        .to_string();
        assert!(serde_json::from_str::<serde_json::Value>(&body).is_err());
        let err = Error::from_response(400, &body);
        assert_eq!(err.kind(), "rate_limit");
        assert_eq!(err.google_status(), Some("RESOURCE_EXHAUSTED"));
        assert!(err.to_string().contains("nested quota"), "{err}");
        assert!(err.details().is_empty());
        // The same depth in an unknown key inside the error
        // object, after the head fields.
        let mut deep = serde_json::json!("x");
        for _ in 0..200 {
            deep = serde_json::json!([deep]);
        }
        let body = serde_json::json!({
            "error": {
                "code": 404,
                "message": "nested sibling",
                "status": "NOT_FOUND",
                "junk": deep,
            }
        })
        .to_string();
        let err = Error::from_response(400, &body);
        assert_eq!(err.kind(), "not_found");
        assert_eq!(err.google_status(), Some("NOT_FOUND"));
    }

    #[test]
    fn out_of_range_classifies_by_status_on_any_pairing() {
        // Round 25, Major 3: OUT_OF_RANGE had no status driven
        // mapping and reached its class only through the canonical
        // HTTP 400 pairing. The status arm now carries it, so the
        // class is the invalid request class on neutral and server
        // side pairings alike.
        let body = r#"{"error": {"code": 418, "message": "too far", "status": "OUT_OF_RANGE"}}"#;
        let err = Error::from_response(418, body);
        assert_eq!(err.kind(), "invalid_request");
        assert_eq!(err.google_status(), Some("OUT_OF_RANGE"));
        let body = r#"{"error": {"code": 500, "message": "too far", "status": "OUT_OF_RANGE"}}"#;
        let err = Error::from_response(500, body);
        assert_eq!(err.kind(), "invalid_request");
        assert_eq!(err.google_status(), Some("OUT_OF_RANGE"));
    }

    #[test]
    fn api_headline_has_no_gap_and_no_duplicate_status() {
        // Round 25, Minor 1: a non envelope body left the Google
        // status empty, and the headline rendered an empty gap
        // where the status would sit plus a second copy of the
        // HTTP status at the start of the inner message.
        let err = Error::from_response(500, "plain text failure");
        let text = err.to_string();
        assert!(text.starts_with("places API error (HTTP 500): "), "{text}");
        assert_eq!(text.matches("HTTP 500").count(), 1, "{text}");
        // An envelope status still renders in the headline.
        let body = r#"{"error": {"code": 503, "message": "down", "status": "UNAVAILABLE"}}"#;
        let err = Error::from_response(503, body);
        assert!(
            err.to_string()
                .starts_with("places API error (HTTP 503 UNAVAILABLE): down"),
            "{err}"
        );
        // An empty body doubles nothing either.
        let err = Error::from_response(404, "");
        let text = err.to_string();
        assert_eq!(text.matches("HTTP 404").count(), 1, "{text}");
    }

    #[test]
    fn config_message_is_the_specific_detail_alone() {
        // Round 25, Minor 8: the fixed prefix repeated the
        // classification the type already carries into every
        // message built from this variant.
        let err = Error::config("radius must be positive".to_owned());
        assert_eq!(err.to_string(), "radius must be positive");
    }

    #[test]
    fn timeout_network_errors_are_retryable() {
        // Round 25, Minor 11: a timeout is the classic case where
        // a caller side retry can plausibly succeed, which is the
        // documented meaning of the flag.
        let err = Error::Network {
            detail: "timeout: operation timed out".to_owned(),
            source: None,
        };
        assert!(err.retryable());
        let err = Error::network_body_read_timeout();
        assert_eq!(err.kind(), "network");
        assert!(err.to_string().contains("timeout"), "{err}");
        assert!(err.retryable());
        // A permanent transport refusal stays conservative.
        let err = Error::Network {
            detail: "connect: connection refused".to_owned(),
            source: None,
        };
        assert!(!err.retryable());
    }

    #[test]
    fn detail_strings_are_capped_at_the_message_discipline() {
        // Round 25, Minor 6: a details entry of 100000 characters
        // was carried whole into the exception on a success status
        // envelope while the message beside it stayed capped.
        let body = serde_json::json!({
            "error": {
                "code": 403,
                "message": "denied",
                "status": "PERMISSION_DENIED",
                "details": [{
                    "@type": "type.googleapis.com/google.rpc.DebugInfo",
                    "detail": "y".repeat(100_000),
                    "nested": {"list": ["z".repeat(600)]},
                }],
            }
        })
        .to_string();
        let err = Error::from_response(200, &body);
        assert_eq!(err.kind(), "auth");
        let detail = &err.details()[0];
        assert_eq!(detail["detail"].as_str().map(str::len), Some(500));
        assert_eq!(
            detail["nested"]["list"][0].as_str().map(str::len),
            Some(500)
        );
        // Short strings pass through untouched.
        assert_eq!(detail["@type"], "type.googleapis.com/google.rpc.DebugInfo");
    }

    /// A value nested past the parser depth limit, as raw JSON
    /// text, for building bodies the whole parse refuses.
    fn deep_fragment() -> String {
        let mut text = String::from("\"x\"");
        for _ in 0..200 {
            text = format!("[{text}]");
        }
        text
    }

    #[test]
    fn head_scan_takes_the_last_of_two_error_objects() {
        // Round 25 landing repair: duplicate keys resolve last
        // wins in the whole document parse, and the head scan
        // resolved a duplicated error key first wins. With the
        // whole parse defeated by a deeply nested sibling, the
        // scan now walks past the first error object, and the
        // later one classifies the call exactly as the whole
        // parse classifies the same body without the sibling.
        let body = |junk: &str| {
            format!(
                r#"{{"error": {{"code": 400, "message": "first", "status": "INVALID_ARGUMENT"}}, "error": {{"code": 429, "message": "second", "status": "RESOURCE_EXHAUSTED"}}, "junk": {junk}}}"#
            )
        };
        let err = Error::from_response(400, &body(&deep_fragment()));
        assert_eq!(err.kind(), "rate_limit");
        assert_eq!(err.google_status(), Some("RESOURCE_EXHAUSTED"));
        assert_eq!(err.error_code(), Some(429));
        assert!(err.to_string().contains("second"), "{err}");
        let control = Error::from_response(400, &body("0"));
        assert_eq!(control.kind(), "rate_limit");
        assert_eq!(control.google_status(), Some("RESOURCE_EXHAUSTED"));
        assert!(control.to_string().contains("second"), "{control}");
    }

    #[test]
    fn head_scan_skips_a_non_object_error_value() {
        // Round 25 landing repair: an `error` value that is not
        // an object silenced the scan outright, even when a real
        // envelope sat under a second `error` key. The scan now
        // skips the non object value and keeps walking.
        let body = |junk: &str| {
            format!(
                r#"{{"error": "not an object", "error": {{"code": 404, "message": "gone", "status": "NOT_FOUND"}}, "junk": {junk}}}"#
            )
        };
        let err = Error::from_response(400, &body(&deep_fragment()));
        assert_eq!(err.kind(), "not_found");
        assert_eq!(err.google_status(), Some("NOT_FOUND"));
        let control = Error::from_response(400, &body("0"));
        assert_eq!(control.kind(), "not_found");
        assert_eq!(control.google_status(), Some("NOT_FOUND"));
    }

    #[test]
    fn head_scan_repeated_status_key_takes_the_last_value() {
        // Round 25 landing repair: a repeated status key whose
        // later value is mistyped clears the field in the whole
        // parse (the later value is read and skipped as mistyped,
        // leaving no status), and the scan kept the earlier
        // string. The scan now clears the field the same way, so
        // both paths classify by the numeric code.
        let body = |junk: &str| {
            format!(
                r#"{{"error": {{"code": 400, "message": "mixed", "status": "RESOURCE_EXHAUSTED", "status": 42, "junk": {junk}}}}}"#
            )
        };
        let err = Error::from_response(400, &body(&deep_fragment()));
        assert_eq!(err.kind(), "invalid_request");
        assert_eq!(err.google_status(), None);
        assert!(err.to_string().contains("mixed"), "{err}");
        let control = Error::from_response(400, &body("0"));
        assert_eq!(control.kind(), "invalid_request");
        assert_eq!(control.google_status(), None);
    }

    #[test]
    fn head_scan_cut_second_error_object_keeps_the_first() {
        // The stated limit of the last wins alignment: a later
        // error object cut off before it yields a head field
        // does not erase an earlier complete one, because the
        // first readable value is the only data there is.
        let body =
            r#"{"error": {"code": 404, "message": "gone", "status": "NOT_FOUND"}, "error": {"sta"#;
        let err = Error::from_response(400, body);
        assert_eq!(err.kind(), "not_found");
        assert_eq!(err.google_status(), Some("NOT_FOUND"));
        assert!(err.to_string().contains("gone"), "{err}");
    }

    #[test]
    fn scan_recovered_envelope_with_a_cut_message_says_it_could_not_be_read_in_full() {
        // Round 25 landing repair: the message runs far past the
        // error read cap, so the capped read cuts it mid string.
        // The scan recovers the status and code, and the fallback
        // text says the message could not be read in full instead
        // of claiming the envelope carried none.
        let body = format!(
            r#"{{"error": {{"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "{}", "details": []}}}}"#,
            "x".repeat(400_000)
        );
        let prefix = &body[..256 * 1024];
        let err = Error::from_capped_error_body(400, prefix, None, 256 * 1024);
        assert_eq!(err.kind(), "rate_limit");
        assert_eq!(err.google_status(), Some("RESOURCE_EXHAUSTED"));
        let text = err.to_string();
        assert!(text.contains("could not be read in full"), "{text}");
        assert!(!text.contains("carried no message"), "{text}");
    }

    #[test]
    fn scan_recovered_envelope_without_a_message_keeps_the_genuine_wording() {
        // The companion shape: the scan reads the error object
        // to its close and the object genuinely carries no
        // message, so the standing wording stands.
        let body = format!(
            r#"{{"error": {{"code": 503, "status": "UNAVAILABLE"}}, "junk": {}}}"#,
            deep_fragment()
        );
        let err = Error::from_response(503, &body);
        assert_eq!(err.kind(), "api");
        assert!(err.to_string().contains("carried no message"), "{err}");
    }

    #[test]
    fn head_scan_garbage_first_key_falls_back_to_the_non_envelope_wording() {
        // Round 25 landing repair: an error object whose first
        // key is not a string yields no scan fields at all. The
        // honest wording is the non envelope one, not a claim
        // that an envelope was read and carried no message.
        let body = format!(
            r#"{{"junk": {}, "error": {{123: "x", "status": "NOT_FOUND"}}}}"#,
            deep_fragment()
        );
        let err = Error::from_response(500, &body);
        assert_eq!(err.kind(), "api");
        let text = err.to_string();
        assert!(text.contains("not a Places error envelope"), "{text}");
        assert!(!text.contains("carried no message"), "{text}");
    }
}
