"""Pins for the Round 47 README teachings.

The second consumer gauntlet found three facts the guides never
stated, and this file pins each repair the way the guide proof
suites pin theirs. The behaviour pins drive the calls the new
passages teach against the offline stub, in the shapes a reader
copying the guides would write, and the text pins hold the new
sentences so a later edit cannot quietly soften them away.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from placekit import Client, DecodeError, FieldMask
from placekit.models import PhotoMedia, PhotoUriResult

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client(api_key, base_url) -> Client:
    return Client(api_key, base_url=base_url)


def _first_place(client):
    result = client.text_search("cafes in Sydney")
    return result.places[0]


def test_details_mask_bare_paths_with_id_succeeds(client):
    # The details form the Field masks section now teaches. Bare
    # field names, with the id identity path named, and the call
    # succeeds. The fixture body carries a resource name beside
    # the id, so the empty name on the result also proves the
    # stub honoured the mask rather than serving the full body.
    place = client.place_details(
        _first_place(client), fields=FieldMask("id", "rating")
    )

    assert place.id
    assert place.name == ""
    assert place.rating == 4.6


def test_details_mask_bare_paths_with_name_succeeds(client):
    # The other identity path satisfies the same floor on its own.
    place = client.place_details(
        _first_place(client), fields=FieldMask("name", "rating")
    )

    assert place.name.startswith("places/")
    assert place.rating == 4.6


def test_details_mask_search_form_raises_decode_error(client):
    # The form the search example teaches, carried across to
    # details unchanged, names no bare identity path in the
    # filtered response and the call refuses it.
    with pytest.raises(DecodeError):
        client.place_details(
            _first_place(client),
            fields=FieldMask("places.id", "places.rating"),
        )


def test_details_mask_display_name_alone_raises_decode_error(client):
    # The floor is id or name exactly. A bare mask naming the
    # display name and a field, but neither identity path, still
    # refuses, which is what keeps the README sentence honest.
    with pytest.raises(DecodeError):
        client.place_details(
            _first_place(client),
            fields=FieldMask("displayName", "rating"),
        )


def test_photo_uri_mode_returns_photo_uri_result(client):
    # The Quickstart passage's mode, asked for with the keyword
    # the guides now name.
    details = client.place_details(_first_place(client))
    photo = details.photos[0]

    result = client.place_photo(photo, skip_http_redirect=True)

    assert isinstance(result, PhotoUriResult)
    assert result.name == photo.name
    assert result.photo_uri.endswith("/photo-image")


def test_photo_default_mode_returns_media(client):
    # The control for the pin above. Without the keyword the same
    # photo downloads as media, so the keyword is what switches
    # the mode and the pin is not vacuous.
    details = client.place_details(_first_place(client))

    media = client.place_photo(details.photos[0], max_width_px=800)

    assert isinstance(media, PhotoMedia)
    assert len(media.content) == 8237


def test_readme_teaching_sentences_are_pinned():
    readme = (REPO_ROOT / "README.md").read_text()
    # Whitespace is normalised before the substring checks, so a
    # rewrap that changes no wording cannot fail these pins while
    # a wording softening still does.
    readme = " ".join(readme.split())
    for teaching in (
        # The Field masks paragraph states the root difference and
        # gives the details form of the search example.
        "Search and nearby masks name their paths under the `places` prefix",
        "while place details mask paths are bare field names with no prefix",
        'the details form of the example above is `FieldMask("id", "displayName", "rating")`',
        # The identity floor, named with its exact two paths.
        "A details mask must also still name `id` or `name`, the two identity paths",
        "the call raises `DecodeError` even on a well-formed response",
        # The endpoints table row names the keyword and the
        # attribute together.
        "`PhotoUriResult` carrying `photo_uri` when `skip_http_redirect=True`",
        # The Quickstart passage names the same pair in prose.
        "Pass `skip_http_redirect=True` to `place_photo` instead",
        "whose `photo_uri` attribute carries the photo URI",
        # The session token paragraph states the caller generated
        # shape.
        "Tokens are caller generated rather than minted by placekit",
        "a UUID is the usual shape",
    ):
        assert teaching in readme
