"""Proof tests for the Round 37 README teachings.

Three README gaps the consumer gauntlet measured are closed by three
edits, and this file pins each one the way the guide proof suites pin
theirs. The examples run here in the same call shapes against the
offline stub, and the teaching sentences are pinned as text so a later
edit cannot quietly soften them away.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from placekit import Client, address
from placekit.models import FormattedText

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client(api_key, base_url) -> Client:
    return Client(api_key, base_url=base_url)


def test_readme_addresses_example_reads_city_and_country(client):
    # The Addresses example, in its call shapes. Details first, then
    # the two readers over the details result.
    result = client.text_search("cafes in Sydney")
    place = client.place_details(result.places[0])

    city = address.resolve_city(place)
    assert city.value == "Sydney"
    assert city.carrier == "locality"

    code = address.country_code(place)
    # The reader returns the plain string itself, never a result
    # object carrying one.
    assert code == "AU"
    assert isinstance(code, str)


def test_readme_addresses_example_none_warning_over_search_results(client):
    # The warning the section now carries. The same readers over a
    # bare search result, whose response carried no address
    # components, answer quietly instead of raising.
    result = client.text_search("cafes in Sydney")
    bare = result.places[0]

    assert address.country_code(bare) is None
    city = address.resolve_city(bare)
    assert city.value is None
    assert city.confidence == "none"


def test_readme_autocomplete_passage_reads_prediction_text(client):
    # The autocomplete passage, in its call shapes. The guarded read
    # reaches the display string through the FormattedText member.
    result = client.autocomplete("Bianco")

    assert result.place_predictions
    assert isinstance(result.query_predictions, list)
    for prediction in result.place_predictions:
        assert prediction.text is not None
        assert isinstance(prediction.text, FormattedText)
        assert prediction.text.text
        assert prediction.text.matches

    prediction = result.place_predictions[0]
    assert prediction.text is not None
    assert prediction.text.text == (
        "Bianco Latte, George Street, Sydney NSW, Australia"
    )
    match = prediction.text.matches[0]
    assert match.start_offset == 0
    assert match.end_offset == 6


def test_readme_opening_hours_example_guards_the_full_path(client):
    # The opening hours example, in its call shapes. The guard tests
    # the dotted expression itself, and the reads behind it print
    # the state and the weekday lines.
    result = client.text_search("cafes in Sydney")
    details = client.place_details(result.places[0])

    assert details.current_opening_hours is not None
    assert details.current_opening_hours.open_now is True
    lines = details.current_opening_hours.weekday_descriptions
    assert len(lines) == 7
    assert lines[0].startswith("Monday")
    assert lines[-1].startswith("Sunday")


def test_readme_teaching_sentences_are_pinned():
    readme = (REPO_ROOT / "README.md").read_text()
    # Whitespace is normalised before the substring checks, so a
    # rewrap that changes no wording cannot fail these pins while a
    # wording softening still does.
    readme = " ".join(readme.split())
    for teaching in (
        # The Addresses edit names the reader and states its plain
        # return against the result object contrast.
        "reads the country with `country_code`",
        "`country_code` returns a plainer shape than that",
        "the region code itself as a plain string or None",
        "code = address.country_code(place)",
        "a city resolution carrying no value and a country code of None",
        # The autocomplete passage names both containers and the
        # guarded text shape.
        "`place_predictions` and `query_predictions`",
        "A prediction's `text` is an optional `FormattedText`",
        "The display string sits at `prediction.text.text`",
        "sit at `prediction.text.matches`",
        # The opening hours example names both spellings of the one
        # field and the full dotted path.
        "the attribute spelling of the wire field `currentOpeningHours`",
        "one field under two spellings",
        "Its open state sits at `current_opening_hours.open_now`",
        "if details.current_opening_hours is not None:",
        "print(details.current_opening_hours.open_now)",
    ):
        assert teaching in readme
