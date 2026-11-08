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
at all. Two pins cover the assert form and
the raise form in that seat, each under a handler
naming the very error the statement raises.

The second delta review of the try repairs found the
same genus one level down, inside the body of a try.
A raised path arising in the body died at the first
join it met, in a conditional arm, in a loop, under
a nested with whose manager suppresses another error,
or in a handler body, so the try join never judged it
and a loading call after the try stood credited for a
fixture it never loads. The fourth repair hands such
a path onward through every join it meets inside the
body, so the try judges each raised path of its body
in its own terms. A conditional arm and a loop hand
the path to the enclosing block where the walk stands
inside a try, and a path a try has already judged and
sent out of itself crosses the regions outside it on
the record of that judgement, so a try standing inside
a loop hands its uncaught path across the loop join.
A nested with inside the body whose one manager
stands as a suppress call under plain names resolves
only the paths whose error it names, and hands the
rest onward unresumed for the try to judge. A raised
path of a handler body leaves the try statement
outright, because no handler of a try catches an
error a handler body raises. Outside the body of a
try every join keeps the treatment the shipped walk
gives it, and the seats the earlier repairs fenced
keep their answers whole. Six pins cover
the conditional arm, the loop in the body, the try
in a loop, the nested with in its refusing form and
in its resolving control form, and the handler body.

The third delta review of the try repairs attacked
the one join the fourth repair read and left
untouched, and found the genus standing there live.
A raised path arising in a match arm died at the
match join, inside the body of a try and outside
any try alike, so a loading call after the match or
after the try stood credited while never loading at
runtime, decidable from the shape alone, a constant
subject and the raising arm the runtime always
takes. The fifth repair teaches the match join the
same hand on the other joins carry. A raised path
of an arm leaves the match as a raised path of the
enclosing block, its plain name travelling with it,
for the regions outside the statement to judge in
their own terms, a try by its seats, a with by
resuming it, a loop and a conditional on the terms
their walks state, and the raised check of a class
body by reading it. The hand on stands at the join
itself and is not read off the standing of the walk
inside a try, because the seat is the join and the
path outside any try is the same path in the same
join. The last five pins cover the assert form in a
try body, the raise twin in the same seat, the
assert form outside any try, the raise form in a
later arm, and the control whose handler names the
error the arm raises.
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


def test_linkage_call_after_an_assert_in_a_conditional_arm_in_a_try_body_earns_no_credit():
    # Round 62, second delta red team Minor 1, the
    # conditional arm form. The assert stands in one arm
    # of a conditional inside the body of the try, and the
    # conditional join dropped its raised path where it
    # stood, so the try join never judged it and the call
    # after the try stood credited. Inside the body of a
    # try the arm hands its raised path to the enclosing
    # block, the try reads its seats, finds no name that
    # could catch the error, and lets the path leave, so
    # the manager resumes it after the block holding
    # nothing and the join strips the call.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                try:
                    if client:
                        assert False
                except KeyError:
                    pass
                after = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_a_raise_in_a_loop_in_a_try_body_earns_no_credit():
    # Round 62, second delta red team Minor 1, the loop
    # form. The raise stands in a loop inside the body of
    # the try, and the loop join ended its path where it
    # stood, on the treatment the shipped walk gives a
    # raise in a loop body, so the try join never saw it.
    # Inside the body of a try the loop hands the raised
    # path to the enclosing block instead, with the plain
    # name the path stands under recorded beside the
    # handed end afresh, and the try judges it and lets
    # it leave on the same terms as a raise standing in
    # the body itself.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                try:
                    for _unused in ("x",):
                        raise AssertionError("stop")
                except KeyError:
                    pass
                after = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_a_raise_in_a_try_in_a_loop_body_earns_no_credit():
    # Round 62, second delta red team Minor 1, the try in
    # a loop form. Here the try stands inside the loop and
    # the credit stands after the loop. The try already
    # judges its raised path and sends it out, and the
    # loop join dropped it on the same shipped treatment,
    # so the path never reached the manager and the call
    # after the loop stood credited. A path a try has
    # judged and sent out of itself crosses the loop join
    # on the record of that judgement, because no
    # mechanism the loop carries resolves it, and the
    # manager resumes it after the block holding nothing.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                for _unused in ("x",):
                    try:
                        raise AssertionError("stop")
                    except KeyError:
                        pass
                after = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_an_assert_under_a_nested_with_suppressing_another_error_in_a_try_body_earns_no_credit():
    # Round 62, second delta red team Minor 1, the nested
    # with form. The assert stands under a nested with
    # whose manager suppresses a different error, inside
    # the body of the try. The nested with converted its
    # raised path to a resumed path on the type blind
    # terms the shipped with model keeps, so the try body
    # never held a raised path for its join to judge.
    # Inside the body of a try the one manager is read by
    # name where it stands as a suppress call under plain
    # names, the name proves it could not suppress the
    # error the assert raises, and the path leaves the
    # with unresumed for the try to judge.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                try:
                    with suppress(KeyError):
                        assert False
                except KeyError:
                    pass
                after = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_an_assert_under_a_nested_with_suppressing_its_own_error_in_a_try_body_still_credits():
    # Positive control for the nested with repair. The
    # nested manager names the very error the assert
    # raises, so it swallows the failure inside the body
    # at runtime and the call after the try truly runs.
    # The name reading resolves the path at the with on
    # the same plain reading that refuses it in the pin
    # above, the conversion stands, and the credit is
    # untouched. The pin fails the day the reading starts
    # refusing paths the manager genuinely suppresses.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                try:
                    with suppress(AssertionError):
                        assert False
                except KeyError:
                    pass
                after = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {CLAIMED, OTHER}


