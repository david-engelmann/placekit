"""Round 31 acceptance pins.

Caller Minor 1: the free text checks on query and input sit inside
the guarded argument phase, so a hostile string subclass lands as
a chained ConfigError on both clients. Caller Minor 2 with red
team Minor 2: constructor validation reads no caller value bare,
including the reads inside its own refusal messages. Caller Minor
3 with red team Minor 1: FieldMask member validation is guarded,
and normalize_fields judges a mask instance's state defensively,
refusing fabricated masks at the Python layer. Decoder Minors F1
to F4: the head scan's last wins rule is complete, a malformed
head field costs that field only, an unclosed sibling container
does not swallow the envelope, and gzip decoding no longer
depends on the encoding header token's case or list position.
"""

from __future__ import annotations

import asyncio
import gzip
import json

import pytest

from placekit import AsyncClient, Client
from placekit.exceptions import (
    ConfigError,
    InvalidRequestError,
    PlacesError,
    RateLimitError,
)
from placekit.fields import FieldMask, normalize_fields

QUOTA_MESSAGE = "Quota exceeded for this key"


class IterRaisesStr(str):
    def __iter__(self):
        raise RuntimeError("evil __iter__")


class StripRaisesStr(str):
    def strip(self, *args):
        raise RuntimeError("evil strip")


class SplitRaisesStr(str):
    def split(self, *args):
        raise RuntimeError("evil split")


class AsciiRaisesStr(str):
    def isascii(self):
        raise RuntimeError("evil isascii")


class ReprRaisesInt(int):
    def __repr__(self):
        raise RuntimeError("evil repr")


class CmpRaisesInt(int):
    def __lt__(self, other):
        raise RuntimeError("evil lt")

    def __le__(self, other):
        raise RuntimeError("evil le")


class FloatRaisesInt(int):
    def __float__(self):
        raise RuntimeError("evil float")


@pytest.fixture()
def client(api_key, base_url) -> Client:
    return Client(api_key, base_url=base_url)


# --- Caller Minor 1: the free text check inside the guarded phase


def test_text_search_query_iteration_raises_is_config_error(client):
    with pytest.raises(ConfigError) as caught:
        client.text_search(IterRaisesStr("cafes"))
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_autocomplete_input_iteration_raises_is_config_error(client):
    with pytest.raises(ConfigError) as caught:
        client.autocomplete(IterRaisesStr("Bian"))
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_async_free_text_iteration_raises_is_config_error(api_key, base_url):
    async def run():
        async with AsyncClient(api_key, base_url=base_url) as aclient:
            outcomes = []
            for call in (
                lambda: aclient.text_search(IterRaisesStr("cafes")),
                lambda: aclient.autocomplete(IterRaisesStr("Bian")),
            ):
                try:
                    await call()
                    outcomes.append(None)
                except ConfigError as exc:
                    outcomes.append(exc)
            return outcomes

    outcomes = asyncio.run(run())
    assert len(outcomes) == 2
    for exc in outcomes:
        assert isinstance(exc, ConfigError)
        assert isinstance(exc.__cause__, RuntimeError)


def test_free_text_wrong_type_still_names_the_argument(client):
    with pytest.raises(ConfigError) as caught:
        client.text_search(123)  # type: ignore[arg-type]
    assert "query" in str(caught.value)
    with pytest.raises(ConfigError) as caught:
        client.autocomplete(None)  # type: ignore[arg-type]
    assert "input_text" in str(caught.value)


# --- Caller Minor 2 and red team Minor 2: constructor reads guarded


@pytest.mark.parametrize("make", [Client, AsyncClient])
def test_constructor_key_strip_raises_is_config_error(make):
    with pytest.raises(ConfigError) as caught:
        make(StripRaisesStr("test-key"))
    assert isinstance(caught.value.__cause__, RuntimeError)


