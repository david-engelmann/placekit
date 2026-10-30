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
    ApiError,
    AuthenticationError,
    ConfigError,
    DecodeError,
    InvalidRequestError,
    NetworkError,
    NotFoundError,
    PlacesError,
    RateLimitError,
)
from placekit.models import Place, TextSearchResult


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
            "postalAddress",
            "adrFormatAddress",
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
    # Postal address and the adr microformat address are typed too
    # (finding C4); both are outside the default mask, as here.
    assert place.postal_address is not None
    assert place.postal_address.region_code == "AU"
    assert place.postal_address.postal_code == "2000"
    assert place.postal_address.administrative_area == "New South Wales"
    assert place.postal_address.locality == "Sydney"
    assert place.postal_address.address_lines == ["Shop 1/123 George St"]
    assert place.adr_format_address is not None
    assert "Shop 1/123 George St" in place.adr_format_address
    assert 'class="postal-code">2000<' in place.adr_format_address


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
    # The stub computes the distance from the origin to the fixture
    # place at (-33.866784, 151.20713) with the haversine formula; this
    # origin sits about 3 meters from it. A constant stand-in value
    # would give the same number for every origin (red team finding A4).
    assert first.distance_meters == 3
    body = json.loads(stub_server.last_request["body"])
    assert body["origin"]["latitude"] == pytest.approx(-33.8668)
    assert body["inputOffset"] == 6
    # The same input from New York gives the computed trans-Pacific
    # distance, proving the value follows the origin.
    far = client.autocomplete("Bianco", origin=(40.7128, -74.0060))
    assert far.place_predictions[0].distance_meters == 15988845


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


def test_text_search_contextual_contents_survive(client):
    # contextualContents is not typed in Python; it must still reach
    # the caller through the catch-all into raw when masked (finding
    # C1). The fixture carries the documented shape so the shipped
    # suite regress-tests this half of C1.
    result = client.text_search(
        "cafes", fields=["places.id", "contextualContents"]
    )
    assert result.raw["contextualContents"] == [
        {
            "justifications": [
                {
                    "reviewJustification": {
                        "highlightedText": "known for single-origin espresso"
                    }
                }
            ]
        }
    ]


def test_masked_raw_carries_no_fabricated_keys(client):
    # A response masked down to places.id must come back with no keys
    # beyond what the wire carried. Absent typed fields stay absent
    # instead of appearing with null or empty values (finding N1).
    result = client.text_search("cafes", fields=["places.id"])
    assert result.places[0].raw == {"id": "ChIJrTLr-GyuEmsRBfy61i59si0"}
    # Autocomplete without an origin: no distanceMeters key at all,
    # not a null one.
    suggestions = client.autocomplete("Bianco")
    prediction = suggestions.place_predictions[0]
    assert "distanceMeters" not in prediction.raw
    # Place Details on the default mask: since Round 5 the default
    # mask requests every modelled field (RC-07), so these keys are
    # present in raw; under an explicit narrow mask they stay absent,
    # which is the no-fabrication principle this test guards.
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    for present in (
        "postalAddress",
        "adrFormatAddress",
        "plusCode",
        "viewport",
        "currentOpeningHours",
        "primaryTypeDisplayName",
    ):
        assert present in place.raw
    narrow = client.place_details(
        "ChIJrTLr-GyuEmsRBfy61i59si0", fields=["id"]
    )
    assert narrow.raw == {"id": "ChIJrTLr-GyuEmsRBfy61i59si0"}


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
    # typed Rust request refuses a circle before anything is sent, and
    # the failure surfaces as ConfigError like the other local
    # validations, not as a bare ValueError (finding S2).
    with pytest.raises(ConfigError):
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
    assert excinfo.value.details
    assert excinfo.value.details[0]["fieldViolations"][0]["field"] == "textQuery"
    assert excinfo.value.context == "text_search"
    assert excinfo.value.retryable is False


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
    # ConfigError specifically, not just any ValueError: it subclasses
    # ValueError, so the old assertion could not tell the documented
    # type from a bare one escaping the hierarchy.
    with pytest.raises(ConfigError):
        Client("", base_url=base_url)


def test_invalid_field_mask_rejected():
    with pytest.raises(ConfigError):
        FieldMask("places.id, places.rating")
    with pytest.raises(ConfigError):
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
        # Computed by the stub from that origin to the fixture place,
        # about 3 meters away.
        assert with_origin.place_predictions[0].distance_meters == 3
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


# ---------------------------------------------------------------------------
# Round 2 (T4) regressions: error envelopes, hostile inputs, attributes
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def envelope(code: int, status: str, message: str = "boom") -> bytes:
    return json.dumps(
        {"error": {"code": code, "message": message, "status": status}}
    ).encode()


def test_error_envelope_on_200_text_search_raises(client, raw_response):
    # The round's worst case: a PERMISSION_DENIED envelope on HTTP 200
    # used to come back as a successful empty result.
    raw_response(200, fixture_bytes("error_denied.json"))
    with pytest.raises(AuthenticationError) as excinfo:
        client.text_search("cafes in Sydney")
    assert excinfo.value.status_code == 200
    assert excinfo.value.google_status == "PERMISSION_DENIED"
    assert "has not been used" in excinfo.value.message


def test_error_envelope_on_200_details_and_autocomplete_raise(client, raw_response):
    raw_response(200, fixture_bytes("error_denied.json"))
    with pytest.raises(AuthenticationError) as excinfo:
        client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert excinfo.value.status_code == 200
    with pytest.raises(AuthenticationError):
        client.autocomplete("Bianco")


