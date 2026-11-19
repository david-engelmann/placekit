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

from placekit.exceptions import ApiError, InvalidRequestError


def _envelope(status_text: str, code: int = 400, details=None) -> str:
    error = {"code": code, "message": "m", "status": status_text}
    if details is not None:
        error["details"] = details
    return json.dumps({"error": error})


def test_status_one_past_the_cap_truncates(client, raw_response):
    raw_response(400, _envelope("s" * 501))
    with pytest.raises(InvalidRequestError) as excinfo:
        client.text_search("pizza")
    exc = excinfo.value
    assert exc.google_status == "s" * 500
    assert "s" * 500 in str(exc)
    assert "s" * 501 not in str(exc)
    assert str(exc).count("s" * 500) == 1


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
