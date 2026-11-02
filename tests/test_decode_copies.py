"""Round 21 (T8) decode copy pins.

The performance landing removed the copies in the decode path
that were not load bearing and kept every copy that is. These
tests pin the invariants the removal leans on, so a later change
that reintroduces aliasing, or removes a copy that is load
bearing, fails here rather than in a consumer.

The pinned invariants are the documented ones. A result shares no
mutable state with the dict a direct caller supplied, on either
decode source. The raw of one node shares no mutable state with
the raw of any other node of the same result, on the direct layer
and through the client alike. Through the client the top raw is
the parsed body the client built for that call, adopted rather
than copied, and one call's result never reaches another call's
result. The owned decode window the client opens is closed when
the call returns and is never inherited across a fork. The copy
census pins the shape of the optimisation itself, at most one
deep copy per decoded node on the direct layer and one fewer
than that through a client conversion, where the top node adopts
its raw instead of copying it.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import textwrap
from pathlib import Path

from placekit import Client
from placekit import address, models
from placekit.client import _Base
from placekit.models import Place

ROOT = Path(__file__).resolve().parent.parent
RICHEST = (
    ROOT
    / "tests"
    / "fixtures"
    / "recorded"
    / "recorded_P15_richest_mall_store.json"
)


def _richest():
    return RICHEST.read_bytes()


def _small_payload():
    return {
        "id": "ChIJx",
        "displayName": {"text": "Cafe", "languageCode": "en"},
        "location": {"latitude": 1.0, "longitude": 2.0},
        "types": ["cafe"],
    }


def test_direct_result_shares_nothing_with_the_callers_dict():
    payload = _small_payload()
    place = Place.from_api(payload)
    payload["displayName"]["text"] = "Mutated"
    payload["location"]["latitude"] = 9.0
    payload["types"].append("bar")
    assert place.display_text == "Cafe"
    assert place.location.latitude == 1.0
    assert place.types == ["cafe"]
    assert place.raw["displayName"]["text"] == "Cafe"
    assert place.raw["types"] == ["cafe"]


def test_direct_result_shares_nothing_with_a_supplied_raw():
    payload = _small_payload()
    raw = _small_payload()
    place = Place.from_api(payload, raw=raw)
    payload["displayName"]["text"] = "Mutated"
    raw["displayName"]["text"] = "Mutated"
    raw["types"].append("bar")
    assert place.display_text == "Cafe"
    assert place.raw["displayName"]["text"] == "Cafe"
    assert place.raw["types"] == ["cafe"]
    assert place.display_name.raw["text"] == "Cafe"


def test_node_raws_share_nothing_with_each_other_direct():
    place = Place.from_api(_small_payload())
    place.display_name.raw["text"] = "Mutated"
    place.location.raw["latitude"] = 9.0
    assert place.raw["displayName"]["text"] == "Cafe"
    assert place.raw["location"]["latitude"] == 1.0
    place = Place.from_api(_small_payload())
    place.raw["displayName"]["text"] = "Mutated"
    place.raw["location"]["latitude"] = 9.0
    assert place.display_name.raw["text"] == "Cafe"
    assert place.location.raw["latitude"] == 1.0


def test_node_raws_share_nothing_with_each_other_through_the_client(
    api_key, base_url
):
    client = Client(api_key, base_url=base_url)
    result = client.text_search("cafes in Sydney")
    place = result.places[0]
    wire_text = place.display_name.raw["text"]
    place.display_name.raw["text"] = "Mutated"
    assert place.raw["displayName"]["text"] == wire_text
    assert result.raw["places"][0]["displayName"]["text"] == wire_text
    result.raw["places"][0]["displayName"]["text"] = "Mutated"
    assert place.raw["displayName"]["text"] == wire_text


def test_client_results_do_not_reach_each_other(api_key, base_url):
    client = Client(api_key, base_url=base_url)
    first = client.text_search("cafes in Sydney")
    second = client.text_search("cafes in Sydney")
    first.raw["places"][0]["displayName"]["text"] = "Mutated"
    first.places[0].display_name.raw["text"] = "Mutated"
    assert second.places[0].display_text == second.raw["places"][0][
        "displayName"
    ]["text"]
    assert (
        second.places[0].display_name.raw["text"]
        == second.places[0].display_text
    )


def test_the_owned_window_closes_when_the_call_returns(api_key, base_url):
    client = Client(api_key, base_url=base_url)
    client.text_search("cafes in Sydney")
    # A direct decode after a client call is a direct decode. The
    # window the conversion opened is gone, so the caller's dict
    # is copied exactly as it is for a caller who never owned a
    # client.
    payload = _small_payload()
    place = Place.from_api(payload)
    payload["displayName"]["text"] = "Mutated"
    assert place.display_text == "Cafe"
    assert place.raw["displayName"]["text"] == "Cafe"


class _Census:
    """Count prepare calls and deep copy invocations in one decode."""

    def __init__(self):
        self.prepares = 0
        self.copies = 0
        self._real_prepare = models._prepare
        self._real_deepcopy = copy.deepcopy

    def __enter__(self):
        census = self

        def counting_prepare(data, raw, model):
            census.prepares += 1
            return census._real_prepare(data, raw, model)

        def counting_deepcopy(value, memo=None, _nil=[]):
            census.copies += 1
            return census._real_deepcopy(value, memo, _nil)

        models._prepare = counting_prepare
        copy.deepcopy = counting_deepcopy
        return self

    def __exit__(self, *exc):
        models._prepare = self._real_prepare
        copy.deepcopy = self._real_deepcopy
        return False


def test_direct_decode_copies_at_most_once_per_node():
    body = json.loads(_richest())
    with _Census() as census:
        Place.from_api(body)
    assert census.prepares > 100  # the richest place is node dense
    assert census.copies == census.prepares


def test_client_conversion_copies_one_fewer_than_once_per_node():
    body_text = _richest().decode()
    typed = json.loads(body_text)
    with _Census() as census:
        result = _Base._convert_body(
            Place.from_api, (typed, body_text, 200), "place_details"
        )
    assert census.prepares > 100
    # Every node below the first copies its raw exactly once, the
    # first node adopts the parsed body, and no node copies the
    # typed dict it reads.
    assert census.copies == census.prepares - 1
    assert result.raw == json.loads(body_text)


def test_forked_child_does_not_inherit_the_owned_window(tmp_path):
    script = textwrap.dedent(
        """
        import json, os, sys
        sys.path.insert(0, sys.argv[2])
        from placekit import models
        from placekit.models import Place

        payload = {
            "id": "ChIJx",
            "displayName": {"text": "Cafe", "languageCode": "en"},
            "types": ["cafe"],
        }
        outcome = {}
        with models._owned_decode({"id": "root"}):
            pid = os.fork()
            if pid == 0:
                # The grandchild inherits the memory of the window
                # but not its process, so its decode must take the
                # ordinary path and copy the caller's dict.
                place = Place.from_api(payload)
                payload["displayName"]["text"] = "Mutated"
                outcome["isolated"] = (
                    place.display_text == "Cafe"
                    and place.raw["displayName"]["text"] == "Cafe"
                )
                with open(sys.argv[1], "w") as fh:
                    json.dump(outcome, fh)
                os._exit(0)
            os.waitpid(pid, 0)
        """
    )
    outcome_path = tmp_path / "outcome.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(outcome_path),
            str(ROOT / "python"),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(outcome_path.read_text())["isolated"] is True


def _counted_validations(monkeypatch):
    calls = {"n": 0}
    real = address._checked_components

    def counting(components):
        calls["n"] += 1
        return real(components)

    monkeypatch.setattr(address, "_checked_components", counting)
    return calls


def _corpus_place():
    body = json.loads(_richest())
    return Place.from_api(body)


def test_address_flags_validates_the_components_once(monkeypatch):
    place = _corpus_place()
    calls = _counted_validations(monkeypatch)
    address.address_flags(place)
    assert calls["n"] == 1


def test_place_level_readings_validate_the_components_once(monkeypatch):
    place = _corpus_place()
    for reading in (
        address.country_code,
        address.postal_code,
        address.city_resolutions,
        address.resolve_city,
        address.resolve_district,
        address.is_premise_level,
    ):
        calls = _counted_validations(monkeypatch)
        reading(place)
        assert calls["n"] == 1, reading.__name__
        monkeypatch.undo()
