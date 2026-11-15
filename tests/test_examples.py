"""Proof tests for the examples folder.

Each example runs offline against the recorded responses the
examples carry, and these tests hold the honesty conditions the
examples promise: the output an example prints is the recorded
body's content, read through the typed models, and the error
example's typed handling carries the recorded envelope's values.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

EXAMPLES = Path(__file__).parent.parent / "examples"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, EXAMPLES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(EXAMPLES))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(EXAMPLES))
    return module


def test_text_search_example_prints_the_recorded_places(capsys):
    _load("text_search").main()
    out = capsys.readouterr().out
    # The recorded places, as the fixture body spells them, and
    # the recorded details line for the first place.
    assert "Bianco Latte 4.6 Shop 1/123 George St, Sydney NSW 2000, Australia" in out
    assert "Harbour Espresso 4.4 45 Circular Quay W, The Rocks NSW 2000, Australia" in out
    assert "(02) 5550 1234 https://example.com/" in out


def test_place_details_example_reads_the_recorded_place(capsys):
    _load("place_details").main()
    out = capsys.readouterr().out
    assert "city Sydney locality heuristic" in out
    assert "country AU" in out
    for line in (
        "Monday: 7:00 AM \u2013 3:00 PM",
        "Tuesday: 7:00 AM \u2013 3:00 PM",
        "Wednesday: 7:00 AM \u2013 3:00 PM",
        "Thursday: 7:00 AM \u2013 3:00 PM",
        "Friday: 7:00 AM \u2013 3:00 PM",
        "Saturday: 8:00 AM \u2013 2:00 PM",
        "Sunday: Closed",
    ):
        assert line in out


def test_readme_relative_links_resolve():
    # The README is the router since the 0.1.1 docs move, so a
    # relative link that names a missing file is a broken route
    # on the package page and the repository page alike.
    import re

    readme = (EXAMPLES.parent / "README.md").read_text()
    targets = re.findall(r"\]\((?!https?://|#)([^)]+)\)", readme)
    assert targets, "the README carries no relative links to check"
    for target in targets:
        assert (EXAMPLES.parent / target).is_file(), target


def test_error_handling_example_carries_the_recorded_envelope(capsys):
    _load("error_handling").main()
    out = capsys.readouterr().out
    # The recorded quota envelope answers 429 with a Retry-After
    # of 7, and the recorded not found envelope answers 404.
    assert "quota 429 RESOURCE_EXHAUSTED 7.0" in out
    assert "not found 404 NOT_FOUND" in out
