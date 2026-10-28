# Changelog

All notable changes to placekit are recorded here. The format follows Keep a Changelog, and versions follow Semantic Versioning.

## [Unreleased]

### Added

- `make check`, one gate for the whole repo (rustfmt, clippy, Rust tests, version coherence, em dash scan, Python tests), with a CI workflow that runs it word for word.
- `scripts/check_version.py`, which fails unless the version agrees across the Cargo manifests, the changelog, and the Python package, and doubles as the release tag guard in the publish workflow.
- `scripts/check_no_emdash.py`, a codepoint scan that keeps em dashes out of tracked text files.

### Changed

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
