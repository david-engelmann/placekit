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

The landing red team then evaded the pass two analysis six
more ways, in repair pass three, by placing the loading call
itself where the interpreter never takes it. The fork and the
join governed bindings only, and the credited set was a single
shared set any walked call could write into, so a call in an
untaken conditional arm, a zero trip loop body, an exception
handler, or an unmatched match arm earned full credit, and so
did a call inside a nested function or a lambda that was never
invoked. The analysis now forks the credited set with the
environment at every region and joins it by intersection, so
a fixture counts only when a loading call resolving to it runs
on every path, it never walks a deferred body, and it keeps
loop body credit only for the loops it can prove run at least
once. The pins below cover those forms, plus the positive
controls that keep the intersection honest.

The landing red team then evaded the pass three analysis in
three more families, in repair pass four. The walk modelled
no path ending, so a loading call after a return, after a
conditional whose arms both return, or after a raise inside
a with body earned credit from dead code. The expression
scan walked flat, so a call inside a comprehension over an
empty sequence, inside a generator expression nobody
consumes, behind a short circuited boolean operand, or in
the untaken branch of a conditional expression earned
credit the interpreter never gave it. And a class body
walked in the enclosing environment, so a binding written
there leaked into the test and shadowed the name the live
call reads. The analysis now ends a path at the statement
that ends it and counts only the paths that complete, the
expression scan carries the same evaluation discipline as
the statement walk, and a class body walks in a forked
environment whose bindings are discarded when the
definition ends. The pins below cover those forms, plus
the positive controls that keep the new rules honest.

The landing red team then evaded the pass four analysis in
three more families, in repair pass five. A loop target
bound to the whole literal set outlived its loop, so a call
after the loop collected every element while loading only
the last one, and a name the body derived from the target
inherited the whole set the same way. The loader set the
guard derives could be poisoned by a helper that calls a
loader without handing over the name it was given, openly
or behind a branch that routes the claimed name elsewhere.
And a suppressing with body could be abandoned by an
exception raised inside an expression, a shape that turns
on data the test source does not carry, so it stands as a
named residual outside the guard's static contract rather
than a repair. The analysis now ends a loop in the state
the interpreter leaves behind, and a helper joins the
loader set only when it provably loads the fixture name it
is handed. The pins below cover the repaired forms, plus
the positive controls that keep the new rules honest.

