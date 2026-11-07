"""Round 54 landing pins.

FieldMask construction is computed in the Rust core from this
round. The Python class reads its arguments through the same
guarded reads as before, converts the checked paths into plain
data, and lets the core decide the path grammar, the duplicate
dropping and the ordering of a set of paths. These pins hold the
delegation to the two halves of that contract. Where a caller
operation raises, construction still surfaces the raise at the
old site under the old ConfigError wording, and the stored paths
are still the caller's own first seen objects. Where a caller
operation returns a wrong answer instead of raising, the
construction follows the values as sent to the core, the
boundary the module docstring and the changelog entry state.
"""

from __future__ import annotations

import pytest

from placekit.exceptions import ConfigError
from placekit.fields import FieldMask


class CountingStr(str):
    """A string member that counts the operations construction
    performs on it."""

    def __init__(self, *args):
        self.counts = {"strip": 0, "split": 0, "contains": 0, "hash": 0, "eq": 0}

    def strip(self, *args):
        self.counts["strip"] += 1
        return super().strip(*args)

    def split(self, *args):
        self.counts["split"] += 1
        return super().split(*args)

    def __contains__(self, item):
        self.counts["contains"] += 1
        return super().__contains__(item)

    def __hash__(self):
        self.counts["hash"] += 1
        return super().__hash__()

    def __eq__(self, other):
        self.counts["eq"] += 1
        return super().__eq__(other)


class StripRaises(str):
    calls = 0

    def strip(self, *args):
        StripRaises.calls += 1
        raise ValueError("strip boom")


class LenLie(str):
    """Truthiness lies. The length reads zero, so the pre port
    truthiness test in the path check refused a sound path."""

    def __len__(self):
        return 0


class ContainsLie(str):
    """Membership lies. A comma is reported in every member, so
    the pre port membership test refused a sound path."""

    def __contains__(self, item):
        return True


class SplitLie(str):
    """Split lies. The segments read as a sound path whatever the
    content holds."""

    def split(self, *args):
        return ["places", "id"]


class EqNever(str):
    """Equality lies. No member ever equals another, so the pre
    port dedupe kept a duplicate the content makes plain."""

    __hash__ = str.__hash__

    def __eq__(self, other):
        return False


class LtNever(str):
    """Comparison lies. No member ever sorts before another, so
    the pre port set ordering kept the materialised order."""

    __hash__ = str.__hash__

    def __lt__(self, other):
        return False


class EncodeBomb(str):
    """Encoding raises. The pre port construction never called
    encode on a member, so the port must not call it either."""

    def encode(self, *args, **kwargs):
        raise RuntimeError("encode boom")


class BadRepr:
    calls = 0

    def __repr__(self):
        BadRepr.calls += 1
        raise RuntimeError("repr boom")


def test_construction_reads_each_member_once_per_site():
    first, second = CountingStr("places.id"), CountingStr("places.id")
    FieldMask(first, second)
    for member in (first, second):
        assert member.counts["strip"] == 1
        assert member.counts["split"] == 1
        assert member.counts["contains"] == 1
        assert member.counts["hash"] == 1
    # The dedupe meets the duplicate exactly once, against the
    # stored first member, and no other read compares members.
    assert first.counts["eq"] == 1
    assert second.counts["eq"] == 0


def test_construction_of_distinct_members_compares_nothing_in_dedupe():
    first, second = CountingStr("places.id"), CountingStr("places.name")
    FieldMask(first, second)
    assert first.counts["eq"] == 0
    assert second.counts["eq"] == 0


def test_dedupe_stores_the_first_seen_object():
    class PlainSub(str):
        pass

    first, second = PlainSub("places.id"), PlainSub("places.id")
    mask = FieldMask(first, second)
    assert mask.paths == ("places.id",)
    assert mask.paths[0] is first


def test_a_refused_first_member_leaves_the_second_untouched():
    StripRaises.calls = 0
    with pytest.raises(ConfigError):
        FieldMask("bad path", StripRaises("places.id"))
    assert StripRaises.calls == 0


def test_a_raising_first_member_surfaces_before_the_second_is_judged():
    StripRaises.calls = 0
    with pytest.raises(ConfigError) as caught:
        FieldMask(StripRaises("places.id"), "bad path")
    assert isinstance(caught.value.__cause__, ValueError)
    assert StripRaises.calls == 1


def test_lying_truthiness_is_judged_by_content():
    mask = FieldMask(LenLie("places.id"))
    assert mask.paths == ("places.id",)
    assert mask.header_value == "places.id"


def test_lying_membership_is_judged_by_content():
    mask = FieldMask(ContainsLie("places.id"))
    assert mask.paths == ("places.id",)


def test_lying_split_is_judged_by_content():
    with pytest.raises(ConfigError):
        FieldMask(SplitLie("places..id"))


def test_lying_equality_dedupes_by_content():
    mask = FieldMask(EqNever("places.id"), "places.id")
    # The stored member is the EqNever itself, whose equality
    # always answers False, so the pin reads its length and its
    # content rather than comparing the tuple.
    assert len(mask.paths) == 1
    assert type(mask.paths[0]) is EqNever
    assert str(mask.paths[0]) == "places.id"


def test_lying_comparison_orders_a_set_by_content():
    mask = FieldMask.of({LtNever("places.name"), LtNever("places.id")})
    assert mask.paths == ("places.id", "places.name")


def test_encode_is_never_called_on_a_member():
    mask = FieldMask(EncodeBomb("places.id"))
    assert mask.paths == ("places.id",)


def test_mixed_set_renders_a_bad_repr_member_once_per_site():
    BadRepr.calls = 0
    with pytest.raises(ConfigError) as caught:
        FieldMask.of({BadRepr(), "places.id"})
    assert "<BadRepr whose repr raised>" in str(caught.value)
    # Once for the sort key, once for the refusal message.
    assert BadRepr.calls == 2


def test_lone_surrogate_member_is_refused():
    with pytest.raises(ConfigError):
        FieldMask("places.id\ud800x")


def test_header_value_of_a_single_exact_member_is_that_member():
    mask = FieldMask("places.id")
    assert mask.header_value is mask.paths[0]


def test_header_value_of_a_single_subclass_member_is_a_plain_string():
    class PlainSub(str):
        pass

    member = PlainSub("places.id")
    mask = FieldMask(member)
    assert mask.header_value == "places.id"
    assert type(mask.header_value) is str
