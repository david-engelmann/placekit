# placekit

A modern client for the Google Places API (New), with a Rust core and a Python surface that feels native.

```bash
pip install placekit
```

Prebuilt wheels cover CPython 3.10 and newer on Linux (x86_64 and aarch64 with glibc 2.28 or newer), macOS (Intel on 10.12 or newer, Apple silicon on 11 or newer), and Windows (x64). Installing is a single small download with zero runtime dependencies. There is nothing to compile and no Rust toolchain is needed. Only if your platform has no wheel does pip fall back to the source distribution. That happens on musl systems such as Alpine and on anything below the floors above, and a source install has its own requirements, covered under Building from source below.

Most Places libraries in Python are wrappers around the retired legacy API, or thin HTTP helpers that hand you back raw JSON. placekit targets the current Places API (New) end to end, with typed request building, field masks as a first-class feature, dataclass response models, and an exception hierarchy that tells you what actually went wrong. Google ships an official client for this API too, the generated google-maps-places package, and it is the right choice when you want the surface exactly as Google generates it. placekit is the hand shaped alternative over the same API, covering the five endpoints below with typed models whose raw attribute is the response body itself, and carrying no runtime dependencies.

## Building from source

When pip finds no wheel it downloads the source distribution and builds it locally. That build needs a Rust toolchain at version 1.88 or newer (rustup installs one), network access while it downloads the crate dependencies from crates.io, and the platform C toolchain. With those in place a source install just works, only slower than a wheel.

Without a Rust toolchain the build backend tries to download and bootstrap one by itself, and when that fails the error talks about cargo metadata rather than the missing toolchain. If a source install fails, install Rust first and retry before debugging anything else. Wheels remain the recommended path wherever one exists.

## Quickstart

Before the first call, the key has to be able to call the API. In the Google Cloud console, enable Places API (New) on the project the key belongs to, and restrict the key to that API so it cannot be used for anything else. A key on a project without the API enabled is rejected on every call.

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

## Coming from googleplaces

placekit targets Places API (New), and python-google-places wraps the
retired legacy API, so the port is more than an import change.
MIGRATING.md walks the four canonical legacy examples across call by
call, with the name mapping, the attribute reading contract, and the
removals named plainly.

