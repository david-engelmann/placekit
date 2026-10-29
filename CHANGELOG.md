# Changelog

All notable changes to placekit are recorded here. The format follows Keep a Changelog, and versions follow Semantic Versioning.

## [Unreleased]

### Added

- Request parameters that previously could not be expressed, across the board. Text Search gains `page_size`, `min_rating`, `ev_options`, `search_along_route`, `routing_parameters` and the two include booleans. Nearby Search gains `included_primary_types`, `excluded_primary_types`, `routing_parameters` and `include_future_opening_businesses`. Autocomplete gains `origin`, `input_offset`, `included_primary_types`, the two include booleans and an optional `fields` mask.
- `PhotoUriResult`, returned by `place_photo` with `skip_http_redirect=True` instead of following the media redirect, carrying the photo name and its short lived URI.
- Typed response coverage for opening hour periods, address components, plus code, viewport, postal address, primary type display name and current opening hours on `Place`, the flag and maps URIs on `Photo`, the resource name on `PlacePrediction`, and `search_uri` plus `routing_summaries` on the search results.
- Parsed error envelope details on every API exception, as `error_code`, `details`, `field_violations` and `quota_violations`.
- A configurable response size cap on the Rust core builder, defaulting to 32 MiB.
- Client side validation for `min_rating`, Nearby Search result counts, session token format, and mutually exclusive location bias and restriction values. Location values are now typed shapes end to end, so a circle in a Text Search restriction fails locally instead of at the API.
- `make check`, one gate for the whole repo (rustfmt, clippy, Rust tests, version coherence, em dash scan, Python tests), with a CI workflow that runs it word for word.
- `scripts/check_version.py`, which fails unless the version agrees across the Cargo manifests, the changelog, and the Python package, and doubles as the release tag guard in the publish workflow.
- `scripts/check_no_emdash.py`, a codepoint scan that keeps em dashes out of tracked text files.
- Core side validation of request coordinates, circle radii and EV charging rates, so non-finite or out-of-range values fail locally with a configuration error instead of serializing as JSON null or passing to the API unchanged.
- `Retry-After` headers in HTTP date form are read alongside the delta seconds form, with a date in the past meaning retry now.

### Changed

- A circle in a Text Search location restriction now raises `ConfigError`, the same type as the other local validations, instead of a bare `ValueError` outside the exception hierarchy.
- Client construction and `FieldMask` raise `ConfigError` for empty keys, invalid timeouts and invalid mask paths instead of bare `ValueError`, so every local misuse has the one documented type.
- Default field masks now include the place resource name on every endpoint, and the README and fields docs state plainly that the defaults reach the Enterprise billing tier.
- Header construction fails loudly on a value that cannot be sent instead of silently dropping the header, and an API key that cannot be a header value is rejected when the client is built.
- The offline test stub now honours field masks, returns autocomplete distances only for requests with an origin, and serves photos through a redirect, so the suite asserts the behaviour the real API actually has.

- Release wheels now build on native arm runners (ubuntu-24.04-arm, macos-14) instead of cross runners, with Linux wheels pinned to manylinux 2_28, and the publish job checks the tag against the manifests before uploading to PyPI through trusted publishing.
- Client construction validates the base URL. A base URL carrying a query string or a fragment, or one whose scheme is not http or https, fails at build time instead of silently rerouting every request, while path prefixes keep working and dot segments can no longer escape the configured prefix.
- The Rust core no longer follows redirects automatically, so the API key header can never be resent to a redirect target. Photo media redirects are followed manually with the API key attached to the first request only.
- Field masks reject duplicate paths, empty segments, wildcard segments and non-ASCII characters, and are bounded at 100 paths and a 4096 character header value.
- The native module rejects timeout values above one hour, the same cap the Python clients document, instead of only the Python layer enforcing it.
- Errors from the Rust core keep their underlying transport or decode cause as a typed source instead of flattening it into message prose.
- Decoded response values are passed through without clamping or range checks, a deliberate posture now stated in the core documentation. The client is a transport and does not hide what the API returned, and request values the caller controls are validated before sending instead.
- The dev profile keeps only line-table debug info, so incremental `maturin develop` builds stay fast; the release profile is unchanged.
- The README now leads with the prebuilt wheel install story; building from source moved into a collapsed section.

