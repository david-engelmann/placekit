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

The landing red team then evaded the repaired analysis three
more ways, in repair pass two. A rebind inside a conditional arm
or a loop body that never runs was walked as if the region
always ran, so the dead binding was the one in force at the
call, and a walrus rebind was invisible to the scanner, so the
stale binding kept the credit. The analysis now joins the paths
of a control flow region conservatively, so a name keeps a
resolved binding after a region only when every path through
the region ends holding the identical binding, and it applies
walrus bindings at their position in the walk. The pins below
cover those forms, plus the positive controls that keep the
join honest.
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


def test_linkage_rebind_in_an_untaken_conditional_arm_earns_no_credit():
    # Repair pass two, red team form 4a. The claimed name is bound
    # only inside the else arm of a conditional whose test the
    # runtime always passes, so the arm never runs and the test
    # loads the other fixture. Only one path through the
    # conditional binds the name to the claimed fixture, so the
    # join leaves the name unresolvable after the conditional and
    # the loading call credits nothing at all.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{OTHER}"
            if client is not None:
                pass
            else:
                fixture_name = "{CLAIMED}"
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == set()


def test_linkage_rebind_in_a_zero_trip_loop_earns_no_credit():
    # Repair pass two, red team form 4b. The claimed name is bound
    # only inside a loop body that iterates over an empty tuple,
    # so the body never runs. The path where the body never runs
    # is one of the paths into the join, so the name reads as
    # unresolvable after the loop and the call credits nothing.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{OTHER}"
            for _unused in ():
                fixture_name = "{CLAIMED}"
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == set()


def test_linkage_walrus_rebind_credits_only_the_walrus_value():
    # Repair pass two, red team form 4c. A walrus expression
    # rebinds the local before the call, and the binding applies
    # at its position in the walk, so the call reads the walrus
    # value and the stale claimed binding earns nothing.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{CLAIMED}"
            rebound = (fixture_name := "{OTHER}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_identical_bindings_on_both_arms_still_credit():
    # Positive control for the join. Both arms of the conditional
    # bind the name to the same fixture, so every path ends
    # holding the identical binding and the name keeps its credit
    # after the region. The join refuses disagreement, not
    # branching itself.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            if client is not None:
                fixture_name = "{CLAIMED}"
            else:
                fixture_name = "{CLAIMED}"
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {CLAIMED}


def test_linkage_walrus_handing_the_name_to_the_call_still_credits():
    # Positive control for the walrus rule. The walrus binds the
    # claimed name as the very argument the loading call receives,
    # so the call earns the credit for it.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            result = search(client, raw_response, (fixture_name := "{CLAIMED}"))
        """
    )
    assert loaded == {CLAIMED}