def test_error_envelope_on_200_nearby_search_raises(client, raw_response):
    raw_response(200, fixture_bytes("error_denied.json"))
    with pytest.raises(AuthenticationError) as excinfo:
        client.nearby_search((-33.8668, 151.2071), 800.0)
    assert excinfo.value.status_code == 200
    assert excinfo.value.google_status == "PERMISSION_DENIED"
    assert "has not been used" in excinfo.value.message


def test_error_envelope_on_200_without_status_maps_by_code(
    client, raw_response
):
    # The red team's exact case: an envelope carrying a code and a
    # message but no status field used to decode as a successful
    # empty result. It raises now, classified by the numeric code.
    raw_response(
        200, b'{"error": {"code": 403, "message": "denied but no status field"}}'
    )
    with pytest.raises(AuthenticationError) as excinfo:
        client.text_search("cafes")
    assert excinfo.value.status_code == 200
    assert excinfo.value.google_status is None
    assert excinfo.value.error_code == 403
    assert "denied but no status field" in excinfo.value.message
    with pytest.raises(AuthenticationError) as excinfo:
        client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert excinfo.value.status_code == 200
    assert excinfo.value.google_status is None
    assert "denied but no status field" in excinfo.value.message


def test_error_envelope_on_200_photo_raises(client, raw_response):
    # Served with an image content type so only the envelope check can
    # catch it; the envelope JSON used to be returned as image bytes.
    raw_response(200, fixture_bytes("error_denied.json"), "image/png")
    with pytest.raises(AuthenticationError) as excinfo:
        client.place_photo(
            "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
            max_width_px=400,
        )
    assert excinfo.value.status_code == 200
    assert excinfo.value.google_status == "PERMISSION_DENIED"


def test_error_envelope_on_200_photo_json_content_type_raises(
    client, raw_response
):
    # Real Google errors carry application/json. On the photo bytes
    # path that content type used to short-circuit into a DecodeError
    # about a non-image body, dropping the envelope's status and
    # message; the envelope now maps like on every other endpoint.
    raw_response(200, fixture_bytes("error_denied.json"))
    with pytest.raises(AuthenticationError) as excinfo:
        client.place_photo(
            "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
            max_width_px=400,
        )
    assert excinfo.value.status_code == 200
    assert excinfo.value.google_status == "PERMISSION_DENIED"
    assert "has not been used" in excinfo.value.message


def test_error_envelope_on_200_photo_skip_redirect_raises(client, raw_response):
    raw_response(200, fixture_bytes("error_denied.json"))
    with pytest.raises(AuthenticationError):
        client.place_photo(
            "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
            max_width_px=400,
            skip_http_redirect=True,
        )


def test_photo_non_image_content_type_is_decode_error(client, raw_response):
    raw_response(200, b"<html><body>not an image</body></html>", "text/html")
    with pytest.raises(DecodeError) as excinfo:
        client.place_photo(
            "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
            max_width_px=400,
        )
    assert excinfo.value.status_code == 200
    assert "text/html" in excinfo.value.message


def test_photo_body_must_match_declared_image_type(client, raw_response):
    # A one byte body and a truncated signature both claim image/png.
    for body in (b"\x00", b"\x89PNG"):
        raw_response(200, body, "image/png")
        with pytest.raises(DecodeError) as excinfo:
            client.place_photo(
                "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
                max_width_px=400,
            )
        assert "content type" in excinfo.value.message


def test_photo_redirect_loop_is_network_error_with_cause(client):
    with pytest.raises(NetworkError) as excinfo:
        client.place_photo("places/ChIJ/photos/loop-photo", max_width_px=100)
    assert "redirect:" in str(excinfo.value)


def test_mid_body_drop_keeps_status_and_read_failure(client):
    with pytest.raises(ApiError) as excinfo:
        client.place_details("drop-place")
    assert excinfo.value.status_code == 500
    assert excinfo.value.google_status is None
    assert "error body unreadable" in excinfo.value.message


def test_gzipped_details_decode(client):
    place = client.place_details("gzip-place")
    assert place.display_text == "Bianco Latte"


def test_quota_error_carries_retry_after(client):
    with pytest.raises(RateLimitError) as excinfo:
        client.text_search("TRIGGER_QUOTA")
    assert excinfo.value.retryable is True
    assert excinfo.value.retry_after == 7
    assert excinfo.value.status_mismatch is False


def test_envelope_http_disagreement_is_flagged(client, raw_response):
    # Repro case 4b: RESOURCE_EXHAUSTED on HTTP 500, envelope code 429.
    raw_response(500, envelope(429, "RESOURCE_EXHAUSTED", "check quota"))
    with pytest.raises(RateLimitError) as excinfo:
        client.text_search("cafes")
    assert excinfo.value.status_code == 500
    assert excinfo.value.error_code == 429
    assert excinfo.value.status_mismatch is True
    assert excinfo.value.retryable is True


def test_server_side_status_on_client_http_code_is_api_error(client, raw_response):
    raw_response(400, envelope(400, "DEADLINE_EXCEEDED", "too slow"))
    with pytest.raises(ApiError) as excinfo:
        client.text_search("cafes")
    assert type(excinfo.value) is ApiError
    assert excinfo.value.google_status == "DEADLINE_EXCEEDED"
    assert excinfo.value.retryable is True


def test_non_json_error_body_has_no_google_status(client, raw_response):
    # Repro case 6, fixed: google_status is None, not an empty string.
    raw_response(500, "Internal Server Error: upstream exploded", "text/plain")
    with pytest.raises(ApiError) as excinfo:
        client.text_search("cafes")
    assert excinfo.value.status_code == 500
    assert excinfo.value.google_status is None
    assert "upstream exploded" in excinfo.value.message


