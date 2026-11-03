"""Round 41 landing pins.

Finding 1 and Finding 2 (one repair): the PlacesError
constructor copied its three list arguments through a plain
``list`` call, the one unguarded and unbounded caller iterable
read left in the library. A value whose iteration raised escaped
construction as a bare builtin, and an endless iterable hung
construction. The copies now sit under the standing discipline.
A plain list or tuple, already materialised in full, is copied
under guard with no ceiling, which is the only shape the library
itself ever passes, including wire details arrays past the
ceiling whose length the Round 35 counting identity rests on.
Any other iterable is materialised through the shared bounded
read under the ceiling of 1000, and anything it raises surfaces
as a chained ConfigError.

Finding 3: a details payload the bindings could not convert, an
integer literal past the interpreter exact conversion limit of
4300 digits is the proven shape, failed the whole attribute
attachment in the native error translation, so the error fell
back to the plainest PlacesError and the caller lost the class,
the Google status, the error code and the retryable flag the
core had classified. The details surface now degrades to empty
for that call and the classification stands.

Finding 4, with its red team extension: an envelope body the
strict whole parse refused lost its whole details array through
the tolerant head scan, even when the poison, a lone surrogate
escape, sat in one entry or in a head field outside the details
entirely. The scan now recovers the array entry by entry, a
poisoned entry degrades alone, a poisoned head field costs the
array nothing, and the whole array fallback remains only when
the array container itself is unreadable in the text.

Finding 5: a corrupt gzip error body on the core decode route,
the whole compressed body arrived and the stream failed after
yielding output, was reported as a read that stopped at the
262144 byte cap, a stop that never happened. A failed stream on
a complete raw read now reports the body unreadable, the same
construction the transport route gives the same body under the
exact lowercase declaration. A failed stream on a capped raw
read keeps the capped reading, because there the failure is the
cut.
"""

from __future__ import annotations

import asyncio
import gzip
import json

import pytest

from placekit import AsyncClient, Client
from placekit.exceptions import (
    AuthenticationError,
    ConfigError,
    InvalidRequestError,
    PlacesError,
    RateLimitError,
    raise_translated,
)

BADREQ = "type.googleapis.com/google.rpc.BadRequest"
QUOTA = "type.googleapis.com/google.rpc.QuotaFailure"
DEBUGINFO = "type.googleapis.com/google.rpc.DebugInfo"

BIG_LITERAL = "9" * 4301
LIMIT_LITERAL = "9" * 4300


@pytest.fixture()
def client(api_key, base_url) -> Client:
    return Client(api_key, base_url=base_url)


def _envelope(details, code=400, status_text="INVALID_ARGUMENT", message="r41 probe"):
    return json.dumps(
        {
            "error": {
                "code": code,
                "message": message,
                "status": status_text,
                "details": details,
            }
        }
    )


def _raised(client, raw_response, body, http_status=400, exc_type=InvalidRequestError, headers=None):
    raw_response(http_status, body, headers=headers)
    with pytest.raises(exc_type) as excinfo:
        client.text_search("anything")
    return excinfo.value


# ------------------------------------------------------------------
# Findings 1 and 2: the constructor copies
# ------------------------------------------------------------------


class RaisingList(list):
    """A list subclass whose iteration raises, the audit shape."""

    def __iter__(self):
        raise RuntimeError("hostile iteration")


@pytest.mark.parametrize(
    "argument", ["details", "field_violations", "quota_violations"]
)
def test_constructor_list_argument_iteration_raises_is_config_error(argument):
    with pytest.raises(ConfigError) as caught:
        PlacesError("boom", **{argument: RaisingList([{"a": 1}])})
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert caught.value.context == "PlacesError"


def test_constructor_hostile_list_through_raise_translated_is_config_error():
    class DuckSource:
        kind = "invalid_request"
        status_code = 400
        google_status = "INVALID_ARGUMENT"
        error_code = 400
        status_mismatch = False
        retryable = False
        retry_after = None
        details = RaisingList([])
        field_violations = []
        quota_violations = []
        context = None

        def __str__(self):
            return "duck invalid request"

    with pytest.raises(ConfigError):
        raise_translated(DuckSource())


def _endless_entries():
    while True:
        yield {"x": 1}


def test_constructor_endless_iterable_refuses_at_the_ceiling():
    with pytest.raises(ConfigError) as caught:
        PlacesError("boom", details=_endless_entries())
    assert "1000" in str(caught.value)


def test_constructor_iterable_past_the_ceiling_refuses():
    entries = ({"i": i} for i in range(2000))
    with pytest.raises(ConfigError) as caught:
        PlacesError("boom", field_violations=entries)
    assert "1000" in str(caught.value)