### Fixed

- Error envelopes that arrive on a success HTTP status now raise the typed exception for their Google status on every endpoint, photos included, instead of decoding as empty results or returning the envelope JSON as image bytes.
- Response bodies are read under a size cap, gzipped bodies decompress, and a failed body read keeps both the HTTP status and the read failure in the resulting error instead of dropping one of them.
- Photo downloads are checked against their declared content type and the signature of the format it claims before the bytes can be saved as an image, and photo failures served by an image host after a redirect are worded as image host failures.
- Place ids and photo resource names are validated strictly and percent encoded segment by segment, closing query injection, fragment truncation and path traversal through both values.
- Non-finite timeout values raise `ConfigError` instead of panicking across the FFI boundary, timeouts are bounded at one hour, and numeric arguments such as result counts and photo dimensions are range validated in Python before they reach the core.
- Envelope error messages are capped at 500 characters, `google_status` is `None` rather than an empty string when no envelope status was parsed, server side canonical statuses such as `DEADLINE_EXCEEDED` classify as `ApiError` instead of falling through to the HTTP classes, and truncated non-envelope bodies say they were truncated.
- Exceptions now carry `status_mismatch`, `retryable`, `retry_after` and `context` attributes, model conversion failures raise `DecodeError` instead of escaping as bare builtin exceptions, and unknown top level fields on Autocomplete responses survive into `raw` as they already did on search.
- `page_size` gets the same range validation as the other numeric arguments instead of reaching the API unchecked or leaking an internal conversion error, error envelopes carrying a code or a message but no status string raise the exception their numeric code maps to instead of succeeding silently, and error envelopes on the photo download path raise that mapped exception with its Google status and server message instead of a decode error that dropped both.
- Partial nested response objects decode with defaults instead of failing the entire response, so a location carrying only a latitude, a viewport carrying only one corner, or a circle carrying only a center no longer poisons every place in the result.
- Unknown fields inside nested response objects are preserved into the raw view like top level fields, counts and dimensions that arrive string encoded or as exactly integral floats decode normally, a zero start offset in autocomplete matches survives reserialization, and unknown fields carrying integers beyond 64 bits keep every digit.
- One mistyped field in an error envelope no longer discards the Google status, message and details the rest of the envelope carried, and retryability follows the HTTP status on every error type that carries one instead of only one variant.
- A failed photo request can no longer leak the API key into the exception message through the photo URL, a photo response with no declared image content type is refused instead of being returned as photo bytes, an empty JSON object in the skip redirect photo form is a decode error instead of a photo result pointing at an empty URI, and a failed body read after a success status carries that status on the error instead of losing it.
- Empty optional strings and lists are omitted from request bodies and empty Place Details query parameters are omitted, instead of being sent as empty values whose meaning differs from absence at the API, and a zero response size cap is rejected when the client is built instead of failing every call.

## [0.1.0] - 2026-10-28

### Added

- Text Search, Nearby Search, Place Details, Autocomplete, and Place Photos against the Google Places API (New), from a typed Rust core using reqwest with rustls.
- Sync `Client` and `AsyncClient` with identical method sets, backed by one shared Tokio runtime in the bindings.
- Dataclass response models with attribute access, including `Place`, `Photo`, `AutocompleteResult`, and `PhotoMedia` with a `save()` helper.
- Field masks as a typed feature via `FieldMask`, with curated per-endpoint defaults and local validation.
- A typed exception hierarchy (`AuthenticationError`, `RateLimitError`, `NotFoundError`, `InvalidRequestError`, `NetworkError`, `DecodeError`, `ConfigError`) translated from Google error envelopes.
- A `base_url` override on both clients, enabling fully offline testing against a stub server.
- Full type stubs and a `py.typed` marker, abi3 wheels for Python 3.10 and newer, and a GitHub Actions workflow that builds wheels for Linux, macOS, and Windows and publishes tagged releases.
