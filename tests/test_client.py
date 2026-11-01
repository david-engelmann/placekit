"""End-to-end tests of the Python API against the local stub server.

No network and no Google API key are involved. Every test asserts on typed
model values, recorded request headers/bodies, or translated exceptions, so
each one fails if the behavior it covers breaks.
"""

from __future__ import annotations

import asyncio
import copy
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
from placekit.models import (
    AccessibilityOptions,
    AddressComponent,
    AddressDescriptor,
    Area,
    Attribution,
    AuthorAttribution,
    ConnectorAggregation,
    ConsumerAlert,
    Date,
    EvChargeOptions,
    FormattedText,
    GenerativeSummary,
    GoogleMapsLinks,
    Landmark,
    LatLng,
    Leg,
    LocalizedText,
    Money,
    OpeningHours,
    OpeningPoint,
    PaymentOptions,
    ParkingOptions,
    Period,
    Photo,
    PhotoMedia,
    Place,
    PlacePrediction,
    PlusCode,
    PostalAddress,
    PriceRange,
    Review,
    ReviewSummary,
    RoutingSummary,
    SpecialDay,
    StringMatch,
    TextSearchResult,
    TimeZone,
    Viewport,
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
    # The default mask requests editorialSummary since Round 6 typed
    # it, so the stub serves it on a default call and the typed
    # attribute is populated.
    assert place.editorial_summary is not None
    assert place.editorial_summary.text.startswith("A bright corner cafe")


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


def test_editorial_summary_typed_needs_explicit_field(client):
    # Round 6 rework of the earlier raw-only form of this test.
    # editorialSummary is typed now as a LocalizedText. Through the
    # client with an explicit mask the typed attribute is populated
    # and the payload still survives in raw, and the field joins the
    # default details mask, so a default call populates it too.
    place = client.place_details(
        "ChIJrTLr-GyuEmsRBfy61i59si0", fields=["id", "editorialSummary"]
    )
    assert place.editorial_summary is not None
    assert place.editorial_summary.text.startswith("A bright corner cafe")
    assert place.raw["editorialSummary"]["text"].startswith("A bright corner cafe")
    # And fields outside the explicit mask stay absent.
    assert place.national_phone_number is None
    default = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert default.editorial_summary is not None
    assert default.editorial_summary.text.startswith("A bright corner cafe")


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


# ---------------------------------------------------------------------------
# Round 8 (T3): object arguments for place_details and place_photo
# ---------------------------------------------------------------------------


def test_place_details_accepts_a_place_object(client):
    # D1: the search result itself is the upgrade argument. The call
    # returns a new Place populated from the details fixture, never
    # the object that was passed in.
    result = client.text_search("cafes in Sydney")
    search_place = result.places[0]
    details = client.place_details(search_place)
    assert isinstance(details, Place)
    assert details.id == search_place.id
    assert details is not search_place
    assert details.national_phone_number == "(02) 5550 1234"


def test_place_details_accepts_a_place_prediction(client, stub_server):
    # D1: a prediction resolves through its place_id, never through
    # its place attribute, which is a resource name (finding R8-F7).
    result = client.autocomplete("Bianco")
    prediction = result.place_predictions[0]
    details = client.place_details(prediction)
    assert details.id == prediction.place_id
    assert stub_server.last_request["path"].endswith(
        f"/places/{prediction.place_id}"
    )


def test_place_details_place_and_id_forms_agree(client, stub_server):
    # D1: the object form is the same call as the string form, with
    # the same mask on the wire and an equal result.
    result = client.text_search("cafes in Sydney")
    place = result.places[0]
    by_id = client.place_details(place.id)
    mask_for_id = header(stub_server, "X-Goog-FieldMask")
    by_object = client.place_details(place)
    mask_for_object = header(stub_server, "X-Goog-FieldMask")
    assert by_object == by_id
    assert mask_for_object == mask_for_id


def test_place_details_rejects_an_id_less_place_before_any_request(
    client, stub_server
):
    # D1: an object with no id came from a mask that never requested
    # one, and the failure says so locally instead of reaching the
    # core or the stub.
    stub_server.last_request = None
    with pytest.raises(ConfigError) as excinfo:
        client.place_details(Place(id=""))
    assert excinfo.value.context == "place_details"
    assert stub_server.last_request is None
    with pytest.raises(ConfigError) as excinfo:
        client.place_details(PlacePrediction(place_id=""))
    assert excinfo.value.context == "place_details"
    assert stub_server.last_request is None


def test_place_details_rejects_wrong_types_before_any_request(
    client, stub_server
):
    # D1: resolution branches on the model types, so an int, None
    # and a Photo (which carries an id shaped name of its own) all
    # fail locally with no request.
    photo = Photo(
        name="places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample"
    )
    for bad in (123, None, photo):
        stub_server.last_request = None
        with pytest.raises(ConfigError):
            client.place_details(bad)
        assert stub_server.last_request is None


def test_place_details_rejects_a_wrongly_typed_id_before_any_request(
    client, stub_server
):
    # D1: the frozen models never type check their fields, so a
    # hand built object can carry an identifier that is not a
    # string at all. Resolution refuses it as a ConfigError
    # before the strip check would die on it, and no request
    # reaches the stub.
    for bad in (
        Place(id=None),
        Place(id=123),
        PlacePrediction(place_id=None),
    ):
        stub_server.last_request = None
        with pytest.raises(ConfigError) as excinfo:
            client.place_details(bad)
        assert excinfo.value.context == "place_details"
        assert stub_server.last_request is None


def test_models_carry_no_fetch_methods():
    # D1 and D2: models are frozen value objects and never perform
    # network I/O. This guard fails the day a fetching method lands
    # on one of them.
    assert not hasattr(Place, "get_details")
    assert not hasattr(Photo, "get")
    assert not hasattr(Photo, "fetch")
    assert not hasattr(PlacePrediction, "get_details")


def test_place_details_accepts_a_place_object_async(api_key, base_url):
    # D1, async mirror of the sync object form test.
    async def run():
        client = AsyncClient(api_key, base_url=base_url)
        result = await client.text_search("cafes in Sydney")
        search_place = result.places[0]
        details = await client.place_details(search_place)
        assert details.id == search_place.id
        assert details is not search_place
        assert details.national_phone_number == "(02) 5550 1234"

    asyncio.run(run())


def test_place_details_rejects_an_id_less_place_before_any_request_async(
    api_key, base_url, stub_server
):
    # D1, async mirror of the id less object rejection.
    async def run():
        client = AsyncClient(api_key, base_url=base_url)
        stub_server.last_request = None
        with pytest.raises(ConfigError) as excinfo:
            await client.place_details(Place(id=""))
        assert excinfo.value.context == "place_details"
        assert stub_server.last_request is None

    asyncio.run(run())


def test_place_details_rejects_a_wrongly_typed_id_before_any_request_async(
    api_key, base_url, stub_server
):
    # D1, async mirror of the wrongly typed id rejection. The
    # resolvers live on the shared base class, so the async
    # client refuses the same hand built objects the same way.
    async def run():
        client = AsyncClient(api_key, base_url=base_url)
        for bad in (
            Place(id=None),
            Place(id=123),
            PlacePrediction(place_id=None),
        ):
            stub_server.last_request = None
            with pytest.raises(ConfigError) as excinfo:
                await client.place_details(bad)
            assert excinfo.value.context == "place_details"
            assert stub_server.last_request is None

    asyncio.run(run())


def test_place_photo_accepts_a_photo_object(client):
    # D2: the Photo itself is the fetch argument. The resolver reads
    # its name and the bytes match the string form assertions.
    details = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    media = client.place_photo(details.photos[0], max_width_px=400)
    assert isinstance(media, PhotoMedia)
    assert media.content_type == "image/png"
    assert media.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(media.content) > 1024
    assert media.content == PHOTO_FIXTURE.read_bytes()


def test_place_photo_photo_form_defaults_to_the_photo_width(
    client, stub_server
):
    # D2: a Photo passed with no sizes defaults its native width,
    # 4032 in the details fixture, and sends no second dimension.
    # The stub records only the last request, and the byte form
    # redirect follow would overwrite the media request, so the
    # wire assertion observes the same call through the URI form
    # after the byte form has been exercised.
    details = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    photo = details.photos[0]
    media = client.place_photo(photo)
    assert isinstance(media, PhotoMedia)
    assert media.content == PHOTO_FIXTURE.read_bytes()
    result = client.place_photo(photo, skip_http_redirect=True)
    assert isinstance(result, PhotoUriResult)
    path = stub_server.last_request["path"]
    assert "maxWidthPx=4032" in path
    assert "maxHeightPx" not in path


def test_place_photo_explicit_size_suppresses_the_default(
    client, stub_server
):
    # D2: passing either size switches the defaulting off entirely,
    # so an explicit height travels alone with no defaulted width
    # beside it. Observed through the URI form for the reason the
    # width default test records.
    details = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    photo = details.photos[0]
    result = client.place_photo(photo, max_height_px=300, skip_http_redirect=True)
    assert isinstance(result, PhotoUriResult)
    path = stub_server.last_request["path"]
    assert "maxHeightPx=300" in path
    assert "maxWidthPx" not in path


def test_place_photo_width_default_is_capped(client, stub_server):
    # D2: a native width above the API cap defaults to the cap, so
    # the default itself never trips the core range check.
    photo = Photo(
        name="places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
        width_px=9999,
        height_px=3024,
    )
    result = client.place_photo(photo, skip_http_redirect=True)
    assert isinstance(result, PhotoUriResult)
    assert "maxWidthPx=4800" in stub_server.last_request["path"]


def test_place_photo_photo_without_dimensions_fails_locally(
    client, stub_server
):
    # D2: zero is the unknown dimension sentinel (finding R8-F8), so
    # a Photo with no dimensions has nothing to default from and
    # fails before any request.
    photo = Photo(
        name="places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample"
    )
    stub_server.last_request = None
    with pytest.raises(ConfigError):
        client.place_photo(photo)
    assert stub_server.last_request is None


def test_place_photo_photo_form_skip_redirect_returns_uri(client):
    # D2: the URI flow is identical for both argument shapes, and
    # the result carries the photo name.
    details = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    photo = details.photos[0]
    result = client.place_photo(photo, skip_http_redirect=True)
    assert isinstance(result, PhotoUriResult)
    assert result.name == photo.name


def test_place_photo_rejects_wrong_types_before_any_request(
    client, stub_server
):
    # D2: a Place has a name attribute and must still be refused,
    # because the resolver branches on the Photo type and never on
    # attribute presence.
    for bad in (Place(id="ChIJrTLr-GyuEmsRBfy61i59si0"), 123):
        stub_server.last_request = None
        with pytest.raises(ConfigError):
            client.place_photo(bad, max_width_px=100)
        assert stub_server.last_request is None


def test_place_photo_rejects_wrongly_typed_dimensions_before_any_request(
    client, stub_server
):
    # D2: a hand built Photo can carry a dimension that is not
    # an integer, and the frozen models never type check it.
    # Resolution refuses it as a ConfigError before any
    # dimension comparison would die on it, and no request
    # reaches the stub.
    name = "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample"
    for bad in (
        Photo(name=name, width_px="4032"),
        Photo(name=name, width_px=None),
    ):
        stub_server.last_request = None
        with pytest.raises(ConfigError) as excinfo:
            client.place_photo(bad)
        assert excinfo.value.context == "place_photo"
        assert stub_server.last_request is None


def test_place_photo_accepts_a_photo_object_async(api_key, base_url):
    # D2, async mirror of the sync object form test.
    async def run():
        client = AsyncClient(api_key, base_url=base_url)
        details = await client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
        media = await client.place_photo(details.photos[0], max_width_px=400)
        assert isinstance(media, PhotoMedia)
        assert media.content == PHOTO_FIXTURE.read_bytes()

    asyncio.run(run())


def test_place_photo_photo_form_defaults_to_the_photo_width_async(
    api_key, base_url, stub_server
):
    # D2, async mirror of the width default test, observed through
    # the URI form for the reason the sync test records.
    async def run():
        client = AsyncClient(api_key, base_url=base_url)
        details = await client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
        result = await client.place_photo(
            details.photos[0], skip_http_redirect=True
        )
        assert isinstance(result, PhotoUriResult)
        assert "maxWidthPx=4032" in stub_server.last_request["path"]

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Round 8 (T3): the attribute reading contract
# ---------------------------------------------------------------------------


def test_unrequested_attributes_read_as_not_returned(client):
    # D3: a search default Place leaves details fields unreturned,
    # and the same fields populate on a details call for the same
    # id. The wire name is absent from the search raw, so raw
    # membership tracks what the response carried.
    result = client.text_search("cafes in Sydney")
    place = result.places[0]
    assert place.website_uri is None
    assert place.national_phone_number is None
    assert place.reviews == []
    assert "websiteUri" not in place.raw
    details = client.place_details(place.id)
    assert details.website_uri == "https://example.com/"
    assert details.national_phone_number == "(02) 5550 1234"


def test_absent_and_explicit_null_read_the_same_but_raw_knows(
    client, raw_response
):
    # D3: an explicit null on an optional scalar reads None, exactly
    # as absence does, but the wire name stays a key in raw, which
    # is the one distinction the contract claims. The assertions
    # below are the full claim. They passed at the model layer from
    # the start and failed through the client while the core
    # reserialized modelled fields and dropped a null valued one
    # before Python saw the payload. Since Round 16 the core passes
    # the response body through beside the typed value and Python
    # builds raw from the body itself, so the claim now holds end
    # to end and the strict xfail marker that recorded the debt is
    # gone.
    data = json.loads(fixture_bytes("place_details.json"))
    data["websiteUri"] = None
    raw_response(200, json.dumps(data).encode())
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert place.website_uri is None
    assert "websiteUri" in place.raw


def test_explicit_null_stays_in_raw_at_the_model_layer():
    # D3: the model layer half of the raw membership claim holds
    # today and is pinned green here. A payload carrying
    # websiteUri as an explicit null decodes with website_uri
    # reading None and the wire name present in raw. Through
    # the client the key is lost, which is what the strict
    # xfail above records.
    place = Place.from_api({"id": "ChIJx", "websiteUri": None})
    assert place.website_uri is None
    assert "websiteUri" in place.raw


def test_the_three_empty_shapes_from_a_minimal_payload():
    # D3: decoding a payload that carries only an id leaves every
    # other attribute in its not returned shape, never an error and
    # never fabricated content.
    place = Place.from_api({"id": "ChIJx"})
    assert place.types == []
    assert place.photos == []
    assert place.reviews == []
    assert place.name == ""


def test_explicit_null_in_a_list_field_is_a_decode_error():
    # D3: an explicit null is a malformed value for a list field,
    # not a synonym for absence, so the documentation never grows a
    # claim that null is a supported no value signal.
    with pytest.raises(DecodeError):
        Place.from_api({"id": "ChIJx", "types": None})


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
    # Typed since round 6 group 11: attribute access, and the duration
    # stays the wire string rather than becoming a parsed interval.
    summary = result.routing_summaries[0]
    assert summary.legs[0].distance_meters == 5587
    assert summary.legs[0].duration == "601s"
    assert isinstance(summary.legs[0].duration, str)
    assert summary.directions_uri == "https://maps.google.com/?directions=example"
    # The untyped dict form stays reachable through the result raw,
    # which is the mitigation for the breaking typed change.
    assert result.raw["routingSummaries"][0]["legs"][0]["distanceMeters"] == 5587
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


def test_photo_svg_is_refused_fail_closed(client, raw_response):
    # R18-A4: an SVG is an XML document that can carry script, and
    # the magic check cannot verify it, so the claim is refused
    # outright instead of passing unchecked as it did before.
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg">'
        b"<script>alert(1)</script></svg>"
    )
    raw_response(200, svg, "image/svg+xml")
    with pytest.raises(DecodeError) as excinfo:
        client.place_photo(
            "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
            max_width_px=400,
        )
    assert "image/svg+xml" in excinfo.value.message


