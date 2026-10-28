//! Typed errors for the Places API core.
//!
//! Every failure mode of the client maps to one variant here. The Python
//! bindings translate these into a matching Python exception hierarchy using
//! [`Error::kind`].

use serde::Deserialize;

/// Errors returned by every `places-core` operation.
#[derive(Debug, thiserror::Error)]
pub enum Error {
    /// The API key was rejected or lacks permission (HTTP 401/403,
    /// `UNAUTHENTICATED`, `PERMISSION_DENIED`).
    #[error("authentication failed (HTTP {status}): {message}")]
    Auth {
        status: u16,
        google_status: String,
        message: String,
    },
    /// Quota exhausted or rate limit hit (HTTP 429, `RESOURCE_EXHAUSTED`).
    #[error("rate limit or quota exceeded (HTTP {status}): {message}")]
    RateLimit {
        status: u16,
        google_status: String,
        message: String,
    },
    /// The requested resource does not exist (HTTP 404, `NOT_FOUND`).
    #[error("not found (HTTP {status}): {message}")]
    NotFound {
        status: u16,
        google_status: String,
        message: String,
    },
    /// The request itself was malformed (HTTP 400, `INVALID_ARGUMENT`).
    #[error("invalid request (HTTP {status}): {message}")]
    InvalidRequest {
        status: u16,
        google_status: String,
        message: String,
    },
    /// Any other error response from the API.
    #[error("places API error (HTTP {status} {google_status}): {message}")]
    Api {
        status: u16,
        google_status: String,
        message: String,
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

    /// Build an error from a non-success HTTP response. Parses the standard
    /// Google error envelope (`{"error": {"code", "message", "status"}}`)
    /// and classifies by the Google status string first, then by HTTP code.
    pub fn from_response(status: u16, body: &str) -> Error {
        let parsed = serde_json::from_str::<GoogleErrorEnvelope>(body).ok();
        let (google_status, message) = match parsed {
            Some(env) => (
                env.error.status.unwrap_or_default(),
                env.error
                    .message
                    .unwrap_or_else(|| format!("HTTP {status}")),
            ),
            None => (
                String::new(),
                if body.trim().is_empty() {
                    format!("HTTP {status}")
                } else {
                    body.chars().take(500).collect()
                },
            ),
        };

        match google_status.as_str() {
            "UNAUTHENTICATED" | "PERMISSION_DENIED" => Error::Auth {
                status,
                google_status,
                message,
            },
            "RESOURCE_EXHAUSTED" => Error::RateLimit {
                status,
                google_status,
                message,
            },
            "NOT_FOUND" => Error::NotFound {
                status,
                google_status,
                message,
            },
            "INVALID_ARGUMENT" | "FAILED_PRECONDITION" => Error::InvalidRequest {
                status,
                google_status,
                message,
            },
            _ => match status {
                401 | 403 => Error::Auth {
                    status,
                    google_status,
                    message,
                },
                429 => Error::RateLimit {
                    status,
                    google_status,
                    message,
                },
                404 => Error::NotFound {
                    status,
                    google_status,
                    message,
                },
                400 => Error::InvalidRequest {
                    status,
                    google_status,
                    message,
                },
                _ => Error::Api {
                    status,
                    google_status,
                    message,
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
    message: Option<String>,
    status: Option<String>,
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
}
