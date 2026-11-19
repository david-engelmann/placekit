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

import pytest

from conftest import envelope as _envelope, raised as _raised
from placekit.exceptions import RateLimitError

BADREQ = "type.googleapis.com/google.rpc.BadRequest"
QUOTA = "type.googleapis.com/google.rpc.QuotaFailure"


def _badreq_body(violations):
    return _envelope([{"@type": BADREQ, "fieldViolations": violations}])


# The well-formed single entry shape of the Round 35 extension
# family, with the view entry the ruled form produces. The full
# nineteen shapes stand in the core pin
# field_violations_single_entry_shapes in errors.rs; this list
# carries the one wiring shape. Well formed entries project
# exactly as they did before the repair; every other entry now
# rides through as its wire value where the old view substituted
# empty strings.
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
