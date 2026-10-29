//! The async Places API (New) client.
//!
//! The client owns a `reqwest` client configured with rustls and a timeout.
//! It deliberately ignores proxy environment variables: connections to the
//! Places API are direct, which keeps behavior identical on a laptop, in CI,
//! and against a local stub server (used by the test suite through
//! [`ClientBuilder::base_url`]).

use std::time::Duration;

use reqwest::header::{HeaderMap, HeaderValue};
use serde::de::DeserializeOwned;

use crate::errors::Error;
use crate::mask::FieldMask;
use crate::models::{
    AutocompleteRequest, AutocompleteResponse, Circle, NearbySearchRequest, PhotoMedia,
    PhotoMediaJson, PhotoResponse, Place, SearchResponse, TextSearchRequest, Viewport,
};

/// Default endpoint root for the Places API (New).
pub const DEFAULT_BASE_URL: &str = "https://places.googleapis.com/v1";

/// Default cap on a single response body, 32 MiB. Legitimate Places
/// responses are orders of magnitude smaller; the cap exists so a
/// broken or hostile endpoint cannot grow memory without bound.
pub const DEFAULT_MAX_RESPONSE_BYTES: usize = 32 * 1024 * 1024;

/// Cap on error response bodies. Error bodies are read only to build
/// the error message, which is itself capped, so they stop early.
const ERROR_BODY_CAP: usize = 256 * 1024;

const API_KEY_HEADER: &str = "x-goog-api-key";
const FIELD_MASK_HEADER: &str = "x-goog-fieldmask";
const USER_AGENT: &str = concat!("placekit/", env!("CARGO_PKG_VERSION"), " (rust core)");

/// Builder for [`Client`].
#[derive(Debug, Clone)]
pub struct ClientBuilder {
    api_key: String,
    base_url: String,
    timeout: Duration,
    max_response_bytes: usize,
}

impl ClientBuilder {
    /// Override the API root. Useful for testing against a stub server.
    pub fn base_url(mut self, base_url: impl Into<String>) -> Self {
        self.base_url = base_url.into();
        self
    }

    /// Per-request timeout (default 10 seconds).
    pub fn timeout(mut self, timeout: Duration) -> Self {
        self.timeout = timeout;
        self
    }

    /// Maximum response body size in bytes (default 32 MiB). A body
    /// that grows past the cap aborts the request with a decode error
    /// naming the cap instead of being buffered whole.
    pub fn max_response_bytes(mut self, max_response_bytes: usize) -> Self {
        self.max_response_bytes = max_response_bytes;
        self
    }

    /// Build the client. Fails on an empty API key, a key that cannot be
    /// sent as an HTTP header value, or a timeout of zero.
    pub fn build(self) -> Result<Client, Error> {
        if self.api_key.trim().is_empty() {
            return Err(Error::config("API key must not be empty"));
        }
        // The key travels in the x-goog-api-key header on every request.
        // Reject values that cannot be header values here, at construction,
        // instead of letting header building drop them later (F13).
        if HeaderValue::from_str(&self.api_key).is_err() {
            return Err(Error::config(
                "API key contains characters that cannot be sent in an HTTP header",
            ));
        }
        if self.timeout.is_zero() {
            return Err(Error::config("timeout must be greater than zero"));
        }
        let http = reqwest::Client::builder()
            .timeout(self.timeout)
            .no_proxy()
            .user_agent(USER_AGENT)
            .build()
            .map_err(Error::network)?;
        Ok(Client {
            api_key: self.api_key,
            base_url: self.base_url.trim_end_matches('/').to_owned(),
            http,
            max_response_bytes: self.max_response_bytes,
        })
    }
}

/// An async client for the Places API (New).
#[derive(Debug, Clone)]
pub struct Client {
    api_key: String,
    base_url: String,
    http: reqwest::Client,
    max_response_bytes: usize,
}

impl Client {
    /// A client with default settings.
    pub fn new(api_key: impl Into<String>) -> Result<Self, Error> {
        Self::builder(api_key).build()
    }

    /// Start configuring a client.
    pub fn builder(api_key: impl Into<String>) -> ClientBuilder {
        ClientBuilder {
            api_key: api_key.into(),
            base_url: DEFAULT_BASE_URL.to_owned(),
            timeout: Duration::from_secs(10),
            max_response_bytes: DEFAULT_MAX_RESPONSE_BYTES,
        }
    }

