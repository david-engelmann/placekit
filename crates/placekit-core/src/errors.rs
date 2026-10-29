//! Typed errors for the Places API core.
//!
//! Every failure mode of the client maps to one variant here. The Python
//! bindings translate these into a matching Python exception hierarchy using
//! [`Error::kind`].

use serde::Deserialize;

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
    },
    /// Quota exhausted or rate limit hit (HTTP 429, `RESOURCE_EXHAUSTED`).
    #[error("rate limit or quota exceeded (HTTP {status}): {message}")]
    RateLimit {
        status: u16,
        google_status: String,
        message: String,
        code: Option<i64>,
        details: Vec<serde_json::Value>,
    },
    /// The requested resource does not exist (HTTP 404, `NOT_FOUND`).
    #[error("not found (HTTP {status}): {message}")]
    NotFound {
        status: u16,
        google_status: String,
        message: String,
        code: Option<i64>,
        details: Vec<serde_json::Value>,
    },
    /// The request itself was malformed (HTTP 400, `INVALID_ARGUMENT`).
    #[error("invalid request (HTTP {status}): {message}")]
    InvalidRequest {
        status: u16,
        google_status: String,
        message: String,
        code: Option<i64>,
        details: Vec<serde_json::Value>,
    },
    /// Any other error response from the API.
    #[error("places API error (HTTP {status} {google_status}): {message}")]
    Api {
        status: u16,
        google_status: String,
        message: String,
        code: Option<i64>,
        details: Vec<serde_json::Value>,
    },
    /// The request never produced an HTTP response (DNS, connect, TLS,
    /// timeout, or a dropped connection).
    #[error("network error: {detail}")]
    Network { detail: String },
    /// The API returned a success status with a body that did not decode
    /// into the expected shape.
    #[error("failed to decode response: {detail}")]
    Decode { detail: String },
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
            _ => None,
        }
    }

    /// The Google RPC status string (for example `INVALID_ARGUMENT`), when
    /// the error came from an API response.
    pub fn google_status(&self) -> Option<&str> {
        match self {
            Error::Auth { google_status, .. }
            | Error::RateLimit { google_status, .. }
            | Error::NotFound { google_status, .. }
            | Error::InvalidRequest { google_status, .. }
            | Error::Api { google_status, .. } => Some(google_status.as_str()),
            _ => None,
        }
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

    /// Build an error from a non-success HTTP response. Parses the standard
    /// Google error envelope (`{"error": {"code", "message", "status",
    /// "details"}}`) and classifies by the Google status string first,
    /// then by HTTP code.
    pub fn from_response(status: u16, body: &str) -> Error {
        let parsed = serde_json::from_str::<GoogleErrorEnvelope>(body).ok();
        let (google_status, message, code, details) = match parsed {
            Some(env) => (
                env.error.status.unwrap_or_default(),
                env.error
                    .message
                    .unwrap_or_else(|| format!("HTTP {status}")),
                env.error.code,
                env.error.details.unwrap_or_default(),
            ),
            None => (
                String::new(),
                if body.trim().is_empty() {
                    format!("HTTP {status}")
                } else {
                    body.chars().take(500).collect()
                },
                None,
                Vec::new(),
            ),
        };

        match google_status.as_str() {
            "UNAUTHENTICATED" | "PERMISSION_DENIED" => Error::Auth {
                status,
                google_status,
                message,
                code,
                details,
            },
            "RESOURCE_EXHAUSTED" => Error::RateLimit {
                status,
                google_status,
                message,
                code,
                details,
            },
            "NOT_FOUND" => Error::NotFound {
                status,
                google_status,
                message,
                code,
                details,
            },
            "INVALID_ARGUMENT" | "FAILED_PRECONDITION" => Error::InvalidRequest {
                status,
                google_status,
                message,
                code,
                details,
            },
            _ => match status {
                401 | 403 => Error::Auth {
                    status,
                    google_status,
                    message,
                    code,
                    details,
                },
                429 => Error::RateLimit {
                    status,
                    google_status,
                    message,
                    code,
                    details,
                },
                404 => Error::NotFound {
                    status,
                    google_status,
                    message,
                    code,
                    details,
                },
                400 => Error::InvalidRequest {
                    status,
                    google_status,
                    message,
                    code,
                    details,
                },
                _ => Error::Api {
                    status,
                    google_status,
                    message,
                    code,
                    details,
                },
            },
        }
    }

    pub(crate) fn network(err: reqwest::Error) -> Error {
        Error::Network {
            detail: err.to_string(),
        }
    }

    pub(crate) fn config(detail: impl Into<String>) -> Error {
        Error::Config {
            detail: detail.into(),
        }
    }
}

#[derive(Debug, Deserialize)]
struct GoogleErrorEnvelope {
    error: GoogleErrorBody,
}

#[derive(Debug, Deserialize)]
struct GoogleErrorBody {
    code: Option<i64>,
    message: Option<String>,
    status: Option<String>,
    details: Option<Vec<serde_json::Value>>,
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
}
