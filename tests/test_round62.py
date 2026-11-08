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

The delta review of the fork found a second seat of the
same genus standing behind the try join. The join dropped
a raised path of every kind where it stood and never read
the errors its handlers named, so an assert or a raise
standing in a try body or a try else arm, under a handler
naming a different error, left a loading call after the
try credited for a fixture it never loads, because the
error the statement raises is not caught and abandons the
rest of the with body on its way out. The second repair
teaches the try walk to read its handler seats where they
stand as plain names. A raised path whose error no named
handler could catch leaves the try as the raised path it
is, for the regions outside to carry in their own terms,
while a seat that is not a plain name, a bare handler, and
a seat naming a base error class each keep the shipped
join whole, and a raise whose expression carries no
statically plain name keeps it too. Four pins
cover the assert form, the raise form, the matching
handler control, and the non plain seat that fences the
repair.

The delta review of the second repair named one
remainder standing beyond the ruling that bounded it,
and the owner overruled that bound. A raised path of a
try else arm was judged by the same names as a raised
path of the body, so an assert or a raise standing in
an else arm under a handler naming its own error kept
the shipped credit while never loading at runtime,
because an error raised in an else arm is never caught
by the handlers of its own try, on any name, the else
arm standing outside the region those handlers guard.
The third repair takes the names out of the else arm
question altogether. A raised path of the else arm
leaves the try as the raised path it is, on every seat
plain or not, exactly as the same path behaves standing
outside a try, and the fence the second repair drew is
never reached for such a path, because no seat is read
at all. The last two pins cover the assert form and
the raise form in that seat, each under a handler
naming the very error the statement raises.
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


def test_linkage_call_after_an_assert_in_a_try_body_with_a_mismatched_handler_earns_no_credit():
    # Round 62, delta red team Minor 1, the assert form.
    # The handler names a different error, so at runtime the
    # failure of the assert is not caught, and it abandons
    # the rest of the with body on its way to the manager,
    # including the call standing after the try. The try walk
    # reads its handler seats where they stand as plain
    # names, finds no name among them that could catch the
    # error the assert raises, and lets the raised path leave
    # the try as it stands, so the manager resumes it after
    # the block holding nothing and the join strips the call.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                try:
                    assert False
                except KeyError:
                    pass
                after = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_a_raise_in_a_try_body_with_a_mismatched_handler_earns_no_credit():
    # Round 62, delta red team Minor 1, the raise twin. The
    # two statements are identical in this seat, because the
    # shipped join dropped a raised path of every kind where
    # it stood. The raise stands under the plain name of the
    # error it constructs, no handler here names that error,
    # and its path leaves the try on the same terms as the
    # assert path in the pin above.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                try:
                    raise AssertionError("stop")
                except KeyError:
                    pass
                after = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_a_try_with_a_matching_handler_still_credits():
    # Positive control for the try repair. The handler names
    # the very error the assert raises, so the failure is
    # caught at runtime and the call after the try runs on
    # the paths that reach it exactly as it did before the
    # repair. The raised path rejoins through the handler,
    # and its credit is untouched.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                try:
                    assert False
                except AssertionError:
                    pass
                after = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {CLAIMED, OTHER}


def test_linkage_call_after_an_assert_in_a_try_body_with_an_attribute_handler_seat_still_credits():
    # The fence of the try repair, pinned as it stands. The
    # handler seat is an attribute form rather than a plain
    # name, so the question of what it catches is not one a
    # static reading settles by name, and the try keeps the
    # shipped join for every raised path it carries, this
    # evasion included. The pin holds the boundary where the
    # repair stops, and it fails the day a change carries
    # the name reading past the seats the ruling names.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            import builtins
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                try:
                    assert False
                except builtins.KeyError:
                    pass
                after = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {CLAIMED, OTHER}


def test_linkage_call_after_an_assert_in_a_try_else_arm_with_a_matching_handler_earns_no_credit():
    # Round 62, the remainder of the try seat, the assert
    # form. The handler names the very error the assert
    # raises, and still the failure is never caught at
    # runtime, because the else arm stands outside the
    # region the handlers of its own try guard, so the
    # error abandons the rest of the with body on its way
    # to the manager and the call after the try never runs.
    # The walk reads no handler name for a raised path of
    # the else arm, so the path leaves the try as it
    # stands, the manager resumes it after the block
    # holding nothing, and the join strips the call.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                try:
                    pass
                except AssertionError:
                    pass
                else:
                    assert False
                after = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_a_raise_in_a_try_else_arm_with_a_matching_handler_earns_no_credit():
    # Round 62, the remainder of the try seat, the raise
    # twin. The raise constructs the very error the handler
    # names, and the seat is identical to the assert form
    # for the same reason, because no name a seat carries
    # can catch an error the else arm raises. Its path
    # leaves the try without a name being read, exactly as
    # the assert path in the pin above leaves it.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                try:
                    pass
                except AssertionError:
                    pass
                else:
                    raise AssertionError("stop")
                after = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}