    /// Text Search: find places matching a free-form query.
    pub async fn text_search(
        &self,
        request: &TextSearchRequest,
        fields: Option<&FieldMask>,
    ) -> Result<SearchResponse, Error> {
        if request.text_query.trim().is_empty() {
            return Err(Error::config("text_query must not be empty"));
        }
        validate_min_rating(request.min_rating)?;
        validate_max_result_count(request.max_result_count)?;
        validate_text_search_locations(request)?;
        let url = format!("{}/places:searchText", self.base_url);
        let mask = fields
            .cloned()
            .unwrap_or_else(FieldMask::text_search_default);
        let builder = self
            .http
            .post(url)
            .headers(self.headers(Some(&mask))?)
            .json(request);
        self.send(builder).await
    }

    /// Nearby Search: find places around a location.
    pub async fn nearby_search(
        &self,
        request: &NearbySearchRequest,
        fields: Option<&FieldMask>,
    ) -> Result<SearchResponse, Error> {
        validate_circle_radius(request.location_restriction.circle.radius)?;
        validate_max_result_count(request.max_result_count)?;
        let url = format!("{}/places:searchNearby", self.base_url);
        let mask = fields
            .cloned()
            .unwrap_or_else(FieldMask::nearby_search_default);
        let builder = self
            .http
            .post(url)
            .headers(self.headers(Some(&mask))?)
            .json(request);
        self.send(builder).await
    }

    /// Place Details for a single place id.
    pub async fn place_details(
        &self,
        place_id: &str,
        fields: Option<&FieldMask>,
        language_code: Option<&str>,
        region_code: Option<&str>,
        session_token: Option<&str>,
    ) -> Result<Place, Error> {
        validate_place_id(place_id)?;
        if let Some(token) = session_token {
            validate_session_token(token)?;
        }
        // The place id is a single path segment; percent encode it so an
        // unusual but valid id cannot reshape the URL (F16). Valid ids are
        // URL safe already, so this is a no-op for them.
        let url = format!("{}/places/{}", self.base_url, encode_path_segment(place_id));
        let mask = fields
            .cloned()
            .unwrap_or_else(FieldMask::place_details_default);
        let mut builder = self.http.get(url).headers(self.headers(Some(&mask))?);
        let mut query: Vec<(&str, &str)> = Vec::new();
        if let Some(v) = language_code {
            query.push(("languageCode", v));
        }
        if let Some(v) = region_code {
            query.push(("regionCode", v));
        }
        if let Some(v) = session_token {
            query.push(("sessionToken", v));
        }
        if !query.is_empty() {
            builder = builder.query(&query);
        }
        let (place, status): (Place, u16) = self.send_with_status(builder).await?;
        // Place Details with any sane field mask always returns an
        // identity. A success body carrying neither an id nor a
        // resource name is the wrong shape entirely, not a real place;
        // search and autocomplete empty objects stay legitimate there,
        // which is why this check lives on this endpoint only.
        if place.id.is_empty() && place.name.is_empty() {
            return Err(Error::Decode {
                detail: "place details response carried no id or name".to_owned(),
                status: Some(status),
            });
        }
        Ok(place)
    }

    /// Autocomplete: place and query predictions for partial input.
    /// A field mask is optional for this endpoint; when given it is sent
    /// like on the other endpoints.
    pub async fn autocomplete(
        &self,
        request: &AutocompleteRequest,
        fields: Option<&FieldMask>,
    ) -> Result<AutocompleteResponse, Error> {
        if request.input.trim().is_empty() {
            return Err(Error::config("autocomplete input must not be empty"));
        }
        if let Some(token) = request.session_token.as_deref() {
            validate_session_token(token)?;
        }
        if request.location_bias.is_some() && request.location_restriction.is_some() {
            return Err(Error::config(
                "location_bias and location_restriction cannot both be set",
            ));
        }
        if let Some(location) = &request.location_bias {
            validate_location_shape("location_bias", &location.rectangle, &location.circle)?;
        }
        if let Some(location) = &request.location_restriction {
            validate_location_shape(
                "location_restriction",
                &location.rectangle,
                &location.circle,
            )?;
        }
        let url = format!("{}/places:autocomplete", self.base_url);
        let builder = self
            .http
            .post(url)
            .headers(self.headers(fields)?)
            .json(request);
        self.send(builder).await
    }

