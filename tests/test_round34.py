"""Round 34 landing pins.

Red team Minor 1: the FieldMask constructor dedupe and the set
sort inside FieldMask.of read members once more past the Round 31
guarded path check, so a member whose hash, equality or comparison
raises escaped standalone construction as a bare builtin. The
dedupe and the sort now sit inside the same typed discipline, on
the constructor, on FieldMask.of, and on the raw iterable door of
normalize_fields alike. Red team Minor 2: the PlacesError
retry_after normalisation admitted int and float by isinstance and
then called float on the value, so an int too large to convert and
numeric subclasses whose conversion raises escaped the constructor
bare, breaking the Round 25 rule that the stored value is a float
or None. A conversion failure now reads as None.
"""

from __future__ import annotations

import pytest

from placekit.exceptions import ConfigError, PlacesError
from placekit.fields import FieldMask, normalize_fields


class HashBomb(str):
    def __hash__(self):
        raise RuntimeError("hash bomb")


class EqBomb(str):
    __hash__ = str.__hash__

    def __eq__(self, other):
        raise RuntimeError("eq bomb")


class LtBomb(str):
    __hash__ = str.__hash__

    def __lt__(self, other):
        raise RuntimeError("lt bomb")


class HashRaisesOnSecondCall(str):
    """Hashes once, so a dict can be built over it, then raises.

    A dict whose keys always raise cannot be constructed at all,
    so the dict keys door of FieldMask.of is pinned with a member
    whose second hash read, the one the constructor dedupe spends,
    is the raising one.
    """

    def __init__(self, *args):
        self.hash_calls = 0

    def __hash__(self):
        self.hash_calls += 1
        if self.hash_calls > 1:
            raise RuntimeError("hash bomb on the second read")
        return str.__hash__(self)


class FloatBomb(float):
    def __float__(self):
        raise RuntimeError("float bomb")


class IntFloatBomb(int):
    def __float__(self):
        raise RuntimeError("int float bomb")


# --- Minor 1: FieldMask member reads past the path check


def test_mask_constructor_hash_raising_member_is_config_error():
    with pytest.raises(ConfigError) as caught:
        FieldMask(HashBomb("places.id"))
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_mask_constructor_equality_raising_duplicate_is_config_error():
    with pytest.raises(ConfigError) as caught:
        FieldMask(EqBomb("places.id"), EqBomb("places.id"))
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_mask_of_list_hash_raising_duplicate_is_config_error():
    with pytest.raises(ConfigError):
        FieldMask.of([HashBomb("places.id"), HashBomb("places.id")])


def test_mask_of_dict_keys_hash_raising_member_is_config_error():
    keys = {
        HashRaisesOnSecondCall("places.id"): 1,
        HashRaisesOnSecondCall("places.id"): 2,
    }
    with pytest.raises(ConfigError):
        FieldMask.of(keys)


def test_mask_of_set_comparison_raising_member_is_config_error():
    with pytest.raises(ConfigError) as caught:
        FieldMask.of({LtBomb("places.id"), LtBomb("places.name")})
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_normalize_fields_list_hash_raising_member_is_config_error():
    with pytest.raises(ConfigError):
        normalize_fields([HashBomb("places.id"), HashBomb("places.id")])


def test_mask_single_equality_raising_member_still_constructs():
    # Equality is never consulted for a lone member, so this door
    # behaves exactly as it did before the repair. The header is
    # the comparison because comparing the stored member itself
    # would spend the equality this class exists to withhold.
    mask = FieldMask(EqBomb("places.id"))
    assert len(mask.paths) == 1
    assert mask.header_value == "places.id"


def test_mask_of_generator_comparison_raising_member_still_constructs():
    # No set reaches the sort on this door, and the dedupe never
    # compares for order, so the mask builds as it did before.
    mask = FieldMask.of(iter([LtBomb("places.id"), LtBomb("places.name")]))
    assert mask.paths == ("places.id", "places.name")


# --- Minor 2: retry_after conversion failures read as None


def test_places_error_retry_after_huge_int_reads_as_none():
    assert PlacesError("x", retry_after=10**400).retry_after is None


def test_places_error_retry_after_float_conversion_raising_reads_as_none():
    assert PlacesError("x", retry_after=FloatBomb(1.5)).retry_after is None


def test_places_error_retry_after_int_conversion_raising_reads_as_none():
    assert PlacesError("x", retry_after=IntFloatBomb(7)).retry_after is None


def test_places_error_retry_after_convertible_values_still_store():
    assert PlacesError("x", retry_after=2**63).retry_after == float(2**63)
    assert PlacesError("x", retry_after=7).retry_after == 7.0