def test_photo_unlisted_image_type_is_refused_fail_closed(
    client, raw_response
):
    # R18-A4: a type the client has no signature for is refused
    # even when the bytes are an honest image in that format; only
    # JPEG, PNG, GIF and WebP claims can pass.
    raw_response(200, b"\x00\x00\x00\x0cftypavif", "image/avif")
    with pytest.raises(DecodeError) as excinfo:
        client.place_photo(
            "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
            max_width_px=400,
        )
    assert "image/avif" in excinfo.value.message


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


def test_http_base_url_requires_a_loopback_host(api_key):
    # R18-A5: plain http sends the key in clear text, so a network
    # host must be reached over https. Construction alone must
    # refuse these; no request is ever made.
    for bad in (
        "http://example.com/v1",
        "http://192.0.2.10/v1",
        "http://evillocalhost.com/v1",
    ):
        with pytest.raises(ConfigError):
            Client(api_key, base_url=bad)
    # The loopback shapes stay available, including a hex IPv4
    # spelling the URL parser canonicalises to the loopback it
    # names, because classification reads the parsed host (red
    # team R3). The whole suite runs on the 127.0.0.1 form.
    Client(api_key, base_url="http://localhost:9/v1")
    Client(api_key, base_url="http://0x7f.1:9/v1")
    Client(api_key, base_url="https://example.com/v1")


def test_photo_redirect_to_a_userinfo_target_is_refused(client, raw_response):
    # Red team R2: userinfo in a redirect target becomes an
    # Authorization Basic header on the followed request, so the
    # hop is refused as a network error and the password the
    # Location carried appears nowhere in it.
    raw_response(
        302,
        b"",
        "text/plain",
        {"Location": "http://user:sekret@127.0.0.1:9/img"},
    )
    with pytest.raises(NetworkError) as excinfo:
        client.place_photo(
            "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
            max_width_px=400,
        )
    assert "redirect:" in str(excinfo.value)
    assert "sekret" not in str(excinfo.value)


def test_photo_redirect_to_a_private_address_is_refused(client, raw_response):
    # R18-A3: a media response steering the client at a private
    # network address is refused at the hop. Nothing listens at
    # the target, so an unscreened follow would surface as a plain
    # transport failure instead of a screening refusal.
    raw_response(
        302, b"", "text/plain", {"Location": "http://192.168.0.1/img"}
    )
    with pytest.raises(NetworkError) as excinfo:
        client.place_photo(
            "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
            max_width_px=400,
        )
    assert "refusing to follow" in str(excinfo.value)


def test_photo_redirect_to_a_public_http_target_is_refused(
    client, raw_response
):
    # R18-A3: from the loopback stub base, a hop out to a public
    # host over plain http is a downgrade out of the local
    # configuration and is refused, not followed.
    raw_response(
        302, b"", "text/plain", {"Location": "http://example.com/img"}
    )
    with pytest.raises(NetworkError) as excinfo:
        client.place_photo(
            "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
            max_width_px=400,
        )
    assert "refusing to follow" in str(excinfo.value)


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


