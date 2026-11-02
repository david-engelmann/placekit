"""Round 25 acceptance pins.

Envelope classification survives the body (Major 1, red team Major):
an error envelope classifies by its Google status even when the
body overflows the read cap or a value in it nests past the JSON
parser depth limit, because the core falls back to a tolerant head
scan. The decoder float contract (Major 2): non finite payload
values refuse as DecodeError. OUT_OF_RANGE (Major 3) classifies by
status on any HTTP pairing. The scalar slots (Major 4 as audited,
recalibrated Minor) validate in Python and name the argument.
Timeout truthfulness (Minor 11, red team Minor 1), the Api
headline shape (Minor 1), the unchained translation (Minor 2),
retry_after normalisation (Minor 3), context coverage (Minor 4),
the details string bound (Minor 6), the Config prefix (Minor 8),
and the in flight async cancellation pin (spec Minor).
"""

from __future__ import annotations

import asyncio
import gzip
import json
import socket
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from placekit import AsyncClient, Client, address
from placekit.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigError,
    DecodeError,
    InvalidRequestError,
    NetworkError,
    NotFoundError,
    PlacesError,
    RateLimitError,
)
from placekit.fields import FieldMask, normalize_fields
from placekit.models import LatLng, Place

QUOTA_MESSAGE = "Quota exceeded for this key"


@pytest.fixture()
def client(api_key, base_url) -> Client:
    return Client(api_key, base_url=base_url)


def _envelope(status_text: str, code: int, message: str, detail: str = "") -> str:
    details = (
        '[{"@type": "type.googleapis.com/google.rpc.DebugInfo", '
        f'"detail": {json.dumps(detail)}}}]'
        if detail
        else "[]"
    )
    return (
        f'{{"error": {{"code": {code}, "message": {json.dumps(message)}, '
        f'"status": "{status_text}", "details": {details}}}}}'
    )


def _nested(depth: int):
    value = "x"
    for _ in range(depth):
        value = [value]
    return value


# --- Major 1 and the red team depth Major: classification survives


def test_over_cap_envelope_classifies_by_status(client, raw_response):
    # The audit shape: a RESOURCE_EXHAUSTED envelope on an HTTP
    # 400 whose DebugInfo detail runs to 300000 characters. The
    # read stops at the cap, the whole document no longer parses,
    # and the classification still follows the envelope.
    body = _envelope("RESOURCE_EXHAUSTED", 429, QUOTA_MESSAGE, "z" * 300_000)
    raw_response(400, body)
    with pytest.raises(RateLimitError) as excinfo:
        client.text_search("pizza")
    exc = excinfo.value
    assert exc.google_status == "RESOURCE_EXHAUSTED"
    assert exc.error_code == 429
    assert QUOTA_MESSAGE in str(exc)
    # The detail bulk sits past the cap and degrades to empty.
    assert not exc.details


def test_over_cap_envelope_mirror_pairing(client, raw_response):
    # The mirror shape: an INVALID_ARGUMENT envelope on an HTTP
    # 429 classifies as the invalid request it is, not as a rate
    # limit.
    body = _envelope("INVALID_ARGUMENT", 400, "Bad field", "z" * 300_000)
    raw_response(429, body)
    with pytest.raises(InvalidRequestError) as excinfo:
        client.text_search("pizza")
    assert excinfo.value.google_status == "INVALID_ARGUMENT"
    assert excinfo.value.error_code == 400


def test_gzip_body_decompressing_past_the_cap_classifies(client, raw_response):
    # The cap applies to the decompressed body, so a small gzip
    # envelope whose plain form overflows it takes the same path.
    body = _envelope("RESOURCE_EXHAUSTED", 429, QUOTA_MESSAGE, "z" * 300_000)
    raw_response(
        400,
        gzip.compress(body.encode()),
        headers={"Content-Encoding": "gzip"},
    )
    with pytest.raises(RateLimitError) as excinfo:
        client.text_search("pizza")
    assert excinfo.value.google_status == "RESOURCE_EXHAUSTED"


