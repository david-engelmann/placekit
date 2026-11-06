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
its raw instead of copying it. The window pins assert the
ownership state and the adoption identity directly, so a leaked
window, a refused window, or a window inherited across a fork
fails on the state itself rather than on an outcome the fail
safe copying path would make true either way. The address pins
count the component scans behind one flags call beside the
validations, so the scan sharing cannot regress silently while
the validation count stays at one.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import placekit
from placekit import Client
from placekit import address, models
from placekit.client import _Base
from placekit.models import Place

ROOT = Path(__file__).resolve().parent.parent
# The directory that holds the placekit package this process
# imported. A develop build resolves it to the source tree python
# folder and an installed wheel to site packages, and a subprocess
# that must import the same placekit puts this directory first on
# its path instead of assuming the source tree.
PACKAGE_PARENT = Path(placekit.__file__).resolve().parent.parent
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


def test_decode_inside_a_window_adopts_the_windows_raw_root():
    # The in window path itself, pinned by identity. A decode
    # whose raw source is the window's own raw root adopts that
    # tree as the top node's raw instead of copying it, which is
    # the one copy a client conversion saves over the direct
    # layer. Were the window not open, or the ownership refused,
    # the raw would come back as a copy and the identity would
    # fail, so this pin can fail for the failure it names.
    root = _small_payload()
    typed = copy.deepcopy(root)
    with models._owned_decode(root):
        assert models._ownership() is not None
        place = Place.from_api(typed, raw=root)
    assert place.raw is root
    # Below the top node the per node raw copies still stand, so
    # a child raw is an equal but separate tree.
    assert place.display_name.raw == root["displayName"]
    assert place.display_name.raw is not root["displayName"]
    place.display_name.raw["text"] = "Mutated"
    assert root["displayName"]["text"] == "Cafe"


