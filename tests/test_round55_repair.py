"""Round 55 D2 repair pins.

The direct ``from_api`` layer promises that a malformed payload
raises a DecodeError naming the problem, never a bare builtin.
The Round 55 census proved the per key read layer broke that
promise wherever a payload's own mapping operations, truthiness,
copy machinery or repr raised during a decode. The repair guards
the operation itself. A raising read converts to a DecodeError
naming the model and the key in a could not be read form, chained
from the original, at every read site. A raising truthiness at a
child gate converts the same way. The raw source copies in
payload preparation carry the same wrap as the payload copy. A
refusal that names a value names it through a safe repr, so a
value whose repr raises is named by its type instead of breaking
the refusal. The Place id fallback reads the decoded name through
the unbound ``str.removeprefix``, so a string subclass override
cannot raise there and cannot steer the stored id.

These pins hold the conversions, the controls that must pass
through untouched, the genus fence (a caller operation returning
a wrong answer is still followed as sent; only raises convert),
the refusal messages on honest shapes, and the read counts,
which do not move.
"""

from __future__ import annotations

import pytest

import placekit.models as models
from placekit.exceptions import ConfigError, DecodeError
from placekit.models import (
    LatLng,
    LocalizedText,
    Place,
    PlacePrediction,
    Suggestion,
    TextSearchResult,
    Viewport,
    _model_elements,
    _owned_decode,
    _raw_element,
    _read,
    _read_or,
    _safe_repr,
    _truthy,
)

RT = RuntimeError("boom")