def test_constructor_iterable_raising_partway_is_config_error():
    def partway():
        yield {"a": 1}
        raise ValueError("midway")

    with pytest.raises(ConfigError) as caught:
        PlacesError("boom", quota_violations=partway())
    assert isinstance(caught.value.__cause__, ValueError)


def test_constructor_short_iterable_materialises():
    entries = ({"i": i} for i in range(3))
    err = PlacesError("boom", details=entries)
    assert err.details == [{"i": 0}, {"i": 1}, {"i": 2}]


def test_constructor_plain_list_past_the_ceiling_is_kept_whole():
    # The library passes its own plain lists, including wire
    # details arrays past the ceiling, and the Round 35 counting
    # identity rests on their length surviving construction.
    entries = [{"i": i} for i in range(5000)]
    err = PlacesError("boom", details=entries)
    assert len(err.details) == 5000
    assert err.details == entries
    assert err.details is not entries


def test_constructor_plain_list_copy_decouples_from_the_caller():
    entries = [{"a": 1}]
    err = PlacesError("boom", details=entries)
    entries.append({"b": 2})
    assert err.details == [{"a": 1}]


def test_constructor_tuple_argument_is_copied_to_a_list():
    err = PlacesError("boom", details=({"a": 1},))
    assert err.details == [{"a": 1}]
    assert isinstance(err.details, list)


def test_constructor_defaults_are_empty_lists():
    err = PlacesError("boom")
    assert err.details == []
    assert err.field_violations == []
    assert err.quota_violations == []


# ------------------------------------------------------------------
# Finding 3: a conversion failing details payload keeps the class
# ------------------------------------------------------------------


def _giant_envelope(member_text, code=400, status_text="INVALID_ARGUMENT"):
    # The digit literal is embedded as raw JSON text, because a
    # Python int of this size cannot even be constructed under
    # the interpreter limit the shape exercises.
    return (
        '{"error": {"code": '
        + str(code)
        + ', "message": "r41 probe", "status": "'
        + status_text
        + '", "details": ['
        + member_text
        + "]}}"
    )


def test_giant_integer_in_a_violation_keeps_the_classification(client, raw_response):
    body = _giant_envelope(
        '{"@type": "'
        + BADREQ
        + '", "fieldViolations": [{"field": "pageSize", "description": '
        + BIG_LITERAL
        + "}]}"
    )
    exc = _raised(client, raw_response, body)
    assert exc.google_status == "INVALID_ARGUMENT"
    assert exc.error_code == 400
    assert exc.details == []
    assert exc.field_violations == []
    assert exc.quota_violations == []


def test_giant_integer_in_a_plain_detail_keeps_the_classification(client, raw_response):
    body = _giant_envelope(
        '{"@type": "' + DEBUGINFO + '", "detail": ' + BIG_LITERAL + "}",
        code=403,
        status_text="PERMISSION_DENIED",
    )
    exc = _raised(
        client, raw_response, body, http_status=200, exc_type=AuthenticationError
    )
    assert exc.google_status == "PERMISSION_DENIED"
    assert exc.details == []


def test_giant_integer_in_a_quota_detail_keeps_class_and_retryable(
    client, raw_response
):
    body = _giant_envelope(
        '{"@type": "'
        + QUOTA
        + '", "violations": [{"subject": "s", "description": "d", "quotaValue": '
        + BIG_LITERAL
        + "}]}",
        code=429,
        status_text="RESOURCE_EXHAUSTED",
    )
    exc = _raised(client, raw_response, body, http_status=429, exc_type=RateLimitError)
    assert exc.retryable is True
    assert exc.details == []
    assert exc.quota_violations == []


def test_integer_at_the_conversion_limit_still_converts_whole(client, raw_response):
    body = _envelope(
        [
            {
                "@type": BADREQ,
                "fieldViolations": [
                    {"field": "pageSize", "description": int(LIMIT_LITERAL)}
                ],
            }
        ]
    )
    exc = _raised(client, raw_response, body)
    assert len(exc.details) == 1
    assert exc.details[0]["fieldViolations"][0]["description"] == int(LIMIT_LITERAL)
    assert exc.field_violations == [
        {"field": "pageSize", "description": int(LIMIT_LITERAL)}
    ]


# ------------------------------------------------------------------
# Finding 4: entry level details recovery on the scan route
# ------------------------------------------------------------------


def _surrogate_body(details_text, status_text="INVALID_ARGUMENT", code_text="400"):
    return (
        '{"error": {"code": '
        + code_text
        + ', "message": "r41 probe", "status": "'
        + status_text
        + '", "details": '
        + details_text
        + "}}"
    )


