"""Round 23 acceptance probes against the offline stub.

The fabrication repair: a response body carrying a partial location
or a partial viewport used to reach Python with coordinates the wire
never sent (a longitude of 0.0 beside a sent latitude, a whole
viewport corner at 0.0, 0.0). Those bodies must now behave like
their explicit null counterparts do, a typed DecodeError through the
client, while the null and complete forms keep their settled
readings.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from placekit import AsyncClient, Client
from placekit.exceptions import ApiError, DecodeError


@pytest.fixture()
def client(api_key, base_url) -> Client:
    return Client(api_key, base_url=base_url)


def _details_body(**place_fields) -> bytes:
    body = {"id": "ChIJx", "name": "places/ChIJx"}
    body.update(place_fields)
    return json.dumps(body).encode()


def test_location_with_only_latitude_is_a_decode_error(client, raw_response):
    # The red team shape B1. Before the repair this call succeeded
    # and the typed place exposed a longitude of 0.0 the wire never
    # sent, while raw beside it carried no longitude at all.
    raw_response(200, _details_body(location={"latitude": 51.5}))
    with pytest.raises(DecodeError) as excinfo:
        client.place_details("ChIJx")
    assert "longitude" in excinfo.value.message
    assert excinfo.value.status_code == 200


def test_location_with_only_latitude_is_a_decode_error_async(
    api_key, base_url, raw_response
):
    async def run():
        client = AsyncClient(api_key, base_url=base_url)
        raw_response(200, _details_body(location={"latitude": 51.5}))
        with pytest.raises(DecodeError) as excinfo:
            await client.place_details("ChIJx")
        assert "longitude" in excinfo.value.message

    asyncio.run(run())


def test_empty_location_object_decodes_as_no_location(client, raw_response):
    # The red team shape B3. An empty location object used to read
    # as a place at the zero coordinate point (both coordinates
    # fabricated upstream). It now behaves exactly like its null
    # counterpart: the place decodes with no location, and raw
    # carries the empty object the wire sent.
    raw_response(200, _details_body(location={}))
    place = client.place_details("ChIJx")
    assert place.location is None
    assert place.raw["location"] == {}


def test_viewport_missing_its_low_corner_is_a_decode_error(client, raw_response):
    # The red team shape B4. The missing corner used to be met by a
    # fabricated LatLng of 0.0 and 0.0 upstream of the Python
    # decoder, whose own contract requires both corners.
    raw_response(
        200,
        _details_body(viewport={"high": {"latitude": 1.0, "longitude": 2.0}}),
    )
    with pytest.raises(DecodeError) as excinfo:
        client.place_details("ChIJx")
    assert "low" in excinfo.value.message


def test_null_location_still_decodes_as_no_location(client, raw_response):
    # The null counterpart whose behaviour the repaired shapes now
    # match in kind: an explicit null location is a place with no
    # location, not an error and not a fabricated point.
    raw_response(200, _details_body(location=None))
    place = client.place_details("ChIJx")
    assert place.location is None
    assert "location" in place.raw
    assert place.raw["location"] is None


def test_null_coordinate_still_refuses_like_absence_now_does(client, raw_response):
    # The explicit null coordinate refused before the repair (the
    # Python decoder meets the null in the typed dict) and refuses
    # after it, naming the same key the absence form now names.
    raw_response(200, _details_body(location={"latitude": 51.5, "longitude": None}))
    with pytest.raises(DecodeError) as excinfo:
        client.place_details("ChIJx")
    assert "longitude" in excinfo.value.message


def test_complete_location_still_decodes_exactly(client, raw_response):
    raw_response(200, _details_body(location={"latitude": 51.5, "longitude": -0.12}))
    place = client.place_details("ChIJx")
    assert place.location.latitude == 51.5
    assert place.location.longitude == -0.12
    assert place.location.raw == {"latitude": 51.5, "longitude": -0.12}


def test_zero_coordinates_are_values_not_absence(client, raw_response):
    # A sent 0.0 is a real coordinate (a place can sit on the
    # equator or the prime meridian) and must survive untouched.
    raw_response(200, _details_body(location={"latitude": 0.0, "longitude": 0.0}))
    place = client.place_details("ChIJx")
    assert place.location.latitude == 0.0
    assert place.location.longitude == 0.0


def test_wrongly_typed_field_refusal_names_its_path(client, raw_response):
    # Round 23 diagnosability for the M2 gate: one misshapen element
    # in one result refuses the whole call, and the refusal names
    # the field path with its element index instead of leaving the
    # caller to guess which documented field changed type.
    body = json.dumps(
        {
            "places": [
                {"id": "ChIJ1", "rating": 4.5},
                {"id": "ChIJ2", "rating": "high"},
            ]
        }
    ).encode()
    raw_response(200, body)
    with pytest.raises(DecodeError) as excinfo:
        client.text_search("cafes")
    assert "places[1].rating" in excinfo.value.message
    assert excinfo.value.status_code == 200


def test_wrongly_typed_scalar_refusal_names_its_path(client, raw_response):
    body = json.dumps({"places": [{"id": "ChIJ1", "priceLevel": 3}]}).encode()
    raw_response(200, body)
    with pytest.raises(DecodeError) as excinfo:
        client.text_search("cafes")
    assert "places[0].priceLevel" in excinfo.value.message


def test_wrongly_typed_field_refusal_names_its_path_async(
    api_key, base_url, raw_response
):
    async def run():
        client = AsyncClient(api_key, base_url=base_url)
        body = json.dumps({"places": [{"id": "ChIJ1", "types": {"cafe": True}}]}).encode()
        raw_response(200, body)
        with pytest.raises(DecodeError) as excinfo:
            await client.text_search("cafes")
        assert "places[0].types" in excinfo.value.message

    asyncio.run(run())


def test_over_cap_error_body_message_states_the_cap(client, raw_response):
    # Round 23: an over cap error body used to be reported with the
    # capped read length (262144) as if it were the body size. The
    # message now states that the read stopped at the cap and the
    # full size is unknown.
    raw_response(500, b"x" * 300_000, "text/html")
    with pytest.raises(ApiError) as excinfo:
        client.text_search("cafes")
    message = excinfo.value.message
    assert "262144 byte cap" in message
    assert "full size is unknown" in message
    assert "error body of 262144 bytes" not in message
    assert "300000" not in message
