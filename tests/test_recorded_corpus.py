"""Conformance tests for the recorded corpus fixtures.

Each test loads one recorded fixture by its literal file name, replays
it through the client, and pins the case the fixture was excerpted for.
Expected values live in this file as literals taken from the cassettes,
never read back out of the fixture, so a builder error that rewrote a
value inside a fixture fails against an independent copy. Raw deep
equality compares the decoded raw against the fixture payload with
type sensitive scalar comparison, so an int token, a float token, and
a boolean never compare equal to one another.

Redacted paths carry synthetic values by the parent ruling recorded in
the coverage manifest, and no pin in this module treats a redacted
value as evidence. The pins read the paths around the redactions, the
review language codes, ratings, and structure, which the ruling left
untouched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from placekit import Client

RECORDED = Path(__file__).parent / "fixtures" / "recorded"


@pytest.fixture()
def client(api_key, base_url) -> Client:
    return Client(api_key, base_url=base_url)


def fixture_bytes(name: str) -> bytes:
    return (RECORDED / name).read_bytes()


def fixture_payload(name: str):
    return json.loads(fixture_bytes(name))


def assert_raw_equal(actual, expected, path="raw"):
    """Deep equality that keeps int, float, and bool tokens distinct."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict), path
        assert set(actual) == set(expected), (
            f"{path} key mismatch {sorted(set(actual) ^ set(expected))}"
        )
        for key in expected:
            assert_raw_equal(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list), path
        assert len(actual) == len(expected), f"{path} length mismatch"
        for index, (a_item, e_item) in enumerate(zip(actual, expected)):
            assert_raw_equal(a_item, e_item, f"{path}[{index}]")
    else:
        assert type(actual) is type(expected), (
            f"{path} type {type(actual).__name__} is not {type(expected).__name__}"
        )
        assert actual == expected, f"{path} value mismatch"


def search(client, raw_response, name):
    """Replay a search shaped fixture and pin its raw end to end."""
    payload = fixture_payload(name)
    raw_response(200, fixture_bytes(name))
    result = client.text_search("corpus replay")
    assert_raw_equal(result.raw, payload)
    assert len(result.places) == len(payload["places"])
    for place, raw_place in zip(result.places, payload["places"]):
        assert_raw_equal(place.raw, raw_place)
    return result


def details(client, raw_response, name, place_id):
    """Replay a details shaped fixture and pin its raw end to end."""
    payload = fixture_payload(name)
    raw_response(200, fixture_bytes(name))
    place = client.place_details(place_id)
    assert place.id == place_id
    assert_raw_equal(place.raw, payload)
    return place


# ---------------------------------------------------------------------------
# Place cases
# ---------------------------------------------------------------------------


def test_recorded_p1_no_address_natural_feature(client, raw_response):
    result = search(client, raw_response, "recorded_P1_no_address_natural_feature.json")
    place = result.places[0]
    assert place.id == "ChIJvZ69FaJU6DkRsrqrBvjcdgU"
    assert "mountain_peak" in place.types
    assert place.formatted_address == "Mt Everest"
    # The only address component is the peak itself. No street, city,
    # or country component exists to build an address from.
    assert len(place.address_components) == 1
    component = place.address_components[0]
    assert component.long_text == "Mount Everest"
    assert component.types == ["mountain_peak", "natural_feature", "establishment"]
    # The short formatted address and the postal address are absent
    # from this body as well, but their fields were not in the request
    # mask, so that absence is observed in the manifest note rather
    # than pinned here.


def test_recorded_p2_transit_station_tree_in_raw(client, raw_response):
    result = search(client, raw_response, "recorded_P2_transit_station.json")
    place = result.places[0]
    assert place.id == "ChIJhRwB-yFawokRi0AhGH87UTc"
    assert "train_station" in place.types
    # The transit station group is raw only in the model, and the tree
    # is the case. Two of five results in the source body carry it.
    tree = place.raw["transitStation"]
    assert tree["displayName"]["text"] == "Grand Central"
    agencies = tree["agencies"]
    assert agencies[0]["displayName"]["text"] == "Metro-North Railroad"
    assert agencies[0]["lines"][0]["vehicleType"] == "HEAVY_RAIL"