def test_long_non_envelope_body_truncation_is_marked(client, raw_response):
    raw_response(503, "y" * 600, "text/html")
    with pytest.raises(ApiError) as excinfo:
        client.text_search("cafes")
    assert "[truncated, 600 bytes, text/html]" in excinfo.value.message


def test_envelope_message_is_capped(client, raw_response):
    raw_response(400, envelope(400, "INVALID_ARGUMENT", "x" * 5000))
    with pytest.raises(InvalidRequestError) as excinfo:
        client.text_search("cafes")
    # The stored envelope message is capped at 500 characters (the
    # exception text adds the class prefix on top of it).
    assert "x" * 500 in excinfo.value.message
    assert "x" * 501 not in excinfo.value.message


def test_malformed_success_body_decode_error_has_status(client, raw_response):
    # Repro case 1: truncated JSON on a 200.
    raw_response(200, b'{"places": [{"id": "ChIJ1", "displayName": {"text": "Cut')
    with pytest.raises(DecodeError) as excinfo:
        client.text_search("cafes")
    assert excinfo.value.status_code == 200
    assert excinfo.value.google_status is None


def test_details_empty_object_is_decode_error_but_search_is_not(
    client, raw_response
):
    # Deliberate asymmetry: Place Details always has an identity, so
    # an empty object there is a wrong shape; an empty search object
    # is indistinguishable from a genuine empty result and stays one.
    raw_response(200, b"{}")
    with pytest.raises(DecodeError) as excinfo:
        client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert "no id or name" in excinfo.value.message
    assert excinfo.value.status_code == 200
    result = client.text_search("cafes")
    assert result.places == []


def test_oversized_response_is_decode_error_naming_the_cap(client, raw_response):
    big = json.dumps({"places": [], "blob": "x" * (33 * 1024 * 1024)}).encode()
    raw_response(200, big)
    with pytest.raises(DecodeError) as excinfo:
        client.text_search("cafes")
    assert excinfo.value.status_code == 200
    assert "maximum" in excinfo.value.message


def test_network_error_names_the_transport_cause(api_key):
    dead = Client(api_key, base_url="http://127.0.0.1:9/v1", timeout=2.0)
    with pytest.raises(NetworkError) as excinfo:
        dead.text_search("cafes")
    assert str(excinfo.value).startswith("network error: connect:")


def test_error_context_names_the_call(client, raw_response):
    with pytest.raises(NotFoundError) as excinfo:
        client.place_details("missing-place")
    assert excinfo.value.context == "place_details place_id=missing-place"
    raw_response(404, fixture_bytes("error_not_found.json"))
    with pytest.raises(NotFoundError) as excinfo:
        client.place_photo("places/ChIJ/photos/ATJ83zh8vExample", max_width_px=10)
    assert (
        excinfo.value.context
        == "place_photo name=places/ChIJ/photos/ATJ83zh8vExample"
    )


def test_place_id_url_hostile_values_rejected(client):
    for hostile in ("ChIJ?sessionToken=evil", "..", "ChIJ#frag", "ChIJ%2e"):
        with pytest.raises(ConfigError):
            client.place_details(hostile)


def test_photo_name_traversal_and_forgery_rejected(client):
    for hostile in (
        "places/ChIJ/photos/../../../../etc/passwd",
        "places/ChIJ/photos/ref?key=forged",
        "places/ChIJ/photos/ref/extra",
        "places//photos/ref",
    ):
        with pytest.raises(ConfigError):
            client.place_photo(hostile, max_width_px=100)


@pytest.mark.parametrize(
    "bad_timeout",
    [float("nan"), float("inf"), float("-inf"), 0, -1, True, "5", 3601],
)
def test_timeout_must_be_positive_finite_and_bounded(api_key, base_url, bad_timeout):
    with pytest.raises(ConfigError):
        Client(api_key, base_url=base_url, timeout=bad_timeout)


def test_timeout_accepts_int_and_float(api_key, base_url):
    Client(api_key, base_url=base_url, timeout=5)
    Client(api_key, base_url=base_url, timeout=0.5)


def test_native_timeout_never_panics(api_key):
    # R4-04: through the native module directly (no Python wrapper in
    # the way), an absurd timeout is a ValueError. A PanicException is
    # a BaseException, not a ValueError, so this fails if the panic
    # ever escapes the FFI boundary again.
    from placekit import _placekit

    with pytest.raises(ValueError):
        _placekit.Client(api_key, timeout=1e20)
    with pytest.raises(ValueError):
        _placekit.Client(api_key, timeout=3601.0)
    _placekit.Client(api_key, timeout=3600.0)


def test_native_dict_body_circle_without_a_complete_center_is_rejected(
    api_key, base_url, stub_server
):
    # Through the native module directly, a hand built dict body is
    # decoded by the core. A circle that omits its center, or whose
    # center omits a coordinate, used to decode through the response
    # leniency defaults and reach the wire aimed at latitude 0.0 and
    # longitude 0.0. It is a configuration error now, raised before
    # any request is made.
    from placekit import _placekit

    native = _placekit.Client(api_key, base_url=base_url)
    stub_server.last_request = None
    with pytest.raises(_placekit.PlacesError) as excinfo:
        native.text_search(
            {"textQuery": "cafes", "locationBias": {"circle": {"radius": 100.0}}}
        )
    assert excinfo.value.kind == "config"
    with pytest.raises(_placekit.PlacesError) as excinfo:
        native.nearby_search(
            {
                "locationRestriction": {
                    "circle": {"center": {"latitude": -33.86}, "radius": 100.0}
                }
            }
        )
    assert excinfo.value.kind == "config"
    assert stub_server.last_request is None


