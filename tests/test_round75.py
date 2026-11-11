"""Round 75 pins for the guarded rendering of refusal values.

The client resolvers formatted the values their refusals name
with raw reads. The place id resolver interpolated a raw type
name read and raw reprs of the value and the resolved id, and
the photo resolver and every other argument validator that
names a caller supplied value shared the shape. A value whose
repr raises, or whose type's name read raises, detonated the
formatting inside the refusal itself, so the seat's own
documented explanation was destroyed and the caller received
only the argument wrap's generic wording, which names the
wrong failure. The exception class and the cause survived
through the wrap, so the defect was one of message fidelity,
in the same genus Round 65 repaired at the other refusal
seats.

The seats now render through the library's guarded forms, the
guarded name reading and the safe repr, and chain the original
raise the raw read produced. For every ordinary value the
refusal messages are byte identical to the messages before
this round, and the controls beside each detonation pin hold
that identity. The audit behind this round drove every raw
repr seat in the client module. The seats the drives proved
identical in shape are pinned here beside the two resolvers
the red team indicted. Both clients share the resolvers and
validators on the base class, and the async pins hold that
sharing to account.
"""

from __future__ import annotations

import asyncio

import pytest

from placekit import AsyncClient, Client
from placekit.exceptions import ConfigError
from placekit.models import Photo, Place, PlacePrediction

REPR_BOOM = RuntimeError("repr detonated")
NAME_BOOM = RuntimeError("name read detonated")

WRAP_WORDING = "raised while it was being validated"


class ReprBomb:
    """A plain value whose repr raises a shared RuntimeError."""

    def __repr__(self):
        raise REPR_BOOM


class ReprBombStr(str):
    def __repr__(self):
        raise REPR_BOOM


class ReprBombInt(int):
    def __repr__(self):
        raise REPR_BOOM


class ReprBombFloat(float):
    def __repr__(self):
        raise REPR_BOOM


class ReprBombList(list):
    def __repr__(self):
        raise REPR_BOOM


class ReprBombDict(dict):
    def __repr__(self):
        raise REPR_BOOM


class NameBombMeta(type):
    @property
    def __name__(cls):
        raise NAME_BOOM


class NameBombPlace(Place, metaclass=NameBombMeta):
    """A Place whose type name read raises."""


class OddNameMeta(type):
    @property
    def __name__(cls):
        return 123


class OddNamePlace(Place, metaclass=OddNameMeta):
    """A Place whose type name read answers a non string."""


# --- The place id resolver, ordinary values (parity controls) ---------


def test_resolver_else_int_control():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_details(12345)
    assert caught.value.message == (
        "place_id must be a string, a Place or a PlacePrediction, "
        "got 12345"
    )
    assert caught.value.context == "place_details"
    assert caught.value.__cause__ is None


def test_resolver_place_int_id_control():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_details(Place(id=12345))
    assert caught.value.message == (
        "place_id from a Place must be a string, got 12345"
    )
    assert caught.value.context == "place_details"
    assert caught.value.__cause__ is None


def test_resolver_prediction_int_id_control():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_details(PlacePrediction(place_id=12345))
    assert caught.value.message == (
        "place_id from a PlacePrediction must be a string, got 12345"
    )
    assert caught.value.context == "place_details"
    assert caught.value.__cause__ is None


def test_resolver_place_none_id_control():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_details(Place(id=None))
    assert caught.value.message == (
        "place_id from a Place must be a string, got None"
    )
    assert caught.value.__cause__ is None


# --- The place id resolver, hostile values ----------------------------


