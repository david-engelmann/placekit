"""The offline stub the examples run against, promoted from the test suite.

It serves the recorded responses in the fixtures folder beside it
and honours the X-Goog-FieldMask request header the way the real
API does, so an example only sees the fields its call asked for.
"""

from __future__ import annotations

import gzip
import json
import math
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

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


def _fixture_place_locations() -> dict[str, dict]:
    """Locations of the fixture places, keyed by place id.

    Drawn from the search and details fixtures, so the autocomplete stub
    measures distances to the same coordinates the rest of the suite
    serves.
    """
    locations: dict[str, dict] = {}
    details = json.loads(load_fixture("place_details.json"))
    for place in (details, *json.loads(load_fixture("text_search.json"))["places"]):
        if place.get("id") and place.get("location"):
            locations[place["id"]] = place["location"]
    return locations


def _haversine_meters(origin: dict, location: dict) -> int:
    """Great circle distance in whole meters between two lat/lng points."""
    lat1 = math.radians(origin["latitude"])
    lat2 = math.radians(location["latitude"])
    dlat = lat2 - lat1
    dlng = math.radians(location["longitude"] - origin["longitude"])
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    return int(math.floor(6371000 * 2 * math.asin(math.sqrt(a)) + 0.5))


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

    def _send(
        self,
        status: int,
        body: bytes,
        content_type: str = "application/json",
        headers: dict | None = None,
    ):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
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
                return self._send(
                    429,
                    load_fixture("error_quota.json"),
                    headers={"Retry-After": "7"},
                )
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
        # distanceMeters exists only when the request carried an origin.
        # The fixture ships without it. The stub computes it from the
        # request origin to each fixture place's location (finding A4
        # with F7), honouring the field mask when one was sent.
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
        origin = payload.get("origin")
        if origin and distance_allowed:
            locations = _fixture_place_locations()
            for suggestion in data.get("suggestions", []):
                prediction = suggestion.get("placePrediction")
                if prediction is None:
                    continue
                location = locations.get(prediction.get("placeId"))
                if location is not None:
                    prediction["distanceMeters"] = _haversine_meters(
                        origin, location
                    )
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
            if "loop-photo" in path:
                # Redirect back to this same media URL forever. The
                # client must stop at its redirect limit, not hang.
                self.send_response(302)
                self.send_header("Location", self.path)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
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
            # client follows. The image bytes never come from this route.
            self.send_response(302)
            self.send_header("Location", f"http://{host}{PHOTO_URI_PATH}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if "/places/" in path:
            place_id = path.rsplit("/", 1)[-1]
            if place_id == "missing-place":
                return self._send_fixture(404, "error_not_found.json")
            if place_id == "gzip-place":
                body = gzip.compress(_filter_fixture("place_details.json", self.headers))
                return self._send(
                    200, body, headers={"Content-Encoding": "gzip"}
                )
            if place_id == "drop-place":
                # Advertise a long error body, send a fragment of an
                # envelope, then close the connection mid-body. The
                # client knows the HTTP status and the read failure,
                # and must lose neither.
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", "9999")
                self.end_headers()
                self.wfile.write(b'{"error": {"code": 500, "mess')
                self.wfile.flush()
                self.close_connection = True
                return
            if place_id == "denied-place":
                return self._send_fixture(403, "error_denied.json")
            if place_id == "unauthenticated-place":
                return self._send_fixture(401, "error_unauthenticated.json")
            return self._send_fixture(200, "place_details.json", filter_mask=True)
        return self._send_fixture(404, "error_not_found.json")


def serve():
    """Start the stub on a local port and return (server, base_url)."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
    server.last_request = None  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, f"http://{host}:{port}/v1"