def test_native_dict_body_complete_circle_reaches_the_wire(
    api_key, base_url, stub_server
):
    # The same dict body path with a complete center is accepted and
    # the circle reaches the stub exactly as supplied.
    from placekit import _placekit

    native = _placekit.Client(api_key, base_url=base_url)
    native.text_search(
        {
            "textQuery": "cafes",
            "locationBias": {
                "circle": {
                    "center": {"latitude": -33.86, "longitude": 151.2},
                    "radius": 100.0,
                }
            },
        }
    )
    body = json.loads(stub_server.last_request["body"])
    assert body["locationBias"]["circle"]["center"] == {
        "latitude": -33.86,
        "longitude": 151.2,
    }
    assert body["locationBias"]["circle"]["radius"] == 100.0


def test_error_carries_all_documented_attributes(client, raw_response):
    # R4-15: a normal error reaches Python with every documented
    # attribute attached, not a silently partial set.
    raw_response(404, fixture_bytes("error_not_found.json"))
    with pytest.raises(NotFoundError) as excinfo:
        client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    err = excinfo.value
    for attr in (
        "kind",
        "status_code",
        "google_status",
        "error_code",
        "status_mismatch",
        "retryable",
        "retry_after",
        "details",
        "field_violations",
        "quota_violations",
    ):
        assert hasattr(err, attr), attr
    assert err.kind == "not_found"
    assert err.status_code == 404
    # Values that exist only if the native attributes were attached
    # and copied across: the envelope code, the Google status.
    assert err.error_code == 404
    assert err.google_status == "NOT_FOUND"


def test_header_unfriendly_api_key_is_config_error(base_url):
    with pytest.raises(ConfigError):
        Client("bad\nkey", base_url=base_url)


@pytest.mark.parametrize("bad", [-1, 0, 2**32, True])
def test_max_results_range_validated(client, bad):
    # max_results is Nearby Search's spelling; its range guard stands.
    with pytest.raises(ConfigError):
        client.nearby_search((-33.8668, 151.2071), 800.0, max_results=bad)


def test_text_search_rejects_the_removed_max_results_spelling(
    client, stub_server
):
    # RC-24 (parent decision): text_search keeps page_size only. The
    # removed duplicate spelling is a plain TypeError now, exactly
    # like any other unknown keyword, and nothing is sent.
    stub_server.last_request = None
    with pytest.raises(TypeError):
        client.text_search("cafes", max_results=5)
    assert stub_server.last_request is None
    result = client.text_search("cafes", page_size=5)
    assert len(result.places) == 2


@pytest.mark.parametrize("bad", [-1, 0, 21, 999999, 2**32, True])
def test_page_size_range_validated(client, stub_server, bad):
    # page_size bypassed the shared numeric validation: 0, 21 and
    # 999999 went to the API verbatim, and negative or huge values
    # leaked an OverflowError message inside the ConfigError. Every
    # rejected value must fail before anything reaches the stub.
    stub_server.last_request = None
    with pytest.raises(ConfigError) as excinfo:
        client.text_search("cafes", page_size=bad)
    assert "page_size" in str(excinfo.value)
    assert "OverflowError" not in str(excinfo.value)
    assert stub_server.last_request is None


def test_page_size_boundaries_reach_the_wire(client, stub_server):
    for size in (1, 20):
        client.text_search("cafes", page_size=size)
        body = json.loads(stub_server.last_request["body"])
        assert body["pageSize"] == size


@pytest.mark.parametrize("bad", [-1, 0, 4801, 2**32])
def test_photo_dimensions_range_validated(client, bad):
    with pytest.raises(ConfigError):
        client.place_photo("places/ChIJ/photos/ATJ83zh8vExample", max_width_px=bad)


def test_model_conversion_failure_is_decode_error(client, monkeypatch):
    def boom(data):
        raise KeyError("places")

    monkeypatch.setattr(TextSearchResult, "from_api", boom)
    with pytest.raises(DecodeError) as excinfo:
        client.text_search("cafes")
    assert "model conversion" in excinfo.value.message


def test_place_from_api_coerces_numeric_fields():
    place = Place.from_api({"id": "ChIJx", "rating": "4.6", "userRatingCount": "1284"})
    assert place.rating == pytest.approx(4.6)
    assert isinstance(place.rating, float)
    assert place.user_rating_count == 1284
    assert isinstance(place.user_rating_count, int)


def test_autocomplete_unknown_top_level_field_survives(client, raw_response):
    data = json.loads(fixture_bytes("autocomplete.json"))
    data["futureSummary"] = {"legs": [1, 2]}
    raw_response(200, json.dumps(data).encode())
    result = client.autocomplete("Bianco")
    assert result.raw["futureSummary"] == {"legs": [1, 2]}


def test_unknown_field_big_integer_survives_exactly(client, raw_response):
    # R4-19: an unknown field carrying an integer beyond 64 bits
    # reaches raw with every digit, as a Python int, not collapsed
    # into a float.
    raw_response(
        200,
        b'{"places": [], "futureCounter": 340282366920938463463374607431768211456}',
    )
    result = client.text_search("cafes")
    assert result.raw["futureCounter"] == 340282366920938463463374607431768211456
    assert isinstance(result.raw["futureCounter"], int)


def test_async_error_attributes_match_sync(api_key, base_url):
    async def run():
        client = AsyncClient(api_key, base_url=base_url)
        with pytest.raises(RateLimitError) as excinfo:
            await client.text_search("TRIGGER_QUOTA")
        assert excinfo.value.status_code == 429
        assert excinfo.value.google_status == "RESOURCE_EXHAUSTED"
        assert excinfo.value.retryable is True
        assert excinfo.value.retry_after == 7
        assert excinfo.value.context == "text_search"
        with pytest.raises(NotFoundError) as excinfo:
            await client.place_details("missing-place")
        assert excinfo.value.context == "place_details place_id=missing-place"
        with pytest.raises(ConfigError):
            await client.place_photo(
                "places/ChIJ/photos/../../../../etc/passwd", max_width_px=100
            )

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Round 5 (T3) regressions: field mask grammar, string guards, defaults
# ---------------------------------------------------------------------------