def test_linkage_call_after_an_assert_in_a_handler_body_earns_no_credit():
    # Round 62, second delta red team Minor 1, the handler
    # body form. The handler catches the failure of the
    # body assert and then fails an assert of its own, and
    # the try join dropped that second raised path where
    # it stood, while the fall path beside it, the path
    # where the handler its own assert holds, carried the
    # call after the try. No handler of a try catches an
    # error a handler body raises, so the raised path of
    # a handler body leaves the try statement outright,
    # the manager resumes it after the block holding
    # nothing, and the join strips the call.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                try:
                    assert False
                except AssertionError:
                    assert False
                after = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_an_assert_in_a_match_arm_in_a_try_body_earns_no_credit():
    # Round 62, third delta red team Minor 1, the assert
    # form. The assert stands in the arm of a match inside
    # the body of a try whose handler names a different
    # error. The match join dropped its raised path where
    # it stood, so the try join never judged it, and the
    # fall path beside it, the path where no arm fits,
    # carried the call after the try. The join at the
    # match now hands the raised path of an arm to the
    # enclosing block, the try judges it by its seats and
    # lets it leave, and the manager resumes it after the
    # block holding nothing, so the join strips the call.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                try:
                    match 1:
                        case _:
                            assert False
                except KeyError:
                    pass
                after = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_a_raise_in_a_match_arm_in_a_try_body_earns_no_credit():
    # Round 62, third delta red team Minor 1, the raise
    # twin. The two statements are identical in this seat,
    # because the match join dropped a raised path of
    # every kind where it stood. The raise stands under
    # the plain name of the error it constructs, the name
    # travels with its path across the match join, no
    # handler here names that error, and its path leaves
    # the try on the same terms as the assert path in the
    # pin above.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                try:
                    match 1:
                        case _:
                            raise AssertionError("arm")
                except KeyError:
                    pass
                after = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_an_assert_in_a_match_arm_outside_any_try_earns_no_credit():
    # Round 62, third delta red team Minor 1, the seat
    # outside any try. The assert stands in a match arm
    # in the body of the suppressing with itself, with
    # the credited call after the match. The hand on at
    # the match join stands at the join itself and is not
    # read off the standing of the walk inside a try, so
    # this path leaves the match on the same terms as the
    # paths in the pins above, the manager resumes it
    # after the block holding nothing, and the join
    # strips the call after the match.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                match 1:
                    case _:
                        assert False
                after = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_a_raise_in_a_later_match_arm_earns_no_credit():
    # Round 62, build pass 5 width sweep, the later arm
    # form. The raising arm stands second, behind an arm
    # the subject never takes and ahead of the wildcard
    # arm, and the credited call stands after the match.
    # The seat is the join and not the arm that carries
    # the statement, so a raised path of any arm leaves
    # the match on the same terms, and this pin fails the
    # day the hand on narrows to the first arm or to the
    # wildcard arm alone.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                match 1:
                    case 2:
                        pass
                    case 1:
                        raise AssertionError("arm")
                    case _:
                        pass
                after = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_a_raise_in_a_match_arm_under_a_handler_naming_it_still_credits():
    # Positive control for the match hand on. The handler
    # names the very error the arm raises, so it catches
    # the failure inside the body at runtime and the call
    # after the try truly runs. The raised path now
    # reaches the try join and is judged there, the name
    # it stands under stands among the names the handler
    # names, and the handlers carry it onward exactly as
    # they carry a raise standing in the body itself, so
    # the credit is untouched. The pin fails the day the
    # hand on starts refusing paths a named handler
    # genuinely catches.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(AssertionError):
                try:
                    match 1:
                        case _:
                            raise AssertionError("arm")
                except AssertionError:
                    pass
                after = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {CLAIMED, OTHER}