    /// Download photo media for a photo resource name returned by other
    /// endpoints (for example `places/{id}/photos/{ref}`).
    ///
    /// The media endpoint authenticates with the API key as a query
    /// parameter rather than the usual header, and at least one of
    /// `max_width_px` / `max_height_px` must be given (each 1 to 4800).
    ///
    /// By default the endpoint redirects to the image and this returns the
    /// downloaded bytes. With `skip_http_redirect`, the endpoint answers
    /// with a JSON object instead, and this returns the photo name and its
    /// short lived URI.
    pub async fn place_photo(
        &self,
        photo_name: &str,
        max_width_px: Option<u32>,
        max_height_px: Option<u32>,
        skip_http_redirect: bool,
    ) -> Result<PhotoMedia, Error> {
        validate_photo_params(photo_name, max_width_px, max_height_px)?;
        // The photo name is structural (places/{id}/photos/{ref}). Its
        // segments are validated strictly, and each segment is percent
        // encoded as it is interpolated, so no segment can reshape the
        // path or smuggle in query parameters. This endpoint carries
        // the API key as a query parameter, which is why path escapes
        // here are credential relevant.
        let url = format!("{}/{}/media", self.base_url, encode_photo_name(photo_name));
        let mut query: Vec<(&str, String)> = vec![("key", self.api_key.clone())];
        if let Some(w) = max_width_px {
            query.push(("maxWidthPx", w.to_string()));
        }
        if let Some(h) = max_height_px {
            query.push(("maxHeightPx", h.to_string()));
        }
        if skip_http_redirect {
            query.push(("skipHttpRedirect", "true".to_owned()));
        }
        let response = self
            .http
            .get(url)
            .query(&query)
            .send()
            .await
            .map_err(Error::network)?;
        let status = response.status();
        let content_type = content_type_of(&response);
        let retry_after = retry_after_of(&response);
        // The host that finally answered, after any redirects. When it
        // is not the API host, failures belong to the image host.
        let final_host = response.url().host_str().map(str::to_owned);
        if !status.is_success() {
            let mut err = read_error_body(response, status.as_u16(), content_type.as_deref())
                .await
                .with_retry_after(retry_after);
            let mut notes: Vec<String> = Vec::new();
            let base_host = reqwest::Url::parse(&self.base_url)
                .ok()
                .and_then(|u| u.host_str().map(str::to_owned));
            if let (Some(final_host), Some(base_host)) = (&final_host, &base_host) {
                if final_host != base_host {
                    notes.push(format!(
                        "the failure came from the image host {final_host} after a redirect, not from the Places API"
                    ));
                }
            }
            if let Some(ct) = &content_type {
                notes.push(format!("content type {ct}"));
            }
            if !notes.is_empty() {
                err = err.with_note(&notes.join("; "));
            }
            return Err(err);
        }
        if skip_http_redirect {
            let body = self.read_success_text(response, status).await?;
            if Error::has_error_envelope(&body) {
                return Err(Error::from_response_detailed(
                    status.as_u16(),
                    &body,
                    content_type.as_deref(),
                )
                .with_retry_after(retry_after));
            }
            let media: PhotoMediaJson = serde_json::from_str(&body).map_err(|e| Error::Decode {
                detail: e.to_string(),
                status: Some(status.as_u16()),
            })?;
            return Ok(PhotoMedia::Uri(media));
        }
        // A success body only becomes a photo when it plausibly is
        // one. The declared type is checked first, then the envelope
        // check catches JSON errors regardless of the declared type,
        // then the magic bytes check the body against the claim.
        if let Some(ct) = &content_type {
            if !ct.starts_with("image/") {
                return Err(Error::Decode {
                    detail: format!("photo endpoint returned a non-image content type: {ct}"),
                    status: Some(status.as_u16()),
                });
            }
        }
        let bytes = match read_body_capped(response, self.max_response_bytes).await {
            BodyRead::Complete(bytes) => bytes,
            BodyRead::TooLarge => {
                return Err(Error::Decode {
                    detail: format!(
                        "photo body exceeded the maximum of {} bytes",
                        self.max_response_bytes
                    ),
                    status: Some(status.as_u16()),
                });
            }
            BodyRead::Failed(read_error) => {
                return Err(Error::network_detail(format!(
                    "HTTP {} received, body read failed: {read_error}",
                    status.as_u16()
                )));
            }
        };
        if let Ok(text) = std::str::from_utf8(&bytes) {
            if Error::has_error_envelope(text) {
                return Err(Error::from_response_detailed(
                    status.as_u16(),
                    text,
                    content_type.as_deref(),
                )
                .with_retry_after(retry_after));
            }
        }
        validate_photo_magic(&bytes, content_type.as_deref(), status.as_u16())?;
        Ok(PhotoMedia::Bytes(PhotoResponse {
            bytes,
            content_type,
        }))
    }

    /// Read a success response body as text under the size cap, for the
    /// JSON form of the photo endpoint. Failures keep the HTTP status.
    async fn read_success_text(
        &self,
        response: reqwest::Response,
        status: reqwest::StatusCode,
    ) -> Result<String, Error> {
        match read_body_capped(response, self.max_response_bytes).await {
            BodyRead::Complete(bytes) => String::from_utf8(bytes).map_err(|e| Error::Decode {
                detail: format!("response body was not valid UTF-8: {e}"),
                status: Some(status.as_u16()),
            }),
            BodyRead::TooLarge => Err(Error::Decode {
                detail: format!(
                    "response body exceeded the maximum of {} bytes",
                    self.max_response_bytes
                ),
                status: Some(status.as_u16()),
            }),
            BodyRead::Failed(read_error) => Err(Error::network_detail(format!(
                "HTTP {} received, body read failed: {read_error}",
                status.as_u16()
            ))),
        }
    }