def test_bare_string_fields_rejected_before_any_request(client, stub_server):
    # RC-01: a bare string used to shred into one-character paths and
    # reach the stub as the header "p,l,a,c,e,s,.,i,d". The stub must
    # see no request at all.
    stub_server.last_request = None
    with pytest.raises(ConfigError):
        client.text_search("cafes", fields="places.id")
    assert stub_server.last_request is None
    with pytest.raises(ConfigError):
        FieldMask.of("places.id")


def test_field_mask_grammar_rejects_semantic_errors():
    # RC-10: snake_case, empty segments, stray punctuation, spaces,
    # wildcards and one-letter segments all fail locally.
    for bad in (
        "places.display_name",
        "places..rating",
        "places.",
        ".places",
        "not a field!!!",
        "a b",
        "*",
        "places.*",
        "a",
        "places.i",
    ):
        with pytest.raises(ConfigError):
            FieldMask(bad)


def test_field_mask_deduplicates_and_set_input_is_deterministic():
    # RC-10: duplicates collapse keeping first seen order, and a set
    # produces the same sorted header on every call.
    assert FieldMask("places.id", "places.id", "places.rating").paths == (
        "places.id",
        "places.rating",
    )
    first = FieldMask.of({"places.rating", "places.id", "places.name"})
    second = FieldMask.of({"places.name", "places.rating", "places.id"})
    assert first.paths == second.paths == ("places.id", "places.name", "places.rating")


def test_place_details_default_mask_covers_modelled_fields(client):
    # RC-07: the default Place Details mask now asks for every modelled
    # field, so these attributes arrive populated instead of reading as
    # permanently empty.
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert place.plus_code is not None and place.plus_code.global_code
    assert place.viewport is not None
    assert place.address_components
    assert place.postal_address is not None
    assert place.current_opening_hours is not None
    assert place.primary_type_display_name is not None


# ---------------------------------------------------------------------------
# Round 5 (T3) regressions: boundary validation, lifecycle, pickle
# ---------------------------------------------------------------------------


def test_bare_string_list_parameters_rejected_before_any_request(
    client, stub_server
):
    # RC-01: every iterable-of-strings slot rejects a bare string, and
    # the stub sees no request for any of them.
    calls = (
        lambda: client.text_search("cafes", price_levels="PRICE_LEVEL_FREE"),
        lambda: client.nearby_search(
            (40.0, -70.0), 100.0, included_types="cafe"
        ),
        lambda: client.autocomplete("par", included_region_codes="AU"),
        lambda: client.autocomplete("par", included_primary_types="cafe"),
    )
    for call in calls:
        stub_server.last_request = None
        with pytest.raises(ConfigError):
            call()
        assert stub_server.last_request is None


def test_non_string_items_in_list_parameters_rejected(client, stub_server):
    stub_server.last_request = None
    with pytest.raises(ConfigError):
        client.text_search("cafes", price_levels=["PRICE_LEVEL_FREE", 3])
    assert stub_server.last_request is None


def test_generator_list_parameter_materialized_once(client, stub_server):
    # RC-06: a generator works for the filter slots exactly as it does
    # for fields, consumed once, its items on the wire.
    result = client.nearby_search(
        (40.0, -70.0), 100.0, included_types=(t for t in ["cafe", "bakery"])
    )
    body = json.loads(stub_server.last_request["body"])
    assert body["includedTypes"] == ["cafe", "bakery"]
    assert len(result.places) == 1


def test_boolean_body_fields_reject_non_bool_before_any_request(
    client, stub_server
):
    # RC-04: the string "false" used to reach the wire as true. Every
    # boolean slot now rejects non-bools locally.
    calls = (
        lambda: client.text_search("cafes", open_now="false"),
        lambda: client.text_search("cafes", open_now=1),
        lambda: client.text_search("cafes", strict_type_filtering="false"),
        lambda: client.autocomplete("par", include_query_predictions="false"),
        lambda: client.place_photo(
            "places/x/photos/y", max_width_px=10, skip_http_redirect="false"
        ),
    )
    for call in calls:
        stub_server.last_request = None
        with pytest.raises(ConfigError):
            call()
        assert stub_server.last_request is None


def test_boolean_body_fields_send_real_bools(client, stub_server):
    # RC-04 wire assertion: a real False is sent as JSON false.
    client.text_search("cafes", open_now=False)
    body = json.loads(stub_server.last_request["body"])
    assert body["openNow"] is False


def test_coordinates_validated_in_python(client, stub_server):
    # RC-05: out-of-range, non-finite, bool and string coordinates all
    # raise ConfigError and nothing reaches the stub.
    bad_locations = (
        (91.0, 0.0),
        (0.0, 181.0),
        (float("nan"), 0.0),
        (float("inf"), 0.0),
        (True, 0.0),
        ("40.0", -70.0),
        (40.0,),
        (40.0, -70.0, 0.0),
    )
    for location in bad_locations:
        stub_server.last_request = None
        with pytest.raises(ConfigError):
            client.nearby_search(location, 100.0)
        assert stub_server.last_request is None


