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


class FloatSecondRaisesInt(int):
    """An int timeout whose float conversion behaves on its
    first call and raises on the second."""

    def __new__(cls):
        return super().__new__(cls, 5)

    def __init__(self):
        self.calls = 0

    def __float__(self):
        self.calls += 1
        if self.calls >= 2:
            raise RuntimeError("float boom on call %d" % self.calls)
        return 5.0


class FloatSecondReturnsStrInt(int):
    """An int timeout whose float conversion returns a string
    on its second call."""

    def __new__(cls):
        return super().__new__(cls, 5)

    def __init__(self):
        self.calls = 0

    def __float__(self):
        self.calls += 1
        if self.calls >= 2:
            return "not-a-number"  # type: ignore[return-value]
        return 5.0


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


@pytest.mark.parametrize("make", [Client, AsyncClient])
def test_constructor_timeout_second_conversion_raises_is_config_error(make):
    # The guarded validation block spends the first float
    # conversion (the finiteness check). The native build then
    # extracts the timeout after the block, and that extraction
    # used to spend the second conversion outside any guard, so
    # this value crossed construction as a bare RuntimeError
    # (landing red team Minor 1). The timeout is now coerced to
    # a plain float inside the guard, so the second conversion
    # spends inside it and lands as the chained ConfigError.
    with pytest.raises(ConfigError) as caught:
        make("test-key", timeout=FloatSecondRaisesInt())
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_constructor_timeout_second_conversion_returning_str_is_config_error():
    # The same second read in its non raising form. A
    # conversion returning a string on its second call made
    # the argument extraction itself raise a bare TypeError.
    with pytest.raises(ConfigError) as caught:
        Client("test-key", timeout=FloatSecondReturnsStrInt())
    assert isinstance(caught.value.__cause__, TypeError)


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


# --- Decoder Minor F4: gzip token spellings


def _envelope(status_text: str, code: int, message: str) -> str:
    return json.dumps(
        {"error": {"code": code, "message": message, "status": status_text}}
    )


QUOTA_BODY = _envelope("RESOURCE_EXHAUSTED", 429, QUOTA_MESSAGE)


@pytest.mark.parametrize(
    "spelling",
    ["GZip", "GZIP", "gzip, identity", "identity, gzip"],
)
def test_gzip_spelling_variants_classify_the_envelope(
    client, raw_response, spelling
):
    raw_response(
        400,
        gzip.compress(QUOTA_BODY.encode()),
        headers={"Content-Encoding": spelling},
    )
    with pytest.raises(RateLimitError) as caught:
        client.text_search("pizza")
    assert caught.value.google_status == "RESOURCE_EXHAUSTED"


def test_gzip_spelling_variants_classify_async(api_key, base_url, raw_response):
    raw_response(
        400,
        gzip.compress(QUOTA_BODY.encode()),
        headers={"Content-Encoding": "GZip"},
    )

    async def run():
        async with AsyncClient(api_key, base_url=base_url) as aclient:
            with pytest.raises(RateLimitError):
                await aclient.text_search("pizza")

    asyncio.run(run())


def test_gzip_exact_lowercase_unchanged(client, raw_response):
    raw_response(
        400,
        gzip.compress(QUOTA_BODY.encode()),
        headers={"Content-Encoding": "gzip"},
    )
    with pytest.raises(RateLimitError):
        client.text_search("pizza")


def test_gzip_variant_on_success_status_envelope(client, raw_response):
    raw_response(
        200,
        gzip.compress(QUOTA_BODY.encode()),
        headers={"Content-Encoding": "GZIP"},
    )
    with pytest.raises(RateLimitError):
        client.text_search("pizza")


def test_gzip_variant_on_a_success_body_decodes(client, raw_response):
    body = json.dumps({"places": []})
    raw_response(
        200,
        gzip.compress(body.encode()),
        headers={"Content-Encoding": "gzip, identity"},
    )
    result = client.text_search("pizza")
    assert result.places == []


def test_gzip_variant_on_the_photo_form_decodes(client, raw_response):
    body = json.dumps(
        {
            "name": "places/x/photos/y",
            "photoUri": "http://127.0.0.1/photo-uri",
        }
    )
    raw_response(
        200,
        gzip.compress(body.encode()),
        headers={"Content-Encoding": "GZip"},
    )
    result = client.place_photo(
        "places/x/photos/y", max_width_px=800, skip_http_redirect=True
    )
    assert result.name == "places/x/photos/y"
    assert result.photo_uri == "http://127.0.0.1/photo-uri"


def test_twice_compressed_declared_once_keeps_its_behaviour(
    client, raw_response
):
    twice = gzip.compress(gzip.compress(QUOTA_BODY.encode()))
    raw_response(400, twice, headers={"Content-Encoding": "gzip"})
    with pytest.raises(InvalidRequestError) as caught:
        client.text_search("pizza")
    assert caught.value.google_status is None


def test_gzip_variant_twice_compressed_decodes_one_layer(
    client, raw_response
):
    # The core side pass runs once: a twice compressed body
    # under a variant spelling still ends compressed, so the
    # envelope stays unseen, the same end state the transport
    # path gives it.
    twice = gzip.compress(gzip.compress(QUOTA_BODY.encode()))
    raw_response(400, twice, headers={"Content-Encoding": "GZip"})
    with pytest.raises(InvalidRequestError) as caught:
        client.text_search("pizza")
    assert caught.value.google_status is None


def test_other_codings_keep_their_behaviour(client, raw_response):
    raw_response(
        400,
        QUOTA_BODY.encode(),
        headers={"Content-Encoding": "deflate"},
    )
    with pytest.raises(RateLimitError):
        client.text_search("pizza")


