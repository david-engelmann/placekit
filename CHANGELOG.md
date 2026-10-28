# Changelog

All notable changes to places-api are recorded here. The format follows Keep a Changelog, and versions follow Semantic Versioning.

## [Unreleased]

## [0.1.0] - 2026-10-28

### Added

- Text Search, Nearby Search, Place Details, Autocomplete, and Place Photos against the Google Places API (New), from a typed Rust core using reqwest with rustls.
- Sync `Client` and `AsyncClient` with identical method sets, backed by one shared Tokio runtime in the bindings.
- Dataclass response models with attribute access, including `Place`, `Photo`, `AutocompleteResult`, and `PhotoMedia` with a `save()` helper.
- Field masks as a typed feature via `FieldMask`, with curated per-endpoint defaults and local validation.
- A typed exception hierarchy (`AuthenticationError`, `RateLimitError`, `NotFoundError`, `InvalidRequestError`, `NetworkError`, `DecodeError`, `ConfigError`) translated from Google error envelopes.
- A `base_url` override on both clients, enabling fully offline testing against a stub server.
- Full type stubs and a `py.typed` marker, abi3 wheels for Python 3.10 and newer, and a GitHub Actions workflow that builds wheels for Linux, macOS, and Windows and publishes tagged releases.