The landing red team then evaded the pass five analysis in
three more families, in repair pass six, every one inside
the fenced contract. The faithfulness proof tried the
parameters of a helper in turn, and a helper that handed
its client or raw response parameter to a multi argument
loader in a non name slot passed the proof through a
parameter carrying no fixture name, while the name slot
itself was fed a fixed name on the fall through path. A
nested definition declaring a name nonlocal rewrote the
binding the walk was tracking, in a test body and inside a
helper under the proof, while the walk treated the call as
inert. And the disk reading seed of the derivation joined
on a dependence check and was never proven, so a seed that
diverted one name, or read its argument as a decoy and
returned a fixed name, lent the whole derived set its
trust. The proof now runs once with every parameter bound
to its own distinct symbolic name and credits only the
argument in a loader's name slot, a name any nested
definition declares nonlocal or global reads as
unresolvable from the definition onward, and the seed is
proven in the same terms with its reads standing in for
loading calls. The pins below cover those forms, plus the
positive control that keeps the stronger proof honest.
"""

from __future__ import annotations

import textwrap

from test_corpus_accounting import (
    RECORDED_LOADERS,
    _fixtures_a_test_loads,
    _loader_function_names,
)

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


def test_linkage_call_in_an_untaken_conditional_arm_earns_no_credit():
    # Repair pass three, red team form 5a. The claimed name is
    # handed to the loader only inside a conditional arm the
    # runtime never takes, while the live call loads the other
    # fixture. The arm is one path through the region and the
    # untouched path is the other, so the intersection of the
    # credited sets holds nothing from the arm.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{OTHER}"
            if client is None:
                dead = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_in_a_zero_trip_loop_body_earns_no_credit():
    # Repair pass three, red team form 5b. The claimed name is
    # handed to the loader only inside a loop body that iterates
    # over an empty tuple, so the body never runs. The zero trip
    # path joins the intersection, so the body credit earns
    # nothing and only the live call after the loop counts.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{OTHER}"
            for _unused in ():
                dead = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_in_an_exception_handler_earns_no_credit():
    # Repair pass three, red team form 5c. The claimed name is
    # handed to the loader only inside an exception handler, and
    # the try body completes without raising, so the handler
    # never runs. The handler path and the body path join by
    # intersection, so the handler credit earns nothing.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{OTHER}"
            try:
                pass
            except Exception:
                dead = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_in_an_uncalled_nested_function_earns_no_credit():
    # Repair pass three, red team form 5d. The claimed name is
    # handed to the loader only inside a nested function the
    # test defines and never calls. A deferred body is never
    # walked, so its calls earn no credit, the same helper
    # treatment a call into another module receives.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{OTHER}"
            def deferred():
                return search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_in_an_unmatched_match_arm_earns_no_credit():
    # Repair pass three, red team form 5e. The claimed name is
    # handed to the loader only inside a match arm whose pattern
    # the subject never fits. The path where no arm fits joins
    # the intersection beside each arm, so the arm credit earns
    # nothing.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{OTHER}"
            match 1:
                case 2:
                    dead = search(client, raw_response, "{CLAIMED}")
                case _:
                    pass
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_in_an_uninvoked_lambda_earns_no_credit():
    # Repair pass three, red team form 5f. The claimed name is
    # handed to the loader only inside a lambda the test binds
    # and never invokes. A lambda body is deferred code and is
    # never walked, so the call inside it earns no credit.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{OTHER}"
            deferred = lambda: search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_in_both_conditional_arms_still_credits():
    # Positive control for the intersection. Both arms of the
    # conditional hand the claimed name to the loader, so the
    # call runs on every path and the credit survives the join.
    # The intersection refuses credit a path skips, not credit
    # every path records.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            if client is not None:
                result = search(client, raw_response, "{CLAIMED}")
            else:
                result = search(client, raw_response, "{CLAIMED}")
        """
    )
    assert loaded == {CLAIMED}


def test_linkage_call_in_a_finally_arm_still_credits():
    # Positive control for the try join. The finally arm runs on
    # every path, so it walks as straight line code after the
    # join and a loading call inside it earns ordinary credit.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            try:
                pass
            finally:
                result = search(client, raw_response, "{CLAIMED}")
        """
    )
    assert loaded == {CLAIMED}


def test_linkage_call_in_a_nonempty_literal_loop_still_credits():
    # Positive control for the loop exemption. The loop runs
    # over a literal tuple with two elements and its body
    # carries no break, continue, return, or raise, so the body
    # is proven to run and the credit its call records survives
    # the join without a zero trip path in the intersection.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            for _unused in ("one", "two"):
                result = search(client, raw_response, "{CLAIMED}")
        """
    )
    assert loaded == {CLAIMED}