def test_resolver_else_repr_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_details(ReprBomb())
    assert caught.value.message == (
        "place_id must be a string, a Place or a PlacePrediction, "
        "got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.context == "place_details"
    assert caught.value.__cause__ is REPR_BOOM


def test_resolver_resolved_repr_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_details(Place(id=ReprBomb()))
    assert caught.value.message == (
        "place_id from a Place must be a string, "
        "got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.context == "place_details"
    assert caught.value.__cause__ is REPR_BOOM


def test_resolver_name_read_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_details(NameBombPlace(id=12345))
    assert caught.value.message == (
        "place_id from a <unrepresentable value> must be a "
        "string, got 12345"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.context == "place_details"
    assert caught.value.__cause__ is NAME_BOOM


def test_resolver_name_nonstring():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_details(OddNamePlace(id=12345))
    assert caught.value.message == (
        "place_id from a <unrepresentable value> must be a "
        "string, got 12345"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.context == "place_details"
    assert caught.value.__cause__ is None


# --- The photo resolver, ordinary values (parity controls) ------------


def test_photo_width_str_control():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_photo(
            Photo(name="n", width_px="wide", height_px=100)
        )
    assert caught.value.message == (
        "a Photo width_px must be an integer, got 'wide'"
    )
    assert caught.value.context == "place_photo"
    assert caught.value.__cause__ is None


def test_photo_height_str_control():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_photo(
            Photo(name="n", width_px=100, height_px="tall")
        )
    assert caught.value.message == (
        "a Photo height_px must be an integer, got 'tall'"
    )
    assert caught.value.context == "place_photo"
    assert caught.value.__cause__ is None


def test_photo_else_int_control():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_photo(12345, max_width_px=100)
    assert caught.value.message == (
        "photo_name must be a string or a Photo, got 12345"
    )
    assert caught.value.context == "place_photo"
    assert caught.value.__cause__ is None


# --- The photo resolver, hostile values -------------------------------


def test_photo_width_repr_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_photo(
            Photo(name="n", width_px=ReprBomb(), height_px=10)
        )
    assert caught.value.message == (
        "a Photo width_px must be an integer, "
        "got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.context == "place_photo"
    assert caught.value.__cause__ is REPR_BOOM


def test_photo_height_repr_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_photo(
            Photo(name="n", width_px=10, height_px=ReprBomb())
        )
    assert caught.value.message == (
        "a Photo height_px must be an integer, "
        "got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.context == "place_photo"
    assert caught.value.__cause__ is REPR_BOOM


def test_photo_else_repr_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_photo(ReprBomb(), max_width_px=100)
    assert caught.value.message == (
        "photo_name must be a string or a Photo, "
        "got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.context == "place_photo"
    assert caught.value.__cause__ is REPR_BOOM


# --- The shared resolvers on the async surface -------------------------


def test_async_resolver_resolved_repr_bomb():
    async def run():
        client = AsyncClient("test-key")
        with pytest.raises(ConfigError) as caught:
            await client.place_details(Place(id=ReprBomb()))
        assert caught.value.message == (
            "place_id from a Place must be a string, "
            "got <ReprBomb whose repr raised>"
        )
        assert WRAP_WORDING not in caught.value.message
        assert caught.value.context == "place_details"
        assert caught.value.__cause__ is REPR_BOOM
        client.close()

    asyncio.run(run())


def test_async_resolver_name_read_bomb():
    async def run():
        client = AsyncClient("test-key")
        with pytest.raises(ConfigError) as caught:
            await client.place_details(NameBombPlace(id=12345))
        assert caught.value.message == (
            "place_id from a <unrepresentable value> must be a "
            "string, got 12345"
        )
        assert WRAP_WORDING not in caught.value.message
        assert caught.value.context == "place_details"
        assert caught.value.__cause__ is NAME_BOOM
        client.close()

    asyncio.run(run())


def test_async_resolver_place_int_id_control():
    async def run():
        client = AsyncClient("test-key")
        with pytest.raises(ConfigError) as caught:
            await client.place_details(Place(id=12345))
        assert caught.value.message == (
            "place_id from a Place must be a string, got 12345"
        )
        assert caught.value.context == "place_details"
        assert caught.value.__cause__ is None
        client.close()

    asyncio.run(run())


def test_async_photo_width_repr_bomb():
    async def run():
        client = AsyncClient("test-key")
        with pytest.raises(ConfigError) as caught:
            await client.place_photo(
                Photo(name="n", width_px=ReprBomb(), height_px=10)
            )
        assert caught.value.message == (
            "a Photo width_px must be an integer, "
            "got <ReprBomb whose repr raised>"
        )
        assert WRAP_WORDING not in caught.value.message
        assert caught.value.context == "place_photo"
        assert caught.value.__cause__ is REPR_BOOM
        client.close()

    asyncio.run(run())


def test_async_photo_width_str_control():
    async def run():
        client = AsyncClient("test-key")
        with pytest.raises(ConfigError) as caught:
            await client.place_photo(
                Photo(name="n", width_px="wide", height_px=100)
            )
        assert caught.value.message == (
            "a Photo width_px must be an integer, got 'wide'"
        )
        assert caught.value.context == "place_photo"
        assert caught.value.__cause__ is None
        client.close()

    asyncio.run(run())


# --- The sibling validator seats the audit proved identical ------------


def test_string_list_single_str_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.text_search(
            "q", price_levels=ReprBombStr("PRICE_LEVEL_FREE")
        )
    assert caught.value.message == (
        "price_levels must be an iterable of strings, not a "
        "single string: <ReprBombStr whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.__cause__ is REPR_BOOM


def test_string_list_item_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.text_search("q", price_levels=[ReprBomb()])
    assert caught.value.message == (
        "price_levels items must be strings, "
        "got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.__cause__ is REPR_BOOM


def test_code_string_nonstr_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_details("abc", language=ReprBomb())
    assert caught.value.message == (
        "language must be a string, got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.__cause__ is REPR_BOOM


def test_code_string_control_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_details("abc", language=ReprBombStr("e\ud800"))
    assert caught.value.message == (
        "language must not contain control characters or "
        "unpaired surrogates, got <ReprBombStr whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.__cause__ is REPR_BOOM


def test_require_str_nonstr_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.autocomplete(ReprBomb())
    assert caught.value.message == (
        "input_text must be a string, got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.context == "autocomplete"
    assert caught.value.__cause__ is REPR_BOOM


def test_require_str_surrogate_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.autocomplete(ReprBombStr("a\ud800"))
    assert caught.value.message == (
        "input_text must not contain unpaired surrogates, "
        "got <ReprBombStr whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.context == "autocomplete"
    assert caught.value.__cause__ is REPR_BOOM


def test_validate_bool_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.text_search("q", open_now=ReprBomb())
    assert caught.value.message == (
        "open_now must be a bool, got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.__cause__ is REPR_BOOM


def test_coordinate_nonnumeric_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.autocomplete("x", origin=(ReprBomb(), 0.0))
    assert caught.value.message == (
        "origin latitude must be a real number, "
        "got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.context == "autocomplete"
    assert caught.value.__cause__ is REPR_BOOM


def test_coordinate_range_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.autocomplete(
            "x", origin=(ReprBombFloat(999.0), 0.0)
        )
    assert caught.value.message == (
        "origin latitude must be finite and within -90 to 90, "
        "got <ReprBombFloat whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.context == "autocomplete"
    assert caught.value.__cause__ is REPR_BOOM


def test_lat_lng_mapping_keys_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.autocomplete(
            "x", origin=ReprBombDict({"lat": 1})
        )
    assert caught.value.message == (
        "origin must carry latitude and longitude, "
        "got <ReprBombDict whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.context == "autocomplete"
    assert caught.value.__cause__ is REPR_BOOM


def test_lat_lng_pair_length_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.autocomplete(
            "x", origin=ReprBombList([1, 2, 3])
        )
    assert caught.value.message == (
        "origin must be a (latitude, longitude) pair, "
        "got <ReprBombList whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.context == "autocomplete"
    assert caught.value.__cause__ is REPR_BOOM


def test_lat_lng_else_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.autocomplete("x", origin=ReprBomb())
    assert caught.value.message == (
        "origin must be a LatLng, a (latitude, longitude) pair "
        "or a latitude/longitude dict, "
        "got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.__cause__ is REPR_BOOM


def test_circle_radius_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.nearby_search((0.0, 0.0), ReprBomb())
    assert caught.value.message == (
        "radius_m must be a finite number, "
        "got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.__cause__ is REPR_BOOM


def test_dict_body_item_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.text_search(
            "q", ev_options={"priceLevels": ReprBombStr("x")}
        )
    assert caught.value.message == (
        "ev_options field 'priceLevels' must be a list of "
        "strings, not a single string: "
        "<ReprBombStr whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.__cause__ is REPR_BOOM


def test_dict_body_key_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.text_search(
            "q", ev_options={ReprBombStr("priceLevels"): "x"}
        )
    assert caught.value.message == (
        "ev_options field <ReprBombStr whose repr raised> must "
        "be a list of strings, not a single string: 'x'"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.__cause__ is REPR_BOOM


def test_mapping_body_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.text_search("q", ev_options=ReprBomb())
    assert caught.value.message == (
        "ev_options must be a dict, got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.__cause__ is REPR_BOOM


def test_location_body_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.text_search("q", location_bias=ReprBomb())
    assert caught.value.message == (
        "location bias or restriction must be a dict, "
        "got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.context == "text_search"
    assert caught.value.__cause__ is REPR_BOOM


def test_routing_body_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.text_search("q", routing_parameters=ReprBomb())
    assert caught.value.message == (
        "routing_parameters must be a dict, "
        "got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.context == "text_search"
    assert caught.value.__cause__ is REPR_BOOM


def test_int_range_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_photo(
            "places/x/photos/y", max_width_px=ReprBomb()
        )
    assert caught.value.message == (
        "max_width_px must be an integer between 1 and 4800, "
        "got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.__cause__ is REPR_BOOM


def test_int_range_subclass_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_photo(
            "places/x/photos/y", max_width_px=ReprBombInt(9999)
        )
    assert caught.value.message == (
        "max_width_px must be an integer between 1 and 4800, "
        "got <ReprBombInt whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.__cause__ is REPR_BOOM


def test_int_range_str_control():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_photo(
            "places/x/photos/y", max_width_px="wide"
        )
    assert caught.value.message == (
        "max_width_px must be an integer between 1 and 4800, "
        "got 'wide'"
    )
    assert caught.value.__cause__ is None


def test_float_range_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.text_search("q", min_rating=ReprBomb())
    assert caught.value.message == (
        "min_rating must be a number between 0 and 5, "
        "got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.__cause__ is REPR_BOOM


def test_float_range_subclass_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.text_search("q", min_rating=ReprBombFloat(99.0))
    assert caught.value.message == (
        "min_rating must be a number between 0 and 5, "
        "got <ReprBombFloat whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.__cause__ is REPR_BOOM


def test_skip_flag_bomb():
    client = Client("test-key")
    with pytest.raises(ConfigError) as caught:
        client.place_photo(
            "places/x/photos/y",
            max_width_px=100,
            skip_http_redirect=ReprBomb(),
        )
    assert caught.value.message == (
        "skip_http_redirect must be a bool, "
        "got <ReprBomb whose repr raised>"
    )
    assert WRAP_WORDING not in caught.value.message
    assert caught.value.__cause__ is REPR_BOOM