def test_async_validation_guards_match_sync(api_key, base_url, stub_server):
    # Round 5 repair (S-9, RC-11 pairing): the guard tests were sync
    # only, so an async method routed around a shared builder would
    # have passed the suite unnoticed. The string guard, the bool
    # guard (typed slot and dict hatch) and the coordinate helper now
    # have async mirrors, each asserting no request reached the stub.
    async def run():
        client = AsyncClient(api_key, base_url=base_url)
        calls = (
            lambda: client.text_search("cafes", fields="places.id"),
            lambda: client.text_search(
                "cafes", price_levels="PRICE_LEVEL_FREE"
            ),
            lambda: client.text_search("cafes", open_now="false"),
            lambda: client.text_search(
                "cafes",
                routing_parameters={
                    "routeModifiers": {"avoidTolls": "false"}
                },
            ),
            lambda: client.nearby_search((91.0, 0.0), 100.0),
            lambda: client.nearby_search({40.0, -70.0}, 100.0),
            lambda: client.autocomplete("par", origin=(0.0, 181.0)),
            lambda: client.autocomplete("par", input_offset=-1),
        )
        for call in calls:
            stub_server.last_request = None
            with pytest.raises(ConfigError):
                await call()
            assert stub_server.last_request is None

    asyncio.run(run())


def test_empty_and_exhausted_iterables_omit_the_filter(client, stub_server):
    # Round 5 repair (RT5-L2), semantics pinned: iterables are
    # materialized once, and an empty result for an optional filter
    # slot means the filter is omitted. An already exhausted
    # generator is indistinguishable from an empty one, so the second
    # use of a consumed generator sends the search unfiltered rather
    # than sending an empty list, uniformly across slots.
    gen = (t for t in ["cafe"])
    client.nearby_search((40.0, -70.0), 100.0, included_types=gen)
    body = json.loads(stub_server.last_request["body"])
    assert body["includedTypes"] == ["cafe"]
    client.nearby_search((40.0, -70.0), 100.0, included_types=gen)
    body = json.loads(stub_server.last_request["body"])
    assert "includedTypes" not in body
    client.text_search("cafes", price_levels=[])
    body = json.loads(stub_server.last_request["body"])
    assert "priceLevels" not in body


def test_model_constructors_reject_bare_strings_in_list_fields():
    # Round 5 repair (RT5-L3): direct construction used to store a
    # bare string in a list-typed field unchecked, so Place(types=
    # "restaurant") iterated as one-character types. The models with
    # list fields now refuse str and bytes at construction, while a
    # proper list constructs normally.
    from placekit.models import OpeningHours, Place, PlacePrediction

    with pytest.raises(ConfigError) as excinfo:
        Place(id="x", types="restaurant")
    assert "types" in str(excinfo.value)
    with pytest.raises(ConfigError):
        Place(id="x", types=b"restaurant")
    with pytest.raises(ConfigError):
        Place(id="x", photos="places/x/photos/y")
    with pytest.raises(ConfigError):
        OpeningHours(weekday_descriptions="Monday")
    with pytest.raises(ConfigError):
        PlacePrediction(place_id="y", types="cafe")
    place = Place(id="x", types=["restaurant"])
    assert place.types == ["restaurant"]


# ---------------------------------------------------------------------------
# Round 6 (T1) group 1: OpeningHours completions, secondary hours, and
# the PhotoUriResult raw fix (fixes section 5.2)
# ---------------------------------------------------------------------------


def test_opening_hours_next_close_time_from_cassette_02():
    # Cut from cassette 02 of the live smoke recordings (the one
    # cassette whose mask requested the opening hours parents whole):
    # each hours object is reduced to its first period, nextCloseTime
    # is verbatim, and the photos array and every URL of the place
    # around them are dropped, keeping ids and timestamps.
    from placekit.models import Place

    place = Place.from_api(
        {
            "id": "ChIJzRBPAz5ZwokRd0AUXGm-2f8",
            "regularOpeningHours": {
                "openNow": True,
                "periods": [
                    {
                        "open": {"day": 0, "hour": 9, "minute": 0},
                        "close": {"day": 0, "hour": 22, "minute": 30},
                    }
                ],
                "nextCloseTime": "2026-10-30T04:00:00Z",
            },
            "currentOpeningHours": {
                "openNow": True,
                "periods": [
                    {
                        "open": {
                            "day": 0,
                            "hour": 9,
                            "minute": 0,
                            "date": {"year": 2026, "month": 11, "day": 1},
                        },
                        "close": {
                            "day": 0,
                            "hour": 22,
                            "minute": 30,
                            "date": {"year": 2026, "month": 11, "day": 1},
                        },
                    }
                ],
                "nextCloseTime": "2026-10-30T04:00:00Z",
            },
        }
    )
    assert place.opening_hours is not None
    assert place.opening_hours.next_close_time == "2026-10-30T04:00:00Z"
    assert place.current_opening_hours is not None
    assert place.current_opening_hours.next_close_time == "2026-10-30T04:00:00Z"


def test_opening_hours_next_open_time_and_absent_close_time():
    # Hand built: the cassette place was open, so only nextCloseTime
    # was populated there. A closed place carries nextOpenTime alone,
    # and the absent sibling must read None, never a shared default.
    from placekit.models import Place

    place = Place.from_api(
        {
            "id": "A",
            "regularOpeningHours": {"nextOpenTime": "2026-10-30T09:00:00Z"},
        }
    )
    assert place.opening_hours is not None
    assert place.opening_hours.next_open_time == "2026-10-30T09:00:00Z"
    assert place.opening_hours.next_close_time is None


def test_opening_hours_special_days_decode_dates():
    from placekit.models import Date, Place

    place = Place.from_api(
        {
            "id": "A",
            "currentOpeningHours": {
                "specialDays": [{"date": {"year": 2026, "month": 12, "day": 25}}]
            },
        }
    )
    assert place.current_opening_hours is not None
    special = place.current_opening_hours.special_days
    assert len(special) == 1
    assert isinstance(special[0].date, Date)
    assert (special[0].date.year, special[0].date.month, special[0].date.day) == (
        2026,
        12,
        25,
    )


def test_secondary_opening_hours_decode_with_type():
    from placekit.models import OpeningHours, Place

    place = Place.from_api(
        {
            "id": "A",
            "currentSecondaryOpeningHours": [
                {
                    "secondaryHoursType": "DRIVE_THROUGH",
                    "periods": [
                        {
                            "open": {"day": 1, "hour": 8, "minute": 0},
                            "close": {"day": 1, "hour": 20, "minute": 0},
                        }
                    ],
                }
            ],
        }
    )
    secondary = place.current_secondary_opening_hours
    assert len(secondary) == 1
    assert isinstance(secondary[0], OpeningHours)
    assert secondary[0].secondary_hours_type == "DRIVE_THROUGH"
    assert secondary[0].periods[0].open is not None
    assert secondary[0].periods[0].open.hour == 8
    # The paired control: no secondary keys, both lists empty.
    plain = Place.from_api({"id": "A"})
    assert plain.current_secondary_opening_hours == []
    assert plain.regular_secondary_opening_hours == []


def _assert_details_only_paths(paths):
    from placekit.fields import (
        NEARBY_SEARCH_FIELDS,
        PLACE_DETAILS_FIELDS,
        TEXT_SEARCH_FIELDS,
    )

    for path in paths:
        assert path in PLACE_DETAILS_FIELDS
        assert f"places.{path}" not in TEXT_SEARCH_FIELDS
        assert f"places.{path}" not in NEARBY_SEARCH_FIELDS


def test_round6_group1_mask_paths():
    # The secondary hours join the details default only. The search
    # defaults are unchanged, so the fields stay requestable in search
    # through a custom mask and nothing else.
    from placekit.fields import PLACE_DETAILS_FIELDS

    _assert_details_only_paths(
        ("currentSecondaryOpeningHours", "regularSecondaryOpeningHours")
    )
    assert set(FieldMask.place_details().paths) == set(PLACE_DETAILS_FIELDS)


def test_photo_uri_result_from_api_preserves_unmodelled_fields():
    # The body is cut from cassette 06 of the live smoke recordings,
    # sanitized as the smoke report prescribes: the signed photo URI
    # is reduced to scheme, host and path shape with its opaque token
    # shortened, and the photo reference is shortened the same way.
    # The sentinel key stands in for the first field Google adds to
    # this JSON form. Before the fix it reached nobody, in raw or
    # typed form, because PhotoUriResult had no raw at all.
    from placekit.models import PhotoUriResult

    result = PhotoUriResult.from_api(
        {
            "name": "places/ChIJzRBPAz5ZwokRd0AUXGm-2f8/photos/AV-0GLfkSvEkSqs",
            "photoUri": "https://lh3.googleusercontent.com/grass-cs/AABkmLexSCJl",
            "zzFutureField": 1,
        }
    )
    assert result.name == "places/ChIJzRBPAz5ZwokRd0AUXGm-2f8/photos/AV-0GLfkSvEkSqs"
    assert result.photo_uri == "https://lh3.googleusercontent.com/grass-cs/AABkmLexSCJl"
    assert result.raw["zzFutureField"] == 1
    assert result.raw["photoUri"] == result.photo_uri


def test_place_photo_skip_redirect_result_carries_raw(client):
    # Client level companion to the model test above: the raw on the
    # returned object equals the JSON form the stub served, which is
    # the property the binding change exists to provide.
    result = client.place_photo(
        "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
        max_width_px=400,
        skip_http_redirect=True,
    )
    assert isinstance(result, PhotoUriResult)
    assert result.raw == {"name": result.name, "photoUri": result.photo_uri}