def test_coordinate_sets_rejected_and_lists_accepted_everywhere(
    client, stub_server
):
    # RC-05: a set would unpack latitude and longitude in arbitrary
    # order, so it is rejected in every coordinate slot; a list is
    # accepted in every slot, uniformly (A9).
    with pytest.raises(ConfigError):
        client.nearby_search({40.0, -70.0}, 100.0)
    with pytest.raises(ConfigError):
        client.autocomplete("par", origin={40.0, -70.0})
    with pytest.raises(ConfigError):
        client.text_search(
            "cafes",
            location_bias={"circle": {"center": {40.0, -70.0}, "radius": 10}},
        )
    result = client.nearby_search([40.0, -70.0], 100.0)
    assert len(result.places) == 1
    client.autocomplete("par", origin=[40.0, -70.0])
    body = json.loads(stub_server.last_request["body"])
    assert body["origin"] == {"latitude": 40.0, "longitude": -70.0}
    client.text_search(
        "cafes",
        location_bias={"circle": {"center": [40.0, -70.0], "radius": 10}},
    )
    body = json.loads(stub_server.last_request["body"])
    assert body["locationBias"]["circle"]["center"] == {
        "latitude": 40.0,
        "longitude": -70.0,
    }


def test_dict_body_coordinates_validated(client, stub_server):
    # RC-05: wire-shape dict coordinates and rectangle corners get the
    # same range checks as tuple inputs.
    stub_server.last_request = None
    with pytest.raises(ConfigError):
        client.text_search(
            "cafes",
            location_bias={
                "circle": {
                    "center": {"latitude": 999.0, "longitude": 0.0},
                    "radius": 10,
                }
            },
        )
    assert stub_server.last_request is None
    with pytest.raises(ConfigError):
        client.text_search(
            "cafes",
            location_restriction={
                "rectangle": {
                    "low": (40.0, -70.0),
                    "high": (1000.0, 0.0),
                }
            },
        )
    assert stub_server.last_request is None


def test_location_body_requires_a_mapping(client):
    # RC-27 (A10): a list used to be silently coerced through dict(...).
    with pytest.raises(ConfigError):
        client.text_search("cafes", location_bias=[("circle", {})])
    with pytest.raises(ConfigError):
        client.text_search("cafes", location_bias="circle")


def test_radius_must_be_a_finite_number(client):
    # RC-11 (A8): radius True used to become a one metre search.
    with pytest.raises(ConfigError):
        client.nearby_search((40.0, -70.0), True)
    with pytest.raises(ConfigError):
        client.nearby_search((40.0, -70.0), "800")


def test_sibling_numeric_parameters_validated(client, stub_server):
    # RC-11: input_offset and min_rating go through the same guards as
    # max_results and page_size.
    stub_server.last_request = None
    for call in (
        lambda: client.autocomplete("par", input_offset=-1),
        lambda: client.autocomplete("par", input_offset=True),
        lambda: client.autocomplete("par", input_offset=1.5),
        lambda: client.text_search("cafes", min_rating=99),
        lambda: client.text_search("cafes", min_rating=float("nan")),
        lambda: client.text_search("cafes", min_rating=True),
    ):
        with pytest.raises(ConfigError):
            call()
    assert stub_server.last_request is None


def test_client_construction_type_checks(base_url):
    # RC-02: non-string keys and base URLs used to escape as bare
    # AttributeError; padded or non-ASCII keys were sent verbatim (R14).
    with pytest.raises(ConfigError):
        Client(123, base_url=base_url)
    with pytest.raises(ConfigError):
        Client("test-key", base_url=123)
    with pytest.raises(ConfigError):
        Client(" padded-key ", base_url=base_url)
    with pytest.raises(ConfigError):
        Client("key with spaces", base_url=base_url)
    with pytest.raises(ConfigError):
        Client("kéy", base_url=base_url)


def test_place_id_must_be_a_string(client):
    # RC-02: an int place id used to escape as a bare PyO3 TypeError.
    with pytest.raises(ConfigError):
        client.place_details(123)


def test_local_errors_carry_the_method_as_context(client):
    # RC-03: locally raised errors name the call that failed, the way
    # translated API errors already did.
    with pytest.raises(ConfigError) as excinfo:
        client.text_search("cafes", open_now="false")
    assert excinfo.value.context == "text_search"
    with pytest.raises(ConfigError) as excinfo:
        client.place_details(123)
    assert excinfo.value.context == "place_details"


def test_place_photo_requires_a_dimension_in_python(client, stub_server):
    # RC-23: the at-least-one-dimension rule is enforced before the
    # native call, not discovered from it.
    stub_server.last_request = None
    with pytest.raises(ConfigError):
        client.place_photo("places/x/photos/y")
    assert stub_server.last_request is None


def test_sync_client_refuses_a_running_event_loop(client):
    # RC-13: a sync call inside a loop used to freeze it for the whole
    # request; it now fails fast pointing at AsyncClient.
    async def run():
        with pytest.raises(ConfigError):
            client.text_search("cafes")

    asyncio.run(run())


def test_client_close_and_context_manager(api_key, base_url):
    # RC-14: close is idempotent, later calls raise ConfigError, and
    # the with statement closes on exit.
    closing = Client(api_key, base_url=base_url)
    closing.close()
    closing.close()
    with pytest.raises(ConfigError):
        closing.text_search("cafes")
    with Client(api_key, base_url=base_url) as managed:
        assert len(managed.text_search("cafes").places) == 2
    with pytest.raises(ConfigError):
        managed.text_search("cafes")


def test_async_client_close_and_context_manager(api_key, base_url):
    # RC-14, async side.
    async def run():
        async with AsyncClient(api_key, base_url=base_url) as managed:
            assert len((await managed.text_search("cafes")).places) == 2
        with pytest.raises(ConfigError):
            await managed.text_search("cafes")

    asyncio.run(run())


