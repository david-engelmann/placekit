"""Proof tests for MIGRATING.md, the googleplaces migration guide.

The guide is a promise, so the suite executes it. Every code block in
the guide that calls the client is run here in the same call shapes
against the offline stub, the fixture extension the guide reads is
asserted as typed values, the recorded live cassettes are decoded when
they are present beside the repo, and the boundary sentences are
pinned as text so a later edit cannot quietly soften them away.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from placekit import Client, types
from placekit.models import (
    AutocompleteResult,
    PhotoMedia,
    Place,
    TextSearchResult,
)

PHOTO_FIXTURE = Path(__file__).parent / "fixtures" / "photo.png"

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The live smoke cassettes live outside the repo, in the rounds
#: workspace beside it. A fresh clone has no such directory, and the
#: cassette test skips there so the suite stays green without them.
CASSETTES = (
    REPO_ROOT.parent / "placekit-rounds" / "live-smoke" / "2026-10-30"
)

SESSION_TOKEN = "guide-session-token"


@pytest.fixture()
def client(api_key, base_url) -> Client:
    return Client(api_key, base_url=base_url)


def _header(stub_server, name: str) -> str | None:
    headers = stub_server.last_request["headers"]
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def _flagship_search(client):
    """The Example 1 searches, in the guide block's call shapes."""
    result = client.text_search(
        "Fish and Chips",
        location_bias={
            "circle": {"center": (51.5074, -0.1278), "radius": 20000.0}
        },
        included_type=types.TYPE_RESTAURANT,
    )
    browse = client.nearby_search(
        (51.5074, -0.1278),
        20000.0,
        included_types=[types.TYPE_RESTAURANT],
    )
    return result, browse


def test_guide_example_1_text_search_and_upgrade(client):
    result, browse = _flagship_search(client)
    assert browse.places

    summary = result.places[0]
    assert summary.display_text == "Bianco Latte"
    assert isinstance(summary.location.latitude, float)
    assert isinstance(summary.location.longitude, float)
    assert summary.location.latitude == -33.866784
    assert summary.location.longitude == 151.20713
    assert summary.id == "ChIJrTLr-GyuEmsRBfy61i59si0"
    # The search mask never requested the details fields.
    assert summary.website_uri is None

    upgraded = client.place_details(summary)
    assert upgraded is not summary
    assert upgraded.website_uri == "https://example.com/"
    assert upgraded.national_phone_number == "(02) 5550 1234"
    assert upgraded.international_phone_number == "+61 2 5550 1234"
    assert upgraded.google_maps_uri == "https://maps.google.com/?cid=1234567890"
    assert upgraded.raw
    assert [a.provider for a in upgraded.attributions] == [
        "Example Maps Data"
    ]
    # The summary object never changes.
    assert summary.website_uri is None
    assert summary.national_phone_number is None


def test_guide_example_1_photo_flow(client, tmp_path):
    details = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert details.photos
    media = client.place_photo(
        details.photos[0], max_width_px=500, max_height_px=500
    )
    assert isinstance(media, PhotoMedia)
    assert media.content_type == "image/png"
    assert media.content == PHOTO_FIXTURE.read_bytes()
    saved = media.save(tmp_path / "photo.jpg")
    assert saved.read_bytes() == media.content


def test_guide_example_2_next_page(client, stub_server):
    result = client.text_search("Fish and Chips")
    assert result.next_page_token
    next_page = client.text_search(
        "Fish and Chips", page_token=result.next_page_token
    )
    assert next_page.places
    body = json.loads(stub_server.last_request["body"])
    assert body["pageToken"] == result.next_page_token


def test_guide_example_3_autocomplete_session(client, stub_server):
    result = client.autocomplete(
        "Hattie B's",
        included_primary_types=[types.TYPE_ESTABLISHMENT],
        included_region_codes=["US"],
        session_token=SESSION_TOKEN,
    )
    body = json.loads(stub_server.last_request["body"])
    assert body["sessionToken"] == SESSION_TOKEN
    recorded = stub_server.last_request

    # The shipped loop reads every prediction and makes no call, so
    # the request the stub last recorded is still the autocomplete
    # request when the loop is done.
    for prediction in result.place_predictions:
        assert prediction.text.text
        assert prediction.place_id
    assert stub_server.last_request == recorded

    prediction = result.place_predictions[0]
    assert prediction.text.text == (
        "Bianco Latte, George Street, Sydney NSW, Australia"
    )
    assert prediction.place_id == "ChIJrTLr-GyuEmsRBfy61i59si0"

    # The session closes with one details call on the one chosen
    # prediction, and that call is the only details request the
    # whole flow makes.
    details = client.place_details(prediction, session_token=SESSION_TOKEN)
    assert details.display_text == "Bianco Latte"
    assert stub_server.last_request["method"] == "GET"
    assert f"/places/{prediction.place_id}" in stub_server.last_request["path"]
    assert f"sessionToken={SESSION_TOKEN}" in stub_server.last_request["path"]


