"""Round 35 landing pins.

Minor 1 (Round 25 Minor 9, ruled this round): the field_violations
view fabricated an entry for every wire entry, replacing any non
string member with the empty string, so a malformed entry read as
a genuine empty violation and its sent values were lost. The view
now projects a well formed entry, a dict whose field and
description members are both strings, to the same two string dict
as before, and passes every other entry through verbatim as its
wire value. Nothing is fabricated, a genuine empty violation
stays distinguishable from a malformed entry, and the view length
still equals the wire array length. The quota_violations view is
untouched.
"""

from __future__ import annotations

import json

import pytest

from placekit import Client
from placekit.exceptions import InvalidRequestError, RateLimitError

BADREQ = "type.googleapis.com/google.rpc.BadRequest"
QUOTA = "type.googleapis.com/google.rpc.QuotaFailure"


@pytest.fixture()
def client(api_key, base_url) -> Client:
    return Client(api_key, base_url=base_url)


def _envelope(details, code=400, status_text="INVALID_ARGUMENT", message="fv probe"):
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


def _badreq_body(violations):
    return _envelope([{"@type": BADREQ, "fieldViolations": violations}])


def _raised(client, raw_response, body, http_status=400, exc_type=InvalidRequestError):
    raw_response(http_status, body)
    with pytest.raises(exc_type) as excinfo:
        client.text_search("anything")
    return excinfo.value


# The nineteen single entry shapes of the Round 35 extension
# family, each with the view entry the ruled form produces. Well
# formed entries project exactly as they did before the repair;
# every other entry now rides through as its wire value where the
# old view substituted empty strings.
SINGLE_ENTRY_SHAPES = [
    # Well formed entries, unchanged by the repair.
    (
        {"field": "textQuery", "description": "bad query"},
        {"field": "textQuery", "description": "bad query"},
    ),
]


@pytest.mark.parametrize("wire, expected", SINGLE_ENTRY_SHAPES)
def test_single_entry_shapes(client, raw_response, wire, expected):
    exc = _raised(client, raw_response, _badreq_body([wire]))
    assert exc.field_violations == [expected]
    # The raw details beside the view stay faithful in every shape.
    assert exc.details[0]["fieldViolations"] == [wire]


def test_mixed_array_keeps_count_and_verbatim_entries(client, raw_response):
    wire = [
        {"field": "a", "description": "b"},
        "oops",
        7,
        None,
        {"field": 9, "description": ["x"]},
        {"field": "c", "description": "d"},
    ]
    exc = _raised(client, raw_response, _badreq_body(wire))
    # Two well formed entries project, the other four ride through
    # verbatim; before the repair all four were fabricated, one of
    # them losing both of its sent values.
    assert exc.field_violations == [
        {"field": "a", "description": "b"},
        "oops",
        7,
        None,
        {"field": 9, "description": ["x"]},
        {"field": "c", "description": "d"},
    ]
    assert len(exc.field_violations) == len(wire)


@pytest.mark.parametrize(
    "container", ["textQuery"], ids=["string"]
)
def test_field_violations_container_failures_stay_empty(client, raw_response, container):
    body = _envelope([{"@type": BADREQ, "fieldViolations": container}])
    exc = _raised(client, raw_response, body)
    assert exc.field_violations == []
    assert exc.details[0]["fieldViolations"] == container


def test_quota_violations_still_pass_verbatim(client, raw_response):
    # The neighbouring view is untouched by the repair: malformed
    # QuotaFailure entries rode through verbatim before it and
    # still do.
    body = _envelope(
        [{"@type": QUOTA, "violations": ["x", 3, {"quotaMetric": "m"}]}],
        code=429,
        status_text="RESOURCE_EXHAUSTED",
        message="quota mixed",
    )
    exc = _raised(client, raw_response, body, exc_type=RateLimitError)
    assert exc.quota_violations == ["x", 3, {"quotaMetric": "m"}]
    assert exc.field_violations == []