def test_deeply_nested_detail_classifies_like_its_control(client, raw_response):
    # The red team shape: a value nested past the parser depth
    # limit inside a detail defeated the whole document parse on
    # a body of about a kilobyte. The deep body classifies
    # identically to the shallow control.
    control = json.dumps(
        {
            "error": {
                "code": 429,
                "message": QUOTA_MESSAGE,
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.DebugInfo",
                        "detail": _nested(10),
                    }
                ],
            }
        }
    )
    raw_response(400, control)
    with pytest.raises(RateLimitError) as control_exc:
        client.text_search("pizza")
    assert control_exc.value.details  # the control keeps its details

    deep = json.dumps(
        {
            "error": {
                "code": 429,
                "message": QUOTA_MESSAGE,
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.DebugInfo",
                        "detail": _nested(150),
                    }
                ],
            }
        }
    )
    assert len(deep) < 4096  # the defeating body is about a kilobyte
    raw_response(400, deep)
    with pytest.raises(RateLimitError) as deep_exc:
        client.text_search("pizza")
    exc = deep_exc.value
    assert exc.google_status == "RESOURCE_EXHAUSTED"
    assert exc.error_code == 429
    assert QUOTA_MESSAGE in str(exc)
    assert not exc.details  # details degrade to empty, the class survives


def test_deeply_nested_unknown_sibling_classifies(client, raw_response):
    # The same depth in an unknown key inside the error object,
    # after the head fields, cannot defeat classification either.
    body = json.dumps(
        {
            "error": {
                "code": 404,
                "message": "gone",
                "status": "NOT_FOUND",
                "junk": _nested(150),
            }
        }
    )
    raw_response(400, body)
    with pytest.raises(NotFoundError) as excinfo:
        client.text_search("pizza")
    assert excinfo.value.google_status == "NOT_FOUND"


# --- Major 3: OUT_OF_RANGE classifies by status on any pairing


@pytest.mark.parametrize("http_status", [418, 500])
def test_out_of_range_on_non_canonical_pairings(client, raw_response, http_status):
    raw_response(
        http_status,
        _envelope("OUT_OF_RANGE", http_status, "too far"),
    )
    with pytest.raises(InvalidRequestError) as excinfo:
        client.text_search("pizza")
    assert excinfo.value.google_status == "OUT_OF_RANGE"


# --- Major 2: the decoder float contract


def test_payload_infinite_coordinate_is_a_decode_error():
    with pytest.raises(DecodeError) as excinfo:
        LatLng.from_api({"latitude": float("inf"), "longitude": 0.0})
    assert "finite" in str(excinfo.value)
    assert "LatLng" in str(excinfo.value)


def test_payload_nan_rating_is_a_decode_error():
    with pytest.raises(DecodeError):
        Place.from_api({"id": "p", "rating": float("nan")})


def test_payload_infinite_location_inside_place_is_a_decode_error():
    with pytest.raises(DecodeError):
        Place.from_api(
            {"id": "p", "location": {"latitude": 0.0, "longitude": float("-inf")}}
        )


def test_direct_non_finite_construction_stays_a_config_error():
    # Direct construction is caller misuse and keeps its
    # ConfigError; only the payload path changed class.
    with pytest.raises(ConfigError):
        LatLng(float("inf"), 0.0)


# --- The scalar slots name the argument (recalibrated Minor)


def test_page_token_wrong_type_names_the_argument(client):
    with pytest.raises(ConfigError) as excinfo:
        client.text_search("pizza", page_token=123)
    assert "page_token" in str(excinfo.value)


def test_rank_preference_wrong_type_names_the_argument(client):
    with pytest.raises(ConfigError) as excinfo:
        client.text_search("pizza", rank_preference=5.0)
    assert "rank_preference" in str(excinfo.value)
    with pytest.raises(ConfigError) as excinfo:
        client.nearby_search((0.0, 0.0), 100.0, rank_preference=5.0)
    assert "rank_preference" in str(excinfo.value)


def test_included_type_wrong_type_names_the_argument(client):
    # included_type is the text search slot; nearby search takes
    # the list forms, which the materialiser already validates.
    with pytest.raises(ConfigError) as excinfo:
        client.text_search("pizza", included_type=7)
    assert "included_type" in str(excinfo.value)


def test_session_token_wrong_type_names_the_argument(client):
    with pytest.raises(ConfigError) as excinfo:
        client.autocomplete("pizza", session_token=3.5)
    assert "session_token" in str(excinfo.value)


