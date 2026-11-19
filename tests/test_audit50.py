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
from placekit.fields import (
    NEARBY_SEARCH_FIELDS,
    PLACE_DETAILS_FIELDS,
    TEXT_SEARCH_FIELDS,
    FieldMask,
)
from placekit.models import LocalizedText, Money, Photo, Place, TextSearchResult


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


class _CountingDict(dict):
    """A payload mapping that counts how often a walk reads it."""

    visits = 0

    def values(self):  # type: ignore[override]
        type(self).visits += 1
        return super().values()


class _RaisingDict(dict):
    """A payload mapping whose values view raises on its
    second exercise, so the first walk reads it and a later
    walk at its own decoder seat converts the raise."""

    def __init__(self, *args):
        super().__init__(*args)
        self.exercises = 0

    def values(self):  # type: ignore[override]
        self.exercises += 1
        if self.exercises >= 2:
            raise RuntimeError("hostile values")
        return super().values()


def _counting(value):
    if isinstance(value, dict):
        return _CountingDict({k: _counting(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_counting(v) for v in value]
    return value


def _dict_nodes(value) -> int:
    if isinstance(value, dict):
        return 1 + sum(_dict_nodes(v) for v in value.values())
    if isinstance(value, list):
        return sum(_dict_nodes(v) for v in value)
    return 0


def _deep_payload() -> dict:
    node: dict = {"text": "x"}
    for _ in range(200):
        node = {"a": node}
    return node


def _count_verdicts(monkeypatch) -> list:
    """Count the depth verdicts one decode asks the core for.

    The walk is the only caller of the core verdict, so the
    count of verdict calls is the count of walks that ran.
    """
    from placekit import _placekit

    original = _placekit.models_payload_depth_within_limit
    calls: list = []

    def counting(trace):
        calls.append(trace)
        return original(trace)

    monkeypatch.setattr(
        _placekit, "models_payload_depth_within_limit", counting
    )
    return calls


class TestRootedDecodeValidation:
    """A50-044: a plain payload is walked once, at the root of
    its decode. A tree carrying any container subclass is
    walked at every level exactly as before, so a hostile
    container still meets the walk at every decoder seat. A
    decoder called directly is its own root and validates its
    input in full."""

    PAYLOAD = {
        "id": "ChIJrTLr-GyuEmsRBfy61i59si0",
        "displayName": {"text": "Cafe", "languageCode": "en"},
        "location": {"latitude": -33.86, "longitude": 151.2},
        "rating": 4.5,
        "userRatingCount": 12,
        "reviews": [
            {
                "name": "places/x/reviews/y",
                "rating": 5,
                "text": {"text": "Great", "languageCode": "en"},
                "authorAttribution": {
                    "displayName": "A",
                    "uri": "https://example.test/a",
                    "photoUri": "https://example.test/p",
                },
            }
        ],
    }

    def test_a_plain_place_walks_once_at_the_root(self, monkeypatch):
        calls = _count_verdicts(monkeypatch)
        place = Place.from_api(self.PAYLOAD)
        assert place.id == "ChIJrTLr-GyuEmsRBfy61i59si0"
        assert len(calls) == 1

    def test_a_hostile_tree_still_walks_at_nested_seats(self):
        payload = _counting(self.PAYLOAD)
        _CountingDict.visits = 0
        place = Place.from_api(payload)
        assert place.id == "ChIJrTLr-GyuEmsRBfy61i59si0"
        assert _CountingDict.visits > _dict_nodes(self.PAYLOAD)

    def test_a_mixed_tree_walks_the_hostile_sibling_plain_first(self):
        # A50-121: a nested walk must not publish its own
        # subtree's plainness. A plain sibling decoded first
        # used to set the flag and disarm the walk for the
        # hostile sibling after it, which then decoded
        # silently where the settled behaviour converts.
        plain = {"id": "p1", "location": {"latitude": 3.0, "longitude": 4.0}}
        hostile = {
            "id": "p2",
            "location": _RaisingDict({"latitude": 1.0, "longitude": 2.0}),
        }
        with pytest.raises(DecodeError):
            TextSearchResult.from_api({"places": [plain, hostile]})

    def test_a_mixed_tree_walks_the_hostile_sibling_hostile_first(self):
        # A50-121: the same mixed tree in the other order.
        # The hostile sibling converts in each order, so the
        # verdict cannot depend on sibling decode order.
        plain = {"id": "p1", "location": {"latitude": 3.0, "longitude": 4.0}}
        hostile = {
            "id": "p2",
            "location": _RaisingDict({"latitude": 1.0, "longitude": 2.0}),
        }
        with pytest.raises(DecodeError):
            TextSearchResult.from_api({"places": [hostile, plain]})

    def test_a_direct_child_decode_validates_in_full(self):
        with pytest.raises(DecodeError):
            LocalizedText.from_api(_deep_payload())

    def test_a_root_decode_still_refuses_a_deep_tree(self):
        with pytest.raises(DecodeError):
            Place.from_api(_deep_payload())

    def test_a_failed_decode_leaves_the_next_call_at_the_root(
        self, monkeypatch
    ):
        with pytest.raises(DecodeError):
            Place.from_api(_deep_payload())
        calls = _count_verdicts(monkeypatch)
        Place.from_api(self.PAYLOAD)
        assert len(calls) == 1


def _sent_mask(stub_server) -> str:
    headers = stub_server.last_request["headers"]
    for key, value in headers.items():
        if key.lower() == "x-goog-fieldmask":
            return value
    raise AssertionError("no field mask header was sent")


class TestDefaultMaskListsAgree:
    """A50-058: the curated default mask lists live in both the
    Python fields module and the Rust core, and the two copies
    must agree. The pin reads the mask the core actually sends
    when no fields are given and compares it with the Python
    tuple, endpoint by endpoint."""

    def test_text_search_default_agrees(self, stub_server, base_url):
        from placekit.fields import TEXT_SEARCH_FIELDS

        client = Client("test-api-key", base_url=base_url)
        client.text_search("cafes in Sydney")
        assert _sent_mask(stub_server) == ",".join(TEXT_SEARCH_FIELDS)

    def test_nearby_search_default_agrees(self, stub_server, base_url):
        from placekit.fields import NEARBY_SEARCH_FIELDS

        client = Client("test-api-key", base_url=base_url)
        client.nearby_search((-33.86, 151.2), 500)
        assert _sent_mask(stub_server) == ",".join(NEARBY_SEARCH_FIELDS)

    def test_place_details_default_agrees(self, stub_server, base_url):
        from placekit.fields import PLACE_DETAILS_FIELDS

        client = Client("test-api-key", base_url=base_url)
        client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
        assert _sent_mask(stub_server) == ",".join(PLACE_DETAILS_FIELDS)


class TestServerMessageAndTypedEntries:
    """A50-027. The bare server message and the typed violation
    entries cross as their own attributes, beside the raw views,
    which keep every entry verbatim."""

    def test_bad_request_envelope(self, raw_response, base_url):
        body = (
            '{"error": {"code": 400, "message": '
            '"Request contains an invalid argument.", "status": '
            '"INVALID_ARGUMENT", "details": [{"@type": '
            '"type.googleapis.com/google.rpc.BadRequest", '
            '"fieldViolations": [{"field": "textQuery", '
            '"description": "Request contains an invalid argument."}, '
            '{"field": 7, "description": "not a pair"}]}]}}'
        )
        raw_response(400, body)
        client = Client("test-api-key", base_url=base_url)
        with pytest.raises(PlacesError) as excinfo:
            client.text_search("pizza")
        err = excinfo.value
        assert err.kind == "invalid_request"
        assert err.server_message == "Request contains an invalid argument."
        assert err.message.startswith(
            "invalid request (HTTP 400): Request contains an invalid argument."
        )
        assert err.field_violation_entries == [
            {
                "field": "textQuery",
                "description": "Request contains an invalid argument.",
            }
        ]
        # The raw view keeps both entries, the malformed one verbatim.
        assert len(err.field_violations) == 2
        assert err.field_violations[1] == {"field": 7, "description": "not a pair"}

    def test_quota_envelope(self, raw_response, base_url):
        body = (
            '{"error": {"code": 429, "message": '
            '"Resource has been exhausted (e.g. check quota).", '
            '"status": "RESOURCE_EXHAUSTED", "details": [{"@type": '
            '"type.googleapis.com/google.rpc.QuotaFailure", '
            '"violations": [{"description": "Quota exceeded.", '
            '"quotaId": "default", "quotaMetric": '
            '"places.googleapis.com/default", "quotaValue": "1000", '
            '"subject": "clientip:203.0.113.10"}, "not an object"]}]}}'
        )
        raw_response(429, body)
        client = Client("test-api-key", base_url=base_url)
        with pytest.raises(PlacesError) as excinfo:
            client.text_search("pizza")
        err = excinfo.value
        assert err.kind == "rate_limit"
        assert err.server_message == (
            "Resource has been exhausted (e.g. check quota)."
        )
        assert err.quota_violation_entries == [
            {
                "subject": "clientip:203.0.113.10",
                "description": "Quota exceeded.",
                "quota_id": "default",
                "quota_metric": "places.googleapis.com/default",
                "quota_value": "1000",
            }
        ]
        assert len(err.quota_violations) == 2

    def test_defaults_on_a_plain_error(self):
        err = PlacesError("plain")
        assert err.server_message is None
        assert err.field_violation_entries == []
        assert err.quota_violation_entries == []


class TestResponseCapKeyword:
    """A50-128: the response cap is settable from Python, with the
    wrapper refusing the values the rule refuses before any native
    call, and a set cap enforced by the core on the wire."""

    def test_refusals(self):
        for bad in (0, -1, True, 2.5, "1024", 2**64):
            with pytest.raises(ConfigError):
                Client("test-api-key", max_response_bytes=bad)

    def test_refusal_message(self):
        with pytest.raises(ConfigError) as caught:
            Client("test-api-key", max_response_bytes=0)
        assert caught.value.message == (
            "max_response_bytes must be a positive int, got 0"
        )

    def test_timeout_refusal_message_states_the_rule(self):
        # A50-134: the timeout refusal states the int or float
        # rule it enforces, pinned exactly like its siblings.
        with pytest.raises(ConfigError) as caught:
            Client("test-api-key", timeout=0)
        assert caught.value.message == (
            "timeout must be a positive, finite int or float, "
            "at most 3600 seconds, got 0"
        )

    def test_a_set_cap_bounds_the_body(self, raw_response, base_url):
        raw_response(200, '{"places": []}')
        client = Client(
            "test-api-key", base_url=base_url, max_response_bytes=8
        )
        with pytest.raises(DecodeError) as caught:
            client.text_search("pizza")
        assert "exceeded the maximum of 8 bytes" in caught.value.message

    def test_an_unset_cap_reads_the_default(self, raw_response, base_url):
        raw_response(200, '{"places": []}')
        client = Client("test-api-key", base_url=base_url)
        assert client.text_search("pizza").places == []


class TestValidatorOverflowRefusals:
    """A50-133: a huge int at a float validator seat raises the
    seat's ConfigError, never a bare OverflowError."""

    def test_coordinate(self):
        client = Client("test-api-key")
        with pytest.raises(ConfigError) as caught:
            client.nearby_search((10**400, 0.0), 100)
        assert caught.value.message.startswith(
            "location latitude must be finite and within -90 to 90, got "
        )

    def test_radius(self):
        client = Client("test-api-key")
        with pytest.raises(ConfigError) as caught:
            client.nearby_search((0.0, 0.0), 10**400)
        assert caught.value.message.startswith(
            "radius_m must be a finite int or float, got "
        )

    def test_min_rating(self):
        client = Client("test-api-key")
        with pytest.raises(ConfigError) as caught:
            client.text_search("q", min_rating=10**400)
        assert caught.value.message.startswith(
            "min_rating must be an int or float between 0 and 5, got "
        )


class _StripRaises(str):
    """A string whose strip read raises, the Round 54 double's
    shape, for the FieldMask construction exercise seat."""

    calls = 0

    def strip(self, *args):
        _StripRaises.calls += 1
        raise ValueError("strip boom")


class _PlainSubclass(str):
    """A string subclass with no overrides, judged per path."""


class TestCuratedDefaultMasks:
    """A50-148: the curated default constructors return standing
    instances instead of rebuilding the mask on every call."""

    def test_defaults_are_standing_instances(self):
        assert FieldMask.text_search() is FieldMask.text_search()
        assert FieldMask.nearby_search() is FieldMask.nearby_search()
        assert FieldMask.place_details() is FieldMask.place_details()

    def test_defaults_equal_fresh_constructions(self):
        assert FieldMask.text_search() == FieldMask(*TEXT_SEARCH_FIELDS)
        assert FieldMask.nearby_search() == FieldMask(*NEARBY_SEARCH_FIELDS)
        assert FieldMask.place_details() == FieldMask(*PLACE_DETAILS_FIELDS)

    def test_a_subclass_still_builds_its_own(self):
        class Sub(FieldMask):
            pass

        assert type(Sub.text_search()) is Sub
        assert Sub.text_search() is not Sub.text_search()


class TestBulkMaskVerdict:
    """A50-149: construction decides a run of plain string paths
    in one core pass, and every refusal still surfaces at the
    seat and in the order the per path verdicts produced."""

    def test_the_first_invalid_path_is_named(self):
        with pytest.raises(ConfigError) as caught:
            FieldMask("places.id", "bad path", "also bad")
        assert "bad path" in str(caught.value)
        assert caught.value.__cause__ is None

    def test_an_invalid_path_ahead_of_a_raising_member_wins(self):
        _StripRaises.calls = 0
        with pytest.raises(ConfigError) as caught:
            FieldMask("bad path", _StripRaises("places.rating"))
        assert "bad path" in str(caught.value)
        assert caught.value.__cause__ is None
        assert _StripRaises.calls == 0

    def test_a_raising_member_ahead_of_an_invalid_path_wins(self):
        _StripRaises.calls = 0
        with pytest.raises(ConfigError) as caught:
            FieldMask(_StripRaises("places.rating"), "bad path")
        assert isinstance(caught.value.__cause__, ValueError)
        assert _StripRaises.calls == 1

    def test_a_non_string_member_after_an_invalid_path_gets_the_verdict(self):
        with pytest.raises(ConfigError) as caught:
            FieldMask("bad path", 42)
        assert "bad path" in str(caught.value)
        assert caught.value.__cause__ is None

    def test_valid_mixed_construction_still_builds(self):
        mask = FieldMask(
            "places.id", _PlainSubclass("places.rating"), "places.displayName"
        )
        assert mask.paths == (
            "places.id",
            "places.rating",
            "places.displayName",
        )

    def test_a_plain_run_crosses_once(self, monkeypatch):
        import placekit._placekit as native

        real = native.mask_first_invalid_path
        calls = []

        def counting(paths):
            calls.append(list(paths))
            return real(paths)

        monkeypatch.setattr(native, "mask_first_invalid_path", counting)
        FieldMask("places.id", "places.rating", "places.displayName")
        assert len(calls) == 1
        assert len(calls[0]) == 3

    def test_a_mixed_run_batches_around_a_subclass(self, monkeypatch):
        import placekit._placekit as native

        real = native.mask_first_invalid_path
        calls = []

        def counting(paths):
            calls.append(list(paths))
            return real(paths)

        monkeypatch.setattr(native, "mask_first_invalid_path", counting)
        FieldMask(
            "places.id",
            "places.rating",
            _PlainSubclass("places.website"),
            "places.name",
        )
        assert [len(call) for call in calls] == [2, 1]


class _ReprRaisesValueError(ValueError):
    def __repr__(self):
        raise RuntimeError("repr detonated")


class _RaisingLenList(list):
    def __len__(self):
        raise ValueError("length detonated")


class TestErrorSurfaceRepairs:
    def test_convert_wrap_names_a_detonating_exception_safely(self):
        # Audit A50-169: the conversion wrap named its caught
        # exception through the raw repr, so an exception whose
        # repr raises escaped the wrap it exists to contain.
        from placekit.client import _Base

        def convert(data):
            raise _ReprRaisesValueError("boom")

        with pytest.raises(DecodeError) as caught:
            _Base._convert(convert, {}, "test conversion")
        assert "<unrepresentable" in str(caught.value)
        assert isinstance(caught.value.__cause__, _ReprRaisesValueError)

    def test_plain_refusals_carry_the_construction_context(self):
        # Audit A50-170: the plain construction refusals carried no
        # context while a core failure at the same seat carried
        # "client construction".
        with pytest.raises(ConfigError) as caught:
            Client("   ")
        assert caught.value.context == "client construction"
        with pytest.raises(ConfigError) as caught:
            Client(123)  # type: ignore[arg-type]
        assert caught.value.context == "client construction"

    def test_missing_key_refusal_carries_the_construction_context(
        self, monkeypatch
    ):
        # Audit A50-170, the arm the review repair completed: the
        # missing key refusal is raised by the environment fallback
        # ahead of the guarded try, so it names the seat itself.
        monkeypatch.delenv("PLACEKIT_API_KEY", raising=False)
        with pytest.raises(ConfigError) as caught:
            Client()
        assert caught.value.context == "client construction"

    def test_raw_read_failure_keeps_its_own_framing(self):
        # Audit A50-176: the raw source read sat inside the decode
        # try, so its failure was re-framed as an element decode
        # failure in front of its own message.
        from placekit.models import _model_elements

        raw = {"results": _RaisingLenList([{}])}
        with pytest.raises(DecodeError) as caught:
            _model_elements(
                [{}], "Place", "results", raw, lambda item, raw_item: item
            )
        assert "could not be read" in str(caught.value)
        assert "failed to decode" not in str(caught.value)


class _RaisingConversionInt(int):
    def __int__(self):
        raise RuntimeError("int boom")


class _RaisingComparisonInt(int):
    def __le__(self, other):
        raise RuntimeError("cmp boom")

    def __ge__(self, other):
        raise RuntimeError("cmp boom")


class _LyingComparisonInt(int):
    def __le__(self, other):
        return True

    def __ge__(self, other):
        return True


class _HostileFloat(float):
    def __float__(self):
        raise RuntimeError("float boom")


class _DivergentConversionInt(int):
    def __int__(self):
        return 5


class TestIntValidatorCoercion:
    """A50-138 and A50-197: the int validator coerces inside its
    guard and judges the plain value, and the float seats catch
    the whole Exception family around their conversion."""

    def test_conversion_detonation_refuses_with_the_seat_message(self):
        from placekit.client import _Base

        with pytest.raises(ConfigError) as caught:
            _Base._validate_int_range(
                "page_size", _RaisingConversionInt(5), 1, 20
            )
        assert "page_size must be an integer between 1 and 20" in str(
            caught.value
        )
        assert isinstance(caught.value.__cause__, RuntimeError)

    def test_conversion_detonation_refuses_at_the_photo_seat(self):
        from placekit.client import _Base

        with pytest.raises(ConfigError) as caught:
            _Base._validate_photo_args(
                "places/x/photos/y",
                _RaisingConversionInt(5),
                None,
                False,
                "place_photo",
            )
        assert "max_width_px must be an integer between 1 and 4800" in str(
            caught.value
        )
        assert isinstance(caught.value.__cause__, RuntimeError)

    def test_lying_comparison_is_refused_on_its_stored_value(self):
        from placekit.client import _Base

        with pytest.raises(ConfigError) as caught:
            _Base._validate_int_range(
                "page_size", _LyingComparisonInt(999), 1, 20
            )
        assert "page_size must be an integer between 1 and 20" in str(
            caught.value
        )

    def test_comparison_is_never_spent_and_the_body_carries_a_plain_int(
        self,
    ):
        from placekit.client import _Base

        body = _Base._text_search_body(
            "pizza",
            page_token=None,
            language=None,
            region=None,
            rank_preference=None,
            open_now=None,
            price_levels=None,
            strict_type_filtering=None,
            included_type=None,
            location_bias=None,
            location_restriction=None,
            page_size=_RaisingComparisonInt(5),
        )
        assert body["pageSize"] == 5
        assert type(body["pageSize"]) is int

    def test_photo_seat_returns_the_judged_plain_int(self):
        # The validator judges the conversion's answer (5), and
        # the photo seat returns that plain int for the caller
        # to pass onward, so the value judged is the value the
        # native call reads, not the stored 999 the caller's
        # object still carries.
        from placekit.client import _Base

        width, height = _Base._validate_photo_args(
            "places/x/photos/y",
            _DivergentConversionInt(999),
            None,
            False,
            "place_photo",
        )
        assert width == 5
        assert type(width) is int
        assert height is None

    def test_hostile_float_conversion_refuses_with_the_seat_message(self):
        from placekit.client import _Base

        with pytest.raises(ConfigError) as caught:
            _Base._validate_float_range("min_rating", _HostileFloat(1.5), 0, 5)
        assert "min_rating must be an int or float between 0 and 5" in str(
            caught.value
        )
        assert isinstance(caught.value.__cause__, RuntimeError)

    def test_huge_int_refusal_text_is_unchanged(self):
        from placekit.client import _Base

        with pytest.raises(ConfigError) as caught:
            _Base._validate_float_range("min_rating", 10**400, 0, 5)
        assert "min_rating must be an int or float between 0 and 5" in str(
            caught.value
        )


def test_exact_string_members_skip_the_construction_exercise(monkeypatch):
    """A50-209: the constructor's caller side exercise is skipped
    for exact string members, whose reads no caller can observe,
    and kept for subclass members, whose reads are the Round 53
    operation sequence."""
    import placekit.fields as fields_module

    calls = []

    def counting(path):
        calls.append(path)
        return True

    monkeypatch.setattr(fields_module, "_valid_path", counting)
    mask = FieldMask("places.id", "places.displayName")
    assert mask.paths == ("places.id", "places.displayName")
    assert calls == []

    class Member(str):
        pass

    FieldMask(Member("places.id"))
    assert calls == [Member("places.id")]

    def raising(path):
        raise ValueError("exercise boom")

    monkeypatch.setattr(fields_module, "_valid_path", raising)
    with pytest.raises(ConfigError):
        FieldMask(Member("places.id"))
    FieldMask("places.id")