# ---------------------------------------------------------------------------
# Round 6 (T1) group 2: PostalAddress completions
# ---------------------------------------------------------------------------


def test_postal_address_completion_fields_decode():
    # The base object is the cassette 02 shaped postalAddress (the
    # regionCode AU shape the offline fixture also carries). The live
    # place returned no sublocality, organization or recipients, so
    # those three keys are added by hand to that shape here.
    from placekit.models import PostalAddress

    address = PostalAddress.from_api(
        {
            "regionCode": "AU",
            "languageCode": "en",
            "postalCode": "2000",
            "administrativeArea": "New South Wales",
            "locality": "Sydney",
            "addressLines": ["Shop 1/123 George St"],
            "sublocality": "The Rocks",
            "organization": "Bianco Latte Pty Ltd",
            "recipients": ["Bianco Latte", "Deliveries Desk"],
        }
    )
    assert address.sublocality == "The Rocks"
    assert address.organization == "Bianco Latte Pty Ltd"
    assert address.recipients == ["Bianco Latte", "Deliveries Desk"]


def test_postal_address_recipients_rejects_bare_string():
    from placekit.models import PostalAddress

    with pytest.raises(DecodeError):
        PostalAddress.from_api({"recipients": "Bianco Latte"})


# ---------------------------------------------------------------------------
# Round 6 (T1) group 3: Place scalars and LocalizedText reuse
# ---------------------------------------------------------------------------


def test_place_moved_fields_decode():
    from placekit.models import Place

    place = Place.from_api(
        {
            "id": "A",
            "movedPlace": "places/ChIJnew",
            "movedPlaceId": "ChIJnew",
        }
    )
    assert place.moved_place == "places/ChIJnew"
    assert place.moved_place_id == "ChIJnew"
    plain = Place.from_api({"id": "A"})
    assert plain.moved_place is None
    assert plain.moved_place_id is None


def test_place_icon_and_opening_date_decode():
    from placekit.models import Date, Place

    place = Place.from_api(
        {
            "id": "A",
            "iconMaskBaseUri": "https://maps.example.com/icon/mask",
            "iconBackgroundColor": "#7B1FA2",
            "openingDate": {"year": 2024, "month": 3, "day": 9},
        }
    )
    assert place.icon_mask_base_uri == "https://maps.example.com/icon/mask"
    assert place.icon_background_color == "#7B1FA2"
    assert isinstance(place.opening_date, Date)
    assert (place.opening_date.year, place.opening_date.month, place.opening_date.day) == (
        2024,
        3,
        9,
    )


def test_place_localized_scalars_reuse_localized_text():
    from placekit.models import LocalizedText, Place

    place = Place.from_api(
        {
            "id": "A",
            "googleMapsTypeLabel": {"text": "Cafe", "languageCode": "en"},
            "editorialSummary": {
                "text": "A bright corner cafe",
                "languageCode": "en",
            },
        }
    )
    assert isinstance(place.google_maps_type_label, LocalizedText)
    assert place.google_maps_type_label.text == "Cafe"
    assert place.google_maps_type_label.language_code == "en"
    assert isinstance(place.editorial_summary, LocalizedText)
    assert place.editorial_summary.text == "A bright corner cafe"
    assert place.editorial_summary.language_code == "en"


def test_place_utc_offset_and_pure_service_area_decode_absent_vs_false():
    # The Rule A control pair: a sent false and a sent negative offset
    # decode as themselves, and absence decodes as None for both, so
    # the two states stay distinguishable.
    from placekit.models import Place

    place = Place.from_api(
        {"id": "A", "utcOffsetMinutes": -300, "pureServiceAreaBusiness": False}
    )
    assert place.utc_offset_minutes == -300
    assert place.pure_service_area_business is False
    plain = Place.from_api({"id": "A"})
    assert plain.utc_offset_minutes is None
    assert plain.pure_service_area_business is None


def test_round6_group3_mask_paths():
    _assert_details_only_paths(
        (
            "googleMapsTypeLabel",
            "editorialSummary",
            "iconMaskBaseUri",
            "iconBackgroundColor",
            "openingDate",
            "utcOffsetMinutes",
            "pureServiceAreaBusiness",
            "movedPlace",
            "movedPlaceId",
        )
    )


# ---------------------------------------------------------------------------
# Round 6 (T1) group 4: Review and Place.reviews
# ---------------------------------------------------------------------------


def _review_payloads() -> list[dict]:
    # Hand built in the fixture style. No cassette contains a review,
    # because reviews were in no recorded mask. The two reviews carry
    # different values in every field, so a crossed decoder line shows
    # as a wrong value instead of passing.
    return [
        {
            "name": "places/ChIJx/reviews/AAA",
            "relativePublishTimeDescription": "2 weeks ago",
            "text": {"text": "Loved the espresso", "languageCode": "en"},
            "originalText": {
                "text": "Me encanto el espresso",
                "languageCode": "es",
            },
            "rating": 5,
            "authorAttribution": {
                "displayName": "Sam Reviewer",
                "uri": "https://maps.example.com/contributor/sam",
                "photoUri": "https://maps.example.com/photo/sam",
            },
            "publishTime": "2026-10-12T08:30:00Z",
            "flagContentUri": "https://maps.example.com/flag/review-a",
            "googleMapsUri": "https://maps.google.com/?cid=111",
            "visitDate": {"year": 2026, "month": 10, "day": 11},
        },
        {
            "name": "places/ChIJx/reviews/BBB",
            "relativePublishTimeDescription": "a month ago",
            "text": {"text": "Good brunch", "languageCode": "en"},
            "originalText": {"text": "Buen brunch", "languageCode": "es"},
            "rating": 4.5,
            "authorAttribution": {
                "displayName": "Jo Critic",
                "uri": "https://maps.example.com/contributor/jo",
                "photoUri": "https://maps.example.com/photo/jo",
            },
            "publishTime": "2026-09-01T10:00:00Z",
            "flagContentUri": "https://maps.example.com/flag/review-b",
            "googleMapsUri": "https://maps.google.com/?cid=222",
            "visitDate": {"year": 2026, "month": 8, "day": 30},
        },
    ]


def test_place_reviews_decode_full_review_objects():
    from placekit.models import Place

    place = Place.from_api({"id": "ChIJx", "reviews": _review_payloads()})
    assert len(place.reviews) == 2
    first = place.reviews[0]
    assert first.name == "places/ChIJx/reviews/AAA"
    assert first.relative_publish_time_description == "2 weeks ago"
    assert first.text is not None and first.text.text == "Loved the espresso"
    assert first.text.language_code == "en"
    assert first.original_text is not None
    assert first.original_text.text == "Me encanto el espresso"
    assert first.original_text.language_code == "es"
    assert first.rating == 5.0
    assert first.author_attribution is not None
    assert first.author_attribution.display_name == "Sam Reviewer"
    assert first.author_attribution.uri == "https://maps.example.com/contributor/sam"
    assert first.author_attribution.photo_uri == "https://maps.example.com/photo/sam"
    assert first.publish_time == "2026-10-12T08:30:00Z"
    assert first.flag_content_uri == "https://maps.example.com/flag/review-a"
    assert first.google_maps_uri == "https://maps.google.com/?cid=111"
    assert first.visit_date is not None
    assert (first.visit_date.year, first.visit_date.month, first.visit_date.day) == (
        2026,
        10,
        11,
    )
    second = place.reviews[1]
    assert second.name == "places/ChIJx/reviews/BBB"
    assert second.rating == 4.5
    assert second.text is not None and second.text.text == "Good brunch"
    assert second.publish_time == "2026-09-01T10:00:00Z"


def test_review_rating_keeps_fraction_and_whole_forms():
    from placekit.models import Review

    fraction = Review.from_api({"rating": 4.5})
    assert fraction.rating == 4.5
    whole = Review.from_api({"rating": 5})
    assert whole.rating == 5.0
    assert isinstance(whole.rating, float)


def test_place_without_reviews_has_empty_list():
    from placekit.models import Place

    assert Place.from_api({"id": "A"}).reviews == []


def test_round6_group4_mask_paths():
    _assert_details_only_paths(("reviews",))


# ---------------------------------------------------------------------------
# Round 6 (T1) group 5: the 23 dine, service and amenity flags
# ---------------------------------------------------------------------------

_FLAG_FIELDS = [
    ("takeout", "takeout"),
    ("delivery", "delivery"),
    ("dine_in", "dineIn"),
    ("curbside_pickup", "curbsidePickup"),
    ("reservable", "reservable"),
    ("serves_breakfast", "servesBreakfast"),
    ("serves_lunch", "servesLunch"),
    ("serves_dinner", "servesDinner"),
    ("serves_beer", "servesBeer"),
    ("serves_wine", "servesWine"),
    ("serves_brunch", "servesBrunch"),
    ("serves_vegetarian_food", "servesVegetarianFood"),
    ("outdoor_seating", "outdoorSeating"),
    ("live_music", "liveMusic"),
    ("menu_for_children", "menuForChildren"),
    ("serves_cocktails", "servesCocktails"),
    ("serves_dessert", "servesDessert"),
    ("serves_coffee", "servesCoffee"),
    ("good_for_children", "goodForChildren"),
    ("allows_dogs", "allowsDogs"),
    ("restroom", "restroom"),
    ("good_for_groups", "goodForGroups"),
    ("good_for_watching_sports", "goodForWatchingSports"),
]