def test_rank_preference_unknown_value_refuses_in_the_core(client):
    # No vocabulary validation was added in Python (the Round 7
    # posture): the code string validator passes an unlisted
    # value through, and the refusal below comes from the core
    # request model, whose rank preference has always been an
    # enum. It surfaces as a ConfigError naming the values the
    # enum accepts.
    with pytest.raises(ConfigError) as excinfo:
        client.text_search("pizza", rank_preference="SOME_FUTURE_VALUE")
    assert "RELEVANCE" in str(excinfo.value)


def test_surrogate_in_free_text_names_the_argument(client):
    with pytest.raises(ConfigError) as excinfo:
        client.text_search("bad\ud800query")
    assert "query" in str(excinfo.value)
    assert excinfo.value.context == "text_search"
    with pytest.raises(ConfigError) as excinfo:
        client.autocomplete("bad\ud800input")
    assert "input" in str(excinfo.value)


def test_surrogate_in_page_token_names_the_argument(client):
    with pytest.raises(ConfigError) as excinfo:
        client.text_search("pizza", page_token="tok\ud800")
    assert "page_token" in str(excinfo.value)


# --- Timeout truthfulness (Minor 11, red team Minor 1)


class _SocketServer:
    """A raw socket server running one handler per connection."""

    def __init__(self, handler):
        self._handler = handler
        self._sock = socket.socket()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self.port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def _serve(self):
        while True:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            threading.Thread(
                target=self._run, args=(conn,), daemon=True
            ).start()

    def _run(self, conn):
        try:
            self._handler(conn)
        except OSError:
            pass
        finally:
            conn.close()

    def __enter__(self):
        self._thread.start()
        return f"http://127.0.0.1:{self.port}/v1"

    def __exit__(self, *exc):
        self._sock.close()


def _read_request(conn):
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = conn.recv(4096)
        if not chunk:
            return
        data += chunk
    head, _, rest = data.partition(b"\r\n\r\n")
    length = 0
    for line in head.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1])
    while len(rest) < length:
        chunk = conn.recv(4096)
        if not chunk:
            return
        rest += chunk


def test_timeout_before_headers_is_retryable(api_key):
    def silent(conn):
        _read_request(conn)
        threading.Event().wait(5)

    with _SocketServer(silent) as base_url:
        slow = Client(api_key, base_url=base_url, timeout=0.3)
        with pytest.raises(NetworkError) as excinfo:
            slow.text_search("pizza")
    exc = excinfo.value
    assert "timeout" in str(exc)
    assert exc.retryable is True


def test_timeout_while_error_body_streams_is_a_timeout(api_key):
    # The red team shape: the headers of an HTTP 400 arrive at
    # once and the body then drips one byte at a time past the
    # configured timeout. The failure used to surface as the bare
    # HTTP class with an unreadable body note and no timeout
    # token anywhere; it is the timeout network error now.
    def drip(conn):
        _read_request(conn)
        conn.sendall(
            b"HTTP/1.1 400 Bad Request\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: 100000\r\n\r\n"
        )
        for _ in range(100):
            conn.sendall(b"x")
            threading.Event().wait(0.1)

    with _SocketServer(drip) as base_url:
        slow = Client(api_key, base_url=base_url, timeout=1.0)
        with pytest.raises(NetworkError) as excinfo:
            slow.text_search("pizza")
    exc = excinfo.value
    assert "timeout" in str(exc)
    assert exc.retryable is True


# --- Minor 1: the Api headline shape


def test_non_envelope_message_carries_the_status_once(client, raw_response):
    raw_response(500, "plain text failure", "text/plain")
    with pytest.raises(ApiError) as excinfo:
        client.text_search("pizza")
    message = str(excinfo.value)
    assert message.startswith("places API error (HTTP 500): ")
    assert message.count("HTTP 500") == 1


def test_envelope_without_message_has_no_bare_status_message(client, raw_response):
    raw_response(503, '{"error": {"code": 503, "status": "UNAVAILABLE"}}')
    with pytest.raises(ApiError) as excinfo:
        client.text_search("pizza")
    message = str(excinfo.value)
    assert message.startswith("places API error (HTTP 503 UNAVAILABLE): ")
    assert "carried no message" in message


# --- Minor 2: the translated exception stands alone