def test_guide_string_location_autocomplete_crossing(client, stub_server):
    # The String locations section, crossing 2, in the guide block's
    # call shapes. The crossing never leaves the shipped surface.
    result = client.autocomplete("Bianco Latte, George Street, Sydney")
    prediction = result.place_predictions[0]
    assert prediction.place_id == "ChIJrTLr-GyuEmsRBfy61i59si0"

    place = client.place_details(prediction, fields=["id", "location"])
    assert place.id == prediction.place_id
    assert place.location.latitude == -33.866784
    assert place.location.longitude == 151.20713
    assert f"/places/{prediction.place_id}" in stub_server.last_request["path"]
    # The narrow mask is the point of the crossing. It is what the
    # stub recorded on the details request, and it is what keeps
    # the call at the Essentials tier the guide prices. The id
    # rides beside location because the client refuses a details
    # response carrying neither an id nor a name.
    assert _header(stub_server, "X-Goog-FieldMask") == "id,location"
    # The mask asked for nothing else, so a field the default
    # details mask carries reads as not returned on the result.
    assert place.website_uri is None


def test_guide_string_location_text_search_crossing(client, stub_server):
    # The String locations section, crossing 3, in the guide block's
    # call shapes. One call, masked to the identifier and location.
    result = client.text_search(
        "Bianco Latte, George Street, Sydney",
        fields=["places.id", "places.location"],
    )
    place = result.places[0]
    assert place.id == "ChIJrTLr-GyuEmsRBfy61i59si0"
    assert place.location.latitude == -33.866784
    assert place.location.longitude == 151.20713
    assert (
        _header(stub_server, "X-Goog-FieldMask")
        == "places.id,places.location"
    )
    body = json.loads(stub_server.last_request["body"])
    assert body["textQuery"] == "Bianco Latte, George Street, Sydney"
    # The mask asked for nothing else, so a field the default
    # search mask carries reads as not returned on the result.
    assert place.rating is None


def test_guide_example_1_reads_reviews_and_icon_fields(client):
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert len(place.reviews) == 1
    review = place.reviews[0]
    assert review.rating == 5
    assert review.text.text.startswith("Best flat white in Sydney")
    assert review.author_attribution.display_name == "Sam Reviewer"
    assert place.icon_mask_base_uri == (
        "https://maps.gstatic.com/mapfiles/place_api/unauthenticated/"
        "icon_mask.png"
    )
    assert place.icon_background_color == "#8651DB"


def _cassette_body(name: str) -> dict:
    exchange = json.loads((CASSETTES / name).read_text())
    return exchange["response"]["body"]


def test_guide_examples_against_the_live_cassettes():
    if not CASSETTES.is_dir():
        pytest.skip("live smoke cassettes are not present beside the repo")

    search = TextSearchResult.from_api(_cassette_body("01_exchange.json"))
    assert len(search.places) == 20
    assert search.places[0].display_text == "Hole In The Wall"
    assert search.next_page_token

    details_body = _cassette_body("02_exchange.json")
    details = Place.from_api(details_body)
    assert len(details.photos) == 10
    assert details.website_uri == (
        "https://holeinthewallnyc.com/williamsburg-1"
    )
    # Cassette 02 carries no reviews key. Its field mask predates the
    # reviews modelling, so the guide makes no cassette claim for
    # reviews and the fixture test above carries that proof instead.
    assert "reviews" not in details_body

    autocomplete = AutocompleteResult.from_api(
        _cassette_body("04_exchange.json")
    )
    assert len(autocomplete.place_predictions) == 5
    assert autocomplete.place_predictions[0].text.text == (
        "Williamsburg Bridge, New York, NY, USA"
    )


def test_guide_file_exists_and_names_the_boundaries():
    guide = (REPO_ROOT / "MIGRATING.md").read_text()
    # Whitespace is normalised before the substring checks, so a
    # rewrap that changes no wording cannot fail these pins while
    # a wording softening still does.
    guide = " ".join(guide.split())
    for removal in (
        "Nearby search keyword and name filters",
        "Adding and deleting places",
        "Checkins",
        "Radar search",
    ):
        assert removal in guide
    assert "There is no compatibility facade" in guide
    # The flagship billing warning ships at full strength, because
    # softening it would reopen the cost trap the guide exists to
    # close.
    assert "the most expensive shape this API offers" in guide