@pytest.mark.parametrize("attribute,wire", _FLAG_FIELDS)
def test_place_dine_service_amenity_flags_decode(attribute, wire):
    # Parametrized over all 23 rather than sampled, so a dropped row
    # in the table is a failing parameter, not a silent gap.
    from placekit.models import Place

    place = Place.from_api({"id": "A", wire: True})
    assert getattr(place, attribute) is True
    # Exactly one flag is set on the whole place. Every other flag
    # reads None, because absence is not a fabricated False.
    set_flags = [
        name for name, _ in _FLAG_FIELDS if getattr(place, name) is not None
    ]
    assert set_flags == [attribute]


def test_place_flag_sent_false_is_not_absence():
    from placekit.models import Place

    place = Place.from_api({"id": "A", "dineIn": False})
    assert place.dine_in is False


def test_round6_group5_mask_paths():
    _assert_details_only_paths([wire for _, wire in _FLAG_FIELDS])


# ---------------------------------------------------------------------------
# Round 6 (T1) group 6: the boolean option objects
# ---------------------------------------------------------------------------


def test_payment_parking_accessibility_options_decode():
    # One payload carrying all three parents, each with a mix of true
    # and false leaves and at least one leaf omitted per object. The
    # omission assertions are the Rule A control: an omitted leaf
    # reads None, never a fabricated False.
    from placekit.models import Place

    place = Place.from_api(
        {
            "id": "A",
            "paymentOptions": {
                "acceptsCreditCards": True,
                "acceptsDebitCards": False,
                "acceptsNfc": True,
            },
            "parkingOptions": {
                "freeParkingLot": True,
                "paidParkingLot": False,
                "paidStreetParking": True,
                "valetParking": False,
                "paidGarageParking": True,
            },
            "accessibilityOptions": {
                "wheelchairAccessibleParking": True,
                "wheelchairAccessibleRestroom": False,
                "wheelchairAccessibleSeating": True,
            },
        }
    )
    payment = place.payment_options
    assert payment is not None
    assert payment.accepts_credit_cards is True
    assert payment.accepts_debit_cards is False
    assert payment.accepts_cash_only is None
    assert payment.accepts_nfc is True
    parking = place.parking_options
    assert parking is not None
    assert parking.free_parking_lot is True
    assert parking.paid_parking_lot is False
    assert parking.free_street_parking is None
    assert parking.paid_street_parking is True
    assert parking.valet_parking is False
    assert parking.free_garage_parking is None
    assert parking.paid_garage_parking is True
    accessibility = place.accessibility_options
    assert accessibility is not None
    assert accessibility.wheelchair_accessible_parking is True
    assert accessibility.wheelchair_accessible_entrance is None
    assert accessibility.wheelchair_accessible_restroom is False
    assert accessibility.wheelchair_accessible_seating is True
    plain = Place.from_api({"id": "A"})
    assert plain.payment_options is None
    assert plain.parking_options is None
    assert plain.accessibility_options is None


def test_round6_group6_mask_paths():
    _assert_details_only_paths(
        ("paymentOptions", "parkingOptions", "accessibilityOptions")
    )


# ---------------------------------------------------------------------------
# Round 6 (T1) group 7: TimeZone, the summaries and the consumer alert
# ---------------------------------------------------------------------------


def test_time_zone_id_decodes_and_version_stays_raw():
    from placekit.models import Place

    place = Place.from_api(
        {"id": "A", "timeZone": {"id": "Australia/Sydney", "version": "2025a"}}
    )
    assert place.time_zone is not None
    assert place.time_zone.id == "Australia/Sydney"
    # The version is database metadata under the stated exception: it
    # is not an attribute of TimeZone and stays reachable in raw.
    assert not hasattr(place.time_zone, "version")
    assert place.raw["timeZone"]["version"] == "2025a"


def test_generative_and_review_summary_localized_text_decode():
    from placekit.models import LocalizedText, Place

    place = Place.from_api(
        {
            "id": "A",
            "generativeSummary": {
                "overview": {"text": "A sunny corner cafe", "languageCode": "en"}
            },
            "reviewSummary": {
                "text": {"text": "Loved for its espresso", "languageCode": "en"}
            },
        }
    )
    assert place.generative_summary is not None
    assert isinstance(place.generative_summary.overview, LocalizedText)
    assert place.generative_summary.overview.text == "A sunny corner cafe"
    assert place.review_summary is not None
    assert isinstance(place.review_summary.text, LocalizedText)
    assert place.review_summary.text.text == "Loved for its espresso"


def test_consumer_alert_overview_and_language_decode():
    # The alert overview is a plain string on the wire, with the
    # language as its sibling. Decoding it through LocalizedText
    # would raise on the string, so this fails on that misread.
    from placekit.models import Place

    place = Place.from_api(
        {
            "id": "A",
            "consumerAlert": {
                "overview": "This place may have closed",
                "languageCode": "en",
            },
        }
    )
    assert place.consumer_alert is not None
    assert place.consumer_alert.overview == "This place may have closed"
    assert place.consumer_alert.language_code == "en"


def test_round6_group7_mask_paths():
    _assert_details_only_paths(
        ("timeZone", "generativeSummary", "reviewSummary", "consumerAlert")
    )


# ---------------------------------------------------------------------------
# Round 6 (T1) group 8: GoogleMapsLinks, PriceRange and Money
# ---------------------------------------------------------------------------


def test_google_maps_links_decode_all_five_uris():
    from placekit.models import Place

    place = Place.from_api(
        {
            "id": "A",
            "googleMapsLinks": {
                "directionsUri": "https://maps.example.com/directions/A",
                "placeUri": "https://maps.example.com/place/A",
                "writeAReviewUri": "https://maps.example.com/write/A",
                "reviewsUri": "https://maps.example.com/reviews/A",
                "photosUri": "https://maps.example.com/photos/A",
            },
        }
    )
    links = place.google_maps_links
    assert links is not None
    assert links.directions_uri == "https://maps.example.com/directions/A"
    assert links.place_uri == "https://maps.example.com/place/A"
    assert links.write_a_review_uri == "https://maps.example.com/write/A"
    assert links.reviews_uri == "https://maps.example.com/reviews/A"
    assert links.photos_uri == "https://maps.example.com/photos/A"


def test_price_range_money_decodes_units_from_string():
    # Units arrive as a JSON string, because the field is an int64, and
    # decode to a real int. Nanos arrive as a plain number.
    from placekit.models import Place

    place = Place.from_api(
        {
            "id": "A",
            "priceRange": {
                "startPrice": {
                    "currencyCode": "AUD",
                    "units": "10",
                    "nanos": 500000000,
                }
            },
        }
    )
    price_range = place.price_range
    assert price_range is not None
    assert price_range.start_price is not None
    assert price_range.start_price.currency_code == "AUD"
    assert price_range.start_price.units == 10
    assert type(price_range.start_price.units) is int
    assert price_range.start_price.nanos == 500000000
    # An absent end price is an open ended range, never a zero Money.
    assert price_range.end_price is None


def test_money_under_fuel_options_stays_raw():
    # The container rule: Money is typed only where it is reachable.
    # The identical shape under fuelOptions is never reached by a
    # Place decode, so the whole fuel container stays raw-only.
    from placekit.models import Place

    place = Place.from_api(
        {
            "id": "A",
            "fuelOptions": {
                "fuelPrices": [
                    {
                        "type": "REGULAR_UNLEADED",
                        "price": {
                            "currencyCode": "AUD",
                            "units": "1",
                            "nanos": 899000000,
                        },
                        "updateTime": "2026-10-29T00:00:00Z",
                    }
                ]
            },
        }
    )
    assert not hasattr(place, "fuel_options")
    fuel_price = place.raw["fuelOptions"]["fuelPrices"][0]
    assert fuel_price["price"]["units"] == "1"
    assert fuel_price["price"]["nanos"] == 899000000


def test_round6_group8_mask_paths():
    _assert_details_only_paths(("googleMapsLinks", "priceRange"))


# ---------------------------------------------------------------------------
# Round 6 (T1) group 9: evChargeOptions completed
# ---------------------------------------------------------------------------


def test_ev_charge_options_decode_aggregation_whole():
    # The three availability fields are typed with the rest, so the
    # whole Message lands rather than as a shell around raw.
    from placekit.models import Place

    place = Place.from_api(
        {
            "id": "A",
            "evChargeOptions": {
                "connectorCount": 6,
                "connectorAggregation": [
                    {
                        "type": "CCS_COMBO_1",
                        "maxChargeRateKw": 50.5,
                        "count": 4,
                        "availableCount": 3,
                        "outOfServiceCount": 1,
                        "availabilityLastUpdateTime": "2026-10-29T06:00:00Z",
                    },
                    {
                        "type": "TESLA",
                        "maxChargeRateKw": 250,
                        "count": 2,
                    },
                ],
            },
        }
    )
    ev = place.ev_charge_options
    assert ev is not None
    assert ev.connector_count == 6
    assert len(ev.connector_aggregation) == 2
    first = ev.connector_aggregation[0]
    assert first.type == "CCS_COMBO_1"
    assert first.max_charge_rate_kw == 50.5
    assert first.count == 4
    assert first.available_count == 3
    assert first.out_of_service_count == 1
    assert first.availability_last_update_time == "2026-10-29T06:00:00Z"
    second = ev.connector_aggregation[1]
    assert second.type == "TESLA"
    assert second.max_charge_rate_kw == 250.0
    assert isinstance(second.max_charge_rate_kw, float)
    assert second.count == 2
    assert second.available_count is None
    assert second.out_of_service_count is None
    assert second.availability_last_update_time is None
    assert Place.from_api({"id": "A"}).ev_charge_options is None


