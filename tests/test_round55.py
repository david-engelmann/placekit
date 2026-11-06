"""Round 55 landing pins.

The depth verdict of payload validation is decided in the Rust
core from this round. The walk in ``placekit.models`` stays in
Python, reading the payload through its own container protocols
in the order it always has, and sends the core one trace event
per container visit, capped at the first visit past the limit.
These pins hold the delegation to that contract. The walk reads
exactly what the pre port walk read, in the same order, a
refusal names the model and the limit and never the node, and
no container past the first visit over the limit is read at
all.
"""

from __future__ import annotations

import pytest

from placekit import _placekit
from placekit.exceptions import DecodeError
from placekit.models import (
    _MAX_PAYLOAD_DEPTH,
    Place,
    _validate_and_copy_payload,
    _validate_payload,
)


class LogDict(dict):
    """A mapping that records every values read against a shared
    log, under a label."""

    log: list = []

    def __init__(self, label, *args):
        super().__init__(*args)
        self.label = label

    def values(self):
        LogDict.log.append(("values", self.label))
        return super().values()


class LogList(list):
    """A list that records every iteration against the shared
    log, under a label."""

    def __init__(self, label, *args):
        super().__init__(*args)
        self.label = label

    def __iter__(self):
        LogDict.log.append(("iter", self.label))
        return super().__iter__()


class LogTuple(tuple):
    """A tuple that records every iteration against the shared
    log, under a label."""

    def __new__(cls, label, items=()):
        obj = super().__new__(cls, items)
        obj.label = label
        return obj

    def __iter__(self):
        LogDict.log.append(("iter", self.label))
        return super().__iter__()


class RaiseValuesDict(LogDict):
    """A mapping whose values read raises the configured
    exception on the configured call."""

    def __init__(self, label, exc, *args):
        super().__init__(label, *args)
        self.exc = exc

    def values(self):
        LogDict.log.append(("values", self.label))
        raise self.exc


class ShallowValuesDict(LogDict):
    """A mapping whose values read reports one scalar child
    whatever the mapping really holds."""

    def values(self):
        LogDict.log.append(("values", self.label))
        return [0]


@pytest.fixture(autouse=True)
def _clear_log():
    LogDict.log = []
    yield
    LogDict.log = []


def _chain_dicts(total_depth):
    node = LogDict(f"d{total_depth}")
    for depth in range(total_depth - 1, 0, -1):
        parent = LogDict(f"d{depth}")
        parent["child"] = node
        node = parent
    return node


def _payload_at_depth(total):
    node = {"leaf": 1}
    for _ in range(total - 2):
        node = {"layer": node}
    return {"id": "x", "unknownFutureField": node}


def test_binding_verdict_over_hand_traces():
    # The empty trace is the one shape the walk itself can never
    # produce, since the payload root is always a mapping visit.
    # The core mirror tests in crates/placekit-core/src/models.rs
    # (payload_depth_empty_trace_stays_within_limit and its
    # companions) carry the same cases on the other side.
    verdict = _placekit.models_payload_depth_within_limit
    assert verdict([]) is True
    assert verdict([(0, 1)]) is True
    assert verdict([(0, 1), (1, 2), (0, 3)]) is True
    assert verdict([(0, _MAX_PAYLOAD_DEPTH)]) is True
    assert verdict([(1, _MAX_PAYLOAD_DEPTH)]) is True
    assert verdict([(0, _MAX_PAYLOAD_DEPTH + 1)]) is False
    assert verdict([(1, _MAX_PAYLOAD_DEPTH + 1)]) is False
    # The verdict reads every event, not the final one.
    assert verdict([(0, 1), (0, _MAX_PAYLOAD_DEPTH + 1), (1, 2)]) is False


def test_depths_inside_the_limit_validate():
    for total in (2, 100, 127, 128):
        _validate_payload(_chain_dicts(total), "Place")


def test_depth_boundary_through_dicts():
    _validate_payload(_chain_dicts(128), "Place")
    with pytest.raises(DecodeError) as caught:
        _validate_payload(_chain_dicts(129), "Place")
    assert str(caught.value) == "Place payload is nested deeper than 128 levels"


def test_depth_boundary_through_lists():
    def payload(total):
        node = LogList(f"l{total}")
        for depth in range(total - 1, 1, -1):
            parent = LogList(f"l{depth}")
            parent.append(node)
            node = parent
        root = LogDict("root")
        root["child"] = node
        return root

    _validate_payload(payload(128), "Place")
    with pytest.raises(DecodeError):
        _validate_payload(payload(129), "Place")


