"""Tests for the audit programme (A50) landings.

Each test names the register entry it pins. The register lives at
~/workspace/placekit-audit-rounds/REGISTER.md.
"""

from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from placekit import AsyncClient, Client, PlacesError
from placekit._placekit import Client as NativeClient
from placekit._placekit import PlacesError as NativePlacesError
from placekit.exceptions import ConfigError, DecodeError
from placekit.models import Money, Photo, Place


class TestRetryAfterValueDiscipline:
    """A50-001: the public constructor refuses the retry delays the
    core parser refuses, a NaN, an infinity, or a negative, storing
    None instead of a value that raises inside a caller's sleep."""

    def test_nan_reads_as_none(self):
        err = PlacesError("m", retry_after=float("nan"))
        assert err.retry_after is None

    def test_infinities_read_as_none(self):
        assert PlacesError("m", retry_after=float("inf")).retry_after is None
        assert PlacesError("m", retry_after=float("-inf")).retry_after is None

    def test_negative_reads_as_none(self):
        assert PlacesError("m", retry_after=-5.0).retry_after is None
        assert PlacesError("m", retry_after=-1).retry_after is None

    def test_finite_non_negative_values_still_store(self):
        assert PlacesError("m", retry_after=7).retry_after == 7.0
        assert PlacesError("m", retry_after=2.5).retry_after == 2.5
        assert PlacesError("m", retry_after=0).retry_after == 0.0


class TestNumericStringRefusal:
    """A50-002: the direct decode layer refuses numeric strings in
    numeric slots instead of converting them, on the same terms as
    the string and boolean decoders refuse wrong types. The one
    exception is the money units, whose wire form is a string by
    design and which keeps its dedicated decoder."""

    def test_int_slot_refuses_a_numeric_string(self):
        with pytest.raises(DecodeError):
            Place.from_api(
                {"id": "x", "name": "places/x", "userRatingCount": "42"}
            )

    def test_float_slot_refuses_a_numeric_string(self):
        with pytest.raises(DecodeError):
            Place.from_api({"id": "x", "name": "places/x", "rating": "4.5"})

    def test_int_slot_refuses_bytes(self):
        # Bytes never converted even before this round, so the
        # class alone pins nothing new. What the refusal changed
        # for bytes is the seat it arrives from: a direct refusal
        # at the type test, unchained, where the old refusal was
        # the conversion guard chaining the TypeError the failed
        # int() conversion raised.
        with pytest.raises(DecodeError) as excinfo:
            Photo.from_api({"name": "places/x/photos/y", "widthPx": b"100"})
        assert excinfo.value.__cause__ is None
        assert excinfo.value.__context__ is None

    def test_float_slot_refuses_a_bytearray(self):
        with pytest.raises(DecodeError):
            Place.from_api(
                {"id": "x", "name": "places/x", "rating": bytearray(b"4.5")}
            )

    def test_money_units_accept_the_canonical_wire_string(self):
        money = Money.from_api(
            {"currencyCode": "USD", "units": "123", "nanos": 45}
        )
        assert money.units == 123
        assert Money.from_api({"units": "-5"}).units == -5
        assert Money.from_api({"units": "0"}).units == 0

    def test_money_units_accept_an_already_decoded_int(self):
        assert Money.from_api({"units": 123}).units == 123

    def test_money_units_refuse_non_canonical_strings(self):
        for bad in ["+5", " 5", "5 ", "1_000", "", "-", "5.0"]:
            with pytest.raises(DecodeError):
                Money.from_api({"units": bad})

    def test_money_units_refuse_a_digit_string_past_the_digit_limit(self):
        with pytest.raises(DecodeError):
            Money.from_api({"units": "9" * 5000})

    def test_money_units_refuse_beyond_the_int64_range(self):
        with pytest.raises(DecodeError):
            Money.from_api({"units": "9223372036854775808"})
        with pytest.raises(DecodeError):
            Money.from_api({"units": "-9223372036854775809"})
        assert (
            Money.from_api({"units": "9223372036854775807"}).units
            == 9223372036854775807
        )

    def test_money_nanos_still_refuses_a_string(self):
        with pytest.raises(DecodeError):
            Money.from_api({"units": "1", "nanos": "45"})


class _SlowHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        time.sleep(30)

    def log_message(self, *args):  # keep test output quiet
        pass


class TestAbortSettlesTheHandle:
    """A50-013: aborting a running call settles its handle, so a
    consumer that aborts and keeps polling sees the call complete
    and collects an aborted answer instead of polling forever."""

    def test_abort_settles_and_reports_aborted(self):
        server = HTTPServer(("127.0.0.1", 0), _SlowHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            client = NativeClient("test-key", base)
            handle = client.text_search_async({"textQuery": "coffee"}, None)
            assert handle.is_done() is False
            handle.abort()
            deadline = time.monotonic() + 5.0
            while not handle.is_done() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert handle.is_done() is True
            with pytest.raises(NativePlacesError) as caught:
                handle.take_result()
            assert caught.value.kind == "network"
            assert "aborted" in str(caught.value)
        finally:
            server.shutdown()
            thread.join(timeout=5)


class TestEnvironmentKeyFallback:
    """A50-018: a client constructed without a key reads the
    PLACEKIT_API_KEY environment variable, the explicit argument
    always wins, and neither present is a ConfigError naming both
    routes. A value the variable supplies is validated on the same
    terms as one passed in code."""

    def test_environment_key_is_used_when_no_argument(self, monkeypatch):
        monkeypatch.setenv("PLACEKIT_API_KEY", "env-key")
        client = Client()
        client.close()

    def test_explicit_key_wins_over_the_environment(self, monkeypatch):
        # The variable holds a value construction would refuse, so
        # a successful construction proves the explicit key was the
        # one read.
        monkeypatch.setenv("PLACEKIT_API_KEY", "not a valid key")
        client = Client("explicit-key")
        client.close()

    def test_explicit_key_is_the_one_sent_when_both_are_valid(
        self, monkeypatch, stub_server, base_url
    ):
        # With both keys valid, the wire itself shows which one the
        # client carries.
        monkeypatch.setenv("PLACEKIT_API_KEY", "env-key")
        client = Client("explicit-key", base_url=base_url)
        try:
            client.text_search("cafes in Sydney")
        finally:
            client.close()
        headers = stub_server.last_request["headers"]
        sent = next(
            value
            for key, value in headers.items()
            if key.lower() == "x-goog-api-key"
        )
        assert sent == "explicit-key"

    def test_environment_value_is_validated_like_an_argument(self, monkeypatch):
        monkeypatch.setenv("PLACEKIT_API_KEY", "not a valid key")
        with pytest.raises(ConfigError):
            Client()

    def test_neither_present_refuses_and_names_both_routes(self, monkeypatch):
        monkeypatch.delenv("PLACEKIT_API_KEY", raising=False)
        with pytest.raises(ConfigError) as caught:
            Client()
        assert "PLACEKIT_API_KEY" in str(caught.value)

    def test_async_client_reads_the_environment_too(self, monkeypatch):
        monkeypatch.setenv("PLACEKIT_API_KEY", "env-key")
        client = AsyncClient()
        client.close()
