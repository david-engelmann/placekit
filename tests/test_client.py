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

from placekit import (
    AsyncClient,
    Client,
    FieldMask,
    PhotoUriResult,
)
from placekit.exceptions import (
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
    assert result.next_page_token == "Aen7H9k2QpXv4mZ8wRtYuIoP3sDfGhJkL6zXcVbNmQ9wErTyUiOpA2sDfGhJkL5zXcVbNmQ8wErTyUiOpA1sDfGhJkL4zXcVbNmQ7wErTy9"
    # The default mask now includes the resource name (finding A3).
    assert first.name == "places/ChIJrTLr-GyuEmsRBfy61i59si0"
    # searchUri is mask gated and not in the default mask.
    assert result.search_uri is None
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
    # Periods are typed (finding C3), with values independent of the
    # weekday description order (spec note N6).
    periods = place.opening_hours.periods
    assert len(periods) == 2
    assert periods[0].open is not None and periods[0].open.day == 3
    assert periods[0].open.hour == 7
    assert periods[0].close is not None and periods[0].close.hour == 15
    # Photo URI fields are typed (finding C5); photos are in the default
    # mask, so these hold on a default call.
    photo = place.photos[0]
    assert photo.flag_content_uri == "https://maps.example.com/flag/photo"
    assert photo.google_maps_uri == "https://maps.google.com/?cid=1234567890"
    # Structured address fields are typed (finding C4) but not in the
    # default mask, so they arrive only when requested, as here.
    assert place.attributions[0].provider == "Example Maps Data"
    # The default mask does not request editorialSummary, so an honest
    # stub cannot serve it on a default call (finding A2).
    assert "editorialSummary" not in place.raw


def test_place_details_typed_fields_with_explicit_mask(client):
    place = client.place_details(
        "ChIJrTLr-GyuEmsRBfy61i59si0",
        fields=[
            "id",
            "addressComponents",
            "plusCode",
            "viewport",
            "primaryTypeDisplayName",
            "currentOpeningHours",
        ],
    )
    assert place.address_components[1].long_text == "George Street"
    assert place.plus_code is not None
    assert place.plus_code.global_code == "4RRH46J5+QJ"
    assert place.viewport is not None
    assert place.viewport.low.latitude == pytest.approx(-33.868)
    assert place.primary_type_display_name is not None
    assert place.primary_type_display_name.text == "Cafe"
    assert place.current_opening_hours is not None
    assert place.current_opening_hours.open_now is True


def test_place_details_editorial_summary_needs_explicit_field(client):
    # The earlier form of this assertion ran against a stub that ignored
    # the field mask, asserting behaviour the real API cannot produce on
    # a default call (finding A2). The field arrives only when requested.
    place = client.place_details(
        "ChIJrTLr-GyuEmsRBfy61i59si0", fields=["id", "editorialSummary"]
    )
    assert place.raw["editorialSummary"]["text"].startswith("A bright corner cafe")
    # And fields outside the explicit mask stay absent.
    assert place.national_phone_number is None


def test_autocomplete_sync(client):
    result = client.autocomplete("Bianco")
    predictions = result.place_predictions
    assert len(predictions) == 2
    first = predictions[0]
    assert first.place_id == "ChIJrTLr-GyuEmsRBfy61i59si0"
    assert first.place == "places/ChIJrTLr-GyuEmsRBfy61i59si0"
    assert first.text is not None and first.text.text.startswith("Bianco Latte,")
    assert first.main_text is not None and first.main_text.text == "Bianco Latte"
    # No origin was sent, so the API returns no distance. The earlier
    # form of this test asserted 1250 against a stub that invented the
    # value, which the real API can never do (finding A4).
    assert first.distance_meters is None


def test_autocomplete_origin_enables_distance(client, stub_server):
    result = client.autocomplete(
        "Bianco", origin=(-33.8668, 151.2071), input_offset=6
    )
    first = result.place_predictions[0]
    assert first.distance_meters == 1250
    body = json.loads(stub_server.last_request["body"])
    assert body["origin"]["latitude"] == pytest.approx(-33.8668)
    assert body["inputOffset"] == 6


def test_autocomplete_primary_types_and_mask(client, stub_server):
    client.autocomplete(
        "Bianco",
        fields=["suggestions.placePrediction.placeId"],
        included_primary_types=["cafe"],
    )
    assert (
        header(stub_server, "X-Goog-FieldMask")
        == "suggestions.placePrediction.placeId"
    )
    body = json.loads(stub_server.last_request["body"])
    assert body["includedPrimaryTypes"] == ["cafe"]


def test_place_photo_sync(client):
    # The stub answers the media request with a redirect to its image
    # route (finding A7), so these bytes travelled over the redirect,
    # not straight from the requested URL.
    photo = client.place_photo(
        "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
        max_width_px=400,
    )
    assert photo.content_type == "image/png"
    assert photo.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(photo.content) > 1024
    assert photo.content == PHOTO_FIXTURE.read_bytes()


def test_place_photo_skip_redirect_returns_uri(client, stub_server, base_url):
    result = client.place_photo(
        "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
        max_width_px=400,
        skip_http_redirect=True,
    )
    assert isinstance(result, PhotoUriResult)
    assert result.name == "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample"
    assert result.photo_uri.startswith("http://")
    assert result.photo_uri.endswith("/photo-image")
    assert "skipHttpRedirect=true" in stub_server.last_request["path"]


def test_text_search_new_parameters_on_the_wire(client, stub_server):
    client.text_search(
        "cafes",
        page_size=5,
        min_rating=4.0,
        ev_options={"minimumChargingRateKw": 50.0},
        routing_parameters={"origin": (-33.86, 151.2), "travelMode": "DRIVE"},
        include_future_opening_businesses=True,
    )
    body = json.loads(stub_server.last_request["body"])
    assert body["pageSize"] == 5
    assert body["minRating"] == pytest.approx(4.0)
    assert body["evOptions"]["minimumChargingRateKw"] == pytest.approx(50.0)
    assert body["routingParameters"]["origin"]["latitude"] == pytest.approx(-33.86)
    assert body["includeFutureOpeningBusinesses"] is True


def test_text_search_top_level_fields_survive(client):
    # searchUri and routingSummaries are served only when masked (B5);
    # they must reach the result instead of being dropped in the Rust
    # reserialization layer (finding C1).
    result = client.text_search(
        "cafes", fields=["places.id", "searchUri", "routingSummaries"]
    )
    assert result.search_uri == "https://maps.google.com/?q=cafes+in+Sydney"
    assert len(result.routing_summaries) == 1
    assert result.routing_summaries[0]["legs"][0]["distanceMeters"] == 5587
    assert result.raw["searchUri"] == result.search_uri
    # Places outside the mask stay out.
    assert result.places[0].display_text is None


def test_min_rating_out_of_range_rejected(client):
    with pytest.raises(ConfigError):
        client.text_search("cafes", min_rating=5.5)


def test_location_bias_and_restriction_are_exclusive(client):
    with pytest.raises(ConfigError):
        client.text_search(
            "cafes",
            location_bias={"circle": {"center": (-33.86, 151.2), "radius": 100.0}},
            location_restriction={
                "rectangle": {"low": (-33.87, 151.2), "high": (-33.86, 151.21)}
            },
        )


def test_text_search_circle_restriction_rejected(client):
    # Text Search restrictions are rectangle only (finding F11); the
    # typed Rust request refuses a circle before anything is sent.
    with pytest.raises(ValueError):
        client.text_search(
            "cafes",
            location_restriction={
                "circle": {"center": (-33.86, 151.2), "radius": 100.0}
            },
        )


def test_nearby_primary_types_on_the_wire(client, stub_server):
    client.nearby_search(
        (-33.8668, 151.2071),
        800.0,
        included_primary_types=["cafe"],
        excluded_primary_types=["bar"],
    )
    body = json.loads(stub_server.last_request["body"])
    assert body["includedPrimaryTypes"] == ["cafe"]
    assert body["excludedPrimaryTypes"] == ["bar"]


def test_nearby_max_results_range_rejected(client):
    with pytest.raises(ConfigError):
        client.nearby_search((-33.8668, 151.2071), 800.0, max_results=21)


def test_session_token_format_validated(client):
    with pytest.raises(ConfigError):
        client.autocomplete("Bianco", session_token="not a token!")
    with pytest.raises(ConfigError):
        client.place_details(
            "ChIJrTLr-GyuEmsRBfy61i59si0", session_token="x" * 40
        )


# ---------------------------------------------------------------------------
# Error mapping, sync
# ---------------------------------------------------------------------------


def test_error_invalid_request(client):
    with pytest.raises(InvalidRequestError) as excinfo:
        client.text_search("TRIGGER_INVALID")
    assert excinfo.value.status_code == 400
    assert excinfo.value.google_status == "INVALID_ARGUMENT"
    # Envelope details are parsed and carried (finding C6); the field
    # name is the wire form textQuery (finding A1).
    assert excinfo.value.error_code == 400
    assert excinfo.value.field_violations == [
        {
            "field": "textQuery",
            "description": "Request contains an invalid argument.",
        }
    ]


def test_error_rate_limit(client):
    with pytest.raises(RateLimitError) as excinfo:
        client.text_search("TRIGGER_QUOTA")
    assert excinfo.value.status_code == 429
    assert excinfo.value.google_status == "RESOURCE_EXHAUSTED"
    violations = excinfo.value.quota_violations
    assert len(violations) == 1
    assert violations[0]["quotaMetric"] == "places.googleapis.com/default"
    assert violations[0]["quotaValue"] == "1000"


def test_error_unauthenticated(client):
    with pytest.raises(AuthenticationError) as excinfo:
        client.place_details("unauthenticated-place")
    assert excinfo.value.status_code == 401
    assert excinfo.value.google_status == "UNAUTHENTICATED"


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
        assert suggestions.place_predictions[0].distance_meters is None
        with_origin = await client.autocomplete(
            "Bianco", origin=(-33.8668, 151.2071)
        )
        assert with_origin.place_predictions[0].distance_meters == 1250
        photo = await client.place_photo(
            "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
            max_height_px=200,
        )
        assert photo.content[:4] == b"\x89PNG"
        uri_result = await client.place_photo(
            "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
            max_height_px=200,
            skip_http_redirect=True,
        )
        assert isinstance(uri_result, PhotoUriResult)
        with pytest.raises(RateLimitError):
            await client.text_search("TRIGGER_QUOTA")
        with pytest.raises(NotFoundError):
            await client.place_details("missing-place")

    asyncio.run(run())
