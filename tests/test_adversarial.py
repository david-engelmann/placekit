"""Standing adversarial tests, adopted from the Round 20 audit.

The two audit harnesses (probes/fuzz_decoder.py, seeded 20261101, and
probes/fuzz_caller.py, deterministic) probed the decoder and caller
lanes with thousands of generated cases. This module pins the ruled
repairs those harnesses motivated as a bounded, deterministic subset
that runs in seconds: bounded materialisation of caller iterables,
the documented list maxima, fraction and wrong type refusal in the
model layer, the direct layer DecodeError hierarchy with its depth
guard, argument error unification, the photo content type case gate,
and the re-decode stability property over every shipped fixture.
Each test names the finding it discriminates in its comment.
"""

from __future__ import annotations

import asyncio
import copy
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from placekit import AsyncClient, Client
from placekit.exceptions import ConfigError, DecodeError
from placekit.fields import MAX_MATERIALIZED_ITEMS, FieldMask
from placekit.models import (
    AutocompleteResult,
    LocalizedText,
    Money,
    NearbySearchResult,
    Place,
    PlacePrediction,
    TextSearchResult,
)

FIXTURES = Path(__file__).parent / "fixtures"
PHOTO_FIXTURE = FIXTURES / "photo.png"
PLACE_ID = "ChIJrTLr-GyuEmsRBfy61i59si0"
PHOTO_NAME = f"places/{PLACE_ID}/photos/ATJ83zh8vExample"


@pytest.fixture()
def client(api_key, base_url) -> Client:
    return Client(api_key, base_url=base_url)


def _serve_details(raw_response, mutate):
    data = json.loads((FIXTURES / "place_details.json").read_bytes())
    mutate(data)
    raw_response(200, json.dumps(data).encode())


# Caller lane: bounded materialisation (R20-F01 and F02).