def test_linkage_call_after_an_unconditional_return_earns_no_credit():
    # Repair pass four, red team form 6a. The claimed name is
    # handed to the loader only after a return has already
    # ended the test, so the call is dead code and the fixture
    # is never opened. The live call before the return loads
    # the other fixture and keeps its credit.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{OTHER}"
            result = search(client, raw_response, fixture_name)
            return
            dead = search(client, raw_response, "{CLAIMED}")
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_a_conditional_whose_arms_both_return_earns_no_credit():
    # Repair pass four, red team form 6c. Both arms of the
    # conditional return, so every path through it has ended
    # and the call after it is dead code on all of them, with
    # no constant condition and no dead arm involved.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{OTHER}"
            result = search(client, raw_response, fixture_name)
            if client is not None:
                return
            else:
                return
            dead = search(client, raw_response, "{CLAIMED}")
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_a_raise_in_a_with_body_earns_no_credit():
    # Repair pass four, red team form 6d. The raise abandons
    # the with body at once, so the call standing after it in
    # the body never runs, whether or not the context manager
    # suppresses the exception. The with walk forks its body,
    # so the dead call earns nothing and the live call after
    # the block loads the other fixture.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            from contextlib import suppress
            fixture_name = "{OTHER}"
            with suppress(RuntimeError):
                raise RuntimeError("stop")
                dead = search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_in_a_comprehension_over_an_empty_sequence_earns_no_credit():
    # Repair pass four, red team form 7a. The comprehension
    # iterates over an empty tuple, so its body runs zero
    # times and the call inside it never runs. A comprehension
    # body earns credit only on a provably nonempty literal
    # sequence, so the claimed fixture earns nothing.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{OTHER}"
            dead = [search(client, raw_response, "{CLAIMED}") for _unused in ()]
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_in_an_unconsumed_generator_expression_earns_no_credit():
    # Repair pass four, red team form 7b. A generator
    # expression is lazy and nothing in the test consumes it,
    # so its body never runs even though its iterable holds an
    # item. The body is deferred code and earns no credit, as
    # a lambda body earns none.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{OTHER}"
            dead = (search(client, raw_response, "{CLAIMED}") for _unused in ("x",))
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_behind_a_short_circuited_operand_earns_no_credit():
    # Repair pass four, red team form 7c. The constant False
    # decides the boolean operation, so the right operand is
    # never evaluated and the call inside it never runs. An
    # operand earns credit only behind constants that
    # guarantee its evaluation.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{OTHER}"
            dead = False and search(client, raw_response, "{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_in_an_untaken_conditional_expression_branch_earns_no_credit():
    # Repair pass four, red team form 7d. The condition of
    # the conditional expression selects the other branch, so
    # the branch holding the claimed call is never evaluated.
    # The branches fork and join by intersection, so a call
    # standing in only one of them earns nothing.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{OTHER}"
            dead = search(client, raw_response, "{CLAIMED}") if client is None else None
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_rebind_inside_a_class_body_earns_no_credit():
    # Repair pass four, red team form 8a. The class body runs
    # when the definition does, but its assignments land in
    # the class namespace, so the test local still holds the
    # other fixture when the live call reads it. The body
    # walks in a forked environment whose bindings are
    # discarded, so the claimed fixture earns nothing.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{OTHER}"
            class Holder:
                fixture_name = "{CLAIMED}"
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_in_both_conditional_expression_branches_still_credits():
    # Positive control for the expression fork. Both branches
    # of the conditional expression hand the claimed name to
    # the loader, so whichever branch the condition selects
    # the call runs, and the credit survives the intersection.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            result = search(client, raw_response, "{CLAIMED}") if client is not None else search(client, raw_response, "{CLAIMED}")
        """
    )
    assert loaded == {CLAIMED}


def test_linkage_call_behind_a_guaranteeing_constant_still_credits():
    # Positive control for the short circuit rule. The
    # constant True guarantees the right operand of the and
    # evaluates, so the call behind it runs on every path and
    # keeps its credit.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            result = True and search(client, raw_response, "{CLAIMED}")
        """
    )
    assert loaded == {CLAIMED}


def test_linkage_call_in_a_comprehension_over_a_nonempty_literal_still_credits():
    # Positive control for the comprehension rule. The
    # comprehension iterates over a literal tuple with two
    # elements, so its body provably runs and the credit its
    # call records is genuine.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            results = [search(client, raw_response, "{CLAIMED}") for _unused in ("x", "y")]
        """
    )
    assert loaded == {CLAIMED}


def test_linkage_call_in_a_class_body_still_credits():
    # Positive control for the class scope rule. A loading
    # call written directly in a class body runs when the
    # class is defined, so it earns its credit, while the
    # same body's rebind earns the enclosing scope nothing
    # and the live call after the definition loads the other
    # fixture.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{OTHER}"
            class Holder:
                fixture_name = "{CLAIMED}"
                payload = fixture_payload("{CLAIMED}")
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {CLAIMED, OTHER}


def test_linkage_call_after_the_loop_through_the_target_earns_no_false_credit():
    # Repair pass five, red team form 9a. Inside the body the
    # target resolves to every element, because the body runs
    # once per element, but the loop ends holding the last
    # element alone, so the call after the loop loads only
    # that one. The claimed fixture is an earlier element the
    # call never opens, and the set binding the walked body
    # pass held earns it nothing after the loop.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            for fixture_name in ("{CLAIMED}", "{OTHER}"):
                pass
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {OTHER}


def test_linkage_call_after_the_loop_through_a_derived_name_earns_no_false_credit():
    # Repair pass five, red team form 9b. The body derives a
    # name from the loop target on every pass, and the loop
    # ends holding the value the last pass left in it, so the
    # call after the loop loads only the last element. The
    # claimed fixture earns nothing through the derived name,
    # which inherits the narrowed end state, not the set the
    # walked body pass carried.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            for fixture_name in ("{CLAIMED}", "{OTHER}"):
                chosen = fixture_name
            result = search(client, raw_response, chosen)
        """
    )
    assert loaded == {OTHER}


