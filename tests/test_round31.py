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