def test_recorded_p4_temporarily_closed_at_search_depth(client, raw_response):
    result = search(client, raw_response, "recorded_P4_temporarily_closed.json")
    place = result.places[0]
    assert place.id == "ChIJzw3eiINbwokRKCVwMLN501M"
    assert place.business_status == "CLOSED_TEMPORARILY"
    assert place.rating == 1.4
    assert place.user_rating_count == 9


def test_recorded_p7_no_photos_key_under_requesting_mask(client, raw_response):
    result = search(client, raw_response, "recorded_P7_no_photos_key.json")
    place = result.places[0]
    assert place.id == "ChIJqXbFE1vGwoARUN09pf8FYqM"
    # Sixteen of twenty places in the source body carry no photos key
    # under a mask that requested photos. Absence, not an empty list.
    assert place.photos == []
    assert "photos" not in place.raw


def test_recorded_p8_no_rating_at_search_and_details_depth(client, raw_response):
    result = search(client, raw_response, "recorded_P8_search_depth_no_rating.json")
    place = result.places[0]
    assert place.id == "ChIJTSFxKQBbwokRnlW6hfLADH8"
    assert place.rating is None
    assert place.user_rating_count is None
    assert "rating" not in place.raw
    assert "userRatingCount" not in place.raw

    place = details(
        client,
        raw_response,
        "recorded_P8_details_depth_no_rating.json",
        "ChIJS_zBNNbXAhURy-FuRT5ib9k",
    )
    # The details mask requested reviews and rating, and the body
    # carries neither. The same absence at the second depth.
    assert place.rating is None
    assert place.user_rating_count is None
    assert place.reviews == []
    assert "rating" not in place.raw
    assert "reviews" not in place.raw


def test_recorded_p10_ev_charging_full_detail(client, raw_response):
    result = search(client, raw_response, "recorded_P10_ev_charging_full_detail.json")
    place = result.places[0]
    assert place.id == "ChIJqy0cdk3GwoARVLngjTmC44A"
    options = place.ev_charge_options
    assert options is not None
    assert options.connector_count == 46
    aggregations = options.connector_aggregation
    assert [a.type for a in aggregations] == [
        "EV_CONNECTOR_TYPE_CHADEMO",
        "EV_CONNECTOR_TYPE_J1772",
        "EV_CONNECTOR_TYPE_CCS_COMBO_1",
    ]
    # The drift rule from the design record. Typed values are floats,
    # and the raw layer pins the token form the cassette carried.
    rates = [a.max_charge_rate_kw for a in aggregations]
    assert rates == [50.0, 7.199999809265137, 50.0]
    assert all(isinstance(rate, float) for rate in rates)
    raw_rates = [
        a["maxChargeRateKw"]
        for a in place.raw["evChargeOptions"]["connectorAggregation"]
    ]
    assert type(raw_rates[0]) is int and raw_rates[0] == 50
    assert type(raw_rates[1]) is float and raw_rates[1] == 7.199999809265137


def test_recorded_p11_fuel_options_in_raw(client, raw_response):
    result = search(client, raw_response, "recorded_P11_fuel_options.json")
    place = result.places[0]
    assert place.id == "ChIJA6GX3IEzsYkRz8NMql4bGB8"
    # The fuel options group is raw only in the model.
    prices = place.raw["fuelOptions"]["fuelPrices"]
    assert len(prices) == 4
    diesel = prices[0]
    assert diesel["type"] == "DIESEL"
    assert diesel["price"]["currencyCode"] == "USD"
    assert diesel["price"]["units"] == "6"
    assert diesel["price"]["nanos"] == 450000000
    assert diesel["updateTime"] == "2026-10-31T15:51:45Z"


def test_recorded_p12_contained_place_partial(client, raw_response):
    place = details(
        client,
        raw_response,
        "recorded_P12_contained_place.json",
        "ChIJ8WvuSB7Lj4ARFyHppkxDRQ4",
    )
    assert place.address_descriptor is not None
    assert len(place.raw["containingPlaces"]) == 1
    assert len(place.raw["entrances"]) == 8
    assert len(place.raw["navigationPoints"]) == 2
    # The partial half of the case. The mask requested subDestinations
    # and the body carries no such key anywhere in either session.
    assert "subDestinations" not in place.raw