def test_round6_group9_mask_paths():
    _assert_details_only_paths(("evChargeOptions",))


# ---------------------------------------------------------------------------
# Round 6 (T1) group 10: addressDescriptor
# ---------------------------------------------------------------------------


def test_address_descriptor_decodes_landmark_relations_and_distances():
    # Two landmarks and one area, with every name paired to a
    # different place id, so a crossed name and id line shows as a
    # wrong pair rather than passing.
    from placekit.models import Place

    place = Place.from_api(
        {
            "id": "A",
            "addressDescriptor": {
                "landmarks": [
                    {
                        "name": "places/L1",
                        "placeId": "L1",
                        "displayName": {
                            "text": "Central Station",
                            "languageCode": "en",
                        },
                        "types": ["train_station", "transit_station"],
                        "spatialRelationship": "NEAR",
                        "straightLineDistanceMeters": 120.5,
                        "travelDistanceMeters": 210,
                    },
                    {
                        "name": "places/L2",
                        "placeId": "L2",
                        "displayName": {
                            "text": "Botanic Gardens",
                            "languageCode": "en",
                        },
                        "types": ["park"],
                        "straightLineDistanceMeters": 45,
                    },
                ],
                "areas": [
                    {
                        "name": "places/A1",
                        "placeId": "A1",
                        "displayName": {
                            "text": "The Rocks",
                            "languageCode": "en",
                        },
                        "containment": "WITHIN",
                    }
                ],
            },
        }
    )
    descriptor = place.address_descriptor
    assert descriptor is not None
    assert len(descriptor.landmarks) == 2
    first = descriptor.landmarks[0]
    assert first.name == "places/L1"
    assert first.place_id == "L1"
    assert first.display_name is not None
    assert first.display_name.text == "Central Station"
    assert first.types == ["train_station", "transit_station"]
    assert first.spatial_relationship == "NEAR"
    assert first.straight_line_distance_meters == 120.5
    assert first.travel_distance_meters == 210.0
    second = descriptor.landmarks[1]
    assert second.name == "places/L2"
    assert second.place_id == "L2"
    assert second.types == ["park"]
    assert second.spatial_relationship is None
    assert second.straight_line_distance_meters == 45.0
    assert second.travel_distance_meters is None
    assert len(descriptor.areas) == 1
    area = descriptor.areas[0]
    assert area.name == "places/A1"
    assert area.place_id == "A1"
    assert area.display_name is not None
    assert area.display_name.text == "The Rocks"
    assert area.containment == "WITHIN"


def test_landmark_types_rejects_bare_string():
    from placekit import ConfigError
    from placekit.models import Landmark

    with pytest.raises(ConfigError):
        Landmark(types="park")


def test_round6_group10_mask_paths():
    _assert_details_only_paths(("addressDescriptor",))


# ---------------------------------------------------------------------------
# Round 6 (T1) group 11: typed routing summaries
# ---------------------------------------------------------------------------


def test_nearby_routing_summaries_are_typed(client):
    # The nearby fixture carries the same routing summary shape as the
    # text fixture, so the second reader is pinned too.
    from placekit.models import RoutingSummary

    result = client.nearby_search(
        (-33.8668, 151.2071),
        800.0,
        fields=["places.id", "routingSummaries"],
    )
    assert len(result.routing_summaries) == 1
    summary = result.routing_summaries[0]
    assert isinstance(summary, RoutingSummary)
    assert summary.legs[0].distance_meters == 5587
    assert summary.legs[0].duration == "601s"
    assert summary.directions_uri == "https://maps.google.com/?directions=example"
    assert result.raw["routingSummaries"][0]["directionsUri"] == (
        "https://maps.google.com/?directions=example"
    )


def test_routing_summary_duration_stays_a_string():
    from placekit.models import RoutingSummary

    summary = RoutingSummary.from_api(
        {"legs": [{"duration": "582s", "distanceMeters": 10}]}
    )
    assert summary.legs[0].duration == "582s"
    assert isinstance(summary.legs[0].duration, str)
    assert summary.legs[0].distance_meters == 10
    assert summary.directions_uri is None


# ---------------------------------------------------------------------------
# Round 6 repair: boolean leaves are validated, not stored verbatim
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["false", "yes", 0, 1, [], {}])
def test_round6_repair_bool_leaves_reject_non_bools(bad):
    # The wire shape of a boolean leaf is a real boolean or nothing. A
    # string like "false" stored verbatim would read as truthy, so a
    # switched off flag would read as on. Every leaf family rejects it.
    from placekit.exceptions import DecodeError
    from placekit.models import OpeningHours, Place

    with pytest.raises(DecodeError):
        Place.from_api({"id": "A", "takeout": bad})
    with pytest.raises(DecodeError):
        Place.from_api({"id": "A", "paymentOptions": {"acceptsCreditCards": bad}})
    with pytest.raises(DecodeError):
        OpeningHours.from_api({"openNow": bad})


def test_round6_repair_bool_leaves_accept_real_bools_and_absence():
    from placekit.models import OpeningHours, Place

    place = Place.from_api(
        {
            "id": "A",
            "takeout": False,
            "paymentOptions": {"acceptsCreditCards": True},
        }
    )
    assert place.takeout is False
    assert place.payment_options is not None
    assert place.payment_options.accepts_credit_cards is True
    assert place.delivery is None
    assert OpeningHours.from_api({}).open_now is None
    assert OpeningHours.from_api({"openNow": True}).open_now is True


def test_round6_repair_money_units_infinity_is_decode_error():
    # int(float("inf")) raises OverflowError, which used to escape the
    # integer decoder bare. It is a DecodeError now.
    from placekit.exceptions import DecodeError
    from placekit.models import Money

    with pytest.raises(DecodeError):
        Money.from_api({"currencyCode": "USD", "units": float("inf"), "nanos": 0})


# ---------------------------------------------------------------------------
# Round 7: child raw and StringMatch offsets
# ---------------------------------------------------------------------------

_SENTINEL = {"unmodelledSentinel": {"nested": [1, 2, 3]}}

_CHILD_RAW_CASES = [
    (LocalizedText, {"text": "Cafe", "languageCode": "en"}),
    (LatLng, {"latitude": -33.86, "longitude": 151.2}),
    (AuthorAttribution, {"displayName": "A", "uri": "u", "photoUri": "p"}),
    (Attribution, {"provider": "x", "providerUri": "y"}),
    (Photo, {"name": "places/x/photos/y", "widthPx": 100, "heightPx": 80}),
    (Date, {"year": 2026, "month": 10, "day": 30}),
    (OpeningPoint, {"day": 5, "hour": 9, "minute": 30}),
    (
        Period,
        {"open": {"day": 5, "hour": 9}, "close": {"day": 5, "hour": 17}},
    ),
    (SpecialDay, {"date": {"year": 2026, "month": 12, "day": 25}}),
    (
        OpeningHours,
        {"openNow": True, "weekdayDescriptions": ["Friday: 9 AM to 5 PM"]},
    ),
    (
        AddressComponent,
        {"longText": "George Street", "shortText": "George St", "types": ["route"]},
    ),
    (PlusCode, {"globalCode": "4RRH46J5+JV", "compoundCode": "46J5+JV Sydney"}),
    (
        Viewport,
        {
            "low": {"latitude": -33.87, "longitude": 151.2},
            "high": {"latitude": -33.86, "longitude": 151.21},
        },
    ),
    (
        PostalAddress,
        {"regionCode": "AU", "locality": "Sydney", "addressLines": ["1 George St"]},
    ),
    (
        Review,
        {
            "name": "places/x/reviews/y",
            "rating": 5,
            "text": {"text": "Great", "languageCode": "en"},
        },
    ),
    (PaymentOptions, {"acceptsCreditCards": True, "acceptsNfc": False}),
    (ParkingOptions, {"freeParkingLot": True}),
    (AccessibilityOptions, {"wheelchairAccessibleEntrance": True}),
    (TimeZone, {"id": "Australia/Sydney"}),
    (GenerativeSummary, {"overview": {"text": "Nice", "languageCode": "en"}}),
    (ReviewSummary, {"text": {"text": "Loved", "languageCode": "en"}}),
    (ConsumerAlert, {"overview": "Alert", "languageCode": "en"}),
    (GoogleMapsLinks, {"directionsUri": "https://example.com/dir"}),
    (Money, {"currencyCode": "AUD", "units": "12", "nanos": 500000000}),
    (PriceRange, {"startPrice": {"currencyCode": "AUD", "units": "10"}}),
    (ConnectorAggregation, {"type": "CCS", "count": 4}),
    (
        EvChargeOptions,
        {"connectorCount": 4, "connectorAggregation": [{"type": "CCS", "count": 4}]},
    ),
    (Landmark, {"name": "places/a", "placeId": "a", "types": ["park"]}),
    (Area, {"name": "places/b", "placeId": "b", "containment": "WITHIN"}),
    (
        AddressDescriptor,
        {
            "landmarks": [{"name": "places/a", "placeId": "a"}],
            "areas": [{"name": "places/b", "placeId": "b"}],
        },
    ),
    (Leg, {"duration": "601s", "distanceMeters": 5587}),
    (
        RoutingSummary,
        {
            "legs": [{"duration": "601s", "distanceMeters": 5587}],
            "directionsUri": "https://example.com",
        },
    ),
    (
        FormattedText,
        {"text": "Bianco", "matches": [{"startOffset": 0, "endOffset": 6}]},
    ),
    (StringMatch, {"startOffset": 0, "endOffset": 6}),
]


