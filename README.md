# placekit

A modern client for the Google Places API (New), with a Rust core and a Python surface that feels native.

```bash
pip install placekit
```

Prebuilt wheels cover CPython 3.10 and newer on Linux (x86_64 and aarch64 with glibc 2.28 or newer), macOS (Intel on 10.12 or newer, Apple silicon on 11 or newer), and Windows (x64). Installing is a single small download with zero runtime dependencies. There is nothing to compile and no Rust toolchain is needed. Only if your platform has no wheel does pip fall back to the source distribution. That happens on musl systems such as Alpine and on anything below the floors above, and a source install has its own requirements, covered under Building from source below.

Most Places libraries in Python are wrappers around the retired legacy API, or thin HTTP helpers that hand you back raw JSON. placekit targets the current Places API (New) end to end, with typed request building, field masks as a first-class feature, dataclass response models, and an exception hierarchy that tells you what actually went wrong.

## Building from source

When pip finds no wheel it downloads the source distribution and builds it locally. That build needs a Rust toolchain at version 1.88 or newer (rustup installs one), network access while it downloads the crate dependencies from crates.io, and the platform C toolchain. With those in place a source install just works, only slower than a wheel.

Without a Rust toolchain the build backend tries to download and bootstrap one by itself, and when that fails the error talks about cargo metadata rather than the missing toolchain. If a source install fails, install Rust first and retry before debugging anything else. Wheels remain the recommended path wherever one exists.

## Quickstart

```python
from placekit import Client

client = Client("YOUR_API_KEY")

result = client.text_search("cafes in Sydney")
for place in result.places:
    print(place.display_text, place.rating, place.formatted_address)

details = client.place_details(result.places[0])
print(details.national_phone_number, details.website_uri)

photo = client.place_photo(details.photos[0], max_width_px=800)
photo.save("cafe.jpg")
```

An `AsyncClient` with the identical method set is included for async code.

```python
import asyncio
from placekit import AsyncClient

async def main():
    client = AsyncClient("YOUR_API_KEY")
    result = await client.text_search("cafes in Sydney")
    print([p.display_text for p in result.places])

asyncio.run(main())
```

The sync `Client` refuses to run inside a running event loop, raising a `ConfigError` that points at `AsyncClient` instead of freezing the loop for the length of a request. Inside async code, use `AsyncClient`.

## Why a Rust core

- One abi3 wheel per platform serves every Python from 3.10 up, so installs on the platforms above are a single small download with no compiler, no build step, and zero runtime dependencies.
- TLS comes from rustls, never OpenSSL, so wheels do not break across system library versions.
- Requests are typed and validated in Rust before anything goes over the wire. A bad field mask or an out-of-range photo size fails locally, not at the API.
- The sync and async clients share one core, so their behavior cannot drift apart.
- Connections ignore proxy environment variables and go direct, which keeps behavior identical on a laptop, in CI, and against a local test server.

## Endpoints

| Method | Endpoint | Returns |
| --- | --- | --- |
| `text_search` | `POST /v1/places:searchText` | `TextSearchResult` with a `next_page_token` for paging |
| `nearby_search` | `POST /v1/places:searchNearby` | `NearbySearchResult` |
| `place_details` | `GET /v1/places/{id}` | `Place` |
| `autocomplete` | `POST /v1/places:autocomplete` | `AutocompleteResult` |
| `place_photo` | `GET /v1/{photo}/media` | `PhotoMedia` with the image bytes |

## Field masks

The Places API (New) only returns the fields named in the `X-Goog-FieldMask` header, and billing follows the fields requested. placekit treats the mask as a typed feature instead of a string you assemble by hand.

```python
from placekit import FieldMask

result = client.text_search(
    "cafes in Sydney",
    fields=FieldMask("places.displayName", "places.rating"),
)
```

Any iterable of path strings works too. Omit `fields` and each endpoint uses a curated default, available as `FieldMask.text_search()`, `FieldMask.nearby_search()`, and `FieldMask.place_details()`.

One billing note on the defaults. They include fields from the Enterprise billing tier, among them rating, user rating counts and price level, so a search call with a default mask is billed at the Enterprise tier. Place Details is the exception. Its default mask requests every modelled field, including current opening hours from the higher Enterprise plus Atmosphere tier, so a default `place_details` call is billed at that tier. Pass a narrower `fields` set when you want a lower tier.

## Constants

Three modules carry the vocabularies callers pass most often, as plain strings that drop into the existing parameters. `placekit.types` holds the place type vocabulary from the official Place Types page, `placekit.lang` holds the supported language codes, and `placekit.ranking` holds the ranking preferences split by method, because Text Search and Nearby Search accept different sets.