def test_translated_traceback_shows_one_exception(client):
    with pytest.raises(RateLimitError) as excinfo:
        client.text_search("TRIGGER_QUOTA pizza")
    exc = excinfo.value
    assert exc.__cause__ is None
    assert exc.__suppress_context__ is True
    rendered = "".join(traceback.format_exception(exc))
    assert rendered.count("Traceback (most recent call last)") == 1
    assert "_core" not in rendered
    # Every attribute survives the unchained raise.
    assert exc.google_status == "RESOURCE_EXHAUSTED"
    assert exc.error_code == 429
    assert exc.status_code == 429
    assert exc.retry_after == 7.0
    assert exc.context == "text_search"


# --- Minor 3: retry_after normalisation at construction


def test_places_error_retry_after_normalises():
    assert PlacesError("x", retry_after=True).retry_after is None
    assert PlacesError("x", retry_after="7").retry_after is None
    assert PlacesError("x", retry_after=None).retry_after is None
    coerced = PlacesError("x", retry_after=7).retry_after
    assert coerced == 7.0 and type(coerced) is float
    assert PlacesError("x", retry_after=7.5).retry_after == 7.5


# --- Minor 4: context coverage


def test_address_helper_failures_carry_the_helper_name():
    with pytest.raises(ConfigError) as excinfo:
        address.postal_code("not a place")
    assert excinfo.value.context == "postal_code"


def test_address_wrapped_failures_carry_the_helper_name():
    bare = object.__new__(Place)  # an instance with no attributes read
    with pytest.raises(ConfigError) as excinfo:
        address.postal_code(bare)
    assert excinfo.value.context == "postal_code"


def test_field_mask_failures_carry_the_mask_context():
    with pytest.raises(ConfigError) as excinfo:
        FieldMask("bad path!")
    assert excinfo.value.context == "FieldMask"
    with pytest.raises(ConfigError) as excinfo:
        FieldMask.of("places.id")
    assert excinfo.value.context == "FieldMask"
    with pytest.raises(ConfigError) as excinfo:
        normalize_fields("places.id")
    assert excinfo.value.context == "FieldMask"


def test_client_fields_failure_carries_the_mask_context(client):
    with pytest.raises(ConfigError) as excinfo:
        client.text_search("pizza", fields="places.id")
    assert excinfo.value.context == "FieldMask"


# --- Minor 6: the details string bound on a success status envelope


def test_success_envelope_detail_strings_are_capped(client, raw_response):
    body = _envelope("PERMISSION_DENIED", 403, "denied", "y" * 100_000)
    raw_response(200, body)
    with pytest.raises(AuthenticationError) as excinfo:
        client.text_search("pizza")
    exc = excinfo.value
    detail = exc.details[0]["detail"]
    assert len(detail) == 500


# --- Minor 8: the core Config rendering drops its prefix


def test_config_message_is_the_specific_text_alone(api_key):
    with pytest.raises(ConfigError) as excinfo:
        Client(api_key, base_url="http://example.com/v1")
    message = str(excinfo.value)
    assert "invalid client configuration or call" not in message
    assert "https" in message


# --- Spec Minor: in flight async cancellation


class _GatedHandler(BaseHTTPRequestHandler):
    gate = threading.Event()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            self.rfile.read(length)
        type(self).gate.wait(timeout=30)
        body = json.dumps(
            {"places": [{"id": "abc", "displayName": {"text": "Cafe"}}]}
        ).encode()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the cancelled request dropped its connection

    def log_message(self, *args):
        pass


class _QuietServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass  # a dropped cancelled connection is the expected case


def test_in_flight_cancellation_keeps_client_and_runtime_healthy(api_key):
    # The README Concurrency section promises that cancelling a
    # task awaiting an AsyncClient call drops the wire request
    # and the same client stays fully usable. The probe at
    # probes-landing/probe_async_cancellation.py drove it first;
    # this is the standing pin (Round 25, spec Minor).
    _GatedHandler.gate = threading.Event()
    server = _QuietServer(("127.0.0.1", 0), _GatedHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}/v1"
    try:

        async def run():
            client = AsyncClient(api_key, base_url=base_url)
            task = asyncio.ensure_future(client.text_search("cafe"))
            await asyncio.sleep(0.5)  # the request is in flight, gated
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            _GatedHandler.gate.set()
            result = await client.text_search("cafe")
            assert result.places and result.places[0].id == "abc"
            client.close()

        asyncio.run(run())
        _GatedHandler.gate.set()
        with Client(api_key, base_url=base_url) as sync_client:
            result = sync_client.text_search("cafe")
            assert result.places and result.places[0].id == "abc"
    finally:
        server.shutdown()
