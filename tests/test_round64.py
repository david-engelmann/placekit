"""Round 64 pins for the extension stub integer widths.

The extension stub declares plain int at three slots whose
bindings read narrower widths. The rank in a mask sorted order
key is an unsigned 8 bit value, the kind tag in a payload depth
trace is an unsigned 8 bit value, and the depth beside it is an
unsigned 32 bit value. No exact stub type states those widths
without misdescribing what the core accepts, so the stub now
carries the widths as prose beside the two declarations, and
these pins hold the runtime to the stated boundaries. A value
at the top of a width is accepted and judged, and a value one
past the width or below zero raises OverflowError before any
judgement happens. The Python layer itself only ever mints 0
and 1 at the rank and kind slots, and the prose states that
beside the widths.
"""

from __future__ import annotations

import pytest

from placekit import _placekit


def test_sorted_order_rank_accepts_the_top_of_its_width():
    assert _placekit.mask_sorted_order([(255, b"ab")]) == [0]
    assert _placekit.mask_sorted_order([(0, b"ab"), (255, b"cd")]) == [0, 1]


def test_sorted_order_rank_refuses_past_its_width():
    with pytest.raises(OverflowError):
        _placekit.mask_sorted_order([(256, b"ab")])


def test_sorted_order_rank_refuses_below_zero():
    with pytest.raises(OverflowError):
        _placekit.mask_sorted_order([(-1, b"ab")])


def test_depth_trace_kind_accepts_the_top_of_its_width():
    assert _placekit.models_payload_depth_within_limit([(255, 1)]) is True


def test_depth_trace_kind_refuses_past_its_width():
    with pytest.raises(OverflowError):
        _placekit.models_payload_depth_within_limit([(256, 1)])


def test_depth_trace_kind_refuses_below_zero():
    with pytest.raises(OverflowError):
        _placekit.models_payload_depth_within_limit([(-1, 1)])


def test_depth_trace_depth_accepts_the_top_of_its_width():
    # A depth at the top of the 32 bit width is read and judged,
    # and the judgement is False against the core depth limit.
    assert _placekit.models_payload_depth_within_limit([(0, 4294967295)]) is False


def test_depth_trace_depth_refuses_past_its_width():
    with pytest.raises(OverflowError):
        _placekit.models_payload_depth_within_limit([(0, 4294967296)])


def test_depth_trace_depth_refuses_below_zero():
    with pytest.raises(OverflowError):
        _placekit.models_payload_depth_within_limit([(0, -1)])