def test_recorded_p15_summaries_at_details_depth(client, raw_response):
    saigon = details(
        client,
        raw_response,
        "recorded_P15_details_depth_saigon.json",
        "ChIJV4k8_9UodTERU5KXbkYpSYs",
    )
    assert saigon.editorial_summary is not None
    assert saigon.editorial_summary.text == (
        "Sleek quarters in a refined hotel with a restaurant & a "
        "bar/lounge, plus a spa, gym & outdoor pool."
    )
    assert saigon.generative_summary is None
    assert saigon.review_summary is None
    assert "generativeSummary" not in saigon.raw
    assert "reviewSummary" not in saigon.raw
    # The attributions side pin. The mask requested place attributions
    # and the body omits the key, the same shape as the A2 fixture.
    assert "attributions" not in saigon.raw
    assert len(saigon.reviews) == 5
    assert {r.text.language_code for r in saigon.reviews} == {"en"}

    mall = details(
        client,
        raw_response,
        "recorded_P15_richest_mall_store.json",
        "ChIJ8WvuSB7Lj4ARFyHppkxDRQ4",
    )
    assert mall.editorial_summary is not None
    assert mall.editorial_summary.text == (
        "Department store chain providing brand-name clothing, "
        "accessories, home furnishings & housewares."
    )
    assert mall.generative_summary is not None
    assert mall.generative_summary.overview is not None
    assert mall.generative_summary.overview.text == (
        "Large department store offering a wide selection of fashion "
        "and clothing."
    )
    assert mall.review_summary is not None
    assert mall.review_summary.text is not None
    assert mall.review_summary.text.text.startswith(
        "This department store is praised for its wide selection"
    )
    assert mall.review_summary.text.language_code == "en-US"
    # The partial half of the case. No body in either session carries
    # a neighborhood summary.
    assert "neighborhoodSummary" not in mall.raw
    assert "neighborhoodSummary" not in saigon.raw


# ---------------------------------------------------------------------------
# Hours and time cases
# ---------------------------------------------------------------------------


def test_recorded_h1_open_24_hours(client, raw_response):
    result = search(client, raw_response, "recorded_H1_open_24_hours.json")
    place = result.places[0]
    assert place.id == "ChIJdzXgRn8E9YgRZCIoanr8GPw"
    assert place.display_text == "Waffle House"
    hours = place.regular_opening_hours
    assert hours is not None
    assert hours.open_now is True
    # One period, opening at day 0 at midnight, with no close point.
    assert len(hours.periods) == 1
    period = hours.periods[0]
    assert (period.open.day, period.open.hour, period.open.minute) == (0, 0, 0)
    assert period.close is None


def test_recorded_h2_split_hours(client, raw_response):
    result = search(client, raw_response, "recorded_H2_split_hours.json")
    place = result.places[0]
    assert place.id == "ChIJ-RAVYVVQqEcRIfxE6EjRZ38"
    hours = place.regular_opening_hours
    assert hours is not None
    # Two periods share every open day, fourteen periods in total.
    assert len(hours.periods) == 14
    from collections import Counter

    assert Counter(p.open.day for p in hours.periods) == {
        0: 2, 1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 2,
    }
    first, second = hours.periods[0], hours.periods[1]
    assert (first.open.hour, first.open.minute) == (7, 0)
    assert (first.close.hour, first.close.minute) == (11, 30)
    assert (second.open.hour, second.open.minute) == (12, 30)
    assert (second.close.day, second.close.hour) == (1, 0)


def test_recorded_h3_overnight_hours(client, raw_response):
    result = search(client, raw_response, "recorded_H3_overnight_hours.json")
    place = result.places[0]
    assert place.id == "ChIJZ5QEJ19PqEcR0ciT7zE11sE"
    hours = place.regular_opening_hours
    assert hours is not None
    overnight = [p for p in hours.periods if p.open.day == 6]
    assert len(overnight) == 1
    period = overnight[0]
    assert (period.open.hour, period.open.minute) == (10, 0)
    # The close lands on day 0 at 03.00, past midnight into the next day.
    assert (period.close.day, period.close.hour, period.close.minute) == (0, 3, 0)


