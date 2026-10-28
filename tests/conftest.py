"""A tiny local stub of the Places API (New), serving recorded fixtures.

The tests run fully offline. The stub also records the last request on the
server object so tests can assert on headers (API key, field mask) and on
the JSON body the client sent.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


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

    def _send_fixture(self, status: int, name: str):
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
            return self._send_fixture(200, "text_search.json")
        if path.endswith("places:searchNearby"):
            return self._send_fixture(200, "nearby_search.json")
        if path.endswith("places:autocomplete"):
            if not payload.get("input"):
                return self._send_fixture(400, "error_invalid.json")
            return self._send_fixture(200, "autocomplete.json")
        return self._send_fixture(404, "error_not_found.json")

    def do_GET(self):
        self._record(None)
        parsed = urlparse(self.path)
        path = parsed.path
        if path.endswith("/media"):
            query = parse_qs(parsed.query)
            if "key" not in query:
                return self._send_fixture(400, "error_invalid.json")
            return self._send(
                200, load_fixture("photo.png"), content_type="image/png"
            )
        if "/places/" in path:
            place_id = path.rsplit("/", 1)[-1]
            if place_id == "missing-place":
                return self._send_fixture(404, "error_not_found.json")
            if place_id == "denied-place":
                return self._send_fixture(403, "error_denied.json")
            return self._send_fixture(200, "place_details.json")
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