    /// Headers shared by every request: the API key, and the field mask
    /// when the endpoint uses one. Fails rather than silently dropping a
    /// header that cannot be constructed (F13); the API key is validated
    /// at build time, so a failure here means a bad mask value.
    fn headers(&self, mask: Option<&FieldMask>) -> Result<HeaderMap, Error> {
        let mut headers = HeaderMap::new();
        let key = HeaderValue::from_str(&self.api_key)
            .map_err(|_| Error::config("API key cannot be sent in an HTTP header"))?;
        headers.insert(API_KEY_HEADER, key);
        if let Some(mask) = mask {
            let value = HeaderValue::from_str(&mask.header_value())
                .map_err(|_| Error::config("field mask cannot be sent in an HTTP header"))?;
            headers.insert(FIELD_MASK_HEADER, value);
        }
        Ok(headers)
    }

    async fn send<T: DeserializeOwned>(
        &self,
        builder: reqwest::RequestBuilder,
    ) -> Result<T, Error> {
        Ok(self.send_with_status(builder).await?.0)
    }

    /// Send a JSON request and decode the success body, keeping the
    /// HTTP status alongside the value for callers that validate the
    /// decoded shape themselves. Every failure keeps both facts it
    /// knows: the HTTP status and, for body read failures, the read
    /// error itself; neither is silently dropped.
    async fn send_with_status<T: DeserializeOwned>(
        &self,
        builder: reqwest::RequestBuilder,
    ) -> Result<(T, u16), Error> {
        let response = builder.send().await.map_err(Error::network)?;
        let status = response.status();
        let retry_after = retry_after_of(&response);
        let content_type = content_type_of(&response);
        if !status.is_success() {
            return Err(
                read_error_body(response, status.as_u16(), content_type.as_deref())
                    .await
                    .with_retry_after(retry_after),
            );
        }
        let body = match read_body_capped(response, self.max_response_bytes).await {
            BodyRead::Complete(bytes) => match String::from_utf8(bytes) {
                Ok(text) => text,
                Err(e) => {
                    return Err(Error::Decode {
                        detail: format!("response body was not valid UTF-8: {e}"),
                        status: Some(status.as_u16()),
                    });
                }
            },
            BodyRead::TooLarge => {
                return Err(Error::Decode {
                    detail: format!(
                        "response body exceeded the maximum of {} bytes",
                        self.max_response_bytes
                    ),
                    status: Some(status.as_u16()),
                });
            }
            BodyRead::Failed(read_error) => {
                return Err(Error::network_detail(format!(
                    "HTTP {} received, body read failed: {read_error}",
                    status.as_u16()
                )));
            }
        };
        // An error envelope on a success status is an error, exactly
        // as if it had arrived on its own HTTP code.
        if Error::has_error_envelope(&body) {
            return Err(Error::from_response_detailed(
                status.as_u16(),
                &body,
                content_type.as_deref(),
            )
            .with_retry_after(retry_after));
        }
        serde_json::from_str::<T>(&body)
            .map(|value| (value, status.as_u16()))
            .map_err(|e| Error::Decode {
                detail: e.to_string(),
                status: Some(status.as_u16()),
            })
    }
}

/// Outcome of reading a response body under a size cap.
enum BodyRead {
    Complete(Vec<u8>),
    TooLarge,
    Failed(String),
}

/// Read a body as a stream, aborting as soon as it grows past `cap`
/// instead of buffering it whole.
async fn read_body_capped(response: reqwest::Response, cap: usize) -> BodyRead {
    use futures_util::StreamExt;
    let mut stream = response.bytes_stream();
    let mut buf = Vec::new();
    while let Some(chunk) = stream.next().await {
        match chunk {
            Ok(chunk) => {
                if buf.len() + chunk.len() > cap {
                    return BodyRead::TooLarge;
                }
                buf.extend_from_slice(&chunk);
            }
            Err(e) => return BodyRead::Failed(e.to_string()),
        }
    }
    BodyRead::Complete(buf)
}