def test_linkage_post_loop_call_credits_exactly_the_last_element():
    # Positive control for the loop end state. The claim sits
    # in the last element of the iterable, so the call after
    # the loop, reading the target the interpreter leaves
    # behind, credits exactly it and no other element. A
    # repair that refused the target after every loop would
    # fail this pin, and so would the set binding it replaces.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            for fixture_name in ("{OTHER}", "{CLAIMED}"):
                pass
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == {CLAIMED}


def _derived_loaders(tmp_path, source: str) -> set[str]:
    # The derivation reads a module file from the tests
    # folder, and an absolute path stands in for it under the
    # joining rules of pathlib, so a synthetic module written
    # to the test's own scratch folder derives its loader set
    # exactly as the shipped module derives its own.
    module = tmp_path / "synthetic_corpus.py"
    module.write_text(textwrap.dedent(source))
    return _loader_function_names(str(module))


def test_loader_derivation_refuses_a_helper_that_drops_its_argument(tmp_path):
    # Repair pass five, red team form 11a. The helper calls a
    # loader on a fixed name of its own and never hands over
    # the name it was given, so it is not a helper that loads
    # a fixture by name. Admitting it would credit a test
    # calling it with the claimed fixture while the helper
    # opens another one.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader("recorded_P1_no_address_natural_feature.json")
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_that_passes_its_argument_on_one_branch(
    tmp_path,
):
    # Repair pass five, red team form 11b. The helper hands
    # its argument to a loader on a branch the claimed name
    # never takes and loads a fixed name on the path it does
    # take, so the name it loads is not the name it is handed
    # on every path, and the derivation refuses it the same
    # way. Passing a name through somewhere is not enough.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            if name == "recorded_P1_no_address_natural_feature.json":
                return reader(name)
            return reader("recorded_P1_no_address_natural_feature.json")
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_admits_a_faithful_helper_and_credits_through_it(tmp_path):
    # Positive control for the derivation. A helper that
    # hands the name it was given to a loader joins the set,
    # and a test calling it with a fixture name earns the
    # credit for that name through it, so the faithfulness
    # proof refuses dishonest helpers without refusing the
    # honest shape the shipped helpers all carry.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def faithful_search(client, raw_response, name):
            return reader(name)
        """,
    )
    assert loaders == {"reader", "faithful_search"}
    loaded = _fixtures_a_test_loads(
        textwrap.dedent(
            f"""
            def test_shape(client, raw_response):
                result = faithful_search(client, raw_response, "{CLAIMED}")
            """
        ),
        loaders,
    )
    assert loaded == {CLAIMED}


def test_loader_derivation_refuses_a_helper_proven_through_a_non_name_parameter(
    tmp_path,
):
    # Repair pass six, red team form 11b in its refined shape.
    # The helper hands its name to a three argument loader on
    # the branch the claimed name never takes and a fixed name
    # on the fall through path it does take. The pass five
    # proof tried the parameters in turn, and the client
    # parameter, handed to the loader in its own slot at both
    # return sites, earned the symbolic credit through a slot
    # that carries no fixture name. The proof now binds every
    # parameter to its own distinct symbolic name in a single
    # run and credits only the argument in the name slot, so
    # the fall through path credits the fixed name, the branch
    # credits the handed name, and no one parameter is
    # credited on every path.
    loaders = _derived_loaders(
        tmp_path,
        f"""
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def replay(client, raw_response, name):
            return reader(name)


        def shadow_search(client, raw_response, name):
            if name == "{OTHER}":
                return replay(client, raw_response, name)
            return replay(client, raw_response, "{OTHER}")
        """,
    )
    assert loaders == {"reader", "replay"}


def test_linkage_nonlocal_rebind_inside_a_nested_function_earns_no_credit():
    # Repair pass six, red team form 12a. The nested
    # definition declares the fed local nonlocal and rebinds
    # it to the other fixture when called, so the live call
    # loads that fixture at runtime. The walk treats the call
    # into a nested definition as inert, which settles the
    # credit its body earns and not the write it lands, so a
    # name any nested definition declares nonlocal or global
    # reads as unresolvable from the definition onward and
    # the claimed fixture earns nothing.
    loaded = _loads(
        f"""
        def test_shape(client, raw_response):
            fixture_name = "{CLAIMED}"
            def swap():
                nonlocal fixture_name
                fixture_name = "{OTHER}"
            swap()
            result = search(client, raw_response, fixture_name)
        """
    )
    assert loaded == set()


def test_loader_derivation_refuses_a_helper_whose_closure_rebinds_its_name(
    tmp_path,
):
    # Repair pass six, red team form 12b. The same write back
    # one level up, inside a helper under the faithfulness
    # proof. The helper's nested definition rebinds its name
    # parameter to the other fixture before the return hands
    # the parameter to the loader, so at runtime the helper
    # loads that fixture whatever it was handed. The declared
    # name reads as unresolvable under the proof as it does
    # in a test body, the return credits nothing, and the
    # helper is refused.
    loaders = _derived_loaders(
        tmp_path,
        f"""
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            def swap():
                nonlocal name
                name = "{OTHER}"
            swap()
            return reader(name)
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_seed_reader_that_diverts_one_name(tmp_path):
    # Repair pass six, red team form 13a. The reader at the
    # bottom of the module returns the other fixture's bytes
    # for the claimed name and reads faithfully for every
    # other name, so the whole corpus module stays green
    # while the one claimed fixture is never opened. The seed
    # joined on a dependence check that never asked what its
    # returns carry. It is now proven in the callers' terms,
    # its reads standing in for loading calls, and the
    # diverting path credits the fixture it actually reads,
    # so the reader is refused and the helper above it,
    # faithful as it is, derives nothing without it.
    loaders = _derived_loaders(
        tmp_path,
        f"""
        ROOT = None


        def fixture_bytes(name):
            if name == "{CLAIMED}":
                return (ROOT / "{OTHER}").read_bytes()
            return (ROOT / name).read_bytes()


        def fixture_payload(name):
            return fixture_bytes(name)
        """,
    )
    assert loaders == set()