```python
from placekit import lang, ranking, types

result = client.nearby_search(
    (-33.8668, 151.2071),
    800.0,
    included_types=[types.TYPE_CAFE],
    language=lang.ENGLISH,
    rank_preference=ranking.DISTANCE,
)
```

The modules are snapshots of the official tables and a convenience only. The client accepts any string in these slots, including values this version has never heard of, so a type or language the API adds tomorrow works without waiting for a placekit release.

## Errors

Every failure raises a subclass of `PlacesError`, carrying `status_code` and `google_status` when the error came from the API.

Classification follows the Google envelope status first and the HTTP code second, so the exception class and `status_code` can come from different sources. A quota envelope on an HTTP 500 is a `RateLimitError` with `status_code` 500, and the `status_mismatch` attribute is True whenever the envelope code and the HTTP status disagree. API exceptions also carry `retryable`, which says whether a caller side retry can plausibly succeed, and `retry_after`, the seconds from a `Retry-After` header when the response sent one. Every exception carries `context`, naming the call that failed.

| Exception | Raised when |
| --- | --- |
| `AuthenticationError` | The key was rejected or lacks permission, HTTP 401 or 403 |
| `RateLimitError` | Quota is exhausted or the rate limit is hit, HTTP 429 |
| `NotFoundError` | The resource does not exist, HTTP 404 |
| `InvalidRequestError` | The request was malformed, HTTP 400 |
| `NetworkError` | No HTTP response was produced |
| `DecodeError` | A success body did not match the expected shape |
| `ConfigError` | The client was called incorrectly, detected before any request |

Local validation follows one coercion rule everywhere. Numbers must be real and finite, bools are never numbers, and strings are never lists, so a value of the wrong kind fails as a `ConfigError` before any request instead of being converted into something else on the wire.

```python
from placekit import Client, RateLimitError

client = Client("YOUR_API_KEY")
try:
    client.text_search("cafes in Sydney")
except RateLimitError as exc:
    print("quota", exc.status_code, exc.google_status)
```

## Pointing the client somewhere else

`Client` and `AsyncClient` accept `base_url` and `timeout` keyword arguments. The base URL override is how the test suite runs fully offline against a local stub server, and it works just as well for proxies you control and regional endpoints.

```python
client = Client("YOUR_API_KEY", base_url="http://127.0.0.1:8080/v1", timeout=5.0)
```

## Development

You need a Rust toolchain at version 1.88 or newer and Python 3.10 or newer. The dev loop builds in debug mode, so it stays fast.

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/maturin develop
.venv/bin/python -m pytest
cargo test -p placekit-core
```

On Windows the venv binaries live under `.venv\Scripts`, so the same steps use `.venv\Scripts\pip`, `.venv\Scripts\maturin` and `.venv\Scripts\python`.

`maturin develop` compiles the Rust core without optimizations and installs it into the venv; iterate with the targeted commands above. The full gate is one command, and CI runs it word for word:

```bash
make check
```

That runs the rustfmt and clippy checks, the Rust test suite, a version coherence check across the manifests, the lockfile and the changelog, an em dash scan, a stubtest pass over the type stubs, and the Python suite.

The test suites need no Google API key and no network. Python tests run against a local stub server that serves recorded fixtures, and the Rust tests decode the same fixtures.

<details>
<summary>Build a release wheel from source</summary>

```bash
pip install "maturin>=1.7,<2.0"
maturin build --release --locked
pip install target/wheels/*.whl
```

In PowerShell on Windows the shell does not expand that glob, so the install step hands the wheel to pip through Get-ChildItem.

```powershell
pip install (Get-ChildItem target\wheels\*.whl).FullName
```

You normally never need this. The Linux wheels are built by GitHub Actions inside manylinux containers, the macOS and Windows wheels are built on native runners for their architectures, and pushing a version tag publishes them to PyPI through trusted publishing from the same workflow.

A wheel built this way on a local machine is tied to that machine. On Linux it carries the local glibc as its floor, 2.34 on a current Ubuntu, not the manylinux 2_28 floor of the released wheels. A local build is for testing and is never a substitute for a released wheel.

The wheels carry no SBOM and no build attestation in this setup. The release trust story is the commit SHA pin on every action in the workflow together with PyPI trusted publishing, which ties each upload to this repository and workflow. Generating a CycloneDX SBOM for each wheel is a named future candidate, not a property of the current builds.

</details>

## License

MIT