class GetRaise(dict):
    """get raises the stored exception, for all keys or named keys."""

    def __init__(self, exc, keys=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._exc = exc
        self._keys = keys

    def get(self, key, default=None):
        if self._keys is None or key in self._keys:
            raise self._exc
        return super().get(key, default)


class OmnRaise(dict):
    """get, getitem and contains all raise the stored exception."""

    def __init__(self, exc, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._exc = exc

    def get(self, key, default=None):
        raise self._exc

    def __getitem__(self, key):
        raise self._exc

    def __contains__(self, key):
        raise self._exc


class GetitemKeyError(dict):
    """Membership says present, the index read says missing."""

    def __getitem__(self, key):
        raise KeyError(key)


class ContainsFalse(dict):
    """Membership lies and says absent for keys that are present."""

    def __contains__(self, key):
        return False


class LenRaiseDict(dict):
    def __len__(self):
        raise RuntimeError("len boom")


class ReprRaise:
    def __repr__(self):
        raise RuntimeError("repr boom")


class ReprRaiseStr(str):
    def __repr__(self):
        raise RuntimeError("repr boom")


class ReprNonString:
    def __repr__(self):
        return 5


class NanReprFloat(float):
    def __repr__(self):
        raise RuntimeError("repr boom")


class FloatMethodRaiseInt(int):
    def __float__(self):
        raise RuntimeError("float boom")


class DeepcopyRaise:
    def __deepcopy__(self, memo):
        raise RuntimeError("deepcopy boom")


class DeepcopyKbd:
    def __deepcopy__(self, memo):
        raise KeyboardInterrupt()


class DeepcopySwap:
    """Copy machinery answers with a different value (genus G5)."""

    def __init__(self, replacement):
        self._replacement = replacement

    def __deepcopy__(self, memo):
        return self._replacement


class ExcReprRaise(Exception):
    """An exception whose own repr raises."""

    def __repr__(self):
        raise RuntimeError("exc repr boom")


class RemoveprefixRaiseStr(str):
    def removeprefix(self, prefix, /):
        raise RuntimeError("removeprefix boom")


class RemoveprefixLieStr(str):
    def removeprefix(self, prefix, /):
        return "steered"


class BoolCounter:
    def __init__(self):
        self.calls = 0

    def __bool__(self):
        self.calls += 1
        return True


class BoolRaiseStr(str):
    def __bool__(self):
        raise RuntimeError("bool boom")


class LenRaiseStr(str):
    def __len__(self):
        raise RuntimeError("len boom")


class BoolLieStr(str):
    """Truthiness lies, answering falsy for non empty content."""

    def __bool__(self):
        return False


class BoolCountStr(str):
    calls = 0

    def __bool__(self):
        type(self).calls += 1
        return True


class LenRaiseList(list):
    def __len__(self):
        raise RuntimeError("raw len boom")


class GetitemRaiseList(list):
    def __getitem__(self, index):
        raise RuntimeError("raw getitem boom")


def deep_raw(levels):
    node = {}
    current = node
    for _ in range(levels):
        current["extra"] = {}
        current = current["extra"]
    return node


# ----------------------------------------------------------------
# The read guard
# ----------------------------------------------------------------

def test_get_raise_at_root_converts_and_names_model_and_key():
    with pytest.raises(DecodeError) as caught:
        LocalizedText.from_api(GetRaise(RT, None, {"text": "x"}))
    assert str(caught.value) == (
        "LocalizedText payload key 'text' could not be read: "
        "RuntimeError('boom')"
    )
    # The decode reads the payload copy, so the chained cause is
    # the copy of the stored exception, equal in type and args.
    cause = caught.value.__cause__
    assert isinstance(cause, RuntimeError) and cause.args == ("boom",)


def test_get_raise_at_a_late_place_read_converts():
    payload = GetRaise(RT, {"rating"}, {"name": "x", "rating": 1.0})
    with pytest.raises(DecodeError) as caught:
        Place.from_api(payload)
    assert str(caught.value) == (
        "Place payload key 'rating' could not be read: "
        "RuntimeError('boom')"
    )


def test_require_contains_raise_converts():
    with pytest.raises(DecodeError) as caught:
        LatLng.from_api(OmnRaise(RT, {"latitude": 1.0, "longitude": 2.0}))
    assert str(caught.value) == (
        "LatLng payload key 'latitude' could not be read: "
        "RuntimeError('boom')"
    )


def test_require_index_keyerror_after_membership_converts():
    payload = GetitemKeyError(
        {"low": {"latitude": 1.0, "longitude": 2.0},
         "high": {"latitude": 3.0, "longitude": 4.0}}
    )
    with pytest.raises(DecodeError) as caught:
        Viewport.from_api(payload)
    assert str(caught.value) == (
        "Viewport payload key 'low' could not be read: KeyError('low')"
    )


def test_custom_exception_with_raising_repr_converts():
    with pytest.raises(DecodeError) as caught:
        LocalizedText.from_api(
            GetRaise(ExcReprRaise("custom"), None, {"text": "x"}))
    assert str(caught.value) == (
        "LocalizedText payload key 'text' could not be read: "
        "<unrepresentable ExcReprRaise>"
    )
    assert isinstance(caught.value.__cause__, ExcReprRaise)


def test_keyboard_interrupt_at_a_read_passes_through():
    payload = GetRaise(KeyboardInterrupt(), {"rating"},
                       {"name": "x", "rating": 1.0})
    with pytest.raises(KeyboardInterrupt):
        Place.from_api(payload)


def test_keyboard_interrupt_at_require_passes_through():
    with pytest.raises(KeyboardInterrupt):
        LatLng.from_api(OmnRaise(KeyboardInterrupt(),
                                 {"latitude": 1.0, "longitude": 2.0}))


# ----------------------------------------------------------------
# Truthiness gates
# ----------------------------------------------------------------

def test_child_gate_len_raise_converts():
    payload = {"name": "x",
               "location": LenRaiseDict(
                   {"latitude": 1.0, "longitude": 2.0})}
    with pytest.raises(DecodeError) as caught:
        Place.from_api(payload)
    assert str(caught.value) == (
        "Place payload key 'location' could not be read: "
        "RuntimeError('len boom')"
    )


def test_place_empty_check_len_raise_converts():
    with pytest.raises(DecodeError) as caught:
        Place.from_api(LenRaiseDict({"name": "x"}))
    assert str(caught.value) == (
        "Place payload could not be read: RuntimeError('len boom')"
    )


def test_structured_format_collapse_len_raise_converts():
    payload = {"placeId": "p",
               "structuredFormat": LenRaiseDict({"mainText": {}})}
    with pytest.raises(DecodeError) as caught:
        PlacePrediction.from_api(payload)
    assert str(caught.value) == (
        "PlacePrediction payload key 'structuredFormat' could not "
        "be read: RuntimeError('len boom')"
    )


def test_truthy_evaluates_the_value_exactly_once():
    value = BoolCounter()
    assert _truthy(value, "Place", "location") is True
    assert value.calls == 1


# ----------------------------------------------------------------
# Raw sources and list elements
# ----------------------------------------------------------------

def test_raw_subtree_get_raise_converts():
    raw = GetRaise(RT, {"displayName"},
                   {"displayName": {"text": "a"}})
    with pytest.raises(DecodeError) as caught:
        Place.from_api({"name": "x", "displayName": {"text": "a"}}, raw=raw)
    assert str(caught.value) == (
        "Place payload key 'displayName' could not be read: "
        "RuntimeError('boom')"
    )


def test_child_decode_error_keeps_the_index_message_byte_for_byte():
    with pytest.raises(DecodeError) as caught:
        Place.from_api(
            {"name": "x", "addressComponents": [{"longText": 5}]})
    assert str(caught.value) == (
        "Place payload key 'addressComponents' element 0 failed to "
        "decode: AddressComponent payload key 'longText' is not a "
        "string: 5"
    )


def test_model_elements_non_decode_failure_converts_with_index():
    def decode(item, raw):
        raise RuntimeError("decode boom")

    with pytest.raises(DecodeError) as caught:
        _model_elements([{}], "Place", "reviews", {}, decode)
    assert str(caught.value) == (
        "Place payload key 'reviews' element 0 could not be read: "
        "RuntimeError('decode boom')"
    )


def test_model_elements_config_error_passes_through_untouched():
    # No from_api path can route a ConfigError into
    # _model_elements today, because the list decoders validate
    # every element before any construction guard can fire, so
    # this pin drives _model_elements in its own call shape with
    # a child decoder that raises one. The ruling it holds is
    # that the widened catch never reclassifies the library's
    # own error family.
    verdict = ConfigError("caller misuse")

    def decode(item, raw):
        raise verdict

    with pytest.raises(ConfigError) as caught:
        _model_elements([{}], "Place", "reviews", {}, decode)
    assert caught.value is verdict
    assert caught.value.message == "caller misuse"
    assert caught.value.__cause__ is None


def test_raw_element_len_raise_converts():
    raw = {"reviews": LenRaiseList([{"rating": 5}])}
    with pytest.raises(DecodeError) as caught:
        _raw_element(raw, "reviews", 0, "fallback", "Place")
    assert str(caught.value) == (
        "Place payload key 'reviews' could not be read: "
        "RuntimeError('raw len boom')"
    )
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_raw_element_getitem_raise_converts():
    raw = {"reviews": GetitemRaiseList([{"rating": 5}])}
    with pytest.raises(DecodeError) as caught:
        _raw_element(raw, "reviews", 0, "fallback", "Place")
    assert str(caught.value) == (
        "Place payload key 'reviews' could not be read: "
        "RuntimeError('raw getitem boom')"
    )
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_raw_element_raises_at_model_level_match_the_raw_get():
    review = {"text": {"text": "great", "languageCode": "en"},
              "rating": 5}
    for raw_items, boom in (
        (LenRaiseList([{"rating": 5}]), "raw len boom"),
        (GetitemRaiseList([{"rating": 5}]), "raw getitem boom"),
    ):
        with pytest.raises(DecodeError) as caught:
            Place.from_api({"name": "x", "reviews": [review]},
                           raw={"reviews": raw_items})
        assert str(caught.value) == (
            "Place payload key 'reviews' element 0 failed to "
            f"decode: Place payload key 'reviews' could not be "
            f"read: RuntimeError({boom!r})"
        )


# ----------------------------------------------------------------
# Copy guards, the red team raw shapes
# ----------------------------------------------------------------

def test_raw_source_copy_raise_at_root_converts():
    raw = {"displayName": DeepcopyRaise()}
    with pytest.raises(DecodeError) as caught:
        Place.from_api({"name": "x"}, raw=raw)
    assert str(caught.value) == (
        "Place payload could not be read: "
        "RuntimeError('deepcopy boom')"
    )


def test_raw_source_copy_raise_in_list_element_converts():
    raw = {"places": [{"displayName": DeepcopyRaise()}]}
    with pytest.raises(DecodeError) as caught:
        TextSearchResult.from_api({"places": [{"name": "x"}]}, raw=raw)
    assert str(caught.value) == (
        "TextSearchResult payload could not be read: "
        "RuntimeError('deepcopy boom')"
    )


def test_raw_source_deep_nesting_copy_converts():
    with pytest.raises(DecodeError) as caught:
        Place.from_api({"name": "x"}, raw=deep_raw(4000))
    assert str(caught.value).startswith(
        "Place payload could not be read: RecursionError(")


def test_window_branch_raw_copy_raise_converts():
    body = {"name": "x"}
    raw = {"displayName": DeepcopyRaise()}
    with _owned_decode(body):
        with pytest.raises(DecodeError) as caught:
            Place.from_api({"name": "x"}, raw=raw)
    assert str(caught.value) == (
        "Place payload could not be read: "
        "RuntimeError('deepcopy boom')"
    )


def test_raw_copy_keyboard_interrupt_passes_through():
    raw = {"displayName": DeepcopyKbd()}
    with pytest.raises(KeyboardInterrupt):
        Place.from_api({"name": "x"}, raw=raw)


# ----------------------------------------------------------------
# Safe repr
# ----------------------------------------------------------------

def test_safe_repr_returns_the_repr_where_repr_works():
    assert _safe_repr(5) == "5"
    assert _safe_repr("x") == "'x'"
    assert _safe_repr(RT) == "RuntimeError('boom')"


def test_safe_repr_names_the_type_where_repr_raises():
    assert _safe_repr(ReprRaise()) == "<unrepresentable ReprRaise>"
    assert _safe_repr(ReprNonString()) == "<unrepresentable ReprNonString>"


def test_scalar_refusal_with_raising_repr_value_converts():
    with pytest.raises(DecodeError) as caught:
        LocalizedText.from_api({"text": ReprRaise()})
    assert str(caught.value) == (
        "LocalizedText payload key 'text' is not a string: "
        "<unrepresentable ReprRaise>"
    )


def test_admission_refusal_with_raising_repr_root_converts():
    with pytest.raises(DecodeError) as caught:
        Place.from_api(ReprRaise())
    assert str(caught.value) == (
        "Place payload must be an object, got ReprRaise: "
        "<unrepresentable ReprRaise>"
    )


def test_prediction_not_an_object_refusal_with_raising_repr_converts():
    payload = {"placeId": "p", "structuredFormat": ReprRaiseStr("x")}
    with pytest.raises(DecodeError) as caught:
        PlacePrediction.from_api(payload)
    assert str(caught.value) == (
        "PlacePrediction payload key 'structuredFormat' is not an "
        "object: <unrepresentable ReprRaiseStr>"
    )


# ----------------------------------------------------------------
# Construction guards
# ----------------------------------------------------------------

def test_latlng_float_conversion_raise_becomes_config_error():
    with pytest.raises(ConfigError) as caught:
        LatLng(FloatMethodRaiseInt(3), 0.0)
    assert str(caught.value) == (
        "LatLng latitude must be a finite real number, got 3"
    )


def test_latlng_huge_int_becomes_config_error():
    with pytest.raises(ConfigError) as caught:
        LatLng(10 ** 400, 0.0)
    assert str(caught.value).startswith(
        "LatLng latitude must be a finite real number, got 1000")


def test_latlng_nan_with_raising_repr_becomes_config_error():
    with pytest.raises(ConfigError) as caught:
        LatLng(NanReprFloat("nan"), 0.0)
    assert str(caught.value) == (
        "LatLng latitude must be a finite real number, got "
        "<unrepresentable NanReprFloat>"
    )


def test_latlng_honest_message_unchanged():
    with pytest.raises(ConfigError) as caught:
        LatLng("1.0", 0.0)
    assert str(caught.value) == (
        "LatLng latitude must be a finite real number, got '1.0'"
    )


# ----------------------------------------------------------------
# The Place id fallback, site class 9
# ----------------------------------------------------------------

def test_id_fallback_removeprefix_raise_decodes():
    place = Place.from_api({"name": RemoveprefixRaiseStr("places/abc")})
    assert place.id == "abc"


def test_id_fallback_removeprefix_lie_cannot_steer_the_id():
    place = Place.from_api({"name": RemoveprefixLieStr("places/abc")})
    assert place.id == "abc"


def test_id_truthiness_bool_raise_converts():
    payload = {"id": BoolRaiseStr("places/xyz"), "name": "places/abc"}
    with pytest.raises(DecodeError) as caught:
        Place.from_api(payload)
    assert str(caught.value) == (
        "Place payload key 'id' could not be read: "
        "RuntimeError('bool boom')"
    )
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_id_truthiness_len_raise_converts():
    payload = {"id": LenRaiseStr("places/xyz"), "name": "places/abc"}
    with pytest.raises(DecodeError) as caught:
        Place.from_api(payload)
    assert str(caught.value) == (
        "Place payload key 'id' could not be read: "
        "RuntimeError('len boom')"
    )
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_id_truthiness_is_evaluated_exactly_once():
    BoolCountStr.calls = 0
    place = Place.from_api(
        {"id": BoolCountStr("places/xyz"), "name": "places/abc"})
    assert place.id == "places/xyz"
    assert BoolCountStr.calls == 1


def test_id_truthiness_lie_is_followed_as_sent():
    place = Place.from_api(
        {"id": BoolLieStr("places/xyz"), "name": "places/abc"})
    assert place.id == "abc"


def test_honest_id_wins_over_the_derivation():
    place = Place.from_api({"id": "places/xyz", "name": "places/abc"})
    assert place.id == "places/xyz"


def test_honest_falsy_id_falls_to_the_derivation():
    assert Place.from_api({"id": "", "name": "places/abc"}).id == "abc"
    assert Place.from_api({"name": "places/abc"}).id == "abc"


# ----------------------------------------------------------------
# The genus fence and honest messages stay put
# ----------------------------------------------------------------

def test_genus_copy_swap_answer_is_followed_as_sent():
    result = LatLng.from_api(
        {"latitude": DeepcopySwap(3.5), "longitude": 2.0})
    assert result.latitude == 3.5


def test_genus_membership_lie_is_followed_as_sent():
    with pytest.raises(DecodeError) as caught:
        LatLng.from_api(
            ContainsFalse({"latitude": 1.0, "longitude": 2.0}))
    assert str(caught.value) == (
        "LatLng payload is missing required key 'latitude'"
    )


def test_genus_falsy_child_gate_still_decodes_to_none():
    assert Suggestion.from_api({"placePrediction": 0}).place_prediction is None
    place = Place.from_api({"name": "x", "location": 0})
    assert place.location is None


def test_honest_missing_key_message_unchanged():
    with pytest.raises(DecodeError) as caught:
        LatLng.from_api({"longitude": 2.0})
    assert str(caught.value) == (
        "LatLng payload is missing required key 'latitude'"
    )


def test_honest_refusal_messages_unchanged():
    with pytest.raises(DecodeError) as caught:
        LocalizedText.from_api({"text": 5})
    assert str(caught.value) == (
        "LocalizedText payload key 'text' is not a string: 5"
    )
    with pytest.raises(DecodeError) as caught:
        Place.from_api({})
    assert str(caught.value) == (
        "Place payload is empty; refusing to fabricate an empty "
        "place from it"
    )


# ----------------------------------------------------------------
# Read counts do not move
# ----------------------------------------------------------------

LOG = []
SENTINEL = object()


class CountingDict(dict):
    """Records each get, contains and getitem against a shared log.

    A get records whether a default argument was passed and the
    default's repr, which is the observable surface of the call
    site default evaluation the repair preserves.
    """

    def __init__(self, label, *args):
        super().__init__(*args)
        self.label = label

    def get(self, key, default=SENTINEL):
        if default is SENTINEL:
            LOG.append((self.label, "get", key, False, ""))
            return super().get(key)
        LOG.append((self.label, "get", key, True, repr(default)))
        return super().get(key, default)

    def __contains__(self, key):
        LOG.append((self.label, "contains", key))
        return super().__contains__(key)

    def __getitem__(self, key):
        LOG.append((self.label, "getitem", key))
        return super().__getitem__(key)


def wrap(value, label):
    if isinstance(value, dict):
        out = CountingDict(label)
        for key, item in value.items():
            dict.__setitem__(out, key, wrap(item, f"{label}.{key}"))
        return out
    if isinstance(value, list):
        return [wrap(item, f"{label}[{i}]") for i, item in enumerate(value)]
    return value


def drive(root, payload):
    LOG.clear()
    getattr(models, root).from_api(wrap(payload, root))
    return list(LOG)


def test_read_counts_localized_text():
    log = drive("LocalizedText", {"text": "A place", "languageCode": "en"})
    assert log == [
        ("LocalizedText", "get", "text", True, "''"),
        ("LocalizedText", "get", "languageCode", False, ""),
    ]


def test_read_counts_latlng():
    log = drive("LatLng", {"latitude": 37.422, "longitude": -122.084})
    assert log == [
        ("LatLng", "contains", "latitude"),
        ("LatLng", "getitem", "latitude"),
        ("LatLng", "contains", "longitude"),
        ("LatLng", "getitem", "longitude"),
    ]


def test_read_counts_viewport():
    payload = {
        "low": {"latitude": 37.422, "longitude": -122.084},
        "high": {"latitude": 37.424, "longitude": -122.082},
    }
    log = drive("Viewport", payload)
    assert log == [
        ("Viewport", "contains", "low"),
        ("Viewport", "getitem", "low"),
        ("Viewport", "contains", "high"),
        ("Viewport", "getitem", "high"),
        ("Viewport", "get", "low", True, "{}"),
        ("Viewport.low", "contains", "latitude"),
        ("Viewport.low", "getitem", "latitude"),
        ("Viewport.low", "contains", "longitude"),
        ("Viewport.low", "getitem", "longitude"),
        ("Viewport", "get", "high", True, "{}"),
        ("Viewport.high", "contains", "latitude"),
        ("Viewport.high", "getitem", "latitude"),
        ("Viewport.high", "contains", "longitude"),
        ("Viewport.high", "getitem", "longitude"),
    ]


def test_read_counts_place_prediction():
    formatted = {
        "text": "Main Street",
        "stringMatches": [{"startOffset": 0, "endOffset": 4}],
    }
    payload = {
        "place": "places/ChIJx",
        "placeId": "ChIJx",
        "text": formatted,
        "structuredFormat": {"mainText": formatted,
                             "secondaryText": formatted},
        "types": ["cafe"],
        "distanceMeters": 350,
    }
    log = drive("PlacePrediction", payload)
    assert log == [
        ("PlacePrediction", "get", "text", False, ""),
        ("PlacePrediction", "get", "structuredFormat", False, ""),
        ("PlacePrediction", "get", "structuredFormat", True, "{}"),
        ("PlacePrediction.structuredFormat", "get", "mainText", False, ""),
        ("PlacePrediction.structuredFormat", "get", "secondaryText",
         False, ""),
        ("PlacePrediction", "get", "placeId", True, "''"),
        ("PlacePrediction", "get", "place", True, "''"),
        ("PlacePrediction", "get", "text", True, "{}"),
        ("PlacePrediction.text", "get", "text", True, "''"),
        ("PlacePrediction.text", "get", "matches", True, "[]"),
        ("PlacePrediction.structuredFormat", "get", "mainText", True, "{}"),
        ("PlacePrediction.structuredFormat.mainText", "get", "text",
         True, "''"),
        ("PlacePrediction.structuredFormat.mainText", "get", "matches",
         True, "[]"),
        ("PlacePrediction.structuredFormat", "get", "secondaryText",
         True, "{}"),
        ("PlacePrediction.structuredFormat.secondaryText", "get", "text",
         True, "''"),
        ("PlacePrediction.structuredFormat.secondaryText", "get", "matches",
         True, "[]"),
        ("PlacePrediction", "get", "types", True, "[]"),
        ("PlacePrediction", "get", "distanceMeters", False, ""),
    ]


def test_read_helpers_perform_exactly_one_get():
    LOG.clear()
    wrapped = wrap({"a": 1}, "Root")
    assert _read(wrapped, "a", "Root") == 1
    assert LOG == [("Root", "get", "a", False, "")]
    LOG.clear()
    marker = object()
    assert _read_or(wrapped, "missing", marker, "Root") is marker
    assert LOG == [("Root", "get", "missing", True, repr(marker))]