def test_loader_derivation_refuses_a_seed_reader_that_reads_a_decoy(tmp_path):
    # Repair pass six, red team form 13b. The reader reads
    # the path built from its argument and throws the bytes
    # away, returning the bytes of a fixed name instead. The
    # dependence check was satisfied by the decoy read while
    # the returned read never consulted the argument. Under
    # the seed proof the one completing path credits both the
    # handed name and the fixed name, which is not the handed
    # name alone, so the reader is refused.
    loaders = _derived_loaders(
        tmp_path,
        f"""
        ROOT = None


        def fixture_bytes(name):
            _ = (ROOT / name).read_bytes()
            return (ROOT / "{OTHER}").read_bytes()


        def fixture_payload(name):
            return fixture_bytes(name)
        """,
    )
    assert loaders == set()


def test_loader_derivation_admits_a_faithful_multi_argument_helper(tmp_path):
    # Positive control for the pass six proof. A helper that
    # hands the name it was given to a three argument loader,
    # in the loader's name slot, with its other parameters in
    # their own slots, derives through the chain and credits
    # a test that calls it, so the distinct symbolic binding
    # and the name slot rule refuse the dishonest shapes
    # without refusing the honest multi argument shape the
    # shipped replayers carry.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def replay(client, raw_response, name):
            return reader(name)


        def faithful_search(client, raw_response, name):
            return replay(client, raw_response, name)
        """,
    )
    assert loaders == {"reader", "replay", "faithful_search"}
    loaded = _fixtures_a_test_loads(
        textwrap.dedent(
            f"""
            def test_shape(client, raw_response):
                result = faithful_search(client, raw_response, "{CLAIMED}")
            """
        ),
        loaders,
    )
    assert loaded == {CLAIMED}