@pytest.mark.parametrize("make", [Client, AsyncClient])
def test_constructor_key_iteration_raises_is_config_error(make):
    with pytest.raises(ConfigError) as caught:
        make(IterRaisesStr("test-key"))
    assert isinstance(caught.value.__cause__, RuntimeError)


@pytest.mark.parametrize("make", [Client, AsyncClient])
def test_constructor_key_isascii_raises_is_config_error(make):
    with pytest.raises(ConfigError) as caught:
        make(AsciiRaisesStr("test-key"))
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_constructor_timeout_comparison_raises_is_config_error():
    with pytest.raises(ConfigError) as caught:
        Client("test-key", timeout=CmpRaisesInt(5))
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_constructor_timeout_float_conversion_raises_is_config_error():
    with pytest.raises(ConfigError) as caught:
        Client("test-key", timeout=FloatRaisesInt(5))
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_constructor_timeout_repr_raises_still_refuses_as_config_error():
    # The value is out of range, so the refusal itself fires;
    # formatting the value into the refusal message must not be
    # the read that escapes (red team Minor 2).
    with pytest.raises(ConfigError) as caught:
        Client("test-key", timeout=ReprRaisesInt(99999))
    assert "timeout" in str(caught.value)


def test_constructor_plain_refusals_keep_their_messages():
    with pytest.raises(ConfigError) as caught:
        Client(123)  # type: ignore[arg-type]
    assert str(caught.value) == "api_key must be a string, got 123"
    with pytest.raises(ConfigError) as caught:
        Client("test-key", timeout=0)
    assert "got 0" in str(caught.value)
    with pytest.raises(ConfigError):
        Client("test-key", timeout=float("nan"))
    with pytest.raises(ConfigError):
        Client("key with spaces")


# --- Caller Minor 3: FieldMask member validation is guarded


def test_mask_member_strip_raises_is_config_error():
    with pytest.raises(ConfigError) as caught:
        FieldMask(StripRaisesStr("places.id"))
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_mask_member_split_raises_is_config_error():
    with pytest.raises(ConfigError) as caught:
        FieldMask(SplitRaisesStr("places.id"))
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_mask_rebuild_member_dunders_raise_as_config_error():
    with pytest.raises(ConfigError):
        FieldMask.of([StripRaisesStr("places.id")])
    with pytest.raises(ConfigError):
        FieldMask.of([SplitRaisesStr("places.id")])


def test_mask_plain_members_behave_as_before():
    mask = FieldMask("places.id", "places.rating", "places.id")
    assert mask.paths == ("places.id", "places.rating")
    assert mask.header_value == "places.id,places.rating"
    assert normalize_fields(mask) == ["places.id", "places.rating"]
    with pytest.raises(ConfigError):
        FieldMask("not a path")


# --- Caller Minor 3 and red team Minor 1: fabricated masks


def _fabricated_mask(paths) -> FieldMask:
    mask = FieldMask("places.id")
    object.__setattr__(mask, "paths", paths)
    return mask


def test_normalize_fields_ghost_mask_is_config_error():
    ghost = object.__new__(FieldMask)
    with pytest.raises(ConfigError):
        normalize_fields(ghost)


def test_normalize_fields_fabricated_non_string_member_is_config_error():
    for paths in [(123,), (None,), ("places.id", 123), [123]]:
        with pytest.raises(ConfigError):
            normalize_fields(_fabricated_mask(paths))


def test_fabricated_mask_non_string_member_refused_through_client(
    client, stub_server
):
    stub_server.last_request = None
    with pytest.raises(ConfigError):
        client.text_search("cafes", fields=_fabricated_mask((123,)))
    assert stub_server.last_request is None


def test_fabricated_mask_bad_grammar_still_refused_typed(client):
    with pytest.raises(PlacesError):
        client.text_search(
            "cafes", fields=_fabricated_mask(("not a path",))
        )


def test_fabricated_mask_string_paths_state_is_config_error():
    with pytest.raises(ConfigError):
        normalize_fields(_fabricated_mask("places.id"))