/// Read an error response body and build the error from it. The read
/// is capped and truncation is harmless (messages are capped again
/// downstream). A read failure discards the partial body, which is
/// unreliable by definition, and keeps the HTTP fallback class with
/// the read failure recorded in the message, so neither the status
/// nor the read error is lost.
async fn read_error_body(
    response: reqwest::Response,
    status: u16,
    content_type: Option<&str>,
) -> Error {
    use futures_util::StreamExt;
    let mut stream = response.bytes_stream();
    let mut buf = Vec::new();
    while buf.len() < ERROR_BODY_CAP {
        match stream.next().await {
            Some(Ok(chunk)) => {
                let take = (ERROR_BODY_CAP - buf.len()).min(chunk.len());
                buf.extend_from_slice(&chunk[..take]);
            }
            Some(Err(e)) => {
                return Error::from_unreadable_body(status, &e.to_string(), content_type);
            }
            None => break,
        }
    }
    Error::from_response_detailed(status, &String::from_utf8_lossy(&buf), content_type)
}

/// The `Retry-After` header as whole seconds, when present and in the
/// integer form. The HTTP date form is left unread.
fn retry_after_of(response: &reqwest::Response) -> Option<u64> {
    response
        .headers()
        .get(reqwest::header::RETRY_AFTER)
        .and_then(|v| v.to_str().ok())
        .and_then(|s| s.trim().parse::<u64>().ok())
}

fn content_type_of(response: &reqwest::Response) -> Option<String> {
    response
        .headers()
        .get(reqwest::header::CONTENT_TYPE)
        .and_then(|v| v.to_str().ok())
        .map(str::to_owned)
}

fn validate_place_id(place_id: &str) -> Result<(), Error> {
    if place_id.trim().is_empty()
        || place_id.contains('/')
        || place_id.contains(char::is_whitespace)
        || place_id == "."
        || place_id == ".."
        || place_id
            .chars()
            .any(|c| matches!(c, '?' | '#' | '%' | '\\') || c.is_control())
    {
        return Err(Error::config(format!("invalid place id: {place_id:?}")));
    }
    Ok(())
}

fn validate_circle_radius(radius: f64) -> Result<(), Error> {
    if !(radius > 0.0 && radius <= 50_000.0) {
        return Err(Error::config(format!(
            "circle radius must be in (0, 50000] meters, got {radius}"
        )));
    }
    Ok(())
}

/// A bias circle may touch either bound, unlike a restriction circle.
fn validate_bias_circle_radius(radius: f64) -> Result<(), Error> {
    if !(0.0..=50_000.0).contains(&radius) {
        return Err(Error::config(format!(
            "bias circle radius must be in [0, 50000] meters, got {radius}"
        )));
    }
    Ok(())
}

fn validate_min_rating(min_rating: Option<f64>) -> Result<(), Error> {
    if let Some(rating) = min_rating {
        // Documented range 0 to 5 at a 0.5 cadence; the API rounds up to
        // the nearest 0.5, so only the range is enforced here.
        if !(0.0..=5.0).contains(&rating) {
            return Err(Error::config(format!(
                "min_rating must be between 0 and 5, got {rating}"
            )));
        }
    }
    Ok(())
}

fn validate_max_result_count(max_result_count: Option<u32>) -> Result<(), Error> {
    if let Some(count) = max_result_count {
        if !(1..=20).contains(&count) {
            return Err(Error::config(format!(
                "max_result_count must be between 1 and 20, got {count}"
            )));
        }
    }
    Ok(())
}

/// Session tokens must be URL and filename safe base64 strings of at most
/// 36 ASCII characters; anything else earns an INVALID_ARGUMENT from the
/// API, so it is rejected locally instead (F14).
fn validate_session_token(token: &str) -> Result<(), Error> {
    let valid = !token.is_empty()
        && token.len() <= 36
        && token
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_');
    if !valid {
        return Err(Error::config(format!(
            "invalid session token: {token:?} (expected URL safe base64, at most 36 characters)"
        )));
    }
    Ok(())
}

fn validate_text_search_locations(request: &TextSearchRequest) -> Result<(), Error> {
    if request.location_bias.is_some() && request.location_restriction.is_some() {
        return Err(Error::config(
            "location_bias and location_restriction cannot both be set",
        ));
    }
    if let Some(bias) = &request.location_bias {
        validate_location_shape("location_bias", &bias.rectangle, &bias.circle)?;
    }
    Ok(())
}

/// One location value carries a rectangle or a circle, never both, and a
/// bias circle radius stays in range. Shared by Text Search and
/// Autocomplete, whose location types differ but whose rules and error
/// wording are the same; `label` names the field in the message.
fn validate_location_shape(
    label: &str,
    rectangle: &Option<Viewport>,
    circle: &Option<Circle>,
) -> Result<(), Error> {
    if rectangle.is_some() && circle.is_some() {
        return Err(Error::config(format!(
            "{label} carries either a rectangle or a circle, not both"
        )));
    }
    if let Some(circle) = circle {
        validate_bias_circle_radius(circle.radius)?;
    }
    Ok(())
}