def test_recorded_h6_truncated_period_points(client, raw_response):
    result = search(client, raw_response, "recorded_H6_truncated_period_points.json")
    place = result.places[0]
    assert place.id == "ChIJZ5QEJ19PqEcR0ciT7zE11sE"
    hours = place.current_opening_hours
    assert hours is not None
    points = []
    for period in hours.periods:
        for point in (period.open, period.close):
            if point is not None and point.truncated:
                points.append(point)
    # One open point truncated at the window start and one close point
    # truncated at the window end, both on live data.
    assert len(points) == 2
    by_kind = {
        (p.day, p.hour, p.minute) for p in points
    }
    assert (0, 0, 0) in by_kind
    assert (6, 23, 59) in by_kind


def test_recorded_h7_secondary_hours(client, raw_response):
    result = search(client, raw_response, "recorded_H7_secondary_hours.json")
    place = result.places[0]
    assert place.id == "ChIJjWm3wdJzToYR8efPhAe5lzY"
    current = place.current_secondary_opening_hours
    assert len(current) == 1
    assert current[0].secondary_hours_type == "DRIVE_THROUGH"
    regular = place.regular_secondary_opening_hours
    assert len(regular) == 1
    assert regular[0].secondary_hours_type == "DRIVE_THROUGH"


def test_recorded_h8_fractional_utc_offset(client, raw_response):
    result = search(client, raw_response, "recorded_H8_fractional_utc_offset.json")
    place = result.places[0]
    assert place.id == "ChIJKc7950UZ6zkRIDoTfViKQyw"
    # Twenty of twenty places in the source body carry this pair.
    assert place.utc_offset_minutes == 345
    assert type(place.utc_offset_minutes) is int
    assert place.time_zone is not None
    assert place.time_zone.id == "Asia/Katmandu"


def test_recorded_h9_extreme_utc_offset(client, raw_response):
    result = search(client, raw_response, "recorded_H9_extreme_utc_offset.json")
    place = result.places[0]
    assert place.id == "ChIJoeTv8C6iAnoR6m3PZFxVVxM"
    assert place.utc_offset_minutes == 840
    assert type(place.utc_offset_minutes) is int
    assert place.time_zone is not None
    assert place.time_zone.id == "Pacific/Kiritimati"


def test_recorded_h10_offset_sample_in_effect_basis(client, raw_response):
    place = details(
        client,
        raw_response,
        "recorded_H10_seasonal_offset_sample.json",
        "ChIJV4k8_9UodTERU5KXbkYpSYs",
    )
    # A replay value from the recorded instant, asserted as a sample
    # with presence, integer type, and a plausible range. No live call
    # today is claimed to return the same value, because the offset
    # moves with the season, which is the point of the case. The
    # session 1 half of this case rests on the in effect geography
    # basis recorded in the manifest, since no session 1 mask asked
    # for the offset field.
    value = place.utc_offset_minutes
    assert value is not None
    assert type(value) is int
    assert -720 <= value <= 840
    assert value == 420


def test_recorded_h11_description_order_disagrees_with_period_anchor(client, raw_response):
    place = details(
        client,
        raw_response,
        "recorded_H11_description_order_vs_period_anchor.json",
        "ChIJV4k8_9UodTERU5KXbkYpSYs",
    )
    hours = place.regular_opening_hours
    assert hours is not None
    # The descriptions run Monday first, in German, while the single
    # period anchors on day 0.
    assert hours.weekday_descriptions[0] == "Montag: 24 Stunden geöffnet"
    assert hours.weekday_descriptions[1].startswith("Dienstag")
    assert len(hours.periods) == 1
    assert (hours.periods[0].open.day, hours.periods[0].open.hour) == (0, 0)
    assert hours.periods[0].close is None


# ---------------------------------------------------------------------------
# Value and identifier cases
# ---------------------------------------------------------------------------