def test_client_pickle_and_copy_name_placekit(client):
    # RC-26: the error names placekit and the real reason, never the
    # phantom builtins.Client, and shallow copy no longer silently
    # shares the live native client.
    import copy
    import pickle

    with pytest.raises(TypeError) as excinfo:
        pickle.dumps(client)
    assert "placekit" in str(excinfo.value)
    assert "builtins" not in str(excinfo.value)
    with pytest.raises(TypeError):
        copy.copy(client)
    with pytest.raises(TypeError):
        copy.deepcopy(client)


# ---------------------------------------------------------------------------
# Round 5 (T3) regressions: model layer
# ---------------------------------------------------------------------------


def test_model_raw_is_a_snapshot_not_an_alias():
    # RC-08: mutating the caller's dict after decoding must not
    # rewrite the model, its raw, or the parent result's raw.
    from placekit.models import TextSearchResult

    payload = {
        "places": [
            {"id": "A", "types": ["cafe"], "photos": [{"name": "p1"}]}
        ]
    }
    result = TextSearchResult.from_api(payload)
    payload["places"][0]["types"].append("hacked")
    payload["places"][0]["photos"][0]["name"] = "changed"
    payload["injected"] = True
    place = result.places[0]
    assert place.types == ["cafe"]
    assert place.raw["photos"][0]["name"] == "p1"
    assert "injected" not in result.raw
    assert place.raw is not result.raw["places"][0]


def test_models_are_frozen_and_latlng_is_hashable():
    # RC-09: assignment to a parsed model raises instead of silently
    # rewriting a shared result; the one pure pair is a valid dict key.
    from dataclasses import FrozenInstanceError

    from placekit.models import LatLng, Place

    place = Place.from_api({"id": "A", "rating": 4.0})
    with pytest.raises(FrozenInstanceError):
        place.rating = 0.0
    with pytest.raises(FrozenInstanceError):
        place.location = LatLng(1.0, 2.0)
    assert hash(LatLng(1.0, 2.0)) == hash(LatLng(1.0, 2.0))
    assert {LatLng(1.0, 2.0): "x"}[LatLng(1.0, 2.0)] == "x"


def test_latlng_construction_rejects_bools_and_non_numbers():
    # RC-05 model side: LatLng(True, False).to_api() used to return
    # the bools themselves.
    from placekit.models import LatLng

    with pytest.raises(ConfigError):
        LatLng(True, False)
    with pytest.raises(ConfigError):
        LatLng("40.0", -70.0)
    with pytest.raises(ConfigError):
        LatLng(float("nan"), 0.0)
    assert LatLng(40, -70).to_api() == {"latitude": 40.0, "longitude": -70.0}


def test_from_api_strictness_policy():
    # RC-18: missing required keys and ghost payloads are DecodeError
    # naming the model, never a bare KeyError or a fabricated object.
    from placekit.models import LatLng, Place, Viewport

    with pytest.raises(DecodeError) as excinfo:
        LatLng.from_api({})
    assert "LatLng" in str(excinfo.value)
    with pytest.raises(DecodeError):
        Viewport.from_api({})
    with pytest.raises(DecodeError):
        Place.from_api({})
    # A payload that merely lacks an id (a field mask that did not
    # request one) still decodes; only the empty payload is a ghost.
    assert Place.from_api({"displayName": {"text": "X"}}).id == ""


def test_from_api_numeric_coercion_is_uniform():
    # RC-18 (A11): distance_meters and opening point fields are typed
    # Optional[int] in the stubs; the decoders now produce ints.
    from placekit.models import OpeningPoint, PlacePrediction

    prediction = PlacePrediction.from_api(
        {"placeId": "A", "distanceMeters": 12.9}
    )
    assert prediction.distance_meters == 12
    assert isinstance(prediction.distance_meters, int)
    point = OpeningPoint.from_api({"day": "2", "hour": "9"})
    assert point.day == 2 and point.hour == 9


def test_from_api_rejects_shredded_type_strings():
    # RC-01 model side: a string in a list slot is not shredded into
    # one-character types.
    from placekit.models import Place

    with pytest.raises(DecodeError):
        Place.from_api({"id": "A", "types": "cafe"})


def test_query_predictions_are_modelled():
    # RC-20: query predictions used to be silently dropped by the
    # autocomplete convenience surface.
    from placekit.models import AutocompleteResult

    result = AutocompleteResult.from_api(
        {
            "suggestions": [
                {
                    "queryPrediction": {
                        "text": {"text": "pizza near me"},
                        "structuredFormat": {
                            "mainText": {"text": "pizza"},
                        },
                    }
                },
                {"placePrediction": {"placeId": "A"}},
            ]
        }
    )
    queries = result.query_predictions
    assert len(queries) == 1
    assert queries[0].text is not None and queries[0].text.text == "pizza near me"
    assert result.suggestions[0].query_prediction is queries[0]
    assert len(result.place_predictions) == 1


def test_place_regular_opening_hours_alias():
    # RC-21: the alias matches the wire name regularOpeningHours.
    from placekit.models import Place

    place = Place.from_api(
        {"id": "A", "regularOpeningHours": {"openNow": True}}
    )
    assert place.opening_hours is not None
    assert place.regular_opening_hours is place.opening_hours
    assert place.regular_opening_hours.open_now is True


def test_repr_and_equality_exclude_raw():
    # RC-19: repr and equality are about the modelled fields only.
    # The two payloads differ ONLY in unmodelled raw content, so the
    # equality assertion fails the moment raw takes part in
    # comparison, and the repr assertions pin both halves directly:
    # modelled fields are shown, the raw payload is not dumped.
    from placekit.models import PhotoMedia, Place

    first = Place.from_api({"id": "A", "rating": 4.0, "unmodelled": 1})
    second = Place.from_api({"id": "A", "rating": 4.0, "unmodelled": 2})
    assert first.raw != second.raw
    assert first.raw["unmodelled"] == 1
    assert second.raw["unmodelled"] == 2
    assert first == second
    assert "rating=4.0" in repr(first)
    assert "'unmodelled': 1" not in repr(first)
    assert "'id': 'A'" not in repr(first)
    media = PhotoMedia(content=b"\x89PNG-long-payload", content_type="image/png")
    assert "PNG-long" not in repr(media)


