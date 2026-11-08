"""Round 62 pins for the corpus linkage guard.

The Round 62 audit evaded the linkage guard with a shape the
Round 52 closure had not fenced. A suppressing with body
abandoned by an assert statement left a loading call standing
after the assert credited for a fixture the test never loads,
because the statement walk scanned the assert test and walked
on with the path alive whatever the test held, while a raise,
a break and a continue in the same seat each end the path.
The fence the closure wrote covers abandonment by a raise
statement and names abandonment by an exception raised while
an expression evaluates as the residual outside the guard
static contract, and an assert is neither of those things,
because its test evaluates cleanly and the statement itself
raises after the evaluation. The red team census in the
round 62 dossier maps the whole class, an assert standing
in the walked body of a suppressing with with a credited
loading call after it, in constant, name bound, nested, loop
body, message raising and plain call forms.

The repair gives the assert statement fork treatment in the
statement walk. The path where the test holds walks on as it
did before, and the path where the test fails ends where it
stands as a raised path of the assert kind, holding the
state the test evaluation left behind, so the regions that
carry a raised path onward carry this one with it in their
own terms. A with converts it to a path resuming after the
block like the raised path of a raise statement, and joins
it by the same intersection, so a call standing after an
assert inside the body is credited only when every path
through the block loads it. A loop hands the assert path to
the enclosing block unchanged in kind instead of joining it
away, because the path abandons the loop entirely. A test
standing as a true constant fails on no path, so such an
assert forks nothing and the code after it credits as it
always did. The pins below cover the repaired forms, plus
the controls that keep the fork honest.
"""

from __future__ import annotations

import textwrap

from test_corpus_accounting import (
    RECORDED_LOADERS,
    _fixtures_a_test_loads,
)

CLAIMED = "recorded_OBS1_requested_field_vanishes.json"
OTHER = "recorded_P1_no_address_natural_feature.json"


def _loads(source: str) -> set[str]:
    return _fixtures_a_test_loads(textwrap.dedent(source), RECORDED_LOADERS)


def test_linkage_call_after_a_false_assert_in_a_with_body_earns_no_credit():
    # Round 62, audit Major 1, the named form. The assert
    # abandons the suppressing with body where it stands, so
    # the call after it in the body never runs, and the live
    # call after the block loads the other fixture. The walk
    # forks at the assert, and the raised path resumes after
    # the block holding no credit for the claimed fixture, so
    # the intersection strips it.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                assert False
                dead = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_a_constant_comparison_assert_in_a_with_body_earns_no_credit():
    # Round 62, audit Major 1, the second named form. The
    # test is a constant expression rather than a literal,
    # and it decides the same way from the source alone. The
    # fork turns on the statement, not on the form of the
    # test, so this shape closes with the literal form.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                assert 1 == 2
                dead = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_a_call_assert_in_a_with_body_earns_no_credit():
    # Round 62, red team width census, the undecidable
    # member of the class. The test is a call whose return
    # no static reading can decide, so a repair that ended
    # the path only at asserts a constant reading proves
    # false would leave this shape evading. The fork treats
    # every assert the same way, decided or not, so the
    # raised path stands beside the fall through path at the
    # join and the claimed fixture earns nothing.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            check = lambda: False
            with suppress(AssertionError):
                assert check()
                dead = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_an_assert_in_a_nested_with_body_earns_no_credit():
    # Round 62, red team width census, the nested form. The
    # assert stands one suppressing with down, and the inner
    # block converts its raised path the same way the outer
    # block converts a raise, so the claimed fixture is
    # stripped at the inner join before the outer join ever
    # sees it.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                with suppress(AssertionError):
                    assert False
                    dead = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_an_assert_in_a_loop_body_in_a_with_earns_no_credit():
    # Round 62, red team width census, the loop body form.
    # The loop is a proven one over a nonempty literal, so
    # no zero trip path stands in the join to strip the
    # credit on its own. The assert abandons the loop
    # entirely, so the loop walk hands its raised path to
    # the enclosing with, which resumes it after the block
    # and joins it by intersection against the fall through
    # path that loaded the claimed fixture.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                for _unused in ("x",):
                    assert False
                    dead = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_before_an_assert_in_a_with_body_still_credits():
    # Positive control for the fork. The loading call stands
    # before the assert, so it runs on both paths the fork
    # makes, and its credit survives the join. The fork
    # refuses credit a path skips, not credit every path
    # records.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                result = search(client, raw_response, "{CLAIMED}")
                assert False
            other = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {CLAIMED, OTHER}


def test_linkage_call_after_a_true_constant_assert_in_a_with_body_still_credits():
    # Positive control for the fork. A test standing as a
    # true constant fails on no path, so the assert forks
    # nothing and the call after it credits exactly as it
    # did before the repair.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                assert True
                result = search(client, raw_response, "{CLAIMED}")
            other = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {CLAIMED, OTHER}