def test_endless_iterables_refuse_promptly_on_every_slot(api_key, base_url):
    # F01: an endless iterable in any caller slot used to hang the
    # call forever. The refusal must be prompt, so the calls run in
    # a subprocess with a hard timeout; a hang fails by timeout, not
    # by assertion. Each slot must surface a ConfigError.
    script = textwrap.dedent(
        """
        import itertools
        import sys
        from collections.abc import Mapping

        from placekit import Client
        from placekit.exceptions import ConfigError

        client = Client(sys.argv[2], base_url=sys.argv[1])


        def endless_strings():
            for i in itertools.count():
                yield f"t{i}"


        class EndlessMapping(Mapping):
            def __getitem__(self, key):
                raise KeyError(key)

            def __iter__(self):
                return iter(())

            def __len__(self):
                return 0

            def items(self):
                for i in itertools.count():
                    yield (f"k{i}", i)


        def expect_config_error(label, thunk):
            try:
                thunk()
            except ConfigError:
                print("ok", label)
                return
            except Exception as exc:
                print("FAIL", label, type(exc).__name__)
                sys.exit(1)
            print("FAIL", label, "returned without error")
            sys.exit(1)


        expect_config_error(
            "nearby included_types",
            lambda: client.nearby_search(
                (0.0, 0.0), 100.0, included_types=endless_strings()
            ),
        )
        expect_config_error(
            "text_search fields",
            lambda: client.text_search("q", fields=endless_strings()),
        )
        expect_config_error(
            "autocomplete primary types",
            lambda: client.autocomplete(
                "q", included_primary_types=endless_strings()
            ),
        )
        expect_config_error(
            "text_search price_levels",
            lambda: client.text_search(
                "q", price_levels=endless_strings()
            ),
        )
        expect_config_error(
            "text_search location_bias mapping",
            lambda: client.text_search(
                "q", location_bias=EndlessMapping()
            ),
        )
        print("all endless slots refused")
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script, base_url, api_key],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "all endless slots refused" in completed.stdout


def test_iterable_failure_during_materialisation_wraps_as_config_error(
    client, stub_server
):
    # F01 companion: an iterable that raises part way through
    # materialisation surfaces as a ConfigError with the original
    # exception chained, and no request is built from the partial
    # contents.
    stub_server.last_request = None

    def broken():
        yield "cafe"
        raise RuntimeError("boom")

    with pytest.raises(ConfigError) as excinfo:
        client.nearby_search((0.0, 0.0), 100.0, included_types=broken())
    chain = []
    cause = excinfo.value.__cause__
    while cause is not None:
        chain.append(type(cause))
        cause = cause.__cause__
    assert RuntimeError in chain
    assert stub_server.last_request is None


def test_documented_list_maxima_are_enforced(client, stub_server):
    # F02: the autocomplete primary types maximum of 5 and the
    # nearby type filter maximum of 50 are stated in the client's
    # own documentation. At the maximum the call proceeds; one past
    # it refuses locally and sends nothing.
    result = client.autocomplete(
        "cafe",
        included_primary_types=["cafe", "bar", "bakery", "bank", "park"],
    )
    assert result.suggestions
    stub_server.last_request = None
    with pytest.raises(ConfigError):
        client.autocomplete(
            "cafe",
            included_primary_types=[
                "cafe",
                "bar",
                "bakery",
                "bank",
                "park",
                "zoo",
            ],
        )
    assert stub_server.last_request is None

    fifty = [f"type_{i}" for i in range(50)]
    result = client.nearby_search((0.0, 0.0), 100.0, included_types=fifty)
    assert result.places
    stub_server.last_request = None
    with pytest.raises(ConfigError):
        client.nearby_search(
            (0.0, 0.0), 100.0, included_types=fifty + ["one_too_many"]
        )
    with pytest.raises(ConfigError):
        client.nearby_search(
            (0.0, 0.0), 100.0, excluded_primary_types=fifty + ["x"]
        )
    assert stub_server.last_request is None


def test_autocomplete_collection_must_stand_alone(client, stub_server):
    # F02: the types documentation states a collection such as
    # (cities) may appear only as the sole primary type value. Mixed
    # with a regular type, or duplicated, it refuses locally; alone
    # it proceeds.
    result = client.autocomplete("cafe", included_primary_types=["(cities)"])
    assert result.suggestions
    stub_server.last_request = None
    with pytest.raises(ConfigError):
        client.autocomplete(
            "cafe", included_primary_types=["(cities)", "cafe"]
        )
    with pytest.raises(ConfigError):
        client.autocomplete(
            "cafe", included_primary_types=["(regions)", "(regions)"]
        )
    assert stub_server.last_request is None


def test_universal_ceiling_covers_slots_without_a_documented_maximum(
    client, stub_server
):
    # F01 and F02: slots with no documented maximum (region codes,
    # fields) fall under the single named universal ceiling instead
    # of being unbounded. At the ceiling the call proceeds; one
    # past it refuses locally.
    at_ceiling = ["AA"] * MAX_MATERIALIZED_ITEMS
    result = client.autocomplete("cafe", included_region_codes=at_ceiling)
    assert result.suggestions
    stub_server.last_request = None
    with pytest.raises(ConfigError):
        client.autocomplete(
            "cafe",
            included_region_codes=["AA"] * (MAX_MATERIALIZED_ITEMS + 1),
        )
    with pytest.raises(ConfigError):
        FieldMask.of(["id"] * (MAX_MATERIALIZED_ITEMS + 1))
    assert stub_server.last_request is None


# Caller lane: argument error unification (R20-F07, F08, F09, F11,
# F16 and F17).


def test_place_details_argument_type_errors_are_config_errors(
    client, stub_server
):
    # F08: place_details used to hand its arguments straight to the
    # native method, so a non-string id or code escaped as a bare
    # PyO3 TypeError while the body methods raised ConfigError for
    # the same misuse. Every shape below is a ConfigError now, and
    # none of them reaches the wire.
    stub_server.last_request = None
    for bad_id in (123, None, {"id": "x"}, ["x"], 4.5):
        with pytest.raises(ConfigError):
            client.place_details(bad_id)
    with pytest.raises(ConfigError):
        client.place_details(PLACE_ID, language=123)
    with pytest.raises(ConfigError):
        client.place_details(PLACE_ID, region=4.5)
    with pytest.raises(ConfigError):
        client.place_details(PLACE_ID, session_token=b"bytes")
    assert stub_server.last_request is None


def test_place_details_argument_type_errors_are_config_errors_async(
    api_key, base_url
):
    # F08 async mirror; the two clients share the contract.
    async def run():
        client = AsyncClient(api_key, base_url=base_url)
        with pytest.raises(ConfigError):
            await client.place_details(123)
        with pytest.raises(ConfigError):
            await client.autocomplete(
                "cafe",
                included_primary_types=["a", "b", "c", "d", "e", "f"],
            )

    asyncio.run(run())


def test_code_strings_refuse_control_characters_and_surrogates(
    client, stub_server
):
    # F07 and F09: control characters in a language or region code
    # used to reach the wire percent encoded, and a lone surrogate
    # escaped the native conversion as a bare UnicodeEncodeError.
    # Both refuse at the Python layer with a ConfigError.
    stub_server.last_request = None
    with pytest.raises(ConfigError):
        client.place_details(PLACE_ID, language="en\n")
    with pytest.raises(ConfigError):
        client.place_details(PLACE_ID, region="U\ud800")
    with pytest.raises(ConfigError):
        client.place_details(PLACE_ID, session_token="a\tb")
    with pytest.raises(ConfigError):
        client.text_search("q", language="en\x00")
    with pytest.raises(ConfigError):
        client.autocomplete("q", region="e\x7f")
    with pytest.raises(ConfigError):
        client.place_photo("places/x/photos/\ud800")
    assert stub_server.last_request is None


class _EvilInt(int):
    def __lt__(self, other):
        raise RuntimeError("evil comparison")

    __le__ = __lt__


class _EvilStr(str):
    def __str__(self):
        raise RuntimeError("evil str")


class _EvilDict(dict):
    def items(self):
        raise RuntimeError("evil items")


class _EvilFloat(float):
    def __float__(self):
        raise RuntimeError("evil float")


def test_hostile_caller_objects_raise_config_error_not_bare_builtins(
    client, stub_server
):
    # F11, F16 and F17: caller objects whose own methods raise used
    # to escape the argument phase as the bare builtin they raised
    # (RuntimeError here). Local misuse has one documented type.
    stub_server.last_request = None
    with pytest.raises(ConfigError):
        client.nearby_search((0.0, 0.0), 100.0, max_results=_EvilInt(5))
    with pytest.raises(ConfigError):
        client.place_details(_EvilStr("places/ChIJx"))
    with pytest.raises(ConfigError):
        client.text_search("q", routing_parameters=_EvilDict())
    with pytest.raises(ConfigError):
        client.text_search(
            "q",
            location_bias={
                "circle": {
                    "center": {"latitude": _EvilFloat(1.0), "longitude": 0.0},
                    "radius": 100.0,
                }
            },
        )
    assert stub_server.last_request is None


# Wire lane: fractions and wrong types refuse through the client
# (R20-F03 and F04); the null settlement is untouched.


def test_wire_fraction_in_an_integer_position_refuses(client, raw_response):
    # F03: utcOffsetMinutes 60.7 used to decode as 60, a typed view
    # contradicting raw with no signal.
    _serve_details(
        raw_response, lambda data: data.update(utcOffsetMinutes=60.7)
    )
    with pytest.raises(DecodeError):
        client.place_details(PLACE_ID)


def test_wire_wrong_type_in_a_string_slot_refuses(client, raw_response):
    # F04: a number in the displayName text slot used to be stored
    # verbatim in a slot declared as a string.
    def mutate(data):
        data["displayName"] = {"text": 42, "languageCode": "en"}

    _serve_details(raw_response, mutate)
    with pytest.raises(DecodeError):
        client.place_details(PLACE_ID)


def test_wire_null_in_a_string_slot_keeps_the_settled_tolerance(
    client, raw_response
):
    # F04 boundary: the null instance in the audit family sits on
    # the Round 16 typed position null settlement and is NOT part
    # of the wrong type repair. A null in the same slot still
    # decodes, landing as None exactly as settled.
    def mutate(data):
        data["displayName"] = {"text": None, "languageCode": "en"}

    _serve_details(raw_response, mutate)
    place = client.place_details(PLACE_ID)
    assert place.display_name is not None
    assert place.display_name.text is None


def test_photo_content_type_gate_ignores_case(client, raw_response):
    # Red team RT1: the core content type gate was case sensitive
    # while the magic check behind it lowercases, so a legal
    # uppercase media type carrying a genuine image was refused.
    # The gate now judges case insensitively, in both directions.
    raw_response(200, PHOTO_FIXTURE.read_bytes(), "IMAGE/PNG")
    media = client.place_photo(PHOTO_NAME, max_width_px=400)
    assert media.content == PHOTO_FIXTURE.read_bytes()
    assert media.content_type.lower() == "image/png"

    raw_response(200, b"<html>not an image</html>", "TEXT/HTML")
    with pytest.raises(DecodeError):
        client.place_photo(PHOTO_NAME, max_width_px=400)

    # A case normalised pass through the gate still meets the magic
    # check: PNG bytes claiming to be a JPEG refuse on the mismatch.
    raw_response(200, PHOTO_FIXTURE.read_bytes(), "Image/Jpeg")
    with pytest.raises(DecodeError):
        client.place_photo(PHOTO_NAME, max_width_px=400)


# Direct layer: hierarchy, depth guard, and scalar validation
# (R20-F03, F04, F05, F06, F12, and the F14 residue).


@pytest.mark.parametrize(
    "decode",
    [
        lambda: Place.from_api(None),
        lambda: Place.from_api(42),
        lambda: Place.from_api("payload"),
        lambda: Place.from_api([{"id": "x"}]),
        lambda: TextSearchResult.from_api({"places": "x"}),
        lambda: TextSearchResult.from_api({"places": None}),
        lambda: Place.from_api({"id": "x", "photos": 7}),
        lambda: Place.from_api({"id": "x", "reviews": {"a": 1}}),
        lambda: PlacePrediction.from_api(
            {"placeId": "x", "structuredFormat": "abc"}
        ),
    ],
)
def test_direct_shape_errors_surface_as_decode_error(decode):
    # F05: these shapes escaped the direct layer as bare
    # AttributeError or TypeError. The documented contract is a
    # DecodeError naming the problem.
    with pytest.raises(DecodeError):
        decode()


def _nested_payload(depth: int) -> dict:
    payload: dict = {"leaf": 1}
    for _ in range(depth):
        payload = {"layer": payload}
    return {"id": "x", "unknownFutureField": payload}


def test_direct_deep_nesting_hits_the_stated_depth_guard():
    # F06: depth 100 decodes; depth 500 used to die with a bare
    # RecursionError inside the payload copy. It now refuses with
    # a DecodeError at the stated guard.
    place = Place.from_api(_nested_payload(100))
    assert place.id == "x"
    with pytest.raises(DecodeError):
        Place.from_api(_nested_payload(500))


def test_direct_string_list_refuses_a_mapping_but_keeps_null_elements():
    # F12: a mapping in a string list slot used to be read as its
    # keys, fabricating list contents. A null element still lands
    # as None at its wire index under the Round 16 settlement for
    # modelled string lists.
    with pytest.raises(DecodeError):
        Place.from_api({"id": "x", "types": {"cafe": 1}})
    place = Place.from_api({"id": "x", "types": [None, "cafe"]})
    assert place.types == [None, "cafe"]


def test_direct_fraction_positions_refuse_and_integral_floats_decode():
    # F03 direct mirror of the wire test above, plus the Money
    # units shape the audit measured (4.9 stored as 4).
    with pytest.raises(DecodeError):
        Place.from_api({"id": "x", "utcOffsetMinutes": 60.7})
    place = Place.from_api({"id": "x", "utcOffsetMinutes": 60.0})
    assert place.utc_offset_minutes == 60
    assert isinstance(place.utc_offset_minutes, int)
    with pytest.raises(DecodeError):
        Money.from_api({"currencyCode": "USD", "units": 4.9})
    money = Money.from_api({"currencyCode": "USD", "units": "5", "nanos": 4.0})
    assert money.units == 5 and money.nanos == 4


def test_direct_null_in_a_string_slot_keeps_the_settled_tolerance():
    # The direct mirror of the F04 boundary pin above.
    text = LocalizedText.from_api({"text": None, "languageCode": None})
    assert text.text is None and text.language_code is None
    absent = LocalizedText.from_api({})
    assert absent.text == "" and absent.language_code is None


def test_direct_oversized_integer_in_a_typed_slot_refuses():
    # F14 residue, verified open before repair: a several thousand
    # digit integer stored in a typed slot, after which repr of the
    # result raised a bare ValueError. The same integer in an
    # unknown field was already clean (raw is repr excluded and
    # carries it untouched), and stays clean.
    huge = 10**5000
    with pytest.raises(DecodeError):
        Place.from_api({"id": "x", "userRatingCount": huge})
    place = Place.from_api({"id": "x", "someFutureField": huge})
    assert place.raw["someFutureField"] == huge
    repr(place)


# The re-decode stability property (spec review): for every shipped
# fixture, decoding its raw again yields an equal result.


def _fixture_cases():
    cases = [
        ("place_details.json", Place, FIXTURES / "place_details.json", None),
        (
            "text_search.json",
            TextSearchResult,
            FIXTURES / "text_search.json",
            None,
        ),
        (
            "nearby_search.json",
            NearbySearchResult,
            FIXTURES / "nearby_search.json",
            None,
        ),
        (
            "autocomplete.json",
            AutocompleteResult,
            FIXTURES / "autocomplete.json",
            None,
        ),
    ]
    for path in sorted((FIXTURES / "recorded").glob("*.json")):
        cases.append((path.name, Place, path, None))
    for path in sorted((FIXTURES / "synthesized").glob("*.json")):
        cases.append((path.name, Place, path, "payload"))
    return cases


@pytest.mark.parametrize(
    "decoder,path,payload_key",
    [
        (decoder, path, key)
        for _name, decoder, path, key in _fixture_cases()
    ],
    ids=[name for name, _d, _p, _k in _fixture_cases()],
)
def test_redecode_stability_for_every_shipped_fixture(
    decoder, path, payload_key
):
    document = json.loads(path.read_bytes())
    payload = document[payload_key] if payload_key else document
    first = decoder.from_api(copy.deepcopy(payload))
    second = decoder.from_api(copy.deepcopy(first.raw))
    assert first == second
