"""End-to-end tests of the Python API against the local stub server.

No network and no Google API key are involved. Every test asserts on typed
model values, recorded request headers/bodies, or translated exceptions, so
each one fails if the behavior it covers breaks.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

PHOTO_FIXTURE = Path(__file__).parent / "fixtures" / "photo.png"

from places_api import (
    AsyncClient,
    Client,
    FieldMask,
)
from places_api.exceptions import (
    AuthenticationError,
    ConfigError,
    InvalidRequestError,
    NotFoundError,
    RateLimitError,
)


@pytest.fixture()
def client(api_key, base_url) -> Client:
    return Client(api_key, base_url=base_url)


def header(stub_server, name: str) -> str | None:
    headers = stub_server.last_request["headers"]
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


# ---------------------------------------------------------------------------
# Happy paths, sync
# ---------------------------------------------------------------------------


def test_text_search_sync(client, stub_server):
    result = client.text_search("cafes in Sydney")
    assert len(result.places) == 2
    first = result.places[0]
    assert first.id == "ChIJrTLr-GyuEmsRBfy61i59si0"
    assert first.display_text == "Bianco Latte"
    assert first.rating == pytest.approx(4.6)
    assert first.user_rating_count == 1284
    assert first.location is not None
    assert first.location.latitude == pytest.approx(-33.866784)
    assert result.next_page_token == "token-abc-123"
    # Protocol assertions on what actually went over the wire.
    assert header(stub_server, "X-Goog-Api-Key") == "test-api-key"
    mask = header(stub_server, "X-Goog-FieldMask")
    assert mask is not None and "places.displayName" in mask
    assert "nextPageToken" in mask


def test_text_search_custom_fields(client, stub_server):
    client.text_search("cafes", fields=["places.id", "places.rating"])
    assert header(stub_server, "X-Goog-FieldMask") == "places.id,places.rating"


def test_text_search_fieldmask_object(client, stub_server):
    result = client.text_search("cafes", fields=FieldMask("places.displayName"))
    assert header(stub_server, "X-Goog-FieldMask") == "places.displayName"
    assert len(result.places) == 2


def test_text_search_pagination_token_sent(client, stub_server):
    client.text_search("cafes", page_token="token-abc-123")
    body = json.loads(stub_server.last_request["body"])
    assert body["pageToken"] == "token-abc-123"
    assert body["textQuery"] == "cafes"


def test_nearby_search_sync(client, stub_server):
    result = client.nearby_search((-33.8668, 151.2071), 800.0, included_types=["cafe"])
    assert len(result.places) == 1
    assert result.places[0].primary_type == "cafe"
    mask = header(stub_server, "X-Goog-FieldMask")
    assert mask is not None and "nextPageToken" not in mask
    body = json.loads(stub_server.last_request["body"])
    circle = body["locationRestriction"]["circle"]
    assert circle["center"]["latitude"] == pytest.approx(-33.8668)
    assert circle["radius"] == pytest.approx(800.0)
    assert body["includedTypes"] == ["cafe"]


def test_place_details_sync(client):
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert place.display_text == "Bianco Latte"
    assert place.national_phone_number == "(02) 5550 1234"
    assert place.website_uri == "https://example.com/"
    assert place.opening_hours is not None
    assert place.opening_hours.open_now is True
    assert len(place.opening_hours.weekday_descriptions) == 7
    assert place.attributions[0].provider == "Example Maps Data"
    # Unmodeled fields survive on the raw payload.
    assert place.raw["editorialSummary"]["text"].startswith("A bright corner cafe")


def test_autocomplete_sync(client):
    result = client.autocomplete("Bianco")
    predictions = result.place_predictions
    assert len(predictions) == 2
    first = predictions[0]
    assert first.place_id == "ChIJrTLr-GyuEmsRBfy61i59si0"
    assert first.text is not None and first.text.text.startswith("Bianco Latte,")
    assert first.main_text is not None and first.main_text.text == "Bianco Latte"
    assert first.distance_meters == 1250


def test_place_photo_sync(client):
    photo = client.place_photo(
        "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
        max_width_px=400,
    )
    assert photo.content_type == "image/png"
    assert photo.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert photo.content == PHOTO_FIXTURE.read_bytes()


# ---------------------------------------------------------------------------
# Error mapping, sync
# ---------------------------------------------------------------------------


def test_error_invalid_request(client):
    with pytest.raises(InvalidRequestError) as excinfo:
        client.text_search("TRIGGER_INVALID")
    assert excinfo.value.status_code == 400
    assert excinfo.value.google_status == "INVALID_ARGUMENT"


def test_error_rate_limit(client):
    with pytest.raises(RateLimitError) as excinfo:
        client.text_search("TRIGGER_QUOTA")
    assert excinfo.value.status_code == 429
    assert excinfo.value.google_status == "RESOURCE_EXHAUSTED"


def test_error_not_found(client):
    with pytest.raises(NotFoundError) as excinfo:
        client.place_details("missing-place")
    assert excinfo.value.status_code == 404


def test_error_authentication(client):
    with pytest.raises(AuthenticationError) as excinfo:
        client.place_details("denied-place")
    assert excinfo.value.status_code == 403
    assert excinfo.value.google_status == "PERMISSION_DENIED"


def test_photo_requires_dimensions(client):
    # Detected client-side, before any request is sent.
    with pytest.raises(ConfigError):
        client.place_photo("places/ChIJ/photos/ATJ83zh8vExample")


def test_photo_rejects_out_of_range_size(client):
    with pytest.raises(ConfigError):
        client.place_photo("places/ChIJ/photos/ATJ83zh8vExample", max_width_px=4801)


def test_photo_rejects_bad_name(client):
    with pytest.raises(ConfigError):
        client.place_photo("not-a-photo-name", max_width_px=100)


def test_empty_api_key_rejected(base_url):
    with pytest.raises(ValueError):
        Client("", base_url=base_url)


def test_invalid_field_mask_rejected():
    with pytest.raises(ValueError):
        FieldMask("places.id, places.rating")
    with pytest.raises(ValueError):
        FieldMask()


# ---------------------------------------------------------------------------
# Async parity
# ---------------------------------------------------------------------------


def test_async_client_matches_sync(api_key, base_url):
    async def run():
        client = AsyncClient(api_key, base_url=base_url)
        result = await client.text_search("cafes in Sydney")
        assert len(result.places) == 2
        assert result.places[0].display_text == "Bianco Latte"
        place = await client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
        assert place.national_phone_number == "(02) 5550 1234"
        nearby = await client.nearby_search((-33.8668, 151.2071), 500.0)
        assert len(nearby.places) == 1
        suggestions = await client.autocomplete("Bianco")
        assert suggestions.place_predictions[0].place_id.startswith("ChIJ")
        photo = await client.place_photo(
            "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
            max_height_px=200,
        )
        assert photo.content[:4] == b"\x89PNG"
        with pytest.raises(RateLimitError):
            await client.text_search("TRIGGER_QUOTA")
        with pytest.raises(NotFoundError):
            await client.place_details("missing-place")

    asyncio.run(run())