def test_recorded_v1_rating_absent_against_rating_whole(client, raw_response):
    result = search(client, raw_response, "recorded_V1_rating_absent_against_whole.json")
    whole, absent = result.places[0], result.places[1]
    assert whole.id == "ChIJL-0tDU9bwokRNIqrbAnPVuc"
    assert absent.id == "ChIJTSFxKQBbwokRnlW6hfLADH8"
    # The drift rule from the design record. The typed rating is the
    # float five, and the raw token keeps the int form the wire sent.
    assert whole.rating == 5.0
    assert isinstance(whole.rating, float)
    assert type(whole.raw["rating"]) is int
    assert whole.raw["rating"] == 5
    assert whole.user_rating_count == 188
    assert absent.rating is None
    assert absent.user_rating_count is None
    assert "rating" not in absent.raw


def test_recorded_v3_top_price_levels(client, raw_response):
    result = search(client, raw_response, "recorded_V3_top_price_levels.json")
    place = result.places[0]
    assert place.id == "ChIJA-K5lEpQqEcRHGv7ScsVIXs"
    assert place.display_text == "Restaurant Facil"
    assert place.price_level == "PRICE_LEVEL_VERY_EXPENSIVE"


def test_recorded_v5_plus_code_without_compound_code(client, raw_response):
    result = search(client, raw_response, "recorded_V5_plus_code_global_only.json")
    place = result.places[0]
    assert place.id == "ChIJvZ69FaJU6DkRsrqrBvjcdgU"
    assert place.plus_code is not None
    assert place.plus_code.global_code == "7MV8XWQG+74"
    assert place.plus_code.compound_code is None
    assert "compoundCode" not in place.raw["plusCode"]


def test_recorded_v10_long_form_place_id_accepted_by_details(client, raw_response):
    long_id = (
        "EiZXaWxsaWFtc2J1cmcgQnJpZGdlLCBOZXcgWW9yaywgTlksIFVTQSIuKiwKFAoSCccn"
        "3dnXW8KJEdugE_vLf17YEhQKEgk7CD_TpU_CiRFi_nfhBo8LyA"
    )
    place = details(
        client, raw_response, "recorded_V10_long_form_place_id.json", long_id
    )
    # The decoded id matches the requested long form id unchanged.
    assert place.id == long_id
    assert place.display_text == "Williamsburg Bridge"


def test_recorded_v11_next_open_time_populated(client, raw_response):
    result = search(client, raw_response, "recorded_V11_next_open_time_populated.json")
    place = result.places[0]
    assert place.id == "ChIJywdI5etRqEcRUVD-ycuGL6M"
    # A replay value from the recorded instant, asserted as recorded.
    # Every place in the source body was closed at the call instant
    # and carries the field in both hours objects.
    assert place.current_opening_hours is not None
    assert place.current_opening_hours.next_open_time == "2026-11-01T11:00:00Z"
    assert place.regular_opening_hours is not None
    assert place.regular_opening_hours.next_open_time == "2026-11-01T11:00:00Z"


# ---------------------------------------------------------------------------
# Address cases
# ---------------------------------------------------------------------------


def _component(place, type_name):
    for component in place.address_components:
        if type_name in component.types:
            return component
    return None


def test_recorded_a1_no_street_number(client, raw_response):
    place = details(
        client,
        raw_response,
        "recorded_A1_no_street_number.json",
        "EiZXaWxsaWFtc2J1cmcgQnJpZGdlLCBOZXcgWW9yaywgTlksIFVTQSIuKiwKFAoSCccn3dnXW8KJEdugE_vLf17YEhQKEgk7CD_TpU_CiRFi_nfhBo8LyA",
    )
    assert place.formatted_address == "Williamsburg Bridge, New York, NY, USA"
    route = _component(place, "route")
    assert route is not None
    assert _component(place, "street_number") is None
    all_types = [t for c in place.address_components for t in c.types]
    assert "street_number" not in all_types