@pytest.mark.parametrize(
    "model,payload",
    _CHILD_RAW_CASES,
    ids=[model.__name__ for model, _ in _CHILD_RAW_CASES],
)
def test_child_raw_carries_the_child_payload(model, payload):
    # Every JSON child class preserves its own payload slice on raw,
    # sentinel included, so a child passed on alone has shed nothing.
    data = copy.deepcopy(payload)
    data.update(copy.deepcopy(_SENTINEL))
    decoded = model.from_api(data)
    assert decoded.raw == data
    assert decoded.raw["unmodelledSentinel"] == {"nested": [1, 2, 3]}
    # The raw is a deep copy, so mutating the caller dict afterwards
    # does not move it.
    data["unmodelledSentinel"]["nested"].append(4)
    assert decoded.raw["unmodelledSentinel"] == {"nested": [1, 2, 3]}


def test_child_raw_excluded_from_equality_and_repr():
    first = LocalizedText.from_api({"text": "Cafe", "sentinel": 1})
    second = LocalizedText.from_api({"text": "Cafe", "sentinel": 2})
    assert first.raw != second.raw
    assert first == second
    assert "sentinel" not in repr(first)


def test_latlng_hash_survives_child_raw():
    point = LatLng.from_api(
        {"latitude": -33.86, "longitude": 151.2, "sentinel": 1}
    )
    assert len({point, point}) == 1
    assert hash(point) == hash(LatLng(latitude=-33.86, longitude=151.2))


def test_child_raw_deep_copy_nested_through_place():
    # The nested form of the deep copy rule, where a shallow copy
    # would hide: mutating the opening hours object inside a decoded
    # Place payload must not move the OpeningHours raw on the place.
    payload = {
        "id": "ChIJx",
        "regularOpeningHours": {
            "openNow": True,
            "weekdayDescriptions": ["Friday: 9 AM to 5 PM"],
        },
    }
    place = Place.from_api(payload)
    payload["regularOpeningHours"]["openNow"] = False
    payload["regularOpeningHours"]["weekdayDescriptions"].append(
        "Saturday: closed"
    )
    hours = place.opening_hours
    assert hours is not None
    assert hours.raw["openNow"] is True
    assert hours.raw["weekdayDescriptions"] == ["Friday: 9 AM to 5 PM"]


def test_string_match_missing_start_offset_is_none_not_zero():
    # Cut from cassette 04 of the live recording, whose matches carry
    # only endOffset. The absent start offset must read None, never a
    # fabricated 0.
    formatted = FormattedText.from_api(
        {"text": "Williamsburg Bridge", "matches": [{"endOffset": 19}]}
    )
    match = formatted.matches[0]
    assert match.end_offset == 19
    assert match.start_offset is None


def test_string_match_explicit_zero_start_offset_survives():
    formatted = FormattedText.from_api(
        {"text": "Bianco Latte", "matches": [{"startOffset": 0, "endOffset": 6}]}
    )
    match = formatted.matches[0]
    assert match.start_offset == 0
    assert match.start_offset is not None
    assert match.end_offset == 6


# ---------------------------------------------------------------------------
# Round 16 (T2), raw fidelity through the core
# ---------------------------------------------------------------------------
#
# Raw through the client is now the response body itself, parsed once
# in Python, while attributes keep decoding from the core typed tree.
# The fidelity pins below each failed on the head before this round,
# through a drop or through a kill, for the reason their text states.
# Three pins are controls by design and passed before the round as
# they pass after it, and they are exempt from the fail first rule
# by name. The exempt pins are
# test_photo_uri_raw_equals_the_served_body and
# test_photo_uri_unmodelled_null_key_stays_in_raw below, and the
# core guard pin in the Rust suite that keeps request bodies byte
# identical.


def _serve_details(raw_response, mutate):
    data = json.loads(fixture_bytes("place_details.json"))
    mutate(data)
    raw_response(200, json.dumps(data).encode())


def test_empty_types_list_keeps_its_key_in_raw(client, raw_response):
    # An explicitly empty modelled list used to drop from raw at the
    # core reserialization (Vec::is_empty guard), so raw could not
    # tell a carried empty list from an unreturned one.
    _serve_details(raw_response, lambda data: data.update(types=[]))
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert place.types == []
    assert place.raw["types"] == []


def test_empty_object_lists_keep_their_keys_in_raw(client, raw_response):
    def mutate(data):
        data["photos"] = []
        data["addressComponents"] = []

    _serve_details(raw_response, mutate)
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert place.photos == []
    assert place.address_components == []
    assert place.raw["photos"] == []
    assert place.raw["addressComponents"] == []


def test_empty_weekday_descriptions_keep_their_key_in_child_raw(
    client, raw_response
):
    # The nested case. The raw threading must reach child models, not
    # only the top level object.
    def mutate(data):
        data["regularOpeningHours"]["weekdayDescriptions"] = []

    _serve_details(raw_response, mutate)
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    hours = place.opening_hours
    assert hours is not None
    assert hours.weekday_descriptions == []
    assert hours.raw["weekdayDescriptions"] == []


def test_empty_types_list_in_search_place_raw(client, raw_response):
    data = json.loads(fixture_bytes("text_search.json"))
    data["places"][0]["types"] = []
    raw_response(200, json.dumps(data).encode())
    result = client.text_search("cafes in Sydney")
    assert result.places[0].types == []
    assert result.places[0].raw["types"] == []


def test_empty_types_list_in_prediction_raw(client, raw_response):
    data = json.loads(fixture_bytes("autocomplete.json"))
    data["suggestions"][0]["placePrediction"]["types"] = []
    raw_response(200, json.dumps(data).encode())
    result = client.autocomplete("Bianco")
    prediction = result.place_predictions[0]
    assert prediction.types == []
    assert prediction.raw["types"] == []


def test_class2_null_short_text_reads_none_and_stays_in_raw(
    client, raw_response
):
    # Class 2. A null in a plain string position killed the whole
    # response at the core. The Python layer tolerates the class and
    # stores None, and raw keeps the key with the null.
    def mutate(data):
        data["addressComponents"][0]["shortText"] = None

    _serve_details(raw_response, mutate)
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    component = place.address_components[0]
    assert component.short_text is None
    assert "shortText" in component.raw
    assert component.raw["shortText"] is None


def test_class2_null_attribution_photo_uri_at_depth(client, raw_response):
    def mutate(data):
        data["photos"][0]["authorAttributions"][0]["photoUri"] = None

    _serve_details(raw_response, mutate)
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    attribution = place.photos[0].author_attributions[0]
    assert attribution.photo_uri is None
    assert "photoUri" in attribution.raw
    assert attribution.raw["photoUri"] is None


def test_class2_null_place_id_on_a_prediction(client, raw_response):
    data = json.loads(fixture_bytes("autocomplete.json"))
    data["suggestions"][0]["placePrediction"]["placeId"] = None
    raw_response(200, json.dumps(data).encode())
    result = client.autocomplete("Bianco")
    prediction = result.place_predictions[0]
    assert prediction.place_id is None
    assert "placeId" in prediction.raw
    assert prediction.raw["placeId"] is None


def test_class4_null_element_inside_types_on_details(client, raw_response):
    # Class 4. A null element inside a modelled string list killed
    # the whole response at the core. The element now lands as None
    # at its wire index, with no dropping or reordering.
    def mutate(data):
        data["types"] = ["cafe", None]

    _serve_details(raw_response, mutate)
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert place.types == ["cafe", None]
    assert place.raw["types"] == ["cafe", None]


def test_class4_null_element_inside_types_keeps_the_search_page(
    client, raw_response
):
    data = json.loads(fixture_bytes("text_search.json"))
    data["places"][0]["types"] = ["cafe", None]
    raw_response(200, json.dumps(data).encode())
    result = client.text_search("cafes in Sydney")
    assert len(result.places) == 2
    assert result.places[0].types == ["cafe", None]
    assert result.places[0].raw["types"] == ["cafe", None]


def test_class4_null_element_inside_prediction_types(client, raw_response):
    data = json.loads(fixture_bytes("autocomplete.json"))
    data["suggestions"][0]["placePrediction"]["types"] = ["cafe", None]
    raw_response(200, json.dumps(data).encode())
    result = client.autocomplete("Bianco")
    prediction = result.place_predictions[0]
    assert prediction.types == ["cafe", None]
    assert prediction.raw["types"] == ["cafe", None]


def test_photo_uri_raw_equals_the_served_body(client, raw_response):
    # Control pin, exempt from the fail first rule by name (see the
    # section header). The two key body already round tripped before
    # this round. The pin now guards the verbatim body path itself.
    body = {
        "name": "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
        "photoUri": "http://127.0.0.1/photo-image",
    }
    raw_response(200, json.dumps(body).encode())
    result = client.place_photo(
        body["name"], max_width_px=400, skip_http_redirect=True
    )
    assert isinstance(result, PhotoUriResult)
    assert result.raw == body


def test_photo_uri_null_photo_uri_reads_none_and_stays_in_raw(
    client, raw_response
):
    body = {
        "name": "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
        "photoUri": None,
    }
    raw_response(200, json.dumps(body).encode())
    result = client.place_photo(
        body["name"], max_width_px=400, skip_http_redirect=True
    )
    assert result.photo_uri is None
    assert "photoUri" in result.raw
    assert result.raw["photoUri"] is None


def test_photo_uri_null_name_reads_none_and_stays_in_raw(
    client, raw_response
):
    body = {"name": None, "photoUri": "http://127.0.0.1/photo-image"}
    raw_response(200, json.dumps(body).encode())
    result = client.place_photo(
        "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
        max_width_px=400,
        skip_http_redirect=True,
    )
    assert result.name is None
    assert "name" in result.raw
    assert result.raw["name"] is None


