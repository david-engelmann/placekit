"""Ranking preference vocabulary for the Places API (New).

The new API splits the ranking vocabulary by method, so this
module does too. Text Search accepts RELEVANCE and DISTANCE and
defaults to relevance behaviour when the parameter is omitted.
Nearby Search accepts DISTANCE and POPULARITY and defaults to
popularity behaviour when the parameter is omitted.

The legacy value prominence is not a wire value in this API and
the legacy lower case spelling of distance is not either, and
pasting either into a call raises an error from the core rather
than silently ranking by a default.
"""

from __future__ import annotations

RELEVANCE = "RELEVANCE"
DISTANCE = "DISTANCE"
POPULARITY = "POPULARITY"

TEXT_SEARCH_VALUES: frozenset[str] = frozenset({RELEVANCE, DISTANCE})
NEARBY_SEARCH_VALUES: frozenset[str] = frozenset({DISTANCE, POPULARITY})

__all__ = [
    "RELEVANCE",
    "DISTANCE",
    "POPULARITY",
    "TEXT_SEARCH_VALUES",
    "NEARBY_SEARCH_VALUES",
]
