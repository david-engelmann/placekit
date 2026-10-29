# Changelog

All notable changes to placekit are recorded here. The format follows Keep a Changelog, and versions follow Semantic Versioning.

## [Unreleased]

### Added

- Request parameters that previously could not be expressed, across the board. Text Search gains `page_size`, `min_rating`, `ev_options`, `search_along_route`, `routing_parameters` and the two include booleans. Nearby Search gains `included_primary_types`, `excluded_primary_types`, `routing_parameters` and `include_future_opening_businesses`. Autocomplete gains `origin`, `input_offset`, `included_primary_types`, the two include booleans and an optional `fields` mask.
- `PhotoUriResult`, returned by `place_photo` with `skip_http_redirect=True` instead of following the media redirect, carrying the photo name and its short lived URI.
- Typed response coverage for opening hour periods, address components, plus code, viewport, postal address, primary type display name and current opening hours on `Place`, the flag and maps URIs on `Photo`, the resource name on `PlacePrediction`, and `search_uri` plus `routing_summaries` on the search results.
- Parsed error envelope details on every API exception, as `error_code`, `details`, `field_violations` and `quota_violations`.
- Client side validation for `min_rating`, Nearby Search result counts, session token format, and mutually exclusive location bias and restriction values. Location values are now typed shapes end to end, so a circle in a Text Search restriction fails locally instead of at the API.
- `make check`, one gate for the whole repo (rustfmt, clippy, Rust tests, version coherence, em dash scan, Python tests), with a CI workflow that runs it word for word.
- `scripts/check_version.py`, which fails unless the version agrees across the Cargo manifests, the changelog, and the Python package, and doubles as the release tag guard in the publish workflow.
- `scripts/check_no_emdash.py`, a codepoint scan that keeps em dashes out of tracked text files.

### Changed

- Default field masks now include the place resource name on every endpoint, and the README and fields docs state plainly that the defaults reach the Enterprise billing tier.
- Header construction fails loudly on a value that cannot be sent instead of silently dropping the header, and an API key that cannot be a header value is rejected when the client is built.
- The offline test stub now honours field masks, returns autocomplete distances only for requests with an origin, and serves photos through a redirect, so the suite asserts the behaviour the real API actually has.

- Release wheels now build on native arm runners (ubuntu-24.04-arm, macos-14) instead of cross runners, with Linux wheels pinned to manylinux 2_28, and the publish job checks the tag against the manifests before uploading to PyPI through trusted publishing.
- The dev profile keeps only line-table debug info, so incremental `maturin develop` builds stay fast; the release profile is unchanged.
- The README now leads with the prebuilt wheel install story; building from source moved into a collapsed section.

## [0.1.0] - 2026-10-28

### Added

- Text Search, Nearby Search, Place Details, Autocomplete, and Place Photos against the Google Places API (New), from a typed Rust core using reqwest with rustls.
- Sync `Client` and `AsyncClient` with identical method sets, backed by one shared Tokio runtime in the bindings.
- Dataclass response models with attribute access, including `Place`, `Photo`, `AutocompleteResult`, and `PhotoMedia` with a `save()` helper.
- Field masks as a typed feature via `FieldMask`, with curated per-endpoint defaults and local validation.
- A typed exception hierarchy (`AuthenticationError`, `RateLimitError`, `NotFoundError`, `InvalidRequestError`, `NetworkError`, `DecodeError`, `ConfigError`) translated from Google error envelopes.
- A `base_url` override on both clients, enabling fully offline testing against a stub server.
- Full type stubs and a `py.typed` marker, abi3 wheels for Python 3.10 and newer, and a GitHub Actions workflow that builds wheels for Linux, macOS, and Windows and publishes tagged releases.
