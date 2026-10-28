# places-api

A modern client for the Google Places API (New), with a Rust core and a Python surface that feels native.

```bash
pip install places-api
```

Most Places libraries in Python are wrappers around the retired legacy API, or thin HTTP helpers that hand you back raw JSON. places-api targets the current Places API (New) end to end, with typed request building, field masks as a first-class feature, dataclass response models, and an exception hierarchy that tells you what actually went wrong.

## Quickstart

```python
from places_api import Client

client = Client("YOUR_API_KEY")

result = client.text_search("cafes in Sydney")
for place in result.places:
    print(place.display_text, place.rating, place.formatted_address)

details = client.place_details(result.places[0].id)
print(details.national_phone_number, details.website_uri)

photo = client.place_photo(details.photos[0].name, max_width_px=800)
photo.save("cafe.jpg")
```

An `AsyncClient` with the identical method set is included for async code.

```python
import asyncio
from places_api import AsyncClient

async def main():
    client = AsyncClient("YOUR_API_KEY")
    result = await client.text_search("cafes in Sydney")
    print([p.display_text for p in result.places])

asyncio.run(main())
```

## Why a Rust core

- One abi3 wheel per platform serves every Python from 3.10 up. Installs are a single small download, with no compiler, no build step, and zero runtime dependencies.
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

The Places API (New) only returns the fields named in the `X-Goog-FieldMask` header, and billing follows the fields requested. places-api treats the mask as a typed feature instead of a string you assemble by hand.

```python
from places_api import FieldMask

result = client.text_search(
    "cafes in Sydney",
    fields=FieldMask("places.displayName", "places.rating"),
)
```

Any iterable of path strings works too. Omit `fields` and each endpoint uses a curated default, available as `FieldMask.text_search()`, `FieldMask.nearby_search()`, and `FieldMask.place_details()`.

## Errors

Every failure raises a subclass of `PlacesError`, carrying `status_code` and `google_status` when the error came from the API.

| Exception | Raised when |
| --- | --- |
| `AuthenticationError` | The key was rejected or lacks permission, HTTP 401 or 403 |
| `RateLimitError` | Quota is exhausted or the rate limit is hit, HTTP 429 |
| `NotFoundError` | The resource does not exist, HTTP 404 |
| `InvalidRequestError` | The request was malformed, HTTP 400 |
| `NetworkError` | No HTTP response was produced |
| `DecodeError` | A success body did not match the expected shape |
| `ConfigError` | The client was called incorrectly, detected before any request |

```python
from places_api import Client, RateLimitError

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

You need a Rust toolchain and Python 3.10 or newer.

```bash
python -m venv .venv
.venv/bin/pip install maturin pytest
.venv/bin/maturin develop
.venv/bin/python -m pytest
cargo test -p places-core
```

The test suites need no Google API key and no network. Python tests run against a local stub server that serves recorded fixtures, and the Rust tests decode the same fixtures.

Wheels for Linux, macOS, and Windows are built by GitHub Actions with maturin, and tagged releases publish to PyPI from the same workflow.

## License

MIT