def test_error_str_shows_context_and_status():
    # RC-17: str(error) carries the context the type collects.
    err = RateLimitError(
        "quota exhausted", status_code=429, google_status="RESOURCE_EXHAUSTED",
        context="text_search",
    )
    text = str(err)
    assert "quota exhausted" in text
    assert "text_search" in text
    assert "429" in text
    assert "RESOURCE_EXHAUSTED" in text
    assert repr(err).startswith("RateLimitError(")


def test_error_list_attributes_are_copied():
    # RC-22: mutating the caller's list after construction must not
    # rewrite the raised exception.
    details = [{"a": 1}]
    err = PlacesError("boom", details=details)
    details.append({"b": 2})
    assert err.details == [{"a": 1}]


def test_routing_parameter_bools_rejected_in_conversion_layer(
    client, stub_server
):
    # RC-04, conversion layer: routing_parameters is a dict the Python
    # layer passes through, so its booleans are guarded where the body
    # is converted. The string "false" must never reach the wire as
    # true, and no request may be sent.
    stub_server.last_request = None
    with pytest.raises(ConfigError):
        client.text_search(
            "cafes",
            routing_parameters={"avoidTolls": "false", "travelMode": "DRIVE"},
        )
    assert stub_server.last_request is None
    client.text_search(
        "cafes", routing_parameters={"travelMode": "DRIVE"}
    )
    assert stub_server.last_request is not None


def test_self_referential_body_dict_raises_typed_error(client, stub_server):
    # Round 5 repair (S-1): the conversion layer's bool walker used to
    # recurse into a self-referential dict body with no bound and
    # segfault the interpreter (exit 139, reproduced against the
    # landed build). It must now surface as a ConfigError, with the
    # process alive and no request sent.
    cyclic = {}
    cyclic["self"] = cyclic
    stub_server.last_request = None
    with pytest.raises(ConfigError):
        client.text_search("cafes", routing_parameters=cyclic)
    assert stub_server.last_request is None
    with pytest.raises(ConfigError):
        client.text_search("cafes", ev_options=cyclic)
    assert stub_server.last_request is None


def test_tuple_nested_body_bools_rejected_in_conversion_layer(
    client, stub_server
):
    # Round 5 repair (S-5): the walker promised any nesting depth but
    # skipped tuples, so a bool field inside a tuple slipped through
    # to a network attempt. Tuples are traversed now.
    stub_server.last_request = None
    with pytest.raises(ConfigError) as excinfo:
        client.text_search(
            "cafes",
            routing_parameters={"routeModifiers": ({"avoidTolls": "false"},)},
        )
    assert "avoidTolls must be a bool, got 'false'" in str(excinfo.value)
    assert stub_server.last_request is None


def test_deeply_nested_body_within_bound_still_works(client, stub_server):
    # Round 5 repair (S-1): the depth bound must not reject deep but
    # legitimate nesting. Forty levels of dicts carrying a real bool
    # at the bottom pass the walker and the request is sent.
    nested = {"avoidTolls": False}
    for _ in range(40):
        nested = {"bundles": [nested]}
    client.text_search("cafes", ev_options=nested)
    assert stub_server.last_request is not None


def test_dict_body_bare_string_list_field_rejected_sync_and_async(
    client, stub_server, api_key, base_url
):
    # Round 5 repair (RT5-L1): the red team's exact case. A bare
    # string in the ev_options dict body used to reach the wire
    # shredded into one-character strings, because dict parameters
    # passed through unchecked. The error names the parameter and
    # the field, and no request reaches the stub, sync or async.
    stub_server.last_request = None
    with pytest.raises(ConfigError) as excinfo:
        client.text_search(
            "pizza",
            ev_options={"connectorTypes": "EV_CONNECTOR_TYPE_OTHER"},
        )
    assert "ev_options" in str(excinfo.value)
    assert "connectorTypes" in str(excinfo.value)
    assert stub_server.last_request is None
    with pytest.raises(ConfigError):
        client.text_search(
            "pizza", ev_options={"connectorTypes": b"EV_CONNECTOR_TYPE_OTHER"}
        )
    assert stub_server.last_request is None
    # The same guard at nesting depth, inside a list inside the dict.
    with pytest.raises(ConfigError):
        client.text_search(
            "pizza",
            ev_options={"bundles": [{"connectorTypes": "EV_CONNECTOR_TYPE_OTHER"}]},
        )
    assert stub_server.last_request is None

    async def run():
        async_client = AsyncClient(api_key, base_url=base_url)
        with pytest.raises(ConfigError) as excinfo:
            await async_client.text_search(
                "pizza", ev_options={"connectorTypes": "AB"}
            )
        assert "connectorTypes" in str(excinfo.value)
        assert stub_server.last_request is None

    asyncio.run(run())


def test_dict_body_proper_list_passes_verbatim(client, stub_server):
    # Round 5 repair (RT5-L1), positive control: a proper list in the
    # same slot reaches the wire exactly as given.
    client.text_search(
        "pizza",
        ev_options={
            "connectorTypes": ["EV_CONNECTOR_TYPE_OTHER"],
            "minimumChargingRateKw": 50.0,
        },
    )
    body = json.loads(stub_server.last_request["body"])
    assert body["evOptions"] == {
        "connectorTypes": ["EV_CONNECTOR_TYPE_OTHER"],
        "minimumChargingRateKw": 50.0,
    }