def test_the_owned_window_closes_when_the_call_returns(api_key, base_url):
    client = Client(api_key, base_url=base_url)
    result = client.text_search("cafes in Sydney")
    # The ownership state itself is the evidence, asserted
    # directly rather than through an isolation outcome the fail
    # safe copying path would make true on both paths. The
    # window the conversion opened is closed when the call
    # returns, so the accessor reports no window in this context.
    assert models._ownership() is None
    # A decode aimed at the returned result's own raw tree, the
    # very tree the conversion window held, must copy that tree
    # rather than adopt it. Had the window leaked past the call,
    # the decode would meet the leaked window, recognise its raw
    # root, and hand back the tree itself.
    payload = _small_payload()
    place = Place.from_api(payload, raw=result.raw)
    assert place.raw is not result.raw
    place.raw["places"][0]["displayName"]["text"] = "Mutated"
    assert result.raw["places"][0]["displayName"]["text"] != "Mutated"


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
        import copy, json, os, sys
        sys.path.insert(0, sys.argv[2])
        from placekit import models
        from placekit.models import Place

        root = {
            "id": "ChIJx",
            "displayName": {"text": "Cafe", "languageCode": "en"},
            "types": ["cafe"],
        }
        typed = copy.deepcopy(root)
        outcome = {}
        with models._owned_decode(root):
            pid = os.fork()
            if pid == 0:
                # The child inherits the memory of the window but
                # not its process. The ownership accessor must
                # refuse the inherited state outright, asserted
                # directly rather than through an isolation
                # outcome the fail safe copying path would make
                # true on both paths.
                outcome["ownership_refused"] = (
                    models._ownership() is None
                )
                # A decode aimed at the inherited raw root must
                # copy that root rather than adopt it, which is
                # the path the refusal protects. Without the
                # process check the decode would meet the
                # inherited window and hand back the root itself.
                place = Place.from_api(typed, raw=root)
                outcome["root_copied_not_adopted"] = (
                    place.raw is not root
                )
                place.raw["displayName"]["text"] = "Mutated"
                outcome["root_untouched"] = (
                    root["displayName"]["text"] == "Cafe"
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
            str(PACKAGE_PARENT),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    outcome = json.loads(outcome_path.read_text())
    assert outcome == {
        "ownership_refused": True,
        "root_copied_not_adopted": True,
        "root_untouched": True,
    }


def test_forked_child_releases_the_inherited_state_on_first_read(tmp_path):
    # Round 29: the refusal now clears the inherited state, so a
    # forked child stops retaining the parent process's parsed
    # body tree through the ownership variable after its first
    # decode. The variable itself is the evidence: it reaches the
    # tree before the read and holds nothing after it.
    script = textwrap.dedent(
        """
        import copy, json, os, sys
        sys.path.insert(0, sys.argv[2])
        from placekit import models
        from placekit.models import Place

        root = {
            "id": "ChIJx",
            "displayName": {"text": "Cafe", "languageCode": "en"},
            "types": ["cafe"],
        }
        typed = copy.deepcopy(root)
        outcome = {}
        with models._owned_decode(root):
            pid = os.fork()
            if pid == 0:
                inherited = models._decode_ownership.get()
                outcome["state_inherited"] = (
                    inherited is not None and inherited.raw_root is root
                )
                # The first decode reads the ownership state,
                # which refuses the inherited window and clears it.
                place = Place.from_api(typed, raw=root)
                outcome["decode_copied_not_adopted"] = place.raw is not root
                outcome["state_cleared"] = (
                    models._decode_ownership.get() is None
                )
                # The child's own window still works after the
                # clear: it opens, adopts its own root, and closes.
                own = {"id": "ChIJy"}
                with models._owned_decode(own):
                    own_place = Place.from_api(
                        copy.deepcopy(own), raw=own
                    )
                    outcome["own_window_adopts"] = own_place.raw is own
                outcome["own_window_closed"] = (
                    models._decode_ownership.get() is None
                )
                with open(sys.argv[1], "w") as fh:
                    json.dump(outcome, fh)
                os._exit(0)
            os.waitpid(pid, 0)
            outcome["parent_window_intact"] = (
                models._ownership() is not None
            )
        with open(sys.argv[3], "w") as fh:
            json.dump(outcome, fh)
        """
    )
    child_path = tmp_path / "child.json"
    parent_path = tmp_path / "parent.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(child_path),
            str(PACKAGE_PARENT),
            str(parent_path),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    child = json.loads(child_path.read_text())
    assert child == {
        "state_inherited": True,
        "decode_copied_not_adopted": True,
        "state_cleared": True,
        "own_window_adopts": True,
        "own_window_closed": True,
    }
    parent = json.loads(parent_path.read_text())
    assert parent["parent_window_intact"] is True


def test_forked_child_token_reset_restores_then_refuses_again(tmp_path):
    # Round 29, the named edge, pinned as documented behaviour: a
    # token reset from an inherited window frame can restore a
    # stale outer state after the lazy clear (the reset restores
    # the value the variable held before the inner window opened,
    # which in a forked child is the outer window's state). The
    # restore is inert: the process check refuses the restored
    # state on the next read and clears it again, so no decode
    # adopts it either way.
    script = textwrap.dedent(
        """
        import copy, json, os, sys
        sys.path.insert(0, sys.argv[2])
        from placekit import models
        from placekit.models import Place

        root_a = {"id": "ChIJa"}
        root_b = {"id": "ChIJb"}
        outcome = {}
        state = {}

        def inner():
            with models._owned_decode(root_b):
                pid = os.fork()
                if pid == 0:
                    state["child"] = True
                    outcome["first_read_refused"] = (
                        models._ownership() is None
                    )
                    outcome["cleared_after_first_read"] = (
                        models._decode_ownership.get() is None
                    )
                    return
                os.waitpid(pid, 0)

        with models._owned_decode(root_a):
            inner()
            if state.get("child"):
                # The inner window's frame has now exited in this
                # child too, so its token reset restored the outer
                # window's state into the variable.
                restored = models._decode_ownership.get()
                outcome["stale_state_restored"] = (
                    restored is not None and restored.raw_root is root_a
                )
                outcome["second_read_refused"] = (
                    models._ownership() is None
                )
                outcome["cleared_again"] = (
                    models._decode_ownership.get() is None
                )
                typed = copy.deepcopy(root_a)
                place = Place.from_api(typed, raw=root_a)
                outcome["decode_still_copies"] = place.raw is not root_a
                with open(sys.argv[1], "w") as fh:
                    json.dump(outcome, fh)
                os._exit(0)
        """
    )
    outcome_path = tmp_path / "outcome.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(outcome_path),
            str(PACKAGE_PARENT),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    outcome = json.loads(outcome_path.read_text())
    assert outcome == {
        "first_read_refused": True,
        "cleared_after_first_read": True,
        "stale_state_restored": True,
        "second_read_refused": True,
        "cleared_again": True,
        "decode_still_copies": True,
    }


def _counted_validations(monkeypatch):
    calls = {"n": 0}
    # The counted surface is the one validation funnel every
    # reading passes through. Since the Round 53 repair the
    # funnel is the pair form, which returns the plain capture
    # the core conversion consumes beside the checked tuple, so
    # the count discipline rides on that name.
    real = address._checked_components_and_plain

    def counting(components):
        calls["n"] += 1
        return real(components)

    monkeypatch.setattr(address, "_checked_components_and_plain", counting)
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


def test_address_flags_pays_one_scan_per_composed_reading(monkeypatch):
    place = _corpus_place()
    scans = {"cores": 0, "public": 0}
    # Since the Round 53 port the scans run in the Rust core, so
    # the counted surface is the core boundary itself, the
    # address functions on the extension module. The pin keeps
    # its shape and its count discipline from the Python scan
    # cores it counted before the port. The repair pass added
    # the first long text index form to the boundary, which the
    # postal reading crosses in place of the text form, and the
    # counted set names it with the rest.
    from placekit import _placekit

    for name in (
        "address_matching_indices",
        "address_untyped_indices",
        "address_first_long_text",
        "address_first_long_text_index",
        "address_first_short_text",
        "address_long_texts",
        "address_short_texts",
        "address_country_code",
        "address_city_resolutions",
        "address_district_resolution",
        "address_postal_code_result",
        "address_component_flags",
        "address_split_compound_code",
    ):
        real = getattr(_placekit, name)

        def counting(*args, _real=real):
            scans["cores"] += 1
            return _real(*args)

        monkeypatch.setattr(_placekit, name, counting)
    real_find = address.find_components

    def counting_find(components, type_name):
        scans["public"] += 1
        return real_find(components, type_name)

    monkeypatch.setattr(address, "find_components", counting_find)
    address.address_flags(place)
    # The flags compose from core readings over the one checked
    # list, seven core crossings for the richest corpus place
    # (the flags reading itself, then the postal, country and
    # city readings the snapshot composes, the country read
    # paying once per reading that asks for it), and no reading
    # routes back through the public find helpers, which rescan
    # the list on every call. Before the sharing, one flags call
    # paid 16.2 find_components scans over the same list, and
    # this pin keeps that shape from returning while every other
    # test stays green.
    assert scans["public"] == 0
    assert scans["cores"] == 7