def test_depth_boundary_through_tuples_and_mixed():
    def tuples(total):
        node = LogTuple(f"t{total}")
        for depth in range(total - 1, 1, -1):
            node = LogTuple(f"t{depth}", (node,))
        root = LogDict("root")
        root["child"] = node
        return root

    def mixed(total):
        node = None
        for depth in range(total, 1, -1):
            if depth % 3 == 0:
                parent = LogDict(f"m{depth}")
                if node is not None:
                    parent["child"] = node
                node = parent
            elif depth % 3 == 1:
                parent = LogList(f"m{depth}")
                if node is not None:
                    parent.append(node)
                node = parent
            else:
                node = LogTuple(f"m{depth}", () if node is None else (node,))
        root = LogDict("root")
        root["child"] = node
        return root

    _validate_payload(tuples(128), "Place")
    with pytest.raises(DecodeError):
        _validate_payload(tuples(129), "Place")
    _validate_payload(mixed(128), "Place")
    with pytest.raises(DecodeError):
        _validate_payload(mixed(129), "Place")


def test_depth_boundary_through_validate_and_copy():
    copied = _validate_and_copy_payload(_payload_at_depth(128), "Place")
    assert copied["unknownFutureField"] is not None
    with pytest.raises(DecodeError) as caught:
        _validate_and_copy_payload(_payload_at_depth(129), "Place")
    assert "nested deeper than 128 levels" in str(caught.value)


def test_depth_boundary_on_the_direct_path():
    place = Place.from_api(_payload_at_depth(128))
    assert place.id == "x"
    with pytest.raises(DecodeError):
        Place.from_api(_payload_at_depth(129))


def test_walk_reads_in_the_pre_port_order():
    leaf = LogDict("leaf")
    seq = LogList("seq")
    seq.append(leaf)
    sibling = LogDict("sibling")
    root = LogDict("root")
    root["a"] = seq
    root["b"] = sibling
    _validate_payload(root, "Place")
    # Children are pushed in iteration order and popped from the
    # end of the stack, so the sibling subtree is read before the
    # sequence subtree even though it was inserted second.
    assert LogDict.log == [
        ("values", "root"),
        ("values", "sibling"),
        ("iter", "seq"),
        ("values", "leaf"),
    ]


def test_breach_stops_the_walk_at_the_first_deep_visit():
    _payload = _chain_dicts(140)
    with pytest.raises(DecodeError):
        _validate_payload(_payload, "Place")
    # The containers at depths 1 to 128 are read. The container
    # at depth 129 is visited but its own values read never
    # happens, and nothing deeper was ever pushed.
    assert LogDict.log == [("values", f"d{depth}") for depth in range(1, 129)]


def test_no_container_past_the_breach_is_read():
    raiser = RaiseValuesDict("raiser", RuntimeError("raiser boom"))
    root = LogDict("root")
    root["a_raiser"] = raiser
    root["z_deep"] = _chain_dicts(129)
    with pytest.raises(DecodeError) as caught:
        _validate_payload(root, "Place")
    # The deep subtree is popped before the raiser in stack
    # order, so the refusal is the depth refusal and the raiser
    # was never read at all.
    assert "nested deeper than 128 levels" in str(caught.value)
    assert ("values", "raiser") not in LogDict.log


def test_values_raise_wraps_as_could_not_be_read():
    root = RaiseValuesDict("root", RuntimeError("values boom"))
    with pytest.raises(DecodeError) as caught:
        _validate_payload(root, "Place")
    assert str(caught.value) == "Place payload could not be read: RuntimeError('values boom')"
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_values_raise_of_decodeerror_escapes_unwrapped():
    # The guarded walk has always let a DecodeError a caller
    # protocol raises pass through as itself, beside the wraps.
    err = DecodeError("caller decode boom")
    root = RaiseValuesDict("root", err)
    with pytest.raises(DecodeError) as caught:
        _validate_payload(root, "Place")
    assert caught.value is err


def test_baseexception_passes_through():
    root = RaiseValuesDict("root", KeyboardInterrupt("halt"))
    with pytest.raises(KeyboardInterrupt):
        _validate_payload(root, "Place")


def test_shallow_values_lie_still_validates():
    # The walk trusts the values answer it is given, so a
    # mapping that understates its nesting validates today
    # (genus G3) and validates identically through the port.
    deep = {"leaf": 1}
    for _ in range(200):
        deep = {"layer": deep}
    shallow = ShallowValuesDict("shallow")
    shallow["deep"] = deep
    root = LogDict("root")
    root["x"] = shallow
    _validate_payload(root, "Place")
    assert LogDict.log == [("values", "root"), ("values", "shallow")]


def test_self_referential_payload_refuses_at_the_guard():
    root = LogDict("root")
    root["self"] = root
    with pytest.raises(DecodeError) as caught:
        _validate_payload(root, "Place")
    assert "nested deeper than 128 levels" in str(caught.value)


def test_nonmapping_root_refusal_unchanged():
    with pytest.raises(DecodeError) as caught:
        _validate_payload([1, 2], "Place")
    assert str(caught.value) == "Place payload must be an object, got list: [1, 2]"
    with pytest.raises(DecodeError) as caught:
        _validate_payload("text", "Place")
    assert str(caught.value) == "Place payload must be an object, got str: 'text'"
