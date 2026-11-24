"""Differential harness for the bindings conversion routes.

Decoder batch, slice 0 (design record at
~/workspace/placekit-audit-rounds/decoder-batch-design.md, item
A50-139). On every successful sync call the bindings convert the
core's typed result into a fresh serde_json Value DOM
(to_value_guarded in src/lib.rs) only for value_to_py to walk that
DOM into Python objects. The batch will replace that round trip
with a serializer that produces Python objects directly from the
typed value. This harness is the instrument that has to prove the
replacement identical before it lands: it runs two conversion
routes over the same response bodies and compares the Python
objects they produce, exactly.

The two routes. The oracle is the production route as it stands:
the core parses the served body into its typed value, the
bindings serialize that value into the DOM and walk the DOM into
Python objects, and the native call returns the resulting tuple.
The subject is whatever candidate a later slice wires into
_run_subject below. In this slice the subject is a copy of the
oracle route, invoked through a second, separately constructed
native client over the same served bytes, so the harness must
come out green against the current code while genuinely
comparing. A later slice rewires _run_subject alone; the inputs
and the comparator do not move.

What is compared, per input body. The whole native result tuple,
element by element:

* The typed dict, recursively and exactly. Every node must carry
  the same type on both sides: a bool is not an int, an int is
  not a float, a string is not a number. Dicts must carry the
  same keys in the same order with recursively exact values.
  Key order is part of the comparison because today's walk emits
  keys in the DOM's order at every level, and the batch promises
  unknown fields land in the Python dict exactly where today's
  walk places them, so placement is a behaviour under test, not
  an artefact to wave through. Lists must match in length and
  element by element. Floats must match in value and in sign,
  compared through repr, so negative zero is not positive zero.
  Ints compare by exact value at any size. Strings and None
  compare by equality and identity respectively.
* The response body text the tuple carries beside the typed
  dict, as identical strings.
* The HTTP status, as equal ints.

What is not compared. The Python model layer downstream of the
tuple (Place.from_api and its siblings) is a second decoder with
its own pins elsewhere in the suite; the batch changes the
bindings conversion, so the harness stops at the tuple the
conversion produces. The raw view is not compared either: the
Python layer builds raw from the body text, not from the typed
dict, and that construction is the raw guarantee's own territory
(A50-152). The body text itself is compared verbatim above,
which is the part of raw's inputs this conversion owns. The
async path is out of scope: its stored form keeps the DOM by
design (Round 17), so the batch's prize is the sync surface this
harness pins. The photo seats convert through their own function
and are named by slice 3; this slice's input sets are the JSON
endpoint bodies the design record names.

The input sets. The 41 recorded corpus bodies, replayed through
the stub exactly as the corpus tests serve them, classified to
the search or details seat by their top level shape. An
adversarial number corpus: integers at the u64 and i64
boundaries and one past each, long digit strings, exponent
forms, negative zero, and values whose float rendering loses
precision, seated both in unknown fields (where arbitrary
precision numbers ride through the flatten maps) and in the
known numeric fields whose typed carriers decide their fate.
Flatten-heavy bodies with unknown fields at every typed nesting
level, unknowns beside known fields at the same level, unknowns
inside unknowns, and case-variant spellings of known fields.
One refusal case stands apart from the sets: an integer past the
interpreter's string conversion limit, which both routes must
refuse with the same decode error rather than convert.

The expectation set. Three of the crafted bodies also carry a
hand-built expected typed dict, written from the model layer's
documented rules (the presence wrappers keep an explicit null
and drop an absent field, a plain optional field collapses an
explicit null to absence, the lenient count decoders surface
string and float encodings as integers, and number_to_py keeps
boundary integers exact and float forms as floats) and from the
serde_json map ordering the DOM walk emits. The oracle is
checked against those literals, so the oracle itself is pinned
to something that is not itself. The literals' key order is the
sorted order the locked serde_json build (no preserve_order
feature) emits at every object level.

Slice 1 adds the number envelope expectations at the end of this
module. Where the sample above pins the oracle on three bodies,
the envelope set pins values per case, for both routes: integer
text at and past the machine boundaries in flatten seats and in
the known numeric seats whose typed carriers decide their fate,
the carriers' three accepted encodings and the values they
surface, float text at its precision edges, and the refusals at
the carriers' hard edge, where a value the carrier cannot hold
is a decode error on both routes rather than a correction.

The comparator carries its own pins below, because a comparator
that cannot fail proves nothing: int against float, bool against
int, negative zero against positive zero, a missing key, a
reordered key set, and a nested divergence naming its path all
raise, and an identical nested tree passes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from placekit import _placekit

RECORDED = Path(__file__).parent / "fixtures" / "recorded"


# -- the comparator -------------------------------------------------------


def assert_same_python_object(actual, expected, path="typed"):
    """Exact, type-strict equality of two converted Python trees.

    Raises AssertionError naming the path of the first divergence.
    Dict key order is compared as part of exactness, for the
    reason the module docstring gives.
    """
    assert type(actual) is type(expected), (
        f"{path}: type {type(actual).__name__} "
        f"is not {type(expected).__name__}"
    )
    if isinstance(expected, dict):
        assert list(actual) == list(expected), (
            f"{path}: keys {list(actual)} are not {list(expected)}"
        )
        for key in expected:
            assert_same_python_object(
                actual[key], expected[key], f"{path}.{key}"
            )
    elif isinstance(expected, list):
        assert len(actual) == len(expected), (
            f"{path}: length {len(actual)} is not {len(expected)}"
        )
        for index, (a_item, e_item) in enumerate(zip(actual, expected)):
            assert_same_python_object(a_item, e_item, f"{path}[{index}]")
    elif isinstance(expected, float):
        # repr distinguishes negative zero from positive zero and
        # round-trips every finite float, so equal reprs are the
        # same value with the same sign.
        assert repr(actual) == repr(expected), (
            f"{path}: float {actual!r} is not {expected!r}"
        )
    else:
        assert actual == expected, f"{path}: {actual!r} is not {expected!r}"


def assert_same_result(actual, expected):
    """Exact equality of two native result tuples.

    The typed dict is compared by assert_same_python_object; the
    body text and the status ride beside it and are compared as
    themselves.
    """
    actual_typed, actual_body, actual_status = actual
    expected_typed, expected_body, expected_status = expected
    assert_same_python_object(actual_typed, expected_typed)
    assert actual_body == expected_body, "response body texts differ"
    assert type(actual_status) is type(expected_status)
    assert actual_status == expected_status, (
        f"status {actual_status} is not {expected_status}"
    )


# -- the routes -----------------------------------------------------------


def _call_route(native, seat):
    """One production conversion, invoked through a native client.

    The stub serves the installed body on every route, so the
    request the seat builds is immaterial to what comes back; the
    seat only decides which typed value the core parses the body
    into and which endpoint conversion runs.
    """
    if seat == "search":
        return native.text_search({"textQuery": "decoder differential harness"})
    return native.place_details("dec0-differential-harness")


def _run_oracle(native, seat):
    """The oracle route: the production conversion, first client."""
    return _call_route(native, seat)


def _run_subject(native, seat):
    """The subject route: the candidate under comparison.

    Slice 0 wires the subject as a copy of the oracle route, run
    through a second, separately constructed native client. A
    later slice rewires this function alone to its candidate
    serializer.
    """
    return _call_route(native, seat)


def _run_pair(oracle_native, subject_native, raw_response, seat, body):
    raw_response(200, body)
    oracle_tuple = _run_oracle(oracle_native, seat)
    subject_tuple = _run_subject(subject_native, seat)
    return oracle_tuple, subject_tuple


@pytest.fixture()
def oracle_native(api_key, base_url):
    return _placekit.Client(api_key, base_url=base_url)


@pytest.fixture()
def subject_native(api_key, base_url):
    return _placekit.Client(api_key, base_url=base_url)


def test_routes_use_independent_clients(oracle_native, subject_native):
    # The two routes must be two conversions, not one result read
    # twice: each runner holds its own native client, so a state
    # leak inside one client cannot masquerade as agreement.
    assert oracle_native is not subject_native


# -- comparator self-pins ---------------------------------------------------


def test_comparator_accepts_an_identical_nested_tree():
    tree = {"a": [1, 2.5, "x", None, True, {"b": -0.0}], "c": {}}
    assert_same_python_object(tree, json.loads(json.dumps(tree)))


def test_comparator_distinguishes_int_from_float():
    with pytest.raises(AssertionError):
        assert_same_python_object(1, 1.0)


def test_comparator_distinguishes_bool_from_int():
    with pytest.raises(AssertionError):
        assert_same_python_object(True, 1)


def test_comparator_distinguishes_negative_zero():
    with pytest.raises(AssertionError):
        assert_same_python_object(-0.0, 0.0)


def test_comparator_requires_the_same_keys():
    with pytest.raises(AssertionError):
        assert_same_python_object({"a": 1}, {"a": 1, "b": 2})


def test_comparator_requires_the_same_key_order():
    with pytest.raises(AssertionError):
        assert_same_python_object({"a": 1, "b": 2}, {"b": 2, "a": 1})


def test_comparator_names_the_diverging_path():
    with pytest.raises(AssertionError) as excinfo:
        assert_same_python_object({"a": [{"b": 1}]}, {"a": [{"b": 2}]})
    assert "typed.a[0].b" in str(excinfo.value)


# -- input set 1: the recorded corpus ---------------------------------------


def _recorded_cases():
    cases = []
    for path in sorted(RECORDED.glob("*.json")):
        payload = json.loads(path.read_bytes())
        seat = "search" if "places" in payload else "details"
        cases.append(pytest.param(path.name, seat, id=path.stem))
    return cases


def test_recorded_corpus_set_is_complete():
    # The design record names 41 recorded bodies as this set. The
    # count is pinned so a fixture added or removed outside the
    # corpus programme cannot silently change what the harness
    # covers.
    assert len(list(RECORDED.glob("*.json"))) == 41


@pytest.mark.parametrize("name,seat", _recorded_cases())
def test_recorded_body_routes_agree(
    oracle_native, subject_native, raw_response, name, seat
):
    body = (RECORDED / name).read_bytes()
    oracle_tuple, subject_tuple = _run_pair(
        oracle_native, subject_native, raw_response, seat, body
    )
    assert_same_result(subject_tuple, oracle_tuple)


# -- input set 2: the adversarial number corpus -----------------------------
#
# Bodies are written as JSON text, never built through a Python
# dict, so integer tokens keep the exact digits written here
# instead of passing through a Python int on the way out.

NUMBER_BODIES = [
    pytest.param(
        "details",
        b'{"id": "dec0-numbers", "name": "places/dec0-numbers",'
        b' "xU64Max": 18446744073709551615,'
        b' "xU64Past": 18446744073709551616,'
        b' "xI64Max": 9223372036854775807,'
        b' "xI64Past": 9223372036854775808,'
        b' "xI64Min": -9223372036854775808,'
        b' "xI64MinPast": -9223372036854775809,'
        b' "xZero": 0, "xNegOne": -1}',
        id="machine-boundaries",
    ),
    pytest.param(
        "details",
        b'{"id": "dec0-numbers",'
        b' "xLong": 123456789012345678901234567890123456789012345678901234567890,'
        b' "xLongNeg": -9876543210987654321098765432109876543210,'
        b' "xDigitString": "123456789012345678901234567890"}',
        id="long-digit-strings",
    ),
    pytest.param(
        "details",
        b'{"id": "dec0-numbers",'
        b' "xExp": 1e2, "xExpCap": 1E2, "xExpNeg": 123e-3,'
        b' "xExpBig": 1.5e300, "xIntValuedExp": 7e22,'
        b' "xNegExp": -2.5e-1}',
        id="exponent-forms",
    ),
    pytest.param(
        "details",
        b'{"id": "dec0-numbers",'
        b' "xNegZero": -0.0, "xPosZero": 0.0,'
        b' "xLossy": 0.30000000000000004,'
        b' "xLongDecimal": 3.141592653589793238462643383279,'
        b' "xJustAboveOne": 1.0000000000000002}',
        id="zero-and-precision",
    ),
    pytest.param(
        "details",
        b'{"id": "dec0-numbers", "rating": 4.567890123456789,'
        b' "userRatingCount": 18446744073709551615}',
        id="known-seats-exact",
    ),
    pytest.param(
        "details",
        b'{"id": "dec0-numbers", "rating": 4, "userRatingCount": "42"}',
        id="known-seats-reencoded",
    ),
    pytest.param(
        "details",
        b'{"id": "dec0-numbers", "rating": 1e2, "userRatingCount": 42.0,'
        b' "photos": [{"name": "places/dec0-numbers/photos/p",'
        b' "widthPx": "4800", "heightPx": 300}]}',
        id="known-seats-float-forms",
    ),
    pytest.param(
        "search",
        b'{"places": [{"id": "dec0-numbers",'
        b' "userRatingCount": 9223372036854775807,'
        b' "xDeep": {"xArr": [18446744073709551616, -0.0, 1e2]}}],'
        b' "xEnvBig": 18446744073709551616,'
        b' "xEnvFloat": 9007199254740993.0}',
        id="search-envelope-numbers",
    ),
]


@pytest.mark.parametrize("seat,body", NUMBER_BODIES)
def test_number_body_routes_agree(
    oracle_native, subject_native, raw_response, seat, body
):
    oracle_tuple, subject_tuple = _run_pair(
        oracle_native, subject_native, raw_response, seat, body
    )
    assert_same_result(subject_tuple, oracle_tuple)


def test_past_digit_limit_integer_refused_by_both_routes(
    oracle_native, subject_native, raw_response
):
    # An integer whose decimal text passes the interpreter's
    # string conversion limit cannot cross exactly, and the
    # conversion refuses it as a decode failure of the bindings
    # layer rather than losing digits or escaping as a bare
    # builtin error. Both routes must refuse it the same way.
    digits = "9" * (sys.get_int_max_str_digits() + 100)
    body = ('{"id": "dec0-giant", "xGiant": ' + digits + "}").encode()
    raw_response(200, body)
    with pytest.raises(_placekit.PlacesError) as oracle_exc:
        _run_oracle(oracle_native, "details")
    with pytest.raises(_placekit.PlacesError) as subject_exc:
        _run_subject(subject_native, "details")
    assert oracle_exc.value.kind == "decode"
    assert subject_exc.value.kind == oracle_exc.value.kind
    assert str(subject_exc.value) == str(oracle_exc.value)


# -- input set 3: flatten-heavy bodies --------------------------------------

FLATTEN_BODIES = [
    pytest.param(
        "details",
        b'{"id": "dec0-flat", "name": "places/dec0-flat",'
        b' "xRoot": "root-unknown",'
        b' "displayName": {"text": "Flat", "languageCode": "en", "xName": 1},'
        b' "location": {"latitude": 10.25, "longitude": 20.5, "xLoc": [1, 2]},'
        b' "regularOpeningHours": {'
        b'   "openNow": true, "xHours": {"xHourInner": true},'
        b'   "periods": [{"open": {"day": 1, "hour": 9, "minute": 0,'
        b'     "xPoint": "p",'
        b'     "date": {"year": 2026, "month": 1, "day": 2, "xDate": 3}},'
        b'    "xPeriod": null}],'
        b'   "weekdayDescriptions": ["Monday: 9 AM - 5 PM"]},'
        b' "addressComponents": [{"longText": "1 Probe Way",'
        b'   "shortText": "1", "types": ["street_address"],'
        b'   "languageCode": "en", "xComp": {"xCompInner": [true]}}],'
        b' "photos": [{"name": "places/dec0-flat/photos/p1",'
        b'   "widthPx": 100, "heightPx": 50, "xPhoto": 1.5,'
        b'   "authorAttributions": [{"displayName": "A U Thor",'
        b'     "uri": "https://example.com/a",'
        b'     "photoUri": "https://example.com/a/p", "xAttr": "a"}]}],'
        b' "plusCode": {"globalCode": "8FW4V75V+8F6",'
        b'   "compoundCode": "V75V+8F6 Probe", "xPlus": 9},'
        b' "viewport": {'
        b'   "low": {"latitude": 1.0, "longitude": 2.0, "xLow": 1},'
        b'   "high": {"latitude": 3.0, "longitude": 4.0, "xHigh": 2},'
        b'   "xView": 5},'
        b' "postalAddress": {"regionCode": "US", "locality": "Probe",'
        b'   "xPostal": "z"},'
        b' "attributions": [{"provider": "Probe Provider",'
        b'   "xAttribution": 0}],'
        b' "xDeepNest": {"level1": {"level2": {"level3":'
        b'   {"level4": [1, {"level5": "bottom"}]}}}}}',
        id="unknowns-at-every-level",
    ),
    pytest.param(
        "search",
        b'{"places": [{"id": "dec0-flat-2",'
        b' "xPlace": {"xPlaceInner": [null, false]}}],'
        b' "nextPageToken": "tok",'
        b' "routingSummaries": [{"legs": [{"xLeg": 1}]}],'
        b' "xEnvelope": [{"xInArray": "yes"}]}',
        id="envelope-unknowns",
    ),
    pytest.param(
        "details",
        b'{"id": "dec0-flat-3", "rating": 3.5,'
        b' "Rating": 9.9, "RATING": "high",'
        b' "xNull": null, "xBool": false, "xStr": "s",'
        b' "xEmptyObj": {}, "xEmptyArr": [], "xEmptyStr": ""}',
        id="case-variants-and-empty-shapes",
    ),
    pytest.param(
        "details",
        b'{"id": "dec0-flat-4",'
        b' "xMatrix": [[1, 2], [{"xCell": {"xRow": [3]}}],'
        b' "text", null, 4.5]}',
        id="unknown-arrays-of-mixed-shape",
    ),
]


@pytest.mark.parametrize("seat,body", FLATTEN_BODIES)
def test_flatten_body_routes_agree(
    oracle_native, subject_native, raw_response, seat, body
):
    oracle_tuple, subject_tuple = _run_pair(
        oracle_native, subject_native, raw_response, seat, body
    )
    assert_same_result(subject_tuple, oracle_tuple)


# -- the hand-built expectation set -----------------------------------------
#
# Each expected typed dict below is written by hand from the
# rules the module docstring names, in the sorted key order the
# DOM walk emits. The oracle is compared against the literal, so
# the oracle is pinned to something that is not itself.

EXPECTATION_CASES = [
    pytest.param(
        "details",
        b'{"id": "probe-place", "name": "places/probe-place",'
        b' "formattedAddress": null,'
        b' "displayName": {"text": "Probe", "languageCode": "en",'
        b'  "xNote": "kept"},'
        b' "location": {"latitude": 1.5, "longitude": null, "xExtra": 7},'
        b' "rating": 4, "userRatingCount": "42", "types": null,'
        b' "photos": [{"name": "places/probe-place/photos/p1",'
        b'  "widthPx": 0, "heightPx": 300}],'
        b' "xRoot": {"nested": [1, 2.5, null, true]}}',
        {
            # formattedAddress is a plain optional field, so its
            # explicit null collapses to absence and the key is
            # gone. types is a presence wrapper, so its explicit
            # null stays null. The photo's widthPx of 0 is the
            # zero the dimension guard omits. The string count
            # surfaces as the integer it encodes, and the integer
            # rating token crosses as the float the field holds.
            "displayName": {
                "languageCode": "en",
                "text": "Probe",
                "xNote": "kept",
            },
            "id": "probe-place",
            "location": {"latitude": 1.5, "longitude": None, "xExtra": 7},
            "name": "places/probe-place",
            "photos": [
                {"heightPx": 300, "name": "places/probe-place/photos/p1"}
            ],
            "rating": 4.0,
            "types": None,
            "userRatingCount": 42,
            "xRoot": {"nested": [1, 2.5, None, True]},
        },
        id="presence-and-reencoding",
    ),
    pytest.param(
        "search",
        b'{"places": [{"id": "p1", "rating": 4.567890123456789,'
        b' "userRatingCount": 18446744073709551615}],'
        b' "nextPageToken": "tok", "xEnvelope": -0.0}',
        {
            "nextPageToken": "tok",
            "places": [
                {
                    "id": "p1",
                    "rating": 4.567890123456789,
                    "userRatingCount": 18446744073709551615,
                }
            ],
            "xEnvelope": -0.0,
        },
        id="search-envelope-sample",
    ),
    pytest.param(
        "details",
        b'{"id": "p2", "xNums": {'
        b' "imax": 9223372036854775807,'
        b' "imaxPlus": 9223372036854775808,'
        b' "umax": 18446744073709551615,'
        b' "umaxPlus": 18446744073709551616,'
        b' "iminMinus": -9223372036854775809,'
        b' "exp": 1e2, "negZero": -0.0}}',
        {
            "id": "p2",
            "xNums": {
                "exp": 100.0,
                "imax": 9223372036854775807,
                "imaxPlus": 9223372036854775808,
                "iminMinus": -9223372036854775809,
                "negZero": -0.0,
                "umax": 18446744073709551615,
                "umaxPlus": 18446744073709551616,
            },
        },
        id="number-envelope-sample",
    ),
]


@pytest.mark.parametrize("seat,body,expected_typed", EXPECTATION_CASES)
def test_oracle_matches_hand_built_expectations(
    oracle_native, raw_response, seat, body, expected_typed
):
    raw_response(200, body)
    typed, body_text, status = _run_oracle(oracle_native, seat)
    assert_same_python_object(typed, expected_typed)
    assert body_text == body.decode()
    assert status == 200



# -- slice 1: the number envelope expectations ------------------------------
#
# Slice 0 compared route against route and pinned the oracle to a
# three case sample. This section pins the number envelope itself:
# every case below carries a hand-built expected typed dict, and
# both routes are checked against the literal, so the envelope is
# pinned to values rather than to agreement between two copies of
# the same code. The verdicts are derived from the two places that
# decide a number's fate. In the bindings, number_to_py keeps an
# integer exact at any size (an i64, then a u64, then the exact
# decimal text read by Python's int) and sends any token carrying
# a fraction or an exponent to f64. In the core, the typed carriers
# decide first: rating is a plain f64, and the lenient count and
# dimension decoders accept an integer token, a canonical unsigned
# decimal string, or an exactly integral float inside the carrier,
# and refuse anything the carrier cannot hold (past the top,
# negative, fractional) as a decode error rather than correcting
# it. Unknown fields skip the carriers and ride the flatten maps
# straight to number_to_py.

ENVELOPE_CASES = [
    pytest.param(
        "details",
        b'{"id": "dec1-flat", "xI64Max": 9223372036854775807,'
        b' "xI64Min": -9223372036854775808,'
        b' "xNegOne": -1, "xNegZero": -0, "xZero": 0}',
        {
            # The i64 edges cross as exact ints. A negative zero
            # integer token has no fraction or exponent, so it
            # takes the integer path and crosses as the int 0:
            # integer zero carries no sign across the boundary.
            "id": "dec1-flat",
            "xI64Max": 9223372036854775807,
            "xI64Min": -9223372036854775808,
            "xNegOne": -1,
            "xNegZero": 0,
            "xZero": 0,
        },
        id="flatten-i64-edges",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-flat", "xI64Past": 9223372036854775808,'
        b' "xI64MinPast": -9223372036854775809,'
        b' "xU64Max": 18446744073709551615}',
        {
            # One past each i64 edge and the u64 top still cross
            # exact: past i64 the value rides the u64 arm of
            # number_to_py, and below i64 min it rides the exact
            # decimal text arm. Neither is rounded.
            "id": "dec1-flat",
            "xI64MinPast": -9223372036854775809,
            "xI64Past": 9223372036854775808,
            "xU64Max": 18446744073709551615,
        },
        id="flatten-past-i64",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-flat",'
        b' "xLong": 123456789012345678901234567890123456789012345678901234567890,'
        b' "xLongNeg": -9876543210987654321098765432109876543210,'
        b' "xU64Past": 18446744073709551616}',
        {
            # Past u64 the integer text arm still crosses exact,
            # at sixty digits as at twenty. The only ceiling on
            # this arm is the interpreter digit limit, whose
            # refusal slice 0 already pins.
            "id": "dec1-flat",
            "xLong": 123456789012345678901234567890123456789012345678901234567890,
            "xLongNeg": -9876543210987654321098765432109876543210,
            "xU64Past": 18446744073709551616,
        },
        id="flatten-past-u64",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-flat", "xExp": 1e2, "xExpCap": 1E2,'
        b' "xExpNeg": 123e-3, "xHuge": 1e400, "xHugeNeg": -1e400,'
        b' "xIntValuedExp": 7e22,'
        b' "xJustAboveOne": 1.0000000000000002,'
        b' "xLongDecimal": 3.141592653589793238462643383279,'
        b' "xLossy": 0.30000000000000004,'
        b' "xNegZero": -0.0, "xNegZeroExp": -0e0,'
        b' "xPast53": 9007199254740993.0,'
        b' "xPointZero": 42.0, "xPosZero": 0.0,'
        b' "xTiny": 1e-400, "xTinyNeg": -1e-400}',
        {
            # Every token here carries a fraction or an exponent,
            # so every verdict is number_to_py's float arm, stated
            # as the value that arm produces. Exponent forms are
            # floats even when their value is integral. A float
            # token naming an integer one past 2**53 rounds to
            # 2**53. Underflow lands on a signed zero, which the
            # comparator's repr check keeps apart from its twin.
            # Overflow does not saturate: the arbitrary precision
            # Number's as_f64 returns None for a magnitude past
            # the f64 range, and the float arm's fallback for
            # None is NaN (src/lib.rs, number_to_py), so both
            # huge tokens cross as NaN and the negative one's
            # sign is lost with its magnitude. The pin records
            # that verdict as it stands; a candidate serializer
            # that saturates to infinity fails here.
            "id": "dec1-flat",
            "xExp": 100.0,
            "xExpCap": 100.0,
            "xExpNeg": 0.123,
            "xHuge": float("nan"),
            "xHugeNeg": float("nan"),
            "xIntValuedExp": 7e22,
            "xJustAboveOne": 1.0000000000000002,
            "xLongDecimal": 3.141592653589793238462643383279,
            "xLossy": 0.30000000000000004,
            "xNegZero": -0.0,
            "xNegZeroExp": -0.0,
            "xPast53": 9007199254740992.0,
            "xPointZero": 42.0,
            "xPosZero": 0.0,
            "xTiny": 0.0,
            "xTinyNeg": -0.0,
        },
        id="flatten-float-verdicts",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-rating", "rating": 4}',
        {
            # The rating carrier is an f64, so an integer token
            # crosses as the float it names.
            "id": "dec1-rating",
            "rating": 4.0,
        },
        id="rating-int-token",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-rating",'
        b' "rating": 4.123456789012345678901234567890}',
        {
            # A long decimal rating keeps the carrier's f64
            # verdict, which is not the double Python's own
            # parser picks for the same text: the core parses
            # the token through serde_json's arbitrary precision
            # float conversion, which lands one ULP above the
            # correctly rounded neighbour on this token. The
            # literal below is the double the carrier actually
            # holds (its repr), and the pin records the
            # carrier's verdict because reproducing it, not the
            # ideal rounding, is the batch's obligation.
            "id": "dec1-rating",
            "rating": 4.123456789012346,
        },
        id="rating-long-decimal",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-rating", "rating": 1e2}',
        {"id": "dec1-rating", "rating": 100.0},
        id="rating-exponent-hundred",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-rating", "rating": 5e-1}',
        {"id": "dec1-rating", "rating": 0.5},
        id="rating-exponent-fraction",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-rating", "rating": -0.0}',
        {
            # The f64 carrier holds the sign of zero and the
            # conversion keeps it.
            "id": "dec1-rating",
            "rating": -0.0,
        },
        id="rating-negative-zero",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-count", "userRatingCount": 0}',
        {
            # A count of zero is a sent value, not an absence:
            # the field's skip guard is absence only, so the key
            # stays with its zero.
            "id": "dec1-count",
            "userRatingCount": 0,
        },
        id="count-zero",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-count",'
        b' "userRatingCount": 18446744073709551615}',
        {
            # The u64 carrier's own top, as an integer token,
            # crosses exact.
            "id": "dec1-count",
            "userRatingCount": 18446744073709551615,
        },
        id="count-u64-max",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-count", "userRatingCount": "42"}',
        {"id": "dec1-count", "userRatingCount": 42},
        id="count-string-small",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-count",'
        b' "userRatingCount": "18446744073709551615"}',
        {
            # The string form is the canonical unsigned decimal,
            # and it reaches the same top of the carrier.
            "id": "dec1-count",
            "userRatingCount": 18446744073709551615,
        },
        id="count-string-u64-max",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-count", "userRatingCount": 42.0}',
        {
            # An exactly integral float encoding carries the
            # same count as the integer token. Note the contrast
            # with a flatten seat, where 42.0 stays a float: the
            # carrier decides the fate, not the token alone.
            "id": "dec1-count",
            "userRatingCount": 42,
        },
        id="count-float-integral",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-count", "userRatingCount": 1e19}',
        {
            # 1e19 is exactly representable as an f64 and sits
            # inside the carrier, so the float encoding surfaces
            # as that exact integer.
            "id": "dec1-count",
            "userRatingCount": 10000000000000000000,
        },
        id="count-float-big",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-count", "userRatingCount": -0.0}',
        {
            # Negative zero as a float encoding is integral and
            # not below zero (the lenient range admits it as
            # zero), so it surfaces as the count 0.
            "id": "dec1-count",
            "userRatingCount": 0,
        },
        id="count-float-negative-zero",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-photo", "photos": [{'
        b'"name": "places/dec1-photo/photos/p",'
        b' "widthPx": "4800", "heightPx": 300.0}]}',
        {
            # The dimension carriers are u32 behind the same
            # lenient decoder: the string form and the integral
            # float form both surface as ints.
            "id": "dec1-photo",
            "photos": [
                {
                    "heightPx": 300,
                    "name": "places/dec1-photo/photos/p",
                    "widthPx": 4800,
                }
            ],
        },
        id="photo-dimension-forms",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-photo", "photos": [{'
        b'"name": "places/dec1-photo/photos/p",'
        b' "widthPx": 4294967295, "heightPx": "4294967295"}]}',
        {
            # The u32 top in both encodings.
            "id": "dec1-photo",
            "photos": [
                {
                    "heightPx": 4294967295,
                    "name": "places/dec1-photo/photos/p",
                    "widthPx": 4294967295,
                }
            ],
        },
        id="photo-dimension-max",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-photo", "photos": [{'
        b'"name": "places/dec1-photo/photos/p",'
        b' "widthPx": 0, "heightPx": null}]}',
        {
            # A zero dimension is the field's absent form and
            # its key is omitted; an explicit null reads as the
            # same zero, so both keys are gone and the photo
            # carries only its name.
            "id": "dec1-photo",
            "photos": [{"name": "places/dec1-photo/photos/p"}],
        },
        id="photo-dimension-zero-and-null",
    ),
    pytest.param(
        "search",
        b'{"places": [{"id": "dec1-s",'
        b' "rating": 4.567890123456789,'
        b' "userRatingCount": 9223372036854775807}]}',
        {
            # The same carriers at the search seat: the rating
            # keeps its f64 precision and the count crosses
            # exact at the i64 top.
            "places": [
                {
                    "id": "dec1-s",
                    "rating": 4.567890123456789,
                    "userRatingCount": 9223372036854775807,
                }
            ],
        },
        id="search-known-carriers",
    ),
]


@pytest.mark.parametrize("seat,body,expected_typed", ENVELOPE_CASES)
def test_number_envelope_matches_hand_built_expectations(
    oracle_native,
    subject_native,
    raw_response,
    seat,
    body,
    expected_typed,
):
    raw_response(200, body)
    oracle_typed, body_text, status = _run_oracle(oracle_native, seat)
    assert_same_python_object(oracle_typed, expected_typed)
    subject_typed, subject_body, subject_status = _run_subject(
        subject_native, seat
    )
    assert_same_python_object(subject_typed, expected_typed)
    assert subject_body == body_text == body.decode()
    assert subject_status == status == 200


# The envelope's hard edge. A value the typed carrier cannot hold
# is refused as a decode error by both routes with the same
# message: the leniency stops at representability, so past the
# carrier's top, below zero, or fractional is never saturated,
# rounded, or truncated into the carrier. These refusals are the
# count and dimension carriers' half of the envelope; the
# interpreter digit limit refusal in slice 0 is the bindings'
# half, and it stands as it was.

ENVELOPE_REFUSAL_CASES = [
    pytest.param(
        "details",
        b'{"id": "dec1-count",'
        b' "userRatingCount": 18446744073709551616}',
        id="count-past-u64-int",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-count",'
        b' "userRatingCount": 18446744073709551616.0}',
        # The float encoding of exactly 2**64: the lenient
        # decoder's bound is strict (u64 max as an f64 rounds up
        # to 2**64 itself), so this is refused, not saturated
        # to the carrier's top.
        id="count-at-two-to-64-float",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-count", "userRatingCount": -1}',
        id="count-negative",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-count", "userRatingCount": 42.5}',
        id="count-fractional",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-count",'
        b' "userRatingCount": "18446744073709551616"}',
        id="count-string-past-u64",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-count", "userRatingCount": "042"}',
        # Zero padding is not the canonical unsigned decimal
        # the string form admits.
        id="count-string-zero-padded",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-count", "userRatingCount": "+42"}',
        id="count-string-signed",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-count", "userRatingCount": "4.0"}',
        id="count-string-decimal",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-photo", "photos": [{'
        b'"name": "places/dec1-photo/photos/p",'
        b' "widthPx": 4294967296}]}',
        id="width-past-u32",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-photo", "photos": [{'
        b'"name": "places/dec1-photo/photos/p",'
        b' "widthPx": -1}]}',
        id="width-negative",
    ),
    pytest.param(
        "details",
        b'{"id": "dec1-photo", "photos": [{'
        b'"name": "places/dec1-photo/photos/p",'
        b' "heightPx": 1.5}]}',
        id="height-fractional",
    ),
]


@pytest.mark.parametrize("seat,body", ENVELOPE_REFUSAL_CASES)
def test_number_envelope_refused_by_both_routes(
    oracle_native, subject_native, raw_response, seat, body
):
    raw_response(200, body)
    with pytest.raises(_placekit.PlacesError) as oracle_exc:
        _run_oracle(oracle_native, seat)
    with pytest.raises(_placekit.PlacesError) as subject_exc:
        _run_subject(subject_native, seat)
    assert oracle_exc.value.kind == "decode"
    assert subject_exc.value.kind == oracle_exc.value.kind
    assert str(subject_exc.value) == str(oracle_exc.value)
