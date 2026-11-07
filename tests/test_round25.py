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
import json
import socket
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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
    # The needle names the native module as it renders, so the
    # assertion discriminates: the pre repair traceback carried
    # the native exception as the cause and printed its class
    # as _placekit.PlacesError. A demo preserved
    # in the round dossier (probes-landing, the traceback needle
    # demo) shows the needle biting on that pre repair form.
    assert "_placekit" not in rendered
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


# --- Landing repair pins (red team BREACH follow up)
#
# A timeout anywhere in a call surfaces as the timeout network
# error, on every body read path rather than only the error
# body read. The head scan resolves duplicate keys the way the
# whole document parse resolves them. The scan fallback wording
# says when the message could not be read in full.


def _drip_details_handler(body: bytes):
    """Serve one success body in eight chunks, one every 0.35
    seconds, so a 1.0 second client deadline fires mid body."""

    def drip(conn):
        _read_request(conn)
        conn.sendall(
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            + f"Content-Length: {len(body)}\r\n\r\n".encode()
        )
        step = max(1, len(body) // 8)
        for i in range(0, len(body), step):
            conn.sendall(body[i : i + step])
            threading.Event().wait(0.35)

    return drip


def _details_body() -> bytes:
    return (Path(__file__).parent / "fixtures" / "place_details.json").read_bytes()


def test_timeout_while_success_body_streams_is_a_timeout(api_key):
    # The red team Major: a success body still streaming when
    # the deadline fired surfaced as a DecodeError reporting a
    # body read failure, with retryable False and no timeout
    # token anywhere. It is the timeout network error now, the
    # same class the error body read produces.
    with _SocketServer(_drip_details_handler(_details_body())) as base_url:
        slow = Client(api_key, base_url=base_url, timeout=1.0)
        with pytest.raises(NetworkError) as excinfo:
            slow.place_details("abc")
    exc = excinfo.value
    assert "timeout" in str(exc)
    assert exc.retryable is True


def test_timeout_while_success_body_streams_is_a_timeout_async(api_key):
    # The async client shares the core read path and the class.
    with _SocketServer(_drip_details_handler(_details_body())) as base_url:

        async def run():
            client = AsyncClient(api_key, base_url=base_url, timeout=1.0)
            with pytest.raises(NetworkError) as excinfo:
                await client.place_details("abc")
            return excinfo.value

        exc = asyncio.run(run())
    assert "timeout" in str(exc)
    assert exc.retryable is True


def test_timeout_while_photo_uri_body_streams_is_a_timeout(api_key):
    # The photo URI form reads a JSON success body through the
    # same capped read; its drip takes the same timeout class.
    photo_json = (
        b'{"name": "places/abc/photos/def", '
        b'"photoUri": "http://127.0.0.1/img"}'
    )

    def drip(conn):
        _read_request(conn)
        conn.sendall(
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            + f"Content-Length: {len(photo_json)}\r\n\r\n".encode()
        )
        step = 6
        for i in range(0, len(photo_json), step):
            conn.sendall(photo_json[i : i + step])
            threading.Event().wait(0.3)

    with _SocketServer(drip) as base_url:
        slow = Client(api_key, base_url=base_url, timeout=1.0)
        with pytest.raises(NetworkError) as excinfo:
            slow.place_photo(
                "places/abc/photos/def",
                max_width_px=100,
                skip_http_redirect=True,
            )
    exc = excinfo.value
    assert "timeout" in str(exc)
    assert exc.retryable is True


def _read_head(conn) -> bytes:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = conn.recv(4096)
        if not chunk:
            return data
        data += chunk
    return data


def test_timeout_while_photo_image_body_streams_is_a_timeout(api_key):
    # The photo bytes form: the media request redirects to an
    # image path whose body then drips past the deadline. The
    # timeout fires inside the capped body read after the
    # redirect completes, and it is the timeout network error.
    def flow(conn):
        head = _read_head(conn)
        first_line = head.split(b"\r\n")[0]
        if b"/media" in first_line:
            host = b"127.0.0.1"
            for line in head.split(b"\r\n"):
                if line.lower().startswith(b"host:"):
                    host = line.split(b":", 1)[1].strip()
            conn.sendall(
                b"HTTP/1.1 302 Found\r\n"
                + b"Location: http://" + host + b"/img\r\n"
                + b"Content-Length: 0\r\n\r\n"
            )
            return
        conn.sendall(
            b"HTTP/1.1 200 OK\r\nContent-Type: image/png\r\n"
            b"Content-Length: 100000\r\n\r\n"
        )
        for _ in range(50):
            conn.sendall(b"\x89PNG")
            threading.Event().wait(0.1)

    with _SocketServer(flow) as base_url:
        slow = Client(api_key, base_url=base_url, timeout=1.0)
        with pytest.raises(NetworkError) as excinfo:
            slow.place_photo("places/abc/photos/def", max_width_px=100)
    exc = excinfo.value
    assert "timeout" in str(exc)
    assert exc.retryable is True


def test_malformed_complete_success_body_stays_a_decode_error(
    client, raw_response
):
    # The timeout carve out is narrow: a complete body that
    # simply does not decode keeps the decode class and its
    # conservative retryable reading.
    raw_response(200, "this is not json", "text/plain")
    with pytest.raises(DecodeError) as excinfo:
        client.text_search("pizza")
    assert excinfo.value.retryable is False


def test_timeout_past_the_error_read_cap_is_a_timeout(api_key):
    # The red team Minor: the body filled the 262144 byte error
    # read cap exactly and then stalled, and the past cap probe
    # read the resulting stream failure as proof of capping, so
    # the timeout token was lost. The timeout is distinguished
    # now and surfaces whole.
    junk = b"x" * 262144

    def fill_then_stall(conn):
        _read_request(conn)
        conn.sendall(
            b"HTTP/1.1 500 Internal Server Error\r\n"
            b"Content-Type: text/plain\r\n"
            b"Content-Length: 9999999\r\n\r\n" + junk
        )
        threading.Event().wait(5)

    with _SocketServer(fill_then_stall) as base_url:
        slow = Client(api_key, base_url=base_url, timeout=1.0)
        with pytest.raises(NetworkError) as excinfo:
            slow.text_search("pizza")
    exc = excinfo.value
    assert "timeout" in str(exc)
    assert exc.retryable is True


def test_completed_over_cap_error_body_still_reports_the_cap(
    client, raw_response
):
    # The pair of the past cap timeout pin: a body that overflows
    # the cap and completes is genuinely capped, and its message
    # keeps the capped wording (the Round 23 discipline).
    raw_response(500, b"x" * 300_000, "text/plain")
    with pytest.raises(ApiError) as excinfo:
        client.text_search("pizza")
    assert "stopped at the 262144 byte cap" in str(excinfo.value)


# --- The head scan and duplicate keys


def _deep_fragment() -> str:
    return json.dumps(_nested(150))


def test_head_scan_takes_the_last_of_two_error_objects(client, raw_response):
    # The whole document parse resolves a duplicated key last
    # wins; the scan resolved a duplicated error key first
    # wins. With the parse defeated by the deep sibling, the
    # scan now walks past the first error object and the later
    # one classifies the call.
    body = (
        '{"error": {"code": 400, "message": "first", '
        '"status": "INVALID_ARGUMENT"}, '
        '"error": {"code": 429, "message": "second", '
        '"status": "RESOURCE_EXHAUSTED"}, '
        f'"junk": {_deep_fragment()}}}'
    )
    raw_response(400, body)
    with pytest.raises(RateLimitError) as excinfo:
        client.text_search("pizza")
    assert excinfo.value.google_status == "RESOURCE_EXHAUSTED"
    assert "second" in str(excinfo.value)


def test_head_scan_skips_a_non_object_error_value(client, raw_response):
    # A first error key holding a string silenced the scan
    # outright, even with a real envelope under a second key.
    # The scan skips the non object value and keeps walking.
    body = (
        '{"error": "not an object", '
        '"error": {"code": 404, "message": "gone", '
        '"status": "NOT_FOUND"}, '
        f'"junk": {_deep_fragment()}}}'
    )
    raw_response(400, body)
    with pytest.raises(NotFoundError) as excinfo:
        client.text_search("pizza")
    assert excinfo.value.google_status == "NOT_FOUND"


def test_head_scan_repeated_status_key_takes_the_last_value(
    client, raw_response
):
    # A repeated status key whose later value is a number reads
    # as no status in the whole parse, which then classifies by
    # the numeric code. The scan kept the earlier string. Both
    # paths now agree.
    body = (
        '{"error": {"code": 400, "message": "mixed", '
        '"status": "RESOURCE_EXHAUSTED", "status": 42, '
        f'"junk": {_deep_fragment()}}}}}'
    )
    raw_response(400, body)
    with pytest.raises(InvalidRequestError) as excinfo:
        client.text_search("pizza")
    assert excinfo.value.google_status is None
    assert excinfo.value.error_code == 400


def test_scan_recovered_envelope_with_a_cut_message_says_so(
    client, raw_response
):
    # The message runs far past the error read cap, so the
    # capped read cuts it mid string and the scan recovers the
    # status and code without it. The fallback text says the
    # message could not be read in full instead of claiming
    # the envelope carried none.
    body = (
        '{"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", '
        '"message": "' + "x" * 400_000 + '", "details": []}}'
    )
    raw_response(400, body)
    with pytest.raises(RateLimitError) as excinfo:
        client.text_search("pizza")
    message = str(excinfo.value)
    assert "could not be read in full" in message
    assert "carried no message" not in message