def test_recorded_a2_no_locality_sublocality_carries_city(client, raw_response):
    place = details(
        client,
        raw_response,
        "recorded_A2_no_locality_sublocality_city.json",
        "ChIJzRBPAz5ZwokRd0AUXGm-2f8",
    )
    assert place.formatted_address == "292 Bedford Ave, Brooklyn, NY 11249, USA"
    # No locality component exists in this body, while the postal
    # address in the same body reports its locality as Brooklyn.
    assert _component(place, "locality") is None
    sublocality = _component(place, "sublocality_level_1")
    assert sublocality is not None
    assert sublocality.long_text == "Brooklyn"
    assert place.postal_address is not None
    assert place.postal_address.locality == "Brooklyn"
    assert place.postal_address.postal_code == "11249"
    # The attributions side pin. The mask requested place attributions
    # and the body omits the key. The taxonomy premise that this
    # cassette returned the field as null is wrong, and the coverage
    # table footnote carries the erratum.
    assert "attributions" not in place.raw


def test_recorded_a3_postal_town_carries_the_city(client, raw_response):
    result = search(client, raw_response, "recorded_A3_postal_town_carries_city.json")
    place = result.places[0]
    assert place.id == "ChIJGZS3NZwlcUgRZF3cPB1OFGk"
    town = _component(place, "postal_town")
    assert town is not None
    assert town.long_text == "Cheltenham"


def test_recorded_a4_locality_and_postal_town_disagree(client, raw_response):
    result = search(client, raw_response, "recorded_A4_locality_postal_town_disagree.json")
    place = result.places[0]
    assert place.id == "ChIJGZS3NZwlcUgRZF3cPB1OFGk"
    # Both carriers sit on the same component list and disagree, on
    # twenty of twenty places in the source body.
    locality = _component(place, "locality")
    town = _component(place, "postal_town")
    assert locality is not None and town is not None
    assert locality.long_text == "Bourton-on-the-Water"
    assert town.long_text == "Cheltenham"
    assert place.formatted_address == (
        "1 Sherborne St, Bourton-on-the-Water, Cheltenham GL54 2BY, UK"
    )


def test_recorded_a5_sublocality_chains(client, raw_response):
    result = search(client, raw_response, "recorded_A5_sublocality_chains.json")
    place = result.places[0]
    assert place.id == "ChIJzVXOw5SPGGAR7yVtRAihT7o"
    chain = [
        c for c in place.address_components
        if any(t.startswith("sublocality_level") for t in c.types)
    ]
    assert len(chain) == 3
    level_two = _component(place, "sublocality_level_2")
    assert level_two is not None
    assert level_two.long_text == "浅草"


def test_recorded_a6_japanese_block_addressing(client, raw_response):
    result = search(client, raw_response, "recorded_A6_japanese_block_addressing.json")
    place = result.places[0]
    assert place.id == "ChIJzVXOw5SPGGAR7yVtRAihT7o"
    all_types = [t for c in place.address_components for t in c.types]
    # The chain descends through ward and district and block fragments
    # with no route and no street number anywhere.
    assert "route" not in all_types
    assert "street_number" not in all_types
    postal = _component(place, "postal_code")
    assert postal is not None
    assert postal.long_text == "111-0032"
    premise = _component(place, "premise")
    assert premise is not None
    # A full width digit string, carried as recorded.
    assert premise.long_text == "１５"
    assert place.postal_address is not None
    assert place.postal_address.postal_code == "111-0032"


def test_recorded_a7_right_to_left_script_address(client, raw_response):
    result = search(client, raw_response, "recorded_A7_rtl_script_address.json")
    assert [p.id for p in result.places] == [
        "ChIJ4TyFlYFCXz4RNMf0stgxhLc",
        "ChIJUUpqvgVDXz4RgVl27UZC1ko",
    ]
    first = result.places[0]
    country = _component(first, "country")
    assert country is not None
    assert country.long_text == "الإمارات العربية المتحدة"
    assert country.language_code == "ar"


