"""Pins for the Round 52 linkage guard repair.

The corpus accounting linkage guard proves a named corpus test
loads the fixtures it claims by static analysis of the test
source. The Round 52 red team evaded it by rebinding a fed local
between the claimed literal and the loading call. The analysis
collected the string constants of every assignment to the local
without regard to order, so the shadowed binding earned the same
credit as the live one and the mutated test passed accounting at
fifteen of fifteen while never opening the fixture it claimed.
The analysis now walks the test body in program order and
resolves each name argument against the binding in effect at the
loading call, so only the binding that reaches the call earns
credit. These pins exercise the analysis directly over synthetic
test sources, one per shape, against the recorded module loader
set the guard itself derives.
"""

from __future__ import annotations

import textwrap

from test_corpus_accounting import RECORDED_LOADERS, _fixtures_a_test_loads

CLAIMED = "recorded_OBS1_requested_field_vanishes.json"
OTHER = "recorded_P1_no_address_natural_feature.json"


def _loads(source: str) -> set[str]:
    return _fixtures_a_test_loads(textwrap.dedent(source), RECORDED_LOADERS)


def test_linkage_literal_argument_credits_the_fixture():
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            result = search(client, raw_response, "{CLAIMED}")
        """
    )
    assert loaded == {CLAIMED}


def test_linkage_bound_name_credits_the_fixture():
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            name = "{CLAIMED}"
            result = search(client, raw_response, name)
        """
    )
    assert loaded == {CLAIMED}


def test_linkage_loop_variable_credits_the_fixture():
    # The shipped observation shape. A loop variable taking its
    # values from a tuple of literals hands each one to the loader.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            for name in ("{CLAIMED}", "{OTHER}"):
                payload = fixture_payload(name)
        """
    )
    assert loaded == {CLAIMED, OTHER}


def test_linkage_name_in_a_comment_earns_no_credit():
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            # the fixture this test claims is {CLAIMED}
            result = search(client, raw_response, "{OTHER}")
        """
    )
    assert loaded == {OTHER}


def test_linkage_dead_assignment_earns_no_credit():
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            name = "{CLAIMED}"
            result = search(client, raw_response, "{OTHER}")
        """
    )
    assert loaded == {OTHER}


def test_linkage_rebound_name_credits_only_the_final_binding():
    # The red team form. The local is bound to the claimed name,
    # rebound to another fixture, and only then handed to the
    # loader, so the claimed fixture is never opened at runtime
    # and earns no credit here either.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{CLAIMED}"
            fixture_name = "{OTHER}"
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_rebinding_after_the_call_keeps_the_earlier_credit():
    # Resolution is per call, not per function. A name bound to
    # one fixture, handed to the loader, rebound, and handed over
    # again earns credit for both, because each call reads the
    # binding in effect at that call.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{CLAIMED}"
            first = search(client, raw_response, fixture_name)
            fixture_name = "{OTHER}"
            second = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {CLAIMED, OTHER}


def test_linkage_helper_return_earns_no_credit():
    # The name arrives as the return value of a call the analysis
    # cannot see into, so nothing is credited. The shape fails
    # closed rather than passing on a name it cannot trace.
    loaded = _loads(
        """
        def test_shape(client, raw_response):
            result = search(client, raw_response, name_from_elsewhere())
        """
    )
    assert loaded == set()
