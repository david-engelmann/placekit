"""Pins for the Round 57 README filter teachings.

The claims census found the endpoints paragraph promising the
filters their endpoints offer while leaving real keywords
unnamed, and the cold read gauntlet found the price_levels value
shape stated nowhere in the document. These pins hold both
repairs. The keyword sets are derived from the client signatures
with inspect, never pasted into this file, so a keyword added to
a call and left untaught fails here. The price level pin reads
the values the README itself spells and drives them through a
call against the offline stub, proving the client takes them.

The spelling guard covers the four read calls whose keyword
surface the endpoints passage and its neighbouring passages
teach. The place_photo keywords stand outside that promise, so
they are derived only for the parity pin.
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest

from placekit import AsyncClient, Client

REPO_ROOT = Path(__file__).resolve().parents[1]

READ_CALLS = ("text_search", "nearby_search", "place_details", "autocomplete")
ALL_CALLS = READ_CALLS + ("place_photo",)


@pytest.fixture()
def client(api_key, base_url) -> Client:
    return Client(api_key, base_url=base_url)


def _keyword_names(cls, method_name):
    parameters = inspect.signature(getattr(cls, method_name)).parameters
    return {
        name
        for name, parameter in parameters.items()
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY
    }


def _spelled(readme, name):
    # A keyword counts as taught when the README names it in
    # backticks or uses it as an argument in an example. A bare
    # prose word does not count, because words such as region
    # also live in passages that teach nothing about the keyword.
    if f"`{name}`" in readme:
        return True
    return re.search(rf"(?<![\w.]){re.escape(name)}=", readme) is not None


def test_sync_and_async_keyword_sets_match():
    # The README teaches one keyword surface per call, which is
    # honest only while the two clients carry the same surface.
    for method_name in ALL_CALLS:
        assert _keyword_names(Client, method_name) == _keyword_names(
            AsyncClient, method_name
        ), method_name


@pytest.mark.parametrize("method_name", READ_CALLS)
def test_readme_spells_every_keyword_of_the_read_calls(method_name):
    readme = (REPO_ROOT / "README.md").read_text()
    unspelled = sorted(
        name
        for name in _keyword_names(Client, method_name)
        if not _spelled(readme, name)
    )
    assert not unspelled, (
        f"{method_name} keywords the README never names: {unspelled}"
    )


def test_readme_price_level_values_reach_the_wire(client, stub_server):
    # The values are read out of the README itself, so the pin
    # holds whatever the document teaches, and the recorded
    # request body proves the client accepts each taught value
    # and sends it under the wire name.
    readme = (REPO_ROOT / "README.md").read_text()
    taught = sorted(set(re.findall(r"PRICE_LEVEL_[A-Z_]+", readme)))
    assert taught, "the README spells no price level values"
    client.text_search("cafes in Sydney", price_levels=taught)
    body = json.loads(stub_server.last_request["body"])
    assert body["priceLevels"] == taught