def test_recorded_a8_multi_script_names_for_one_place(client, raw_response):
    japanese = search(client, raw_response, "recorded_A8_tokyo_japanese.json")
    english = search(client, raw_response, "recorded_A8_tokyo_english.json")
    ja_place = japanese.places[0]
    en_place = english.places[0]
    assert ja_place.id == en_place.id == "ChIJzVXOw5SPGGAR7yVtRAihT7o"
    # The roman display name stays the same while the address script
    # and the component scripts and the address order all change.
    assert ja_place.display_text == "FUGLEN ASAKUSA"
    assert en_place.display_text == "FUGLEN ASAKUSA"
    assert ja_place.formatted_address == "日本、〒111-0032 東京都台東区浅草２丁目６−１５"
    assert en_place.formatted_address == (
        "2-chōme-6-15 Asakusa, Taito City, Tokyo 111-0032, Japan"
    )
    # A transliteration language tag leaks into the English response.
    leaked = [
        c for c in en_place.address_components if c.language_code == "ja-Latn"
    ]
    assert len(leaked) >= 1
    assert all(c.language_code == "ja" for c in ja_place.address_components)


def test_recorded_a9_country_without_postal_codes(client, raw_response):
    result = search(client, raw_response, "recorded_A9_country_without_postal_codes.json")
    place = result.places[0]
    assert place.id == "ChIJ98qoMwBDXz4RXUcEE0Tvwug"
    # None of the twenty places in the source body carries a postal
    # code component, and every postal address omits the field.
    all_types = [t for c in place.address_components for t in c.types]
    assert "postal_code" not in all_types
    assert place.postal_address is not None
    assert place.postal_address.region_code == "AE"
    assert place.postal_address.postal_code is None
    assert "postalCode" not in place.postal_address.raw


def test_recorded_a10_disputed_administrative_area_pair(client, raw_response):
    plain = details(
        client,
        raw_response,
        "recorded_A10_jerusalem_no_region_code.json",
        "ChIJS_zBNNbXAhURy-FuRT5ib9k",
    )
    region = details(
        client,
        raw_response,
        "recorded_A10_jerusalem_region_ps.json",
        "ChIJS_zBNNbXAhURy-FuRT5ib9k",
    )
    # The expected variance did not occur. The component sets are
    # identical across the pair, and the only body differences sit in
    # the photo entries, which the photo trim reduces to one entry.
    assert_raw_equal(
        [c.raw for c in plain.address_components],
        [c.raw for c in region.address_components],
    )
    for place in (plain, region):
        country = _component(place, "country")
        assert country is not None
        assert country.long_text == "Israel"
        assert place.formatted_address == "Jerusalem, Israel"
        assert place.display_text == "Jerusalem"


def test_recorded_a12_very_long_name_and_address_ceiling(client, raw_response):
    result = search(client, raw_response, "recorded_A12_long_village_name.json")
    assert [p.id for p in result.places] == [
        "ChIJaXoVnASpZUgRwmxnGAkXgx4",
        "ChIJ6UJwtHmpZUgR0gUI1R5g0D4",
    ]
    station = result.places[0]
    village = "Llanfairpwllgwyngyllgogerychwyrndrobwllllantysiliogogogoch"
    assert len(village) == 58
    assert station.display_text == village + " Station Sign"
    # Google abbreviates the village inside the formatted addresses,
    # and the longest of them in this body runs 46 characters. The
    # corpus length record sits with the Arabic addresses instead,
    # pinned as an observation on the A7 fixture.
    assert all(len(p.formatted_address) == 46 for p in result.places)


def test_recorded_a13_premise_and_subpremise(client, raw_response):
    result = search(client, raw_response, "recorded_A13_premise_and_subpremise.json")
    place = result.places[0]
    assert place.id == "ChIJUXs3NtOPGGARhehCaUQo5J8"
    premise = _component(place, "premise")
    subpremise = _component(place, "subpremise")
    assert premise is not None
    assert premise.long_text == "３７"
    assert subpremise is not None
    assert subpremise.long_text == "1"
    # The first component in this body carries no types key at all,
    # and it rides verbatim in raw while decoding with empty types.
    first_raw = place.raw["addressComponents"][0]
    assert "types" not in first_raw
    assert place.address_components[0].types == []


# ---------------------------------------------------------------------------
# Observations. Shapes the taxonomy did not predict, pinned on host
# fixtures and never counted toward the fifty five cases.
# ---------------------------------------------------------------------------


