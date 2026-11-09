"""Round 65 pins for the guarded rendering of caught exceptions.

Several seats formatted a caught exception or a caller supplied
value with a plain repr or a plain string conversion inside the
very code whose documented job is converting caller failures
into a chained ConfigError or rendering an exception safely. A
crafted exception whose own repr raises detonated those seats
and escaped bare through the exception constructor, the field
mask builder, the client argument wrap, the address entry guard
and the exception string conversion itself. The class name the
exception repr reads stood outside that repair and fell to the
build red team, and its pins close this file. The seats now render
through a guarded path on the models pattern. The ordinary
rendering is tried first, a failure falls back to a form naming
the type through a guarded name reading, and where the name
cannot be read as a plain string a fixed unrepresentable form
stands in. For every ordinary exception, value and message the
rendered wording is byte identical to the wording before this
round, and the controls beside each detonation pin hold that
identity. One wording change is intended rather than incidental.
A routing mapping whose items method itself raises now surfaces
under the mapping copy wording its own docstring always
promised, naming the parameter, instead of the argument wrap
wording that used to catch it one level up.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from placekit import Client
from placekit.address import country_code, untyped_components
from placekit.exceptions import ConfigError, PlacesError
from placekit.fields import FieldMask
from placekit.models import AddressComponent, Place


class ReprBomb(Exception):
    """An exception whose repr raises a plain RuntimeError."""

    def __repr__(self):
        raise RuntimeError("repr detonated")


BOMB = ReprBomb("kaboom")


class IterBomb:
    def __iter__(self):
        raise BOMB


class IterPlain:
    def __iter__(self):
        raise ValueError("plain iter failure")


def bomb_details_gen():
    yield {"ok": 1}
    raise BOMB


def plain_details_gen():
    yield {"ok": 1}
    raise ValueError("plain stream failure")


def bomb_mask_gen():
    yield "places.displayName"
    raise BOMB


def plain_mask_gen():
    yield "places.displayName"
    raise ValueError("plain stream failure")


# --- The bounded read seats, driven through the constructor ----------


def test_ctor_details_iter_bomb_converts():
    with pytest.raises(ConfigError) as caught:
        PlacesError("m", details=IterBomb())
    assert caught.value.message == (
        "details could not be read as an iterable: "
        "<ReprBomb whose repr raised>"
    )
    assert caught.value.context == "PlacesError"
    assert caught.value.__cause__ is BOMB


def test_ctor_details_iter_plain_control():
    with pytest.raises(ConfigError) as caught:
        PlacesError("m", details=IterPlain())
    assert caught.value.message == (
        "details could not be read as an iterable: "
        "ValueError('plain iter failure')"
    )
    assert caught.value.context == "PlacesError"
    assert isinstance(caught.value.__cause__, ValueError)


def test_ctor_details_gen_bomb_converts():
    with pytest.raises(ConfigError) as caught:
        PlacesError("m", details=bomb_details_gen())
    assert caught.value.message == (
        "details raised while being read: "
        "<ReprBomb whose repr raised>"
    )
    assert caught.value.context == "PlacesError"
    assert caught.value.__cause__ is BOMB


def test_ctor_details_gen_plain_control():
    with pytest.raises(ConfigError) as caught:
        PlacesError("m", details=plain_details_gen())
    assert caught.value.message == (
        "details raised while being read: "
        "ValueError('plain stream failure')"
    )
    assert caught.value.context == "PlacesError"
    assert isinstance(caught.value.__cause__, ValueError)


# --- The bounded read seat, driven through FieldMask.of ---------------


def test_fieldmask_of_gen_bomb_converts():
    with pytest.raises(ConfigError) as caught:
        FieldMask.of(bomb_mask_gen())
    assert caught.value.message == (
        "field paths raised while being read: "
        "<ReprBomb whose repr raised>"
    )
    assert caught.value.context == "FieldMask"
    assert caught.value.__cause__ is BOMB


def test_fieldmask_of_gen_plain_control():
    with pytest.raises(ConfigError) as caught:
        FieldMask.of(plain_mask_gen())
    assert caught.value.message == (
        "field paths raised while being read: "
        "ValueError('plain stream failure')"
    )
    assert caught.value.context == "FieldMask"
    assert isinstance(caught.value.__cause__, ValueError)


# --- The fields safe repr fallback ------------------------------------


class ReprBombValue:
    def __repr__(self):
        raise RuntimeError("repr detonated")


class OddNameMeta(type):
    @property
    def __name__(cls):
        return 5


class OddNameValue(metaclass=OddNameMeta):
    def __repr__(self):
        raise RuntimeError("repr detonated")


def test_fieldmask_ctor_unreadable_name_value_converts():
    with pytest.raises(ConfigError) as caught:
        FieldMask(OddNameValue())
    assert caught.value.message == (
        "invalid field mask path: <unrepresentable value>"
    )
    assert caught.value.context == "FieldMask"


def test_fieldmask_ctor_repr_bomb_value_keeps_fallback_wording():
    with pytest.raises(ConfigError) as caught:
        FieldMask(ReprBombValue())
    assert caught.value.message == (
        "invalid field mask path: <ReprBombValue whose repr raised>"
    )
    assert caught.value.context == "FieldMask"


# --- The client mapping copy seats ------------------------------------


class BombMapping(Mapping):
    def __getitem__(self, key):
        raise KeyError(key)

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def items(self):
        raise BOMB


class ItemsPlainMapping(Mapping):
    def __getitem__(self, key):
        raise KeyError(key)

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def items(self):
        raise ValueError("plain items failure")


class StreamBombMapping(Mapping):
    def __getitem__(self, key):
        raise KeyError(key)

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def items(self):
        def stream():
            yield ("origin", {"latitude": 1.0, "longitude": 2.0})
            raise BOMB

        return stream()


class StreamPlainMapping(Mapping):
    def __getitem__(self, key):
        raise KeyError(key)

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def items(self):
        def stream():
            yield ("origin", {"latitude": 1.0, "longitude": 2.0})
            raise ValueError("plain stream failure")

        return stream()


def test_text_search_routing_items_bomb_converts():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.text_search("coffee", routing_parameters=BombMapping())
    assert caught.value.message == (
        "routing_parameters raised while being read: "
        "<ReprBomb whose repr raised>"
    )
    assert caught.value.context == "text_search"
    assert caught.value.__cause__ is BOMB


def test_text_search_routing_items_plain_new_wording():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.text_search(
            "coffee", routing_parameters=ItemsPlainMapping()
        )
    assert caught.value.message == (
        "routing_parameters raised while being read: "
        "ValueError('plain items failure')"
    )
    assert caught.value.context == "text_search"
    assert isinstance(caught.value.__cause__, ValueError)


def test_text_search_routing_stream_bomb_converts():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.text_search(
            "coffee", routing_parameters=StreamBombMapping()
        )
    assert caught.value.message == (
        "routing_parameters raised while being read: "
        "<ReprBomb whose repr raised>"
    )
    assert caught.value.context == "text_search"
    assert caught.value.__cause__ is BOMB


def test_text_search_routing_stream_plain_control():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.text_search(
            "coffee", routing_parameters=StreamPlainMapping()
        )
    assert caught.value.message == (
        "routing_parameters raised while being read: "
        "ValueError('plain stream failure')"
    )
    assert caught.value.context == "text_search"
    assert isinstance(caught.value.__cause__, ValueError)


# --- The client argument wrap ------------------------------------------


class BombInt(int):
    def __ge__(self, other):
        raise BOMB

    def __le__(self, other):
        raise BOMB


class PlainInt(int):
    def __ge__(self, other):
        raise ValueError("plain comparison failure")

    def __le__(self, other):
        raise ValueError("plain comparison failure")


def test_place_photo_bomb_int_converts():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_photo(
            "places/x/photos/y", max_width_px=BombInt(100)
        )
    assert caught.value.message == (
        "an argument for place_photo raised while it was being "
        "validated: <ReprBomb whose repr raised>"
    )
    assert caught.value.context == "place_photo"
    assert caught.value.__cause__ is BOMB


def test_place_photo_plain_int_control():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_photo(
            "places/x/photos/y", max_width_px=PlainInt(100)
        )
    assert caught.value.message == (
        "an argument for place_photo raised while it was being "
        "validated: ValueError('plain comparison failure')"
    )
    assert caught.value.context == "place_photo"
    assert isinstance(caught.value.__cause__, ValueError)


class FloatBomb(float):
    def __float__(self):
        raise BOMB


def test_text_search_min_rating_float_bomb_converts():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.text_search("coffee", min_rating=FloatBomb(3.0))
    assert caught.value.message == (
        "an argument for text_search raised while it was being "
        "validated: <ReprBomb whose repr raised>"
    )
    assert caught.value.context == "text_search"
    assert caught.value.__cause__ is BOMB


# --- The address entry guard -------------------------------------------


class BombList(list):
    def __iter__(self):
        raise BOMB


class PlainList(list):
    def __iter__(self):
        raise ValueError("plain types failure")


def bomb_component():
    return AddressComponent(
        long_text="Main Street",
        short_text="Main St",
        types=BombList(["route"]),
    )


def plain_component():
    return AddressComponent(
        long_text="Main Street",
        short_text="Main St",
        types=PlainList(["route"]),
    )


def test_address_untyped_components_bomb_converts():
    with pytest.raises(ConfigError) as caught:
        untyped_components([bomb_component()])
    assert caught.value.message == (
        "an argument for untyped_components raised while it was "
        "being read: <ReprBomb whose repr raised>"
    )
    assert caught.value.context == "untyped_components"
    assert caught.value.__cause__ is BOMB


def test_address_country_code_bomb_converts():
    place = Place(id="x", address_components=[bomb_component()])
    with pytest.raises(ConfigError) as caught:
        country_code(place)
    assert caught.value.message == (
        "an argument for country_code raised while it was "
        "being read: <ReprBomb whose repr raised>"
    )
    assert caught.value.context == "country_code"
    assert caught.value.__cause__ is BOMB


def test_address_untyped_components_plain_control():
    with pytest.raises(ConfigError) as caught:
        untyped_components([plain_component()])
    assert caught.value.message == (
        "an argument for untyped_components raised while it was "
        "being read: ValueError('plain types failure')"
    )
    assert caught.value.context == "untyped_components"
    assert isinstance(caught.value.__cause__, ValueError)


# --- The exception string conversion ------------------------------------


class FormatBomb:
    def __str__(self):
        raise RuntimeError("str detonated")

    def __format__(self, spec):
        raise RuntimeError("format detonated")

    def __repr__(self):
        raise RuntimeError("repr detonated")


class StrBomb:
    def __str__(self):
        raise RuntimeError("str detonated")

    def __format__(self, spec):
        raise RuntimeError("format detonated")

    def __repr__(self):
        return "StrBomb()"


def test_str_int_message():
    assert str(PlacesError(123)) == "123"


def test_repr_int_message():
    assert repr(PlacesError(123)) == "PlacesError('123')"


def test_str_format_bomb_with_context():
    err = PlacesError(FormatBomb(), context="some call")
    assert str(err) == "<unrepresentable FormatBomb> (context=some call)"


def test_str_format_bomb_no_context():
    assert str(PlacesError(FormatBomb())) == "<unrepresentable FormatBomb>"


def test_str_str_bomb_falls_back_to_repr():
    assert str(PlacesError(StrBomb())) == "StrBomb()"


def test_str_context_part_bomb():
    err = PlacesError("ok", context=FormatBomb())
    assert str(err) == "ok (context=<unrepresentable FormatBomb>)"


def test_str_status_part_bomb():
    err = PlacesError("ok", status_code=FormatBomb())
    assert str(err) == "ok (status_code=<unrepresentable FormatBomb>)"


def test_str_ordinary_no_parts_control():
    assert str(PlacesError("plain message")) == "plain message"


def test_str_ordinary_with_parts_control():
    err = PlacesError(
        "quota",
        status_code=429,
        google_status="RESOURCE_EXHAUSTED",
        retry_after=2.5,
        context="text_search",
    )
    assert str(err) == (
        "quota (context=text_search, status_code=429, "
        "google_status=RESOURCE_EXHAUSTED, retry_after=2.5)"
    )


def test_str_int_message_with_parts_control():
    assert str(PlacesError(123, context="x")) == "123 (context=x)"


def test_repr_ordinary_control():
    assert repr(PlacesError("plain")) == "PlacesError('plain')"


# --- The exception repr class name ---------------------------------------


class NonStrNameMeta(type):
    @property
    def __name__(cls):
        return 42


class RaisingNameMeta(type):
    @property
    def __name__(cls):
        raise RuntimeError("name detonated")


class NonStrNameError(PlacesError, metaclass=NonStrNameMeta):
    pass


class RaisingNameError(PlacesError, metaclass=RaisingNameMeta):
    pass


def test_repr_non_string_class_name_renders_fixed_form():
    rendered = repr(NonStrNameError("m"))
    assert rendered == "<unrepresentable value>('m')"


def test_repr_raising_class_name_renders_fixed_form():
    rendered = repr(RaisingNameError("m"))
    assert rendered == "<unrepresentable value>('m')"
