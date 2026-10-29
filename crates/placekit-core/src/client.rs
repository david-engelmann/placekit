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
    AutocompleteRequest, AutocompleteResponse, Circle, EvOptions, LatLng, NearbySearchRequest,
    PhotoMedia, PhotoMediaJson, PhotoResponse, Place, SearchResponse, TextSearchRequest, Viewport,
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
    /// sent as an HTTP header value, a timeout of zero, a response cap
    /// of zero, or a base URL that does not parse, is not http or https,
    /// or carries a query string or a fragment.
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
        if self.max_response_bytes == 0 {
            return Err(Error::config(
                "max_response_bytes must be greater than zero",
            ));
        }
        let base_url = parse_base_url(&self.base_url)?;
        let http = reqwest::Client::builder()
            .timeout(self.timeout)
            .no_proxy()
            // Redirects are never followed automatically (R4-05):
            // reqwest's default policy resends the API key header to
            // whatever host a redirect names, and the Places JSON
            // endpoints do not redirect, so a redirect there surfaces
            // as an ordinary error response. The photo endpoint, which
            // does redirect, follows them manually in place_photo.
            .redirect(reqwest::redirect::Policy::none())
            .user_agent(USER_AGENT)
            .build()
            .map_err(Error::network)?;
        Ok(Client {
            api_key: self.api_key,
            base_url,
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
        validate_page_size(request.page_size)?;
        validate_text_search_locations(request)?;
        if let Some(ev) = &request.ev_options {
            validate_ev_options(ev)?;
        }
        if let Some(origin) = request
            .routing_parameters
            .as_ref()
            .and_then(|r| r.origin.as_ref())
        {
            validate_lat_lng(origin, "routing_parameters origin")?;
        }
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
        validate_circle(
            &request.location_restriction.circle,
            "location_restriction circle",
            true,
        )?;
        validate_max_result_count(request.max_result_count)?;
        if let Some(origin) = request
            .routing_parameters
            .as_ref()
            .and_then(|r| r.origin.as_ref())
        {
            validate_lat_lng(origin, "routing_parameters origin")?;
        }
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
        // An empty optional value means "not supplied" and is omitted,
        // not sent as an empty query parameter (R4-23, the query side
        // of the R4-17 body rule).
        let mut query: Vec<(&str, &str)> = Vec::new();
        if let Some(v) = language_code {
            if !v.is_empty() {
                query.push(("languageCode", v));
            }
        }
        if let Some(v) = region_code {
            if !v.is_empty() {
                query.push(("regionCode", v));
            }
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
                source: None,
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
            validate_location_shape("location_bias", &location.rectangle, &location.circle, false)?;
        }
        if let Some(location) = &request.location_restriction {
            validate_location_shape(
                "location_restriction",
                &location.rectangle,
                &location.circle,
                true,
            )?;
        }
        if let Some(origin) = &request.origin {
            validate_lat_lng(origin, "origin")?;
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
        let response = self.fetch_photo(&url, &query).await?;
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
            if let Some(err) =
                envelope_error(status.as_u16(), &body, content_type.as_deref(), retry_after)
            {
                return Err(err);
            }
            let media: PhotoMediaJson = serde_json::from_str(&body).map_err(|e| Error::Decode {
                detail: e.to_string(),
                status: Some(status.as_u16()),
                source: Some(Box::new(e)),
            })?;
            // The same identity guard Place Details carries (R4-06):
            // a success body with neither a name nor a URI is the
            // wrong shape entirely, not a photo result pointing at an
            // empty URI.
            if media.name.is_empty() && media.photo_uri.is_empty() {
                return Err(Error::Decode {
                    detail: "photo media response carried no name or photo uri".to_owned(),
                    status: Some(status.as_u16()),
                    source: None,
                });
            }
            return Ok(PhotoMedia::Uri(media));
        }
        // The body is read and checked for an error envelope before
        // any content type reasoning. Real error responses carry
        // application/json, so gating on the declared type first
        // would throw the envelope's status and message away; only a
        // body that is not an envelope goes on to the declared type
        // gate and the magic bytes check that judge an image claim.
        let bytes = self
            .read_capped_body(response, status, "photo body")
            .await?;
        if let Ok(text) = std::str::from_utf8(&bytes) {
            if let Some(err) =
                envelope_error(status.as_u16(), text, content_type.as_deref(), retry_after)
            {
                return Err(err);
            }
        }
        // A photo body must declare an image content type (R4-06).
        // Accepting bytes with no declared type let a redirect target
        // serve anything at all (an HTML error page, a metadata
        // response) and have it handed back as a photo.
        match &content_type {
            Some(ct) if ct.starts_with("image/") => {}
            Some(ct) => {
                return Err(Error::Decode {
                    detail: format!("photo endpoint returned a non-image content type: {ct}"),
                    status: Some(status.as_u16()),
                    source: None,
                });
            }
            None => {
                return Err(Error::Decode {
                    detail: "photo endpoint returned no content type; refusing to treat the body as an image".to_owned(),
                    status: Some(status.as_u16()),
                    source: None,
                });
            }
        }
        validate_photo_magic(&bytes, content_type.as_deref(), status.as_u16())?;
        Ok(PhotoMedia::Bytes(PhotoResponse {
            bytes,
            content_type,
        }))
    }

    /// Fetch the photo resource, following redirects manually. The
    /// shared reqwest client never follows redirects on its own
    /// (R4-05), so this loop is the one place they are followed: at
    /// most ten hops, each `Location` resolved against the current
    /// URL. The query string (which carries the API key) is attached
    /// to the first request only; a redirect target receives whatever
    /// its own URL says, never the key (the R4-05 test's wire evidence
    /// showed reqwest did not forward it either, and here that is by
    /// construction). Every transport failure goes through the
    /// redacted mapping (R4-07), because the failing URL embeds the
    /// key.
    async fn fetch_photo(
        &self,
        url: &str,
        query: &[(&str, String)],
    ) -> Result<reqwest::Response, Error> {
        const MAX_PHOTO_REDIRECTS: u32 = 10;
        let mut current = reqwest::Url::parse(url)
            .map_err(|e| Error::config(format!("invalid photo request URL: {e}")))?;
        {
            let mut pairs = current.query_pairs_mut();
            for (name, value) in query {
                pairs.append_pair(name, value);
            }
        }
        let mut hops = 0;
        loop {
            let response = self
                .http
                .get(current.clone())
                .send()
                .await
                .map_err(Error::network_redacted)?;
            if !matches!(response.status().as_u16(), 301 | 302 | 303 | 307 | 308) {
                return Ok(response);
            }
            let location = response
                .headers()
                .get(reqwest::header::LOCATION)
                .and_then(|v| v.to_str().ok())
                .map(str::to_owned);
            let Some(location) = location else {
                // A redirect status with nowhere to go is the final
                // response; the caller's status handling judges it.
                return Ok(response);
            };
            hops += 1;
            if hops > MAX_PHOTO_REDIRECTS {
                return Err(Error::network_detail(format!(
                    "redirect: too many redirects (over {MAX_PHOTO_REDIRECTS}) following the photo resource"
                )));
            }
            current = current.join(&location).map_err(|e| {
                Error::network_detail(format!(
                    "redirect: the photo endpoint sent an invalid redirect location: {e}"
                ))
            })?;
        }
    }

    /// Read a success response body as text under the size cap, for the
    /// JSON form of the photo endpoint. Failures keep the HTTP status.
    async fn read_success_text(
        &self,
        response: reqwest::Response,
        status: reqwest::StatusCode,
    ) -> Result<String, Error> {
        let bytes = self
            .read_capped_body(response, status, "response body")
            .await?;
        String::from_utf8(bytes).map_err(|e| Error::Decode {
            detail: format!("response body was not valid UTF-8: {e}"),
            status: Some(status.as_u16()),
            source: Some(Box::new(e)),
        })
    }

    /// Read a success response body under the size cap, mapping the
    /// outcome onto the errors every endpoint shares. Over the cap is
    /// a decode error naming the cap; a failed read is a decode error
    /// that keeps the HTTP status as data (R4-10: the failure used to
    /// be classified Network, whose contract is that no response was
    /// produced, and the status survived only as message prose).
    /// `label` names the body in the cap message: "response body" on
    /// the JSON paths, "photo body" on the photo bytes path, whose
    /// wording predates this shared helper.
    async fn read_capped_body(
        &self,
        response: reqwest::Response,
        status: reqwest::StatusCode,
        label: &str,
    ) -> Result<Vec<u8>, Error> {
        match read_body_capped(response, self.max_response_bytes).await {
            BodyRead::Complete(bytes) => Ok(bytes),
            BodyRead::TooLarge => Err(Error::Decode {
                detail: format!(
                    "{label} exceeded the maximum of {} bytes",
                    self.max_response_bytes
                ),
                status: Some(status.as_u16()),
                source: None,
            }),
            BodyRead::Failed(read_error) => Err(Error::Decode {
                detail: format!(
                    "HTTP {} received, body read failed: {read_error}",
                    status.as_u16()
                ),
                status: Some(status.as_u16()),
                source: None,
            }),
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
        let bytes = self
            .read_capped_body(response, status, "response body")
            .await?;
        let body = match String::from_utf8(bytes) {
            Ok(text) => text,
            Err(e) => {
                return Err(Error::Decode {
                    detail: format!("response body was not valid UTF-8: {e}"),
                    status: Some(status.as_u16()),
                    source: Some(Box::new(e)),
                });
            }
        };
        // An error envelope on a success status is an error, exactly
        // as if it had arrived on its own HTTP code.
        if let Some(err) =
            envelope_error(status.as_u16(), &body, content_type.as_deref(), retry_after)
        {
            return Err(err);
        }
        serde_json::from_str::<T>(&body)
            .map(|value| (value, status.as_u16()))
            .map_err(|e| Error::Decode {
                detail: e.to_string(),
                status: Some(status.as_u16()),
                source: Some(Box::new(e)),
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

/// The mapped error for a success response whose body is actually a
/// Google error envelope, with the response's `Retry-After` attached,
/// or `None` when the body carries no envelope. Shared by the JSON
/// paths and both photo branches so the check and the error
/// construction cannot drift apart.
fn envelope_error(
    status: u16,
    body: &str,
    content_type: Option<&str>,
    retry_after: Option<u64>,
) -> Option<Error> {
    if Error::has_error_envelope(body) {
        Some(
            Error::from_response_detailed(status, body, content_type).with_retry_after(retry_after),
        )
    } else {
        None
    }
}

/// The `Retry-After` header as whole seconds, when present. Both
/// forms are read (R4-25): delta seconds, and the HTTP date form,
/// where a date in the past yields zero (retry now). An unparseable
/// value is left unread, as before.
fn retry_after_of(response: &reqwest::Response) -> Option<u64> {
    let raw = response
        .headers()
        .get(reqwest::header::RETRY_AFTER)?
        .to_str()
        .ok()?;
    parse_retry_after(raw, std::time::SystemTime::now())
}

fn parse_retry_after(raw: &str, now: std::time::SystemTime) -> Option<u64> {
    let raw = raw.trim();
    if let Ok(seconds) = raw.parse::<u64>() {
        return Some(seconds);
    }
    let when = httpdate::parse_http_date(raw).ok()?;
    match when.duration_since(now) {
        Ok(duration) => Some(duration.as_secs()),
        Err(_) => Some(0),
    }
}

fn content_type_of(response: &reqwest::Response) -> Option<String> {
    response
        .headers()
        .get(reqwest::header::CONTENT_TYPE)
        .and_then(|v| v.to_str().ok())
        .map(str::to_owned)
}

/// Parse and normalize a configured base URL (R4-02). The value used
/// to be interpolated unchecked, so a base carrying a query string or
/// a fragment silently rerouted every request (the endpoint path
/// landed inside the query) and still built. Now the base must parse,
/// must be http or https with a host, and must carry neither a query
/// nor a fragment. Parsing also resolves dot segments in the path, so
/// a configured prefix cannot be escaped by the appended endpoint
/// path. A trailing slash is trimmed as before, and path prefixes
/// (the documented stub form `http://host:port/v1`) keep working.
fn parse_base_url(raw: &str) -> Result<String, Error> {
    let url = url::Url::parse(raw.trim())
        .map_err(|e| Error::config(format!("base_url is not a valid URL: {e}")))?;
    if url.scheme() != "http" && url.scheme() != "https" {
        return Err(Error::config(format!(
            "base_url scheme must be http or https, got {:?}",
            url.scheme()
        )));
    }
    if url.host_str().is_none() {
        return Err(Error::config("base_url must name a host"));
    }
    if url.query().is_some() || url.fragment().is_some() {
        return Err(Error::config(
            "base_url must not carry a query string or a fragment",
        ));
    }
    Ok(url.to_string().trim_end_matches('/').to_owned())
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

fn validate_page_size(page_size: Option<u32>) -> Result<(), Error> {
    if let Some(size) = page_size {
        if !(1..=20).contains(&size) {
            return Err(Error::config(format!(
                "page_size must be between 1 and 20, got {size}"
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
        validate_location_shape("location_bias", &bias.rectangle, &bias.circle, false)?;
    }
    if let Some(restriction) = &request.location_restriction {
        validate_viewport(&restriction.rectangle, "location_restriction rectangle")?;
    }
    Ok(())
}

/// Coordinates are validated in the core, where requests are
/// assembled, not only in the Python layer (R4-03): a non-finite
/// coordinate serializes as JSON null and an out-of-range one passes
/// to the wire unchanged, so both are local errors here. Latitude
/// must be finite and within -90 to 90, longitude finite and within
/// -180 to 180, exactly the ranges the API documents.
fn validate_lat_lng(point: &LatLng, label: &str) -> Result<(), Error> {
    if !point.latitude.is_finite() || !(-90.0..=90.0).contains(&point.latitude) {
        return Err(Error::config(format!(
            "{label} latitude must be finite and within -90 to 90, got {}",
            point.latitude
        )));
    }
    if !point.longitude.is_finite() || !(-180.0..=180.0).contains(&point.longitude) {
        return Err(Error::config(format!(
            "{label} longitude must be finite and within -180 to 180, got {}",
            point.longitude
        )));
    }
    Ok(())
}

fn validate_viewport(viewport: &Viewport, label: &str) -> Result<(), Error> {
    validate_lat_lng(&viewport.low, &format!("{label} low"))?;
    validate_lat_lng(&viewport.high, &format!("{label} high"))
}

/// Validate a circle's center and radius. Restriction circles use the
/// strict radius rule (greater than 0, at most 50000; the zero radius
/// autocomplete restriction of R4-21 fails here); bias circles may
/// touch either bound, the rule the API documents for a bias.
fn validate_circle(circle: &Circle, label: &str, restriction: bool) -> Result<(), Error> {
    validate_lat_lng(&circle.center, &format!("{label} center"))?;
    if restriction {
        validate_circle_radius(circle.radius)
    } else {
        validate_bias_circle_radius(circle.radius)
    }
}

/// EV option values are caller supplied floats; a non-finite one
/// serializes as JSON null (R4-03), so it is rejected locally.
fn validate_ev_options(ev: &EvOptions) -> Result<(), Error> {
    if let Some(rate) = ev.minimum_charging_rate_kw {
        if !rate.is_finite() {
            return Err(Error::config(format!(
                "ev_options minimum_charging_rate_kw must be finite, got {rate}"
            )));
        }
    }
    Ok(())
}

/// One location value carries exactly one shape: a rectangle or a
/// circle, never both and never neither (R4-14). The carried shape is
/// validated as well: corners and center against the coordinate
/// ranges, and the circle radius against the bias bounds for a bias
/// or the strict bounds for a restriction (a zero radius restriction
/// circle fails, R4-21). Shared by Text Search and Autocomplete,
/// whose location types differ but whose rules and error wording are
/// the same; `label` names the field in the message.
fn validate_location_shape(
    label: &str,
    rectangle: &Option<Viewport>,
    circle: &Option<Circle>,
    restriction: bool,
) -> Result<(), Error> {
    match (rectangle, circle) {
        (Some(_), Some(_)) => Err(Error::config(format!(
            "{label} carries either a rectangle or a circle, not both"
        ))),
        (None, None) => Err(Error::config(format!(
            "{label} must carry a rectangle or a circle"
        ))),
        (Some(rectangle), None) => validate_viewport(rectangle, label),
        (None, Some(circle)) => {
            validate_circle(circle, &format!("{label} circle"), restriction)
        }
    }
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
            source: None,
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
    fn base_url_with_query_or_fragment_is_a_config_error() {
        // R4-02: these used to build, and the query form silently
        // rerouted every request (the endpoint path landed inside the
        // query string) while the wrong empty reply decoded as a
        // legitimate empty result.
        for bad in [
            "http://localhost:8080/v1?tenant=acme",
            "http://localhost:8080/v1#frag",
            "localhost:8080/v1",
            "ftp://localhost:8080/v1",
        ] {
            assert_eq!(
                Client::builder("k").base_url(bad).build().unwrap_err().kind(),
                "config",
                "{bad}"
            );
        }
    }

    #[test]
    fn base_url_dot_segments_cannot_escape_the_prefix() {
        // R4-02: parsing resolves dot segments, so the stored base is
        // the normalized prefix and appended endpoint paths stay in it.
        let client = Client::builder("k")
            .base_url("http://127.0.0.1:9/a/../v1")
            .build()
            .unwrap();
        assert_eq!(client.base_url, "http://127.0.0.1:9/v1");
        let client = Client::builder("k")
            .base_url("http://127.0.0.1:9/v1/./")
            .build()
            .unwrap();
        assert_eq!(client.base_url, "http://127.0.0.1:9/v1");
    }

    #[test]
    fn builder_rejects_zero_max_response_bytes() {
        // R4-20: a zero cap used to build and then fail every call as
        // a misleading decode error.
        let err = Client::builder("k")
            .max_response_bytes(0)
            .build()
            .unwrap_err();
        assert_eq!(err.kind(), "config");
    }

    #[test]
    fn retry_after_parses_delta_seconds_and_http_dates() {
        // R4-25: both header forms are read; a past date is zero.
        let now = httpdate::parse_http_date("Sun, 06 Nov 1994 08:49:37 GMT").unwrap();
        assert_eq!(parse_retry_after("7", now), Some(7));
        assert_eq!(
            parse_retry_after("Thu, 06 Nov 2994 08:49:37 GMT", now),
            Some(31_556_995_200)
        );
        let later = httpdate::parse_http_date("Thu, 06 Nov 2994 08:49:37 GMT").unwrap();
        assert_eq!(
            parse_retry_after("Sun, 06 Nov 1994 08:49:37 GMT", later),
            Some(0)
        );
        assert_eq!(parse_retry_after("whenever", now), None);
    }

    #[test]
    fn public_methods_validate_coordinates_and_shapes() {
        // R4-03, R4-14, R4-21 through the public methods: every one of
        // these used to reach the wire (NaN as JSON null, out-of-range
        // unchanged, a shapeless location, a zero radius restriction).
        let client = test_client();
        let nearby = |center: LatLng, radius: f64| NearbySearchRequest {
            location_restriction: crate::models::LocationRestriction {
                circle: Circle { center, radius },
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
        for req in [
            nearby(LatLng::new(f64::NAN, 151.2), 100.0),
            nearby(LatLng::new(91.0, 151.2), 100.0),
            nearby(LatLng::new(-33.86, f64::INFINITY), 100.0),
            nearby(LatLng::new(-33.86, 151.2), f64::NAN),
        ] {
            let err = poll_once(client.nearby_search(&req, None))
                .expect("validation must resolve immediately")
                .unwrap_err();
            assert_eq!(err.kind(), "config");
        }
        // An infinite EV charging rate serializes as null; rejected.
        let req = TextSearchRequest {
            text_query: "charging".to_owned(),
            ev_options: Some(EvOptions {
                minimum_charging_rate_kw: Some(f64::INFINITY),
                connector_types: None,
            }),
            ..Default::default()
        };
        let err = poll_once(client.text_search(&req, None))
            .expect("validation must resolve immediately")
            .unwrap_err();
        assert_eq!(err.kind(), "config");
        // A bias carrying neither shape violates the one-shape rule.
        let req = TextSearchRequest {
            text_query: "cafes".to_owned(),
            location_bias: Some(crate::models::TextSearchLocationBias {
                rectangle: None,
                circle: None,
            }),
            ..Default::default()
        };
        let err = poll_once(client.text_search(&req, None))
            .expect("validation must resolve immediately")
            .unwrap_err();
        assert_eq!(err.kind(), "config");
        // A zero radius autocomplete restriction circle fails, where a
        // zero radius bias circle stays allowed by the bias rule.
        let req = AutocompleteRequest {
            input: "Bianco".to_owned(),
            location_restriction: Some(crate::models::AutocompleteLocation {
                rectangle: None,
                circle: Some(Circle {
                    center: LatLng::new(-33.86, 151.2),
                    radius: 0.0,
                }),
            }),
            ..Default::default()
        };
        let err = poll_once(client.autocomplete(&req, None))
            .expect("validation must resolve immediately")
            .unwrap_err();
        assert_eq!(err.kind(), "config");
        let req = AutocompleteRequest {
            input: "Bianco".to_owned(),
            location_bias: Some(crate::models::AutocompleteLocation {
                rectangle: None,
                circle: Some(Circle {
                    center: LatLng::new(-33.86, 151.2),
                    radius: 0.0,
                }),
            }),
            ..Default::default()
        };
        // And the same bias on the wire succeeds against the stub,
        // proving the valid shape passes validation end to end.
        let stub = Stub::start(|_| stub_json(200, r#"{"suggestions":[]}"#));
        let stub_client = stub.client("k");
        let result = block_on(stub_client.autocomplete(&req, None)).unwrap();
        assert!(result.suggestions.is_empty());
    }

    #[test]
    fn text_search_sends_the_built_request_to_the_wire() {
        // Drives Client::text_search itself against the recording
        // stub (R4-28). The previous version rebuilt the request by
        // hand from the client's internals and asserted on its own
        // construction, so a change to the endpoint path, a dropped
        // mask header or a broken body serialization inside
        // text_search would have failed nothing.
        let stub = Stub::start(|_| stub_json(200, r#"{"places":[]}"#));
        let client = stub.client("test-key");
        let req = TextSearchRequest {
            text_query: "pizza in Sydney".to_owned(),
            ..Default::default()
        };
        let result = block_on(client.text_search(&req, None)).unwrap();
        assert!(result.places.is_empty());
        let requests = stub.requests();
        assert_eq!(requests.len(), 1);
        let sent = &requests[0];
        assert_eq!(sent.method, "POST");
        assert_eq!(sent.path, "/v1/places:searchText");
        assert_eq!(sent.header("x-goog-api-key"), Some("test-key"));
        let mask = FieldMask::text_search_default();
        assert_eq!(
            sent.header("x-goog-fieldmask"),
            Some(mask.header_value().as_str())
        );
        let body: serde_json::Value = serde_json::from_slice(&sent.body).unwrap();
        assert_eq!(body["textQuery"], "pizza in Sydney");
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
        let req = TextSearchRequest {
            text_query: "cafes".to_owned(),
            page_size: Some(0),
            ..Default::default()
        };
        let err = poll_once(client.text_search(&req, None))
            .expect("validation must resolve immediately")
            .unwrap_err();
        assert_eq!(err.kind(), "config");
    }

    #[test]
    fn nearby_search_rejects_an_invalid_circle_before_any_request() {
        // Drives Client::nearby_search itself (R4-28). The previous
        // version called the free radius validator directly, so
        // deleting the validation call from nearby_search would have
        // failed nothing. Validation resolves before any request is
        // attempted, so the call must complete with the config error
        // under a single poll; if validation is dropped, the future
        // proceeds to the network and the poll stays pending.
        let client = test_client();
        let req = NearbySearchRequest {
            location_restriction: crate::models::LocationRestriction {
                circle: crate::models::Circle {
                    center: LatLng::new(0.0, 0.0),
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
        let err = poll_once(client.nearby_search(&req, None))
            .expect("validation must resolve immediately")
            .unwrap_err();
        assert_eq!(err.kind(), "config");
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
    fn page_size_validation() {
        assert!(validate_page_size(None).is_ok());
        assert!(validate_page_size(Some(1)).is_ok());
        assert!(validate_page_size(Some(20)).is_ok());
        assert!(validate_page_size(Some(0)).is_err());
        assert!(validate_page_size(Some(21)).is_err());
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

    // -- Recording HTTP stub --------------------------------------------
    //
    // A minimal HTTP server on a loopback port: every request is
    // recorded (method, path, headers, body) and answered by the
    // test's handler, so tests assert on what actually went over the
    // wire. Responses end the connection, keeping one request per
    // connection and the ordering simple.

    #[derive(Debug, Clone)]
    struct RecordedRequest {
        method: String,
        path: String,
        headers: Vec<(String, String)>,
        body: Vec<u8>,
    }

    impl RecordedRequest {
        fn header(&self, name: &str) -> Option<&str> {
            self.headers
                .iter()
                .find(|(k, _)| k.eq_ignore_ascii_case(name))
                .map(|(_, v)| v.as_str())
        }
    }

    struct StubResponse {
        status: u16,
        content_type: Option<String>,
        headers: Vec<(String, String)>,
        body: Vec<u8>,
        /// Write these bytes verbatim instead of a composed response
        /// (for malformed and truncated wire shapes).
        raw: Option<Vec<u8>>,
    }

    fn stub_json(status: u16, body: &str) -> StubResponse {
        StubResponse {
            status,
            content_type: Some("application/json".to_owned()),
            headers: Vec::new(),
            body: body.as_bytes().to_vec(),
            raw: None,
        }
    }

    struct Stub {
        base_url: String,
        requests: std::sync::Arc<std::sync::Mutex<Vec<RecordedRequest>>>,
        stop: std::sync::Arc<std::sync::atomic::AtomicBool>,
        thread: Option<std::thread::JoinHandle<()>>,
    }

    impl Stub {
        fn start(
            handler: impl Fn(&RecordedRequest) -> StubResponse + Send + Sync + 'static,
        ) -> Stub {
            use std::io::{Read, Write};
            let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
            listener.set_nonblocking(true).unwrap();
            let port = listener.local_addr().unwrap().port();
            let requests = std::sync::Arc::new(std::sync::Mutex::new(Vec::new()));
            let stop = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false));
            let handler = std::sync::Arc::new(handler);
            let thread = {
                let requests = requests.clone();
                let stop = stop.clone();
                std::thread::spawn(move || {
                    while !stop.load(std::sync::atomic::Ordering::Relaxed) {
                        let mut stream = match listener.accept() {
                            Ok((stream, _)) => stream,
                            Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                                std::thread::sleep(std::time::Duration::from_millis(2));
                                continue;
                            }
                            Err(_) => break,
                        };
                        let _ = stream.set_read_timeout(Some(std::time::Duration::from_secs(5)));
                        let mut buf = Vec::new();
                        let mut chunk = [0u8; 8192];
                        let mut header_end = None;
                        let mut content_length = 0usize;
                        loop {
                            match stream.read(&mut chunk) {
                                Ok(0) => break,
                                Ok(n) => {
                                    buf.extend_from_slice(&chunk[..n]);
                                    if header_end.is_none() {
                                        if let Some(pos) = buf
                                            .windows(4)
                                            .position(|w| w == b"\r\n\r\n")
                                        {
                                            header_end = Some(pos + 4);
                                            let head =
                                                String::from_utf8_lossy(&buf[..pos]).into_owned();
                                            for line in head.lines().skip(1) {
                                                if let Some((k, v)) = line.split_once(':') {
                                                    if k.trim()
                                                        .eq_ignore_ascii_case("content-length")
                                                    {
                                                        content_length =
                                                            v.trim().parse().unwrap_or(0);
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    if let Some(end) = header_end {
                                        if buf.len() >= end + content_length {
                                            break;
                                        }
                                    }
                                }
                                Err(_) => break,
                            }
                        }
                        let Some(end) = header_end else { continue };
                        let head = String::from_utf8_lossy(&buf[..end]).into_owned();
                        let mut lines = head.lines();
                        let request_line = lines.next().unwrap_or_default().to_owned();
                        let mut parts = request_line.split_whitespace();
                        let recorded = RecordedRequest {
                            method: parts.next().unwrap_or_default().to_owned(),
                            path: parts.next().unwrap_or_default().to_owned(),
                            headers: lines
                                .filter_map(|line| {
                                    line.split_once(':')
                                        .map(|(k, v)| (k.trim().to_owned(), v.trim().to_owned()))
                                })
                                .collect(),
                            body: buf[end..].to_vec(),
                        };
                        let response = handler(&recorded);
                        requests.lock().unwrap().push(recorded);
                        let bytes = if let Some(raw) = &response.raw {
                            raw.clone()
                        } else {
                            let reason = match response.status {
                                200 => "OK",
                                301 => "Moved Permanently",
                                302 => "Found",
                                307 => "Temporary Redirect",
                                308 => "Permanent Redirect",
                                404 => "Not Found",
                                500 => "Internal Server Error",
                                _ => "Status",
                            };
                            let mut out = format!(
                                "HTTP/1.1 {} {}\r\ncontent-length: {}\r\nconnection: close\r\n",
                                response.status,
                                reason,
                                response.body.len()
                            );
                            if let Some(ct) = &response.content_type {
                                out.push_str(&format!("content-type: {ct}\r\n"));
                            }
                            for (k, v) in &response.headers {
                                out.push_str(&format!("{k}: {v}\r\n"));
                            }
                            out.push_str("\r\n");
                            let mut bytes = out.into_bytes();
                            bytes.extend_from_slice(&response.body);
                            bytes
                        };
                        let _ = stream.write_all(&bytes);
                        let _ = stream.flush();
                    }
                })
            };
            Stub {
                base_url: format!("http://127.0.0.1:{port}"),
                requests,
                stop,
                thread: Some(thread),
            }
        }

        fn client(&self, api_key: &str) -> Client {
            Client::builder(api_key)
                .base_url(format!("{}/v1", self.base_url))
                .build()
                .unwrap()
        }

        fn requests(&self) -> Vec<RecordedRequest> {
            self.requests.lock().unwrap().clone()
        }
    }

    impl Drop for Stub {
        fn drop(&mut self) {
            self.stop.store(true, std::sync::atomic::Ordering::Relaxed);
            if let Some(thread) = self.thread.take() {
                let _ = thread.join();
            }
        }
    }

    fn block_on<F: std::future::Future>(fut: F) -> F::Output {
        tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .unwrap()
            .block_on(fut)
    }

    const PNG_BYTES: &[u8] = &[0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 1, 2, 3];

    #[test]
    fn redirect_on_a_json_endpoint_never_resends_the_api_key() {
        // R4-05: stub A answers a 308 naming stub B; B must receive
        // nothing at all, and the caller sees the redirect as an
        // error, because redirects are not followed on JSON endpoints.
        let target = Stub::start(|_| stub_json(200, r#"{"places":[]}"#));
        let target_location = format!("{}/v1/places:searchText", target.base_url);
        let source = Stub::start(move |_| {
            let mut response = stub_json(308, "");
            response
                .headers
                .push(("location".to_owned(), target_location.clone()));
            response
        });
        let client = source.client("secret-key");
        let req = TextSearchRequest {
            text_query: "cafes".to_owned(),
            ..Default::default()
        };
        let err = block_on(client.text_search(&req, None)).unwrap_err();
        assert_eq!(err.kind(), "api");
        assert_eq!(err.status_code(), Some(308));
        assert!(target.requests().is_empty());
    }

    #[test]
    fn photo_follows_redirects_and_requires_an_image_content_type() {
        // R4-06: the photo endpoint's redirect is followed manually to
        // the image host, and its bytes are accepted. The same bytes
        // with no declared content type are refused.
        let image = Stub::start(|_| StubResponse {
            status: 200,
            content_type: Some("image/png".to_owned()),
            headers: Vec::new(),
            body: PNG_BYTES.to_vec(),
            raw: None,
        });
        let image_location = format!("{}/img", image.base_url);
        let media = Stub::start(move |_| {
            let mut response = stub_json(302, "");
            response
                .headers
                .push(("location".to_owned(), image_location.clone()));
            response
        });
        let client = media.client("k");
        let result = block_on(client.place_photo("places/ChIJ/photos/ref", Some(100), None, false))
            .unwrap();
        match result {
            PhotoMedia::Bytes(photo) => {
                assert_eq!(photo.bytes, PNG_BYTES);
                assert_eq!(photo.content_type.as_deref(), Some("image/png"));
            }
            PhotoMedia::Uri(_) => panic!("expected downloaded bytes"),
        }
        assert_eq!(image.requests().len(), 1);

        let untyped = Stub::start(|_| StubResponse {
            status: 200,
            content_type: None,
            headers: Vec::new(),
            body: b"INTERNAL SERVICE RESPONSE".to_vec(),
            raw: None,
        });
        let client = untyped.client("k");
        let err = block_on(client.place_photo("places/ChIJ/photos/ref", Some(100), None, false))
            .unwrap_err();
        assert_eq!(err.kind(), "decode");
    }

    #[test]
    fn photo_skip_redirect_empty_object_is_a_decode_error() {
        // R4-06: the JSON photo form applies the identity guard Place
        // Details already had; an empty object is not a photo result.
        let stub = Stub::start(|_| stub_json(200, "{}"));
        let client = stub.client("k");
        let err = block_on(client.place_photo("places/ChIJ/photos/ref", Some(100), None, true))
            .unwrap_err();
        assert_eq!(err.kind(), "decode");
        let stub = Stub::start(|_| {
            stub_json(200, r#"{"name":"places/ChIJ/photos/ref","photoUri":"https://example.test/img"}"#)
        });
        let client = stub.client("k");
        let result = block_on(client.place_photo("places/ChIJ/photos/ref", Some(100), None, true))
            .unwrap();
        match result {
            PhotoMedia::Uri(media) => {
                assert_eq!(media.photo_uri, "https://example.test/img");
            }
            PhotoMedia::Bytes(_) => panic!("expected the URI form"),
        }
    }

    #[test]
    fn photo_transport_errors_never_carry_the_api_key() {
        // R4-07: the photo URL embeds the key as a query parameter, so
        // a transport failure against a dead endpoint must not surface
        // the key in the error text.
        let client = Client::builder("SECRET-KEY-123")
            .base_url("http://127.0.0.1:9/v1")
            .build()
            .unwrap();
        let err = block_on(client.place_photo("places/ChIJ/photos/ref", Some(100), None, false))
            .unwrap_err();
        assert_eq!(err.kind(), "network");
        assert!(
            !err.to_string().contains("SECRET-KEY-123"),
            "error leaked the key: {err}"
        );
    }

    #[test]
    fn failed_body_read_on_a_success_status_keeps_the_status() {
        // R4-10: headers arrive with a 200 and a promised length, then
        // the connection drops mid body. The error is a decode error
        // whose status_code is the HTTP status, as data.
        let stub = Stub::start(|_| StubResponse {
            status: 200,
            content_type: None,
            headers: Vec::new(),
            body: Vec::new(),
            raw: Some(
                b"HTTP/1.1 200 OK\r\ncontent-type: application/json\r\ncontent-length: 100\r\nconnection: close\r\n\r\n{\"places\":"
                    .to_vec(),
            ),
        });
        let client = stub.client("k");
        let req = TextSearchRequest {
            text_query: "cafes".to_owned(),
            ..Default::default()
        };
        let err = block_on(client.text_search(&req, None)).unwrap_err();
        assert_eq!(err.kind(), "decode");
        assert_eq!(err.status_code(), Some(200));
    }
}