/// Percent encode one URL path segment. Unreserved characters and the
/// base64url characters place ids use pass through unchanged.
fn encode_path_segment(segment: &str) -> String {
    let mut out = String::with_capacity(segment.len());
    for byte in segment.bytes() {
        match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(byte as char)
            }
            _ => {
                out.push_str(&format!("%{byte:02X}"));
            }
        }
    }
    out
}

/// Percent encode a photo resource name segment by segment, keeping
/// the structural slashes. Segments are validated before this runs;
/// encoding is the second line of defense, so a future validator gap
/// still cannot change the request path.
fn encode_photo_name(photo_name: &str) -> String {
    photo_name
        .split('/')
        .map(encode_path_segment)
        .collect::<Vec<_>>()
        .join("/")
}

/// Check a downloaded photo body against the format its content type
/// claims, for the formats with a fixed signature. A body shorter
/// than the signature or not matching it is a decode failure, not an
/// image; unlisted image types pass unchecked.
fn validate_photo_magic(
    bytes: &[u8],
    content_type: Option<&str>,
    status: u16,
) -> Result<(), Error> {
    let claimed = content_type.map(|ct| {
        ct.split(';')
            .next()
            .unwrap_or("")
            .trim()
            .to_ascii_lowercase()
    });
    let matches_claim = match claimed.as_deref() {
        Some("image/jpeg") => bytes.starts_with(&[0xFF, 0xD8, 0xFF]),
        Some("image/png") => bytes.starts_with(&[0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),
        Some("image/gif") => bytes.starts_with(b"GIF8"),
        Some("image/webp") => {
            bytes.len() >= 12 && &bytes[..4] == b"RIFF" && &bytes[8..12] == b"WEBP"
        }
        _ => return Ok(()),
    };
    if matches_claim {
        Ok(())
    } else {
        Err(Error::Decode {
            detail: format!(
                "photo body does not match its declared content type {}",
                claimed.unwrap_or_default()
            ),
            status: Some(status),
        })
    }
}

fn validate_photo_params(
    photo_name: &str,
    max_width_px: Option<u32>,
    max_height_px: Option<u32>,
) -> Result<(), Error> {
    // The documented shape is exactly places/{id}/photos/{ref}: four
    // segments, no more path separators than the structure carries,
    // and neither id nor reference empty.
    let segments: Vec<&str> = photo_name.split('/').collect();
    let shape_ok = segments.len() == 4
        && segments[0] == "places"
        && segments[2] == "photos"
        && !segments[1].is_empty()
        && !segments[3].is_empty();
    if !shape_ok {
        return Err(Error::config(format!(
            "invalid photo resource name: {photo_name:?} (expected places/{{id}}/photos/{{ref}})"
        )));
    }
    // Nothing in a valid name can reshape the URL or the query string,
    // and no segment may be a dot segment that collapses the path.
    if photo_name
        .chars()
        .any(|c| matches!(c, '?' | '#' | '%' | '\\') || c.is_control())
        || segments.iter().any(|seg| *seg == ".." || *seg == ".")
    {
        return Err(Error::config(format!(
            "invalid photo resource name: {photo_name:?} (unexpected characters or path segments)"
        )));
    }
    if max_width_px.is_none() && max_height_px.is_none() {
        return Err(Error::config(
            "place_photo requires max_width_px or max_height_px",
        ));
    }
    for (label, value) in [
        ("max_width_px", max_width_px),
        ("max_height_px", max_height_px),
    ] {
        if let Some(v) = value {
            if v == 0 || v > 4800 {
                return Err(Error::config(format!(
                    "{label} must be in 1..=4800, got {v}"
                )));
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::LatLng;

    fn test_client() -> Client {
        Client::builder("test-key")
            .base_url("http://127.0.0.1:9/v1")
            .build()
            .unwrap()
    }

    #[test]
    fn builder_rejects_empty_api_key() {
        assert_eq!(Client::new("  ").unwrap_err().kind(), "config");
        assert_eq!(Client::new("").unwrap_err().kind(), "config");
    }

    #[test]
    fn builder_rejects_api_key_that_cannot_be_a_header() {
        // A control character would make header construction drop the key
        // silently; the builder now fails instead (F13).
        assert_eq!(Client::new("bad\nkey").unwrap_err().kind(), "config");
        assert_eq!(Client::new("bad\u{1}key").unwrap_err().kind(), "config");
    }

    #[test]
    fn headers_carry_api_key_and_field_mask() {
        let client = test_client();
        let mask = FieldMask::new(vec!["places.id".to_owned()]).unwrap();
        let headers = client.headers(Some(&mask)).unwrap();
        assert_eq!(headers.get("x-goog-api-key").unwrap(), "test-key");
        assert_eq!(headers.get("x-goog-fieldmask").unwrap(), "places.id");
        let bare = client.headers(None).unwrap();
        assert!(bare.get("x-goog-fieldmask").is_none());
    }

    #[test]
    fn base_url_trailing_slash_is_trimmed() {
        let client = Client::builder("k")
            .base_url("http://localhost:8080/v1/")
            .build()
            .unwrap();
        assert_eq!(client.base_url, "http://localhost:8080/v1");
    }

    #[test]
    fn text_search_request_building() {
        let client = test_client();
        let req = TextSearchRequest {
            text_query: "pizza in Sydney".to_owned(),
            ..Default::default()
        };
        let mask = FieldMask::text_search_default();
        let request = client
            .http
            .post(format!("{}/places:searchText", client.base_url))
            .headers(client.headers(Some(&mask)).unwrap())
            .json(&req)
            .build()
            .unwrap();
        assert_eq!(request.method(), reqwest::Method::POST);
        assert_eq!(
            request.url().as_str(),
            "http://127.0.0.1:9/v1/places:searchText"
        );
        assert_eq!(
            request.headers().get("x-goog-fieldmask").unwrap(),
            mask.header_value().as_str()
        );
        let body = String::from_utf8(request.body().unwrap().as_bytes().unwrap().to_vec()).unwrap();
        let value: serde_json::Value = serde_json::from_str(&body).unwrap();
        assert_eq!(value["textQuery"], "pizza in Sydney");
    }

    #[test]
    fn place_id_validation() {
        assert!(validate_place_id("ChIJrTLr-GyuEmsRBfy61i59si0").is_ok());
        assert_eq!(validate_place_id("").unwrap_err().kind(), "config");
        assert_eq!(
            validate_place_id("places/ChIJ").unwrap_err().kind(),
            "config"
        );
        assert_eq!(validate_place_id("has space").unwrap_err().kind(), "config");
    }

    #[test]
    fn place_id_validation_rejects_url_hostile_ids() {
        // Each of these reshaped the request URL when it was only
        // interpolated: query injection, fragment truncation, path
        // collapse, and pre-encoded traversal.
        for hostile in [
            "ChIJ?sessionToken=evil",
            "ChIJ#fragment",
            ".",
            "..",
            "ChIJ%2e%2e",
            "back\\slash",
            "tab\tchar",
        ] {
            assert_eq!(
                validate_place_id(hostile).unwrap_err().kind(),
                "config",
                "{hostile}"
            );
        }
    }

    #[test]
    fn circle_radius_validation() {
        assert!(validate_circle_radius(1.0).is_ok());
        assert!(validate_circle_radius(50_000.0).is_ok());
        assert!(validate_circle_radius(0.0).is_err());
        assert!(validate_circle_radius(50_001.0).is_err());
    }

    #[test]
    fn photo_param_validation() {
        let name = "places/ChIJ/photos/ATJ83zh8";
        assert!(validate_photo_params(name, Some(400), None).is_ok());
        assert!(validate_photo_params(name, None, Some(4800)).is_ok());
        // No dimensions at all is a client-side error.
        assert_eq!(
            validate_photo_params(name, None, None).unwrap_err().kind(),
            "config"
        );
        // Out-of-range dimensions.
        assert!(validate_photo_params(name, Some(0), None).is_err());
        assert!(validate_photo_params(name, Some(4801), None).is_err());
        // Malformed resource names.
        assert!(validate_photo_params("ChIJ", Some(1), None).is_err());
        assert!(validate_photo_params("places/ChIJ", Some(1), None).is_err());
    }

    #[test]
    fn photo_name_validation_rejects_traversal_and_forgery() {
        // The traversal form escaped the media path entirely (with the
        // API key query attached); the forged form smuggled a second
        // key parameter; the rest break the documented shape.
        for hostile in [
            "places/ChIJ/photos/../../../../etc/passwd",
            "places/../photos/x",
            "places/ChIJ/photos/ref?key=forged",
            "places/ChIJ/photos/ref#frag",
            "places/ChIJ/photos/re%2f",
            "places/ChIJ/photos/ref/extra",
            "places//photos/ref",
            "places/ChIJ/photos/",
            "places/ChIJ/images/ref",
        ] {
            assert_eq!(
                validate_photo_params(hostile, Some(1), None)
                    .unwrap_err()
                    .kind(),
                "config",
                "{hostile}"
            );
        }
    }

    #[test]
    fn photo_magic_must_match_the_declared_type() {
        let png = [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 1, 2];
        assert!(validate_photo_magic(&png, Some("image/png"), 200).is_ok());
        assert!(validate_photo_magic(&png, Some("image/png; charset=binary"), 200).is_ok());
        // A one byte body claims PNG and matches nothing.
        assert_eq!(
            validate_photo_magic(&[0x89], Some("image/png"), 200)
                .unwrap_err()
                .kind(),
            "decode"
        );
        // JPEG bytes under a PNG claim fail; under their own claim pass.
        let jpeg = [0xFF, 0xD8, 0xFF, 0xE0, 9, 9];
        assert!(validate_photo_magic(&jpeg, Some("image/png"), 200).is_err());
        assert!(validate_photo_magic(&jpeg, Some("image/jpeg"), 200).is_ok());
        // Unlisted types and missing types stay permissive.
        assert!(validate_photo_magic(&[1, 2, 3], Some("image/avif"), 200).is_ok());
        assert!(validate_photo_magic(&[1, 2, 3], None, 200).is_ok());
    }

    /// Poll a future once with a no-op waker. Validation failures
    /// return before the first await point, so public method entry
    /// points can be tested without a runtime or a server.
    fn poll_once<F: std::future::Future>(fut: F) -> Option<F::Output> {
        use std::sync::Arc;
        use std::task::{Context, Poll, Wake};
        struct Noop;
        impl Wake for Noop {
            fn wake(self: Arc<Self>) {}
        }
        let waker = std::task::Waker::from(Arc::new(Noop));
        let mut cx = Context::from_waker(&waker);
        let mut fut = Box::pin(fut);
        match fut.as_mut().poll(&mut cx) {
            Poll::Ready(value) => Some(value),
            Poll::Pending => None,
        }
    }

    #[test]
    fn public_methods_validate_before_any_request() {
        // These go through the public methods, not the free helpers,
        // so a dropped validation call inside a method fails here.
        let client = test_client();
        let err = poll_once(client.place_details("ChIJ?sessionToken=evil", None, None, None, None))
            .expect("validation must resolve immediately")
            .unwrap_err();
        assert_eq!(err.kind(), "config");
        let err = poll_once(client.place_photo(
            "places/ChIJ/photos/../../../../etc/passwd",
            Some(100),
            None,
            false,
        ))
        .expect("validation must resolve immediately")
        .unwrap_err();
        assert_eq!(err.kind(), "config");
        let req = TextSearchRequest {
            text_query: "   ".to_owned(),
            ..Default::default()
        };
        let err = poll_once(client.text_search(&req, None))
            .expect("validation must resolve immediately")
            .unwrap_err();
        assert_eq!(err.kind(), "config");
    }

    #[test]
    fn nearby_request_requires_valid_circle() {
        let req = NearbySearchRequest {
            location_restriction: crate::models::LocationRestriction {
                circle: crate::models::Circle {
                    center: LatLng {
                        latitude: 0.0,
                        longitude: 0.0,
                    },
                    radius: -5.0,
                },
            },
            included_types: None,
            excluded_types: None,
            included_primary_types: None,
            excluded_primary_types: None,
            max_result_count: None,
            language_code: None,
            region_code: None,
            rank_preference: None,
            routing_parameters: None,
            include_future_opening_businesses: None,
        };
        assert_eq!(
            validate_circle_radius(req.location_restriction.circle.radius)
                .unwrap_err()
                .kind(),
            "config"
        );
    }

    #[test]
    fn min_rating_range_validation() {
        assert!(validate_min_rating(None).is_ok());
        assert!(validate_min_rating(Some(0.0)).is_ok());
        assert!(validate_min_rating(Some(5.0)).is_ok());
        assert!(validate_min_rating(Some(5.5)).is_err());
        assert!(validate_min_rating(Some(-0.5)).is_err());
    }

    #[test]
    fn nearby_max_result_count_validation() {
        assert!(validate_max_result_count(None).is_ok());
        assert!(validate_max_result_count(Some(1)).is_ok());
        assert!(validate_max_result_count(Some(20)).is_ok());
        assert!(validate_max_result_count(Some(0)).is_err());
        assert!(validate_max_result_count(Some(21)).is_err());
    }

    #[test]
    fn session_token_validation() {
        assert!(validate_session_token("dGhpcyBpcyBhIHRva2Vu").is_ok());
        assert!(validate_session_token("").is_err());
        assert!(validate_session_token(&"a".repeat(37)).is_err());
        assert!(validate_session_token("has space").is_err());
        assert!(validate_session_token("plus+slash/").is_err());
    }

    #[test]
    fn path_segment_encoding_leaves_valid_ids_alone() {
        assert_eq!(
            encode_path_segment("ChIJrTLr-GyuEmsRBfy61i59si0"),
            "ChIJrTLr-GyuEmsRBfy61i59si0"
        );
        assert_eq!(encode_path_segment("a b"), "a%20b");
        assert_eq!(encode_path_segment("a?b"), "a%3Fb");
    }
}