def test_lone_surrogate_entry_degrades_alone(client, raw_response):
    details = (
        '[{"@type": "'
        + BADREQ
        + '", "fieldViolations": [{"field": "a", "description": "clean"}]}, '
        + '{"@type": "'
        + DEBUGINFO
        + '", "detail": "lone \\ud800 surrogate"}, '
        + '{"@type": "'
        + DEBUGINFO
        + '", "detail": "also clean"}]'
    )
    exc = _raised(client, raw_response, _surrogate_body(details))
    assert exc.google_status == "INVALID_ARGUMENT"
    assert len(exc.details) == 2
    assert exc.details[1]["detail"] == "also clean"
    assert exc.field_violations == [{"field": "a", "description": "clean"}]


def test_lone_surrogate_in_the_status_field_costs_the_details_nothing(
    client, raw_response
):
    body = _surrogate_body(
        '[{"@type": "t", "detail": "kept"}]', status_text="INVALID_\\ud800ARGUMENT"
    )
    exc = _raised(client, raw_response, body)
    assert exc.google_status is None
    assert len(exc.details) == 1
    assert exc.details[0]["detail"] == "kept"


def test_lone_surrogate_in_the_code_field_costs_the_details_nothing(
    client, raw_response
):
    body = _surrogate_body(
        '[{"@type": "t", "detail": "kept"}]', code_text='"4\\ud8000"'
    )
    exc = _raised(client, raw_response, body)
    assert exc.google_status == "INVALID_ARGUMENT"
    assert exc.error_code is None
    assert len(exc.details) == 1


def test_unterminated_details_array_keeps_the_whole_array_fallback(
    client, raw_response
):
    body = (
        '{"error": {"code": 400, "message": "r41 probe", '
        '"status": "INVALID_ARGUMENT", "details": [{"@type": "a"}, {"@type": "b"'
    )
    exc = _raised(client, raw_response, body)
    assert exc.google_status == "INVALID_ARGUMENT"
    assert exc.details == []


# ------------------------------------------------------------------
# Finding 5: a corrupt gzip stream on a complete read
# ------------------------------------------------------------------


def _corrupt_gzip_body() -> bytes:
    # A long envelope flipped late in its deflate stream, so the
    # stream yields its output and then fails, a checksum failure
    # on this body. The raw read is complete, far under the cap.
    detail = "quota detail text " * 60
    body = json.dumps(
        {
            "error": {
                "code": 429,
                "message": "slow down",
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": QUOTA,
                        "violations": [
                            {"subject": "quota", "description": detail}
                        ],
                    }
                ],
            }
        }
    ).encode()
    packed = bytearray(gzip.compress(body, mtime=0))
    packed[int(len(packed) * 0.7)] ^= 0xFF
    return bytes(packed)


@pytest.mark.parametrize("spelling", ["GZip", "gzip"])
def test_corrupt_gzip_on_a_complete_read_reports_unreadable(
    client, raw_response, spelling
):
    exc = _raised(
        client,
        raw_response,
        _corrupt_gzip_body(),
        headers={"Content-Encoding": spelling},
    )
    assert "unreadable" in str(exc)
    assert "stopped at" not in str(exc)
    assert "262144" not in str(exc)


def test_capped_error_body_still_reports_the_cap(client, raw_response):
    exc = _raised(client, raw_response, "x" * 300_000)
    assert "stopped at the 262144 byte cap" in str(exc)


# ------------------------------------------------------------------
# Sync and async parity on the repaired shapes
# ------------------------------------------------------------------


def test_async_parity_on_the_repaired_shapes(api_key, base_url, raw_response):
    giant = _giant_envelope(
        '{"@type": "'
        + BADREQ
        + '", "fieldViolations": [{"field": "pageSize", "description": '
        + BIG_LITERAL
        + "}]}"
    )
    surrogate = _surrogate_body(
        '[{"@type": "t", "detail": "kept"}, '
        '{"@type": "t", "detail": "lone \\ud800 surrogate"}]'
    )

    async def run():
        outcomes = []
        async with AsyncClient(api_key, base_url=base_url) as aclient:
            for body in (giant, surrogate):
                raw_response(400, body)
                try:
                    await aclient.text_search("anything")
                    outcomes.append(None)
                except PlacesError as exc:
                    outcomes.append(exc)
        return outcomes

    giant_exc, surrogate_exc = asyncio.run(run())
    assert isinstance(giant_exc, InvalidRequestError)
    assert giant_exc.google_status == "INVALID_ARGUMENT"
    assert giant_exc.details == []
    assert isinstance(surrogate_exc, InvalidRequestError)
    assert len(surrogate_exc.details) == 1
    assert surrogate_exc.details[0]["detail"] == "kept"