[Migrating from python-google-places](https://github.com/david-engelmann/placekit/blob/main/MIGRATING.md)

## Why a Rust core

- One abi3 wheel per platform serves every Python from 3.10 up, so installs on the platforms above are a single small download with no compiler, no build step, and zero runtime dependencies.
- TLS comes from rustls, never OpenSSL, so wheels do not break across system library versions.
- Requests are typed and validated locally before anything goes over the wire. Field mask grammar and photo size ranges are checked on the Python side first, and the Rust core validates coordinates, radii and charging rates again on its side, so a bad field mask or an out-of-range photo size fails locally, not at the API.
- The sync and async clients share one core, so their behavior cannot drift apart.
- Connections ignore proxy environment variables and go direct, which keeps behavior identical on a laptop, in CI, and against a local test server.

## Endpoints

| Method | Endpoint | Returns |
| --- | --- | --- |
| `text_search` | `POST /v1/places:searchText` | `TextSearchResult` with a `next_page_token` for paging |
| `nearby_search` | `POST /v1/places:searchNearby` | `NearbySearchResult` |
| `place_details` | `GET /v1/places/{id}` | `Place` |
| `autocomplete` | `POST /v1/places:autocomplete` | `AutocompleteResult` split into place and query predictions |
| `place_photo` | `GET /v1/{photo}/media` | `PhotoMedia` with the image bytes, or `PhotoUriResult` in skip redirect mode |

The search and autocomplete calls take the filters their endpoints offer as keyword arguments. Text Search accepts `page_size`, `min_rating`, `open_now`, `price_levels`, `strict_type_filtering`, `included_type`, location bias and location restriction shapes, `ev_options`, `search_along_route` and `routing_parameters`. Nearby Search accepts its included and excluded type filters beside `max_results` and `routing_parameters`, and Autocomplete accepts `origin`, `input_offset` and primary type filters beside its input.

Search results page through `next_page_token`. Pass it back as `page_token` on the same call to fetch the next page.

```python
page = client.text_search("cafes in Sydney")
while page.next_page_token:
    page = client.text_search("cafes in Sydney", page_token=page.next_page_token)
```

Autocomplete and Place Details both accept `session_token`. One token ties a run of autocomplete calls to the details call that closes the session, and that grouping is the shape the API bills as one session, so an autocomplete flow in production should mint a fresh token for each session and pass it to both calls.

## Field masks

The Places API (New) only returns the fields named in the `X-Goog-FieldMask` header, and billing follows the fields requested. placekit treats the mask as a typed feature instead of a string you assemble by hand.

```python
from placekit import FieldMask

result = client.text_search(
    "cafes in Sydney",
    fields=FieldMask("places.displayName", "places.rating"),
)
```

Any iterable of path strings works too. Omit `fields` on a search or details call and that endpoint uses a curated default, available as `FieldMask.text_search()`, `FieldMask.nearby_search()`, and `FieldMask.place_details()`. Autocomplete takes an optional `fields` mask with no curated default behind it, and `place_photo` takes no `fields` argument at all.

One billing note on the defaults. They include fields from the Enterprise billing tier, among them rating, user rating counts and price level, so a search call with a default mask is billed at the Enterprise tier. Place Details is the exception. Its default mask requests every modelled field, including current opening hours from the higher Enterprise plus Atmosphere tier, so a default `place_details` call is billed at that tier. Pass a narrower `fields` set when you want a lower tier.

### Reading attributes the mask did not request

A place from a search call only carries the fields the search mask asked for. Reading an attribute outside the mask gives None, an empty list, or an empty default, never an error and never a fabricated value, and the object cannot say whether the field was unrequested or simply had no value. The `raw` attribute on every model is the response body itself rather than a reserialization of the typed fields, so a name sits in `raw` exactly when the response carried that field, and membership in `raw` is an exact record of what arrived. Two habits follow. Check membership in `raw` with the wire name when the distinction matters. Call `place_details` with the place when the full modelled set is needed, since its default mask requests every modelled field.

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

## Addresses

`placekit.address` reads the structured address a place already carries and answers the questions its two carrier sets raise. It looks components up by type and has a reader for the components that carry no type at all, reads the country and the administrative area across both carrier sets, and splits plus codes from a plus code object or a compound code string. Its `postal_code` reader returns a `PostalCodeResult` that carries the value with its carrier, a present or absent status, and any competing value the other carrier set holds, and the postal address readers read the second carrier set on its own terms. Presence helpers and an `address_flags` summary answer the shape questions about a place. City resolution is the careful part, because which carrier holds the city changes by country and the carriers sometimes disagree on the same place, so `resolve_city` returns the value with the carrier it came from and a confidence grade in the open.

```python
from placekit import address

city = address.resolve_city(place)
city.value, city.carrier, city.confidence
```

`city_resolutions` returns every reading a place supports, and where the carriers disagree the reading carries its rival on the result itself, as `competing_value` and `competing_carrier`. A British place whose locality and postal town differ therefore hands back both values with the rivalry visible, instead of one value with the other hidden.

Stated answers ship for Japan and the United Arab Emirates and the United Kingdom, each built from recorded places inside one sampled locality, and every other country follows a generic fallback chain capped at the heuristic grade. The module never parses formatted text and never composes a display address, and a resolved city is a reading of one response rather than a fact of the same kind as a place ID.

The normalization guide teaches the address handling the recorded corpus and this module embody, with an oddities catalogue of the shapes the corpus actually returned, per country readings that state how far each one reaches, worked recipes that run against the recorded fixtures, and a list of the things no helper here can promise.

[Normalizing addresses with placekit](https://github.com/david-engelmann/placekit/blob/main/NORMALIZATION.md)

## Errors

Every failure raises a subclass of `PlacesError`, carrying `status_code` and `google_status` when the error came from the API.

Classification follows the Google envelope status first and the HTTP code second, so the exception class and `status_code` can come from different sources. A quota envelope on an HTTP 500 is a `RateLimitError` with `status_code` 500, and the `status_mismatch` attribute is True whenever the envelope code and the HTTP status disagree. API exceptions also carry `retryable`, which says whether a caller side retry can plausibly succeed, and `retry_after`, the seconds from a `Retry-After` header when the response sent one. Every exception carries `context`, naming the call that failed. API exceptions also carry the parsed envelope details, as `error_code` and `details` and `field_violations` and `quota_violations`, so a rejected request shows which fields it broke and which quota it hit.

| Exception | Raised when |
| --- | --- |
| `AuthenticationError` | The key was rejected or lacks permission, HTTP 401 or 403 |
| `RateLimitError` | Quota is exhausted or the rate limit is hit, HTTP 429 |
| `NotFoundError` | The resource does not exist, HTTP 404 |
| `InvalidRequestError` | The request was malformed, HTTP 400 |
| `ApiError` | A canonical Google status with no narrower class, such as deadline exceeded |
| `NetworkError` | No HTTP response was produced |
| `DecodeError` | A success body did not match the expected shape |
| `ConfigError` | The client was called incorrectly, detected before any request |

`QuotaError` is exported as an alias of `RateLimitError`, so either name catches a quota failure.

Local validation follows one coercion rule everywhere. Numbers must be real and finite, bools are never numbers, and strings are never lists, so a value of the wrong kind fails as a `ConfigError` before any request instead of being converted into something else on the wire.

```python
from placekit import Client, RateLimitError

client = Client("YOUR_API_KEY")
try:
    client.text_search("cafes in Sydney")
except RateLimitError as exc:
    print("quota", exc.status_code, exc.google_status)
```

## Concurrency and lifecycle

One `Client` may be shared across threads, and one `AsyncClient` may be shared across tasks and used from more than one event loop. Calls on a shared client run concurrently, and each call returns its own result.

`close()` gates later calls with `ConfigError`. It neither cancels nor waits for calls already in flight, and those calls finish with their own results. Closing is idempotent, and the context managers close on exit.

Cancelling a task that is awaiting an `AsyncClient` call drops the wire request, and the same client stays fully usable for the next call.

Each client instance holds its own connection pool, so a program holding a `Client` and an `AsyncClient` for the same work holds two pools. Pool sizes and the idle expiry are the inherited reqwest defaults, with no configuration surface in placekit. The idle expiry is ninety seconds under the reqwest version the current release locks, and that figure is an inherited default rather than a placekit promise, so a future reqwest update can move it. Under parallel async load the upstream pool can also open a connection that ends up carrying no request. Every client in one process shares a single Tokio runtime that is built on first use and lives for the life of the process, holding its worker threads until the process exits. Connection counts observed against a local stub also carry a transport limit, because the stub speaks HTTP 1.1 with keep alive while the real API can multiplex over HTTP 2.

A result is the holder's to mutate in place, within the shallow freeze the models document. Mutating a result while other threads read it is not safe. A reader can meet a typed view and a raw view that no longer agree, and a reader iterating a list or a raw dict while it changes can fail with a `RuntimeError`. Share a result between threads only when nobody mutates it, or hand each thread its own result.

A process may fork after using placekit. The bindings detect the new process on the next call and rebuild their runtime and client state for the child, so calls in the child work on fresh and inherited clients alike. The native module does not load under subinterpreters, so a host that runs application code inside subinterpreters cannot use this library. One ordering consequence is worth knowing. If a subinterpreter attempts the import before the main interpreter has imported the module, the main interpreter import afterwards fails too, so the refusal is not contained to the subinterpreter in that order. Work through the Python `Client` and `AsyncClient` classes. The native module behind them is private, and direct use of it is unsupported.

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

That runs the rustfmt and clippy checks, the Rust test suite, a version coherence check across the manifests, the lockfile and the changelog, an em dash scan, a maturin develop build, a stubtest pass over the type stubs, and the Python suite.

The test suites need no Google API key and no network. The client tests run against a local stub server that serves recorded fixtures, and the Rust tests decode the same fixtures. The corpus conformance and accounting suites and the proof suites for both guides decode the recorded fixtures directly, and none of them passes through the stub server.

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

Each wheel carries an embedded CycloneDX SBOM that the build generates for the Rust dependency tree, stored inside the wheel under its dist-info sboms folder. The release trust story is that SBOM together with the commit SHA pin on every action in the workflow and PyPI trusted publishing, which ties each upload to this repository and workflow.

</details>

## License

MIT
