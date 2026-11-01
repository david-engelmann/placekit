"""Tests for the synthesized corpus fixtures.

Synthesized fixtures are authored shapes for cases no recording
exists for, and they are marked three ways at once. They live in
their own folder, their bytes carry an envelope naming their origin,
and every test in this module carries the word synthesized in its
name. The loader here refuses anything that blurs the line, and the
refusals are pinned with temporary copies so the guard cannot rot.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from placekit import Client

FIXTURES = Path(__file__).parent / "fixtures"
SYNTHESIZED = FIXTURES / "synthesized"
RECORDED = FIXTURES / "recorded"


@pytest.fixture()
def client(api_key, base_url) -> Client:
    return Client(api_key, base_url=base_url)


class EnvelopeError(ValueError):
    """A fixture file does not carry a well formed synthesized envelope."""


def load_synthesized(path: Path):
    """Load one synthesized fixture and return its payload member.

    Refuses a bare body, a malformed envelope, an origin other than
    synthesized, a missing payload, and a mark whose case disagrees
    with the case token in the file name.
    """
    data = json.loads(path.read_bytes())
    if not isinstance(data, dict) or set(data) != {"fixtureMark", "payload"}:
        raise EnvelopeError(f"{path.name} is not a synthesized envelope")
    mark = data["fixtureMark"]
    if not isinstance(mark, dict) or mark.get("origin") != "synthesized":
        raise EnvelopeError(f"{path.name} does not claim synthesized origin")
    case_token = path.name.split("_")[1]
    if mark.get("case") != case_token:
        raise EnvelopeError(
            f"{path.name} mark names case {mark.get('case')}, not {case_token}"
        )
    payload = data["payload"]
    if not isinstance(payload, dict):
        raise EnvelopeError(f"{path.name} payload is not an object")
    return payload


def load_recorded_payload(path: Path):
    """Load one recorded fixture, refusing any envelope found there."""
    data = json.loads(path.read_bytes())
    if isinstance(data, dict) and "fixtureMark" in data:
        raise EnvelopeError(f"{path.name} carries an envelope in the recorded folder")
    return data


def replay_details(client, raw_response, payload, place_id):
    raw_response(200, json.dumps(payload).encode())
    return client.place_details(place_id)


def test_synthesized_p6_moved_place_decodes(client, raw_response):
    payload = load_synthesized(SYNTHESIZED / "synthesized_P6_moved_place.json")
    place = replay_details(client, raw_response, payload, "ChIJExampleMovedPlace00001")
    assert place.moved_place == "places/ChIJExampleMovedPlace00002"
    assert place.moved_place_id == "ChIJExampleMovedPlace00002"
    assert place.raw["movedPlace"] == "places/ChIJExampleMovedPlace00002"
    assert place.raw["movedPlaceId"] == "ChIJExampleMovedPlace00002"


def test_synthesized_p13_consumer_alert_decodes(client, raw_response):
    payload = load_synthesized(SYNTHESIZED / "synthesized_P13_consumer_alert.json")
    place = replay_details(client, raw_response, payload, "ChIJExampleAlertPlace00001")
    alert = place.consumer_alert
    assert alert is not None
    assert alert.overview == "Example consumer alert overview for a fictional place."
    assert alert.language_code == "en"
    # The nested detail blocks ride in raw, matching how the model
    # treats that group.
    assert alert.raw["details"][0]["title"] == "Example alert detail"


def test_synthesized_v6_single_point_viewport_decodes(client, raw_response):
    payload = load_synthesized(SYNTHESIZED / "synthesized_V6_single_point_viewport.json")
    place = replay_details(client, raw_response, payload, "ChIJExampleViewportPlace01")
    assert place.viewport is not None
    assert place.viewport.low == place.viewport.high
    assert place.viewport.low.latitude == 51.5007
    assert place.viewport.low.longitude == -0.1246
    assert place.raw["viewport"]["low"] == place.raw["viewport"]["high"]


def test_synthesized_a11_component_present_but_empty_decodes(client, raw_response):
    payload = load_synthesized(
        SYNTHESIZED / "synthesized_A11_component_present_but_empty.json"
    )
    raw_response(200, json.dumps(payload).encode())
    result = client.text_search("corpus replay")
    empty_text, empty_list = result.places
    assert empty_text.id == "ChIJExampleEmptyText000001"
    component = empty_text.address_components[0]
    assert component.long_text == ""
    assert component.short_text == ""
    assert component.types == ["route"]
    assert empty_list.id == "ChIJExampleEmptyList000001"
    assert empty_list.address_components == []
    # Present but empty is the shape, and raw membership proves the
    # key was carried rather than omitted.
    assert "addressComponents" in empty_list.raw
    assert empty_list.raw["addressComponents"] == []
    assert empty_list.formatted_address == "Example Lane, Example Town"


# ---------------------------------------------------------------------------
# The marking guards, pinned so they cannot rot
# ---------------------------------------------------------------------------


def test_synthesized_loader_refuses_a_bare_body(tmp_path):
    source = SYNTHESIZED / "synthesized_P6_moved_place.json"
    payload = load_synthesized(source)
    bare = tmp_path / "synthesized_P6_moved_place.json"
    bare.write_bytes(json.dumps(payload).encode())
    with pytest.raises(EnvelopeError):
        load_synthesized(bare)


def test_synthesized_loader_refuses_an_envelope_in_the_recorded_folder(tmp_path):
    target = tmp_path / "recorded_P6_moved_place.json"
    shutil.copy(SYNTHESIZED / "synthesized_P6_moved_place.json", target)
    with pytest.raises(EnvelopeError):
        load_recorded_payload(target)


def test_synthesized_loader_accepts_every_recorded_fixture():
    # The recorded loader half of the guard. Every shipped recorded
    # fixture is a bare body and loads without refusal.
    for path in sorted(RECORDED.glob("*.json")):
        payload = load_recorded_payload(path)
        assert isinstance(payload, dict)


def test_synthesized_loader_refuses_a_missing_payload(tmp_path):
    mark = {
        "fixtureMark": {
            "origin": "synthesized",
            "case": "P6",
            "basis": "example",
            "statement": "example",
        }
    }
    target = tmp_path / "synthesized_P6_moved_place.json"
    target.write_bytes(json.dumps(mark).encode())
    with pytest.raises(EnvelopeError):
        load_synthesized(target)


def test_synthesized_loader_refuses_a_wrong_origin(tmp_path):
    data = json.loads((SYNTHESIZED / "synthesized_P6_moved_place.json").read_bytes())
    data["fixtureMark"]["origin"] = "recorded"
    target = tmp_path / "synthesized_P6_moved_place.json"
    target.write_bytes(json.dumps(data).encode())
    with pytest.raises(EnvelopeError):
        load_synthesized(target)


def test_synthesized_loader_refuses_a_case_mismatch(tmp_path):
    data = json.loads((SYNTHESIZED / "synthesized_P6_moved_place.json").read_bytes())
    target = tmp_path / "synthesized_P13_consumer_alert.json"
    target.write_bytes(json.dumps(data).encode())
    with pytest.raises(EnvelopeError):
        load_synthesized(target)
