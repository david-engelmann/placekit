"""A tiny local stub of the Places API (New), serving recorded fixtures.

The tests run fully offline. The stub also records the last request on the
server object so tests can assert on headers (API key, field mask) and on
the JSON body the client sent.

The stub behaves like the real API in the ways the suite depends on:

* It honours the ``X-Goog-FieldMask`` request header, returning only the
  fields the mask names, so a test can only see a field the client
  actually asked for (the fix for findings A2 and A3).
* Autocomplete predictions carry ``distanceMeters`` only when the request
  carried an ``origin``, as the API documents (finding A4).
* The photo media route answers with an HTTP redirect to a second route
  that serves the image, and with ``skipHttpRedirect=true`` it answers
  with the documented JSON photo object instead (finding A7 with F8).
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

#: Photo URI the stub reports in its skipHttpRedirect JSON form. It points
#: at the stub's own image route so the value is followable in tests.
PHOTO_URI_PATH = "/photo-image"


def load_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _mask_paths(headers) -> list[str] | None:
    for key, value in headers.items():
        if key.lower() == "x-goog-fieldmask":
            return [path.strip() for path in value.split(",") if path.strip()]
    return None


def _filter_to_mask(value, mask: list[str]):
    """Filter a decoded JSON payload down to the paths a mask names.

    A path is a dot path such as ``places.displayName`` or ``id``. Listing
    a parent (``places`` or ``places.photos``) keeps the whole subtree.
    A bare ``*`` keeps everything.
    """
    if "*" in mask:
        return value
    paths = set(mask)

    def allowed(prefix: str, key: str) -> bool:
        full = f"{prefix}.{key}" if prefix else key
        # A field is kept when the mask names it exactly, names one of its
        # ancestors (keeping the whole subtree), or names something below
        # it (so its parents survive to reach the named leaf).
        return any(
            p == full or full.startswith(p + ".") or p.startswith(full + ".")
            for p in paths
        )

    def walk(node, prefix: str):
        if isinstance(node, dict):
            return {
                key: walk(child, f"{prefix}.{key}" if prefix else key)
                for key, child in node.items()
                if allowed(prefix, key)
            }
        if isinstance(node, list):
            return [walk(item, prefix) for item in node]
        return node

    return walk(value, "")


def _filter_fixture(name: str, headers) -> bytes:
    mask = _mask_paths(headers)
    if mask is None:
        return load_fixture(name)
    data = json.loads(load_fixture(name))
    return json.dumps(_filter_to_mask(data, mask)).encode()


class StubHandler(BaseHTTPRequestHandler):
    server_version = "places-stub/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep test output quiet
        pass

    # -- helpers -----------------------------------------------------------

    def _send(self, status: int, body: bytes, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_fixture(self, status: int, name: str, *, filter_mask: bool = False):
        if filter_mask:
            self._send(status, _filter_fixture(name, self.headers))
        else:
            self._send(status, load_fixture(name))

    def _record(self, body: bytes | None):
        self.server.last_request = {  # type: ignore[attr-defined]
            "method": self.command,
            "path": self.path,
            "headers": dict(self.headers.items()),
            "body": body,
        }

    # -- routes --------------------------------------------------------------

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        self._record(body)
        path = urlparse(self.path).path
        payload = json.loads(body) if body else {}
        if path.endswith("places:searchText"):
            query = payload.get("textQuery", "")
            if "TRIGGER_QUOTA" in query:
                return self._send_fixture(429, "error_quota.json")
            if "TRIGGER_INVALID" in query:
                return self._send_fixture(400, "error_invalid.json")
            return self._send_fixture(200, "text_search.json", filter_mask=True)
        if path.endswith("places:searchNearby"):
            return self._send_fixture(200, "nearby_search.json", filter_mask=True)
        if path.endswith("places:autocomplete"):
            if not payload.get("input"):
                return self._send_fixture(400, "error_invalid.json")
            return self._send_autocomplete(payload)
        return self._send_fixture(404, "error_not_found.json")

    def _send_autocomplete(self, payload):
        # distanceMeters exists only when the request carried an origin;
        # the fixture ships without it and the stub adds a stand-in value
        # when it may legitimately appear (finding A4 with F7), honouring
        # the field mask when one was sent.
        data = json.loads(load_fixture("autocomplete.json"))
        mask = _mask_paths(self.headers)
        if mask is not None:
            data = _filter_to_mask(data, mask)
        distance_allowed = mask is None or any(
            path
            in (
                "*",
                "suggestions",
                "suggestions.placePrediction",
                "suggestions.placePrediction.distanceMeters",
            )
            for path in mask
        )
        if payload.get("origin") and distance_allowed:
            for suggestion in data.get("suggestions", []):
                prediction = suggestion.get("placePrediction")
                if prediction is not None:
                    prediction["distanceMeters"] = 1250
        self._send(200, json.dumps(data).encode())

    def do_GET(self):
        self._record(None)
        parsed = urlparse(self.path)
        path = parsed.path
        if path == PHOTO_URI_PATH:
            return self._send(
                200, load_fixture("photo.png"), content_type="image/png"
            )
        if path.endswith("/media"):
            query = parse_qs(parsed.query)
            if "key" not in query:
                return self._send_fixture(400, "error_invalid.json")
            host = self.headers.get("Host", "127.0.0.1")
            if query.get("skipHttpRedirect") == ["true"]:
                photo_name = path[path.index("places/") : -len("/media")]
                body = json.dumps(
                    {
                        "name": photo_name,
                        "photoUri": f"http://{host}{PHOTO_URI_PATH}",
                    }
                ).encode()
                return self._send(200, body)
            # Default behaviour is an HTTP redirect to the image, which the
            # client follows; the image bytes never come from this route.
            self.send_response(302)
            self.send_header("Location", f"http://{host}{PHOTO_URI_PATH}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if "/places/" in path:
            place_id = path.rsplit("/", 1)[-1]
            if place_id == "missing-place":
                return self._send_fixture(404, "error_not_found.json")
            if place_id == "denied-place":
                return self._send_fixture(403, "error_denied.json")
            if place_id == "unauthenticated-place":
                return self._send_fixture(401, "error_unauthenticated.json")
            return self._send_fixture(200, "place_details.json", filter_mask=True)
        return self._send_fixture(404, "error_not_found.json")


@pytest.fixture(scope="session")
def stub_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
    server.last_request = None  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    thread.join(timeout=5)


@pytest.fixture()
def base_url(stub_server) -> str:
    host, port = stub_server.server_address[:2]
    return f"http://{host}:{port}/v1"


@pytest.fixture()
def api_key() -> str:
    return "test-api-key"