def test_observation_requested_field_vanishes_across_a_result_set(client, raw_response):
    result = search(client, raw_response, "recorded_OBS1_requested_field_vanishes.json")
    place = result.places[0]
    assert place.id == "ChIJx7K17Ji3t4kRr3VvqMTw7cc"
    # The mask requested priceLevel and all twenty results in the
    # source body omit the key. The manifest note carries the set
    # wide basis, twenty of twenty omitting.
    assert place.price_level is None
    assert "priceLevel" not in place.raw


def test_observation_pure_service_area_business_splits_by_depth(client, raw_response):
    result = search(client, raw_response, "recorded_OBS2_pure_service_area_depth_split.json")
    place = result.places[0]
    assert place.id == "ChIJkaUn1JPTD4gR7ZWpE9cCuow"
    # At search depth the key is omitted across the whole set, while
    # every details body in session 2 carries the field as explicit
    # false. Presence splits by endpoint, not by place.
    assert place.pure_service_area_business is None
    assert "pureServiceAreaBusiness" not in place.raw


def test_observation_secondary_hours_carry_their_own_next_close_time(client, raw_response):
    result = search(client, raw_response, "recorded_H7_secondary_hours.json")
    place = result.places[0]
    secondary = place.raw["currentSecondaryOpeningHours"][0]
    assert secondary["nextCloseTime"] == "2026-11-01T09:30:00Z"
    assert "nextOpenTime" not in secondary


def test_observation_plus_code_component_type(client, raw_response):
    result = search(client, raw_response, "recorded_A7_rtl_script_address.json")
    place = result.places[0]
    plus = _component(place, "plus_code")
    assert plus is not None
    assert plus.long_text == "57XF+J8R"


def test_observation_landmark_component_type(client, raw_response):
    result = search(client, raw_response, "recorded_A9_country_without_postal_codes.json")
    place = result.places[0]
    landmark = _component(place, "landmark")
    assert landmark is not None
    assert landmark.long_text == "Dubai Mall"


def test_observation_arabic_formatted_address_length_record(client, raw_response):
    result = search(client, raw_response, "recorded_A7_rtl_script_address.json")
    lengths = [len(p.formatted_address) for p in result.places]
    # A recorded length range held as literals, never a count of the
    # fixture characters. The longest formatted addresses in the
    # corpus are Arabic, running from 126 to 130 characters.
    assert max(lengths) == 130
    assert min(lengths) == 96
    assert all(96 <= n <= 130 for n in lengths)


def test_observation_business_status_absent_on_non_business_places(client, raw_response):
    for name in (
        "recorded_A10_jerusalem_no_region_code.json",
        "recorded_A10_jerusalem_region_ps.json",
        "recorded_A1_no_street_number.json",
    ):
        payload = fixture_payload(name)
        raw_response(200, fixture_bytes(name))
        place = client.place_details(payload["id"])
        assert_raw_equal(place.raw, payload)
        # No business status key at all, rather than any enum value.
        assert place.business_status is None
        assert "businessStatus" not in place.raw


def test_observation_review_sample_changes_with_request_language(client, raw_response):
    english = details(
        client,
        raw_response,
        "recorded_P15_details_depth_saigon.json",
        "ChIJV4k8_9UodTERU5KXbkYpSYs",
    )
    german = details(
        client,
        raw_response,
        "recorded_H11_description_order_vs_period_anchor.json",
        "ChIJV4k8_9UodTERU5KXbkYpSYs",
    )
    # The language filter selects a different sample rather than
    # translating one sample. A review pin is only ever a pin for the
    # language its fixture requested.
    assert [r.rating for r in english.reviews] == [5.0, 5.0, 2.0, 5.0, 5.0]
    assert [r.rating for r in german.reviews] == [5.0, 5.0, 4.0, 4.0, 5.0]
    assert {r.text.language_code for r in english.reviews} == {"en"}
    assert {r.text.language_code for r in german.reviews} == {"de"}
    assert english.reviews[0].publish_time == "2026-07-28T02:16:31.263221690Z"
    assert german.reviews[0].publish_time == "2018-02-27T14:00:01.084Z"
