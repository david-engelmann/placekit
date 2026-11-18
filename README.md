# placekit

[![PyPI version](https://img.shields.io/pypi/v/placekit)](https://pypi.org/project/placekit/)
[![Supported Pythons](https://img.shields.io/pypi/pyversions/placekit)](https://pypi.org/project/placekit/)
[![CI](https://github.com/david-engelmann/placekit/actions/workflows/ci.yml/badge.svg)](https://github.com/david-engelmann/placekit/actions/workflows/ci.yml)

Modern Google Places API (New) client for Python, powered by a Rust core.

placekit targets the current Places API (New) end to end, with typed request building, field masks as a first-class feature, dataclass response models, and an exception hierarchy that tells you what actually went wrong. Google ships an official client for this API too, the generated google-maps-places package, and it is the right choice when you want the surface exactly as Google generates it. placekit is the hand shaped alternative over the same API, covering the five endpoints in the reference with typed models whose raw attribute is the response body itself, with the one exception of PhotoMedia, the downloaded photo form, which carries no raw.

The current release is 0.1.1, dated 2026-11-15. It changes no library behavior, and the install below is the whole evaluation path.

[Documentation](docs/README.md) · [Examples](examples/README.md) · [Changelog](CHANGELOG.md) · [Migrating from python-google-places](docs/MIGRATING.md)

## Contents

- [Install](#install)
- [Quickstart](#quickstart)
- [Coming from googleplaces](#coming-from-googleplaces)
- [Why a Rust core](#why-a-rust-core)
- [Reference](#reference)
- [Concurrency and lifecycle](#concurrency-and-lifecycle)
- [Pointing the client somewhere else](#pointing-the-client-somewhere-else)
- [Building from source](#building-from-source)
- [Development](#development)
- [License](#license)

## Install

```bash
pip install placekit
```

Prebuilt wheels cover CPython 3.10 and newer on Linux (x86_64 and aarch64 with glibc 2.28 or newer), macOS (Intel on 10.12 or newer, Apple silicon on 11 or newer), and Windows (x64). Installing is a single small download with zero runtime dependencies. There is nothing to compile and no Rust toolchain is needed. Only if your platform has no wheel does pip fall back to the source distribution. That happens on musl systems such as Alpine and on anything below the floors above, and a source install has its own requirements, covered under Building from source below.

Verify the install without a key. Field masks are built locally, so this runs offline, and it prints the header value a mask sends.

```bash
python -c "from placekit import FieldMask; print(FieldMask('places.displayName').header_value)"
```

```
places.displayName
```

Before the first live call, the key has to be able to call the API. In the Google Cloud console, enable Places API (New) on the project the key belongs to, and restrict the key to that API so it cannot be used for anything else. A key on a project without the API enabled is rejected on every call, and the project needs billing enabled, because the API charges per call and by the tier of the fields requested.

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

The key may be omitted from the constructor, in which case the client reads the `PLACEKIT_API_KEY` environment variable, and construction refuses when neither is present.

The search loop prints one line per place. Output recorded from the live API:

```
Bianco Latte 4.6 Shop 1/123 George St, Sydney NSW 2000, Australia
Harbour Espresso 4.4 45 Circular Quay W, The Rocks NSW 2000, Australia
(02) 5550 1234 https://example.com/
```

The examples folder runs the search and details calls offline against the recorded responses, so the output above is reproducible without a key.

The photo call downloads the image itself by default. Pass `skip_http_redirect=True` to `place_photo` instead and the call returns a `PhotoUriResult` whose `photo_uri` attribute carries the photo URI, for callers who would rather fetch the image themselves or hand the URI to something else. The size is set with `max_width_px`, with `max_height_px` as the other member of the size pair beside it, and each value runs from 1 to 4800. At least one of the pair is required when the photo is passed by name, and a call by name with neither raises `ConfigError` before any request. Pass a `Photo` object instead of its name and one size defaults from the photo itself when neither is given.

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
The migration guide walks the four canonical legacy examples across call by
call, with the name mapping, the attribute reading contract, and the
removals named plainly.

[Migrating from python-google-places](docs/MIGRATING.md)

## Why a Rust core

- One abi3 wheel per platform serves every Python from 3.10 up, so installs on the platforms above need no compiler and no build step.
- TLS comes from rustls, never OpenSSL, so wheels do not break across system library versions.
- Requests are typed and validated locally before anything goes over the wire. Field mask grammar and photo size ranges are checked on the Python side first, and the Rust core validates coordinates, radii and charging rates again on its side, so a bad field mask or an out-of-range photo size fails locally, not at the API.
- The sync and async clients share one core, so their behavior cannot drift apart.
- Connections ignore proxy environment variables and go direct, which keeps behavior identical on a laptop, in CI, and against a local test server.

## Reference

The reference lives in the docs folder, one file per subject, under one index.

- [Endpoints](docs/endpoints.md) names the five calls, what each returns, and the keyword arguments each one takes.
- [Field masks](docs/field-masks.md) covers mask construction, the curated defaults and their billing tiers, and reading attributes the mask did not request.
- [Constants](docs/constants.md) covers the type, language, and ranking vocabularies.
- [Addresses](docs/addresses.md) covers the address readers and city resolution across the two carrier sets.
- [Errors](docs/errors.md) covers the exception hierarchy and the attributes every API exception carries.
- [Normalizing addresses with placekit](docs/NORMALIZATION.md) teaches the address handling the recorded corpus and the address module embody.

## Concurrency and lifecycle

One `Client` may be shared across threads, and one `AsyncClient` may be shared across tasks and used from more than one event loop. Calls on a shared client run concurrently, and each call returns its own result.

`close()` gates later calls with `ConfigError`. It neither cancels nor waits for calls already in flight, and those calls finish with their own results. Closing is idempotent, and the context managers close on exit.

Cancelling a task that is awaiting an `AsyncClient` call drops the wire request, and the same client stays fully usable for the next call.

Each client instance holds its own connection pool, so a program holding a `Client` and an `AsyncClient` for the same work holds two pools. Pool sizes and the idle expiry are the inherited reqwest defaults, with no configuration surface in placekit. The idle expiry is ninety seconds under the reqwest version the current release locks, and that figure is an inherited default rather than a placekit promise, so a future reqwest update can move it. Under parallel async load the upstream pool can also open a connection that ends up carrying no request. Every client in one process shares a single Tokio runtime that is built on first use and lives for the life of the process, holding its worker threads until the process exits. Connection counts observed against a local stub also carry a transport limit, because the stub speaks HTTP 1.1 with keep alive while the real API can multiplex over HTTP 2.

A result is the holder's to mutate in place, within the shallow freeze the models document. Mutating a result while other threads read it is not safe. A reader can meet a typed view and a raw view that no longer agree, and a reader iterating a list or a raw dict while it changes can fail with a `RuntimeError`. Share a result between threads only when nobody mutates it, or hand each thread its own result.

A process may fork after using placekit. The bindings detect the new process on the next call and rebuild their runtime and client state for the child, so calls in the child work on fresh and inherited clients alike. The native module does not load under subinterpreters, so a host that runs application code inside subinterpreters cannot use this library. One ordering consequence is worth knowing. If a subinterpreter attempts the import before the main interpreter has imported the module, the main interpreter import afterwards fails too, so the refusal is not contained to the subinterpreter in that order. Work through the Python `Client` and `AsyncClient` classes. The native module behind them is private, and direct use of it is unsupported.

## Pointing the client somewhere else

`Client` and `AsyncClient` accept `base_url`, `timeout` and `max_response_bytes` keyword arguments. The base URL override is how the test suite runs fully offline against a local stub server, and it works just as well for proxies you control and regional endpoints. The response cap bounds how large a successful response body may grow before the request aborts with a decode error, and it defaults to 32 MiB. Error response bodies keep a fixed limit of their own.

```python
client = Client("YOUR_API_KEY", base_url="http://127.0.0.1:8080/v1", timeout=5.0)
```

## Building from source

When pip finds no wheel it downloads the source distribution and builds it locally. That build needs a Rust toolchain at version 1.88 or newer (rustup installs one), network access while it downloads the crate dependencies from crates.io, and the platform C toolchain. With those in place a source install just works, only slower than a wheel.

Without a Rust toolchain the build backend tries to download and bootstrap one by itself, and when that fails the error talks about cargo metadata rather than the missing toolchain. If a source install fails, install Rust first and retry before debugging anything else. Wheels remain the recommended path wherever one exists.

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

`maturin develop` compiles the Rust core without optimizations and installs it into the venv. Iterate with the targeted commands above. The full gate is one command, and CI runs it word for word:

```bash
make check
```

That runs the rustfmt and clippy checks, the Rust test suite, a version coherence check across the manifests and the lockfile, an em dash scan, a maturin develop build, a stubtest pass over the type stubs, and the Python suite. The changelog joins the version comparison once it carries a release heading, and the publish form of the check enforces the changelog on the tag path.

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

A wheel built this way on a local machine is tied to that machine. On Linux it carries the local glibc as its floor, 2.39 on Ubuntu 24.04, not the manylinux 2_28 floor of the released wheels. A local build is for testing and is never a substitute for a released wheel.

Each wheel carries an embedded CycloneDX SBOM that the build generates for the Rust dependency tree, stored inside the wheel under its dist-info sboms folder. The tree it covers is the full locked tree across every platform that tree supports, so the SBOM also names components a given wheel platform never compiles, such as the Windows and WebAssembly branches of shared dependencies. The release trust story is that SBOM together with the commit SHA pin on every action in the workflow and PyPI trusted publishing, which ties each upload to this repository and workflow.

</details>

## License

placekit is released under the [MIT License](LICENSE).
