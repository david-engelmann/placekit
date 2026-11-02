"""Round 28 acceptance pins.

Finding 1: the envelope status text joins the 500 character cap
the message and the detail strings already honour. The status is
truncated where the error is built, so the whole document parse
and the tolerant head scan (the parse path a body takes when a
value in it nests past the parser depth limit) both inherit it,
and the rendered exception is bounded on the error path, where
the status renders once, and on the success envelope path,
where it renders twice.
"""

from __future__ import annotations

import json

import pytest

from placekit import Client
from placekit.exceptions import ApiError, InvalidRequestError


@pytest.fixture()
def client(api_key, base_url) -> Client:
    return Client(api_key, base_url=base_url)


def _envelope(status_text: str, code: int = 400, details=None) -> str:
    error = {"code": code, "message": "m", "status": status_text}
    if details is not None:
        error["details"] = details
    return json.dumps({"error": error})


def _nested(depth: int):
    value = "x"
    for _ in range(depth):
        value = [value]
    return value


def test_status_at_the_cap_is_kept_whole(client, raw_response):
    status = "s" * 500
    raw_response(400, _envelope(status))
    with pytest.raises(InvalidRequestError) as excinfo:
        client.text_search("pizza")
    assert excinfo.value.google_status == status


def test_status_one_past_the_cap_truncates(client, raw_response):
    raw_response(400, _envelope("s" * 501))
    with pytest.raises(InvalidRequestError) as excinfo:
        client.text_search("pizza")
    exc = excinfo.value
    assert exc.google_status == "s" * 500
    assert "s" * 500 in str(exc)
    assert "s" * 501 not in str(exc)


def test_status_far_past_the_cap_truncates_on_the_error_path(client, raw_response):
    raw_response(400, _envelope("s" * 5000))
    with pytest.raises(InvalidRequestError) as excinfo:
        client.text_search("pizza")
    exc = excinfo.value
    assert exc.google_status == "s" * 500
    # The error path renders the status once, so the whole
    # exception stays within one cap of status text.
    assert str(exc).count("s" * 500) == 1


def test_status_truncates_on_the_head_scan_path(client, raw_response):
    # The detail nested 200 deep defeats the whole document
    # parse, so the status is recovered by the tolerant head
    # scan; the cap holds there too.
    body = _envelope("s" * 5000, details=[_nested(200)])
    raw_response(400, body)
    with pytest.raises(InvalidRequestError) as excinfo:
        client.text_search("pizza")
    assert excinfo.value.google_status == "s" * 500


def test_padded_known_status_still_falls_to_the_http_class(client, raw_response):
    # A padded known status never matched when it passed through
    # whole; truncating it must not start matching it.
    raw_response(400, _envelope("RESOURCE_EXHAUSTED" + "s" * 5000))
    with pytest.raises(InvalidRequestError) as excinfo:
        client.text_search("pizza")
    assert excinfo.value.google_status == ("RESOURCE_EXHAUSTED" + "s" * 5000)[:500]


def test_markup_status_is_bounded_on_the_success_envelope_path(client, raw_response):
    # An envelope on a success status renders the status twice,
    # once in the ApiError headline and once in the attribute
    # suffix; the cap bounds both renderings at once.
    status = "<b>" + "z" * 5022
    raw_response(200, _envelope(status))
    with pytest.raises(ApiError) as excinfo:
        client.text_search("pizza")
    exc = excinfo.value
    capped = status[:500]
    assert exc.google_status == capped
    assert str(exc).count(capped) == 2
    assert "z" * 498 not in str(exc)