def test_photo_uri_unmodelled_null_key_stays_in_raw(client, raw_response):
    # Control pin, exempt from the fail first rule by name (see the
    # section header). Unmodelled fields rode the flattened extra map
    # verbatim before this round and must keep doing so.
    body = {
        "name": "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample",
        "photoUri": "http://127.0.0.1/photo-image",
        "zzFutureField": None,
    }
    raw_response(200, json.dumps(body).encode())
    result = client.place_photo(
        body["name"], max_width_px=400, skip_http_redirect=True
    )
    assert "zzFutureField" in result.raw
    assert result.raw["zzFutureField"] is None


def test_empty_display_name_text_keeps_its_key_in_child_raw(
    client, raw_response
):
    # An explicitly empty string on a plain string field used to drop
    # from raw under the is_empty_string guard. Only raw membership
    # moves. The attribute read the empty string all along.
    def mutate(data):
        data["displayName"]["text"] = ""

    _serve_details(raw_response, mutate)
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert place.display_name is not None
    assert place.display_name.text == ""
    assert "text" in place.display_name.raw
    assert place.display_name.raw["text"] == ""


def test_zero_photo_width_keeps_its_key_in_raw(client, raw_response):
    def mutate(data):
        data["photos"][0]["widthPx"] = 0

    _serve_details(raw_response, mutate)
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    photo = place.photos[0]
    assert photo.width_px == 0
    assert "widthPx" in photo.raw
    assert photo.raw["widthPx"] == 0


def test_zero_photo_height_keeps_its_key_in_raw(client, raw_response):
    def mutate(data):
        data["photos"][0]["heightPx"] = 0

    _serve_details(raw_response, mutate)
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    photo = place.photos[0]
    assert photo.height_px == 0
    assert "heightPx" in photo.raw
    assert photo.raw["heightPx"] == 0


def test_zero_date_component_keeps_its_key_in_child_raw(
    client, raw_response
):
    def mutate(data):
        data["regularOpeningHours"]["periods"][0]["open"]["date"] = {
            "year": 0,
            "month": 1,
            "day": 7,
        }

    _serve_details(raw_response, mutate)
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    hours = place.opening_hours
    assert hours is not None
    date = hours.periods[0].open.date
    assert date is not None
    assert date.year == 0
    assert "year" in date.raw
    assert date.raw["year"] == 0


def test_partial_location_raw_carries_no_fabricated_longitude(
    client, raw_response
):
    # Both halves in one pin. The typed attribute keeps the core
    # leniency default, because the typed path does not change. The
    # raw location is the wire object, latitude alone, with no
    # longitude key the wire never sent.
    def mutate(data):
        data["location"] = {"latitude": -33.866784}

    _serve_details(raw_response, mutate)
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert place.location is not None
    assert place.location.latitude == pytest.approx(-33.866784)
    assert place.location.longitude == 0.0
    assert place.raw["location"] == {"latitude": -33.866784}


def test_empty_viewport_raw_fabricates_no_corners(client, raw_response):
    # The viewport case of the same fabrication family one level
    # down. The core viewport type holds both corners as non
    # optional defaulted values, so the typed tree always carries
    # both, and an empty viewport object on the wire used to hand
    # each corner a raw holding the zero pair the wire never sent.
    # The typed attributes keep the core leniency defaults. Only
    # the corner raws stop inventing the pair.
    _serve_details(raw_response, lambda data: data.update(viewport={}))
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert place.viewport is not None
    assert place.raw["viewport"] == {}
    assert place.viewport.low.latitude == 0.0
    assert place.viewport.low.longitude == 0.0
    assert place.viewport.high.latitude == 0.0
    assert place.viewport.high.longitude == 0.0
    assert place.viewport.low.raw == {}
    assert place.viewport.high.raw == {}


def test_viewport_with_only_a_low_corner_fabricates_no_high_corner(
    client, raw_response
):
    # A field mask can name one corner alone, so a partial
    # viewport is a reachable wire shape, not a synthetic one.
    def mutate(data):
        data["viewport"] = {"low": {"latitude": -33.868}}

    _serve_details(raw_response, mutate)
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert place.viewport is not None
    assert place.viewport.low.raw == {"latitude": -33.868}
    assert place.viewport.low.longitude == 0.0
    assert place.viewport.high.raw == {}
    assert place.viewport.high.latitude == 0.0
    assert place.viewport.high.longitude == 0.0


def test_viewport_with_only_a_high_corner_fabricates_no_low_corner(
    client, raw_response
):
    def mutate(data):
        data["viewport"] = {"high": {"longitude": 151.2084}}

    _serve_details(raw_response, mutate)
    place = client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert place.viewport is not None
    assert place.viewport.high.raw == {"longitude": 151.2084}
    assert place.viewport.high.latitude == 0.0
    assert place.viewport.low.raw == {}
    assert place.viewport.low.latitude == 0.0
    assert place.viewport.low.longitude == 0.0


def test_model_layer_non_string_name_never_becomes_an_id():
    # The id fallback derives an id from the resource name, and a
    # name that is not a string carries no id to derive. A numeric
    # name used to pass through a string coercion and hand back
    # its decimal form as the id, a value the wire never sent. A
    # string name still derives its id exactly as before.
    assert Place.from_api({"name": "places/ChIJx"}).id == "ChIJx"
    assert Place.from_api({"name": 123}).id == ""


# Branch A pins for classes 1 and 3. The core forwards the explicit
# null and the documented Python contract decides it, the contract
# test_explicit_null_in_a_list_field_is_a_decode_error pins at the
# model layer. The whole response is still lost, exactly as before
# this round. What moves is the origin of the error, and each pin
# asserts the stable origin marker of its position family plus the
# HTTP status the core threaded across, so each pin fails on the
# head before this round, where the core raised with serde wording.


def test_branch_a_null_types_list_raises_the_python_decoder_error(
    client, raw_response
):
    _serve_details(raw_response, lambda data: data.update(types=None))
    with pytest.raises(DecodeError) as excinfo:
        client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert excinfo.value.status_code == 200
    assert "Place payload key 'types' is not a list" in excinfo.value.message


def test_branch_a_null_weekday_descriptions_raises_the_python_decoder_error(
    client, raw_response
):
    def mutate(data):
        data["regularOpeningHours"]["weekdayDescriptions"] = None

    _serve_details(raw_response, mutate)
    with pytest.raises(DecodeError) as excinfo:
        client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert excinfo.value.status_code == 200
    assert (
        "OpeningHours payload key 'weekdayDescriptions' is not a list"
        in excinfo.value.message
    )


def test_branch_a_null_latitude_raises_the_python_decoder_error(
    client, raw_response
):
    def mutate(data):
        data["location"] = {"latitude": None, "longitude": 151.20713}

    _serve_details(raw_response, mutate)
    with pytest.raises(DecodeError) as excinfo:
        client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert excinfo.value.status_code == 200
    assert "LatLng payload key 'latitude'" in excinfo.value.message


def test_branch_a_null_object_list_raises_the_conversion_wrapper_error(
    client, raw_response
):
    # Object list positions name no model and no key today. Their
    # origin marker is the generic conversion wrapper form.
    _serve_details(raw_response, lambda data: data.update(photos=None))
    with pytest.raises(DecodeError) as excinfo:
        client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
    assert excinfo.value.status_code == 200
    assert "response failed model conversion" in excinfo.value.message


def test_d3_2_scenario_async(api_key, base_url, raw_response):
    # Async mirror of the flipped D3-2 test above.
    data = json.loads(fixture_bytes("place_details.json"))
    data["websiteUri"] = None
    raw_response(200, json.dumps(data).encode())

    async def run():
        client = AsyncClient(api_key, base_url=base_url)
        place = await client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
        assert place.website_uri is None
        assert "websiteUri" in place.raw

    asyncio.run(run())


def test_empty_types_list_scenario_async(api_key, base_url, raw_response):
    data = json.loads(fixture_bytes("text_search.json"))
    data["places"][0]["types"] = []
    raw_response(200, json.dumps(data).encode())

    async def run():
        client = AsyncClient(api_key, base_url=base_url)
        result = await client.text_search("cafes in Sydney")
        assert result.places[0].types == []
        assert result.places[0].raw["types"] == []

    asyncio.run(run())


def test_class4_scenario_async(api_key, base_url, raw_response):
    data = json.loads(fixture_bytes("place_details.json"))
    data["types"] = ["cafe", None]
    raw_response(200, json.dumps(data).encode())

    async def run():
        client = AsyncClient(api_key, base_url=base_url)
        place = await client.place_details("ChIJrTLr-GyuEmsRBfy61i59si0")
        assert place.types == ["cafe", None]
        assert place.raw["types"] == ["cafe", None]

    asyncio.run(run())


def test_class2_null_id_and_name_on_a_search_place(client, raw_response):
    # Class 2 at the Place identity positions. The null id falls
    # back to the name exactly as an absent id does, and a null name
    # reads as the empty default in that fallback, never as the
    # string form of None. Raw keeps both nulls.
    data = json.loads(fixture_bytes("text_search.json"))
    data["places"][0]["id"] = None
    data["places"][0]["name"] = None
    raw_response(200, json.dumps(data).encode())
    result = client.text_search("cafes in Sydney")
    place = result.places[0]
    assert place.id == ""
    assert place.raw["id"] is None
    assert place.raw["name"] is None
