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

The landing red team then evaded the pass six analysis in
one more family, in repair pass seven, through the proofs
themselves. Both proofs judged a candidate on the credit
of the paths that complete alone, and a path that ends in
a raise contributed no entry at all, so a helper that
loaded a fixed name on a branch and then raised off it
was judged on its honest paths, and the seed reader could
hide the same load in the same way at the root of the
derivation. A caller wrapping the certified helper in a
suppressing with survives the raise and asserts on a
fixture it loaded honestly, so the claimed name borrowed
credit for a fixture the test never opened. The proofs
now count the paths that end in a raise beside the paths
that complete, and a candidate is refused when a raised
path holds credit for anything but the one symbolic name
its completing paths proved. The pins below cover both
forms, plus the positive control that keeps the raised
counting honest.

The landing red team then evaded the pass seven analysis
in one more family, in repair pass eight, at the
derivation's own premise about what a certified name is.
The proofs judged a candidate by the body of one function
definition, and never asked whether calling the name runs
that body, or whether the module level name still denotes
it. A generator function helper loads nothing when it is
called, because its body is deferred entire, and a helper
rebound by a later module level assignment, or displaced
by a decorator at definition time, leaves the certified
body dead code under a live name. Admission to the proofs
now refuses all three shapes before any proof runs, a
candidate whose own body holds a yield outside a nested
definition, a candidate carrying a decorator, and a
candidate whose name a later module level statement
rebinds, and a pin holds the neighbouring async shape,
which the candidate collection has never gathered, so its
door cannot open in silence either. The pins below cover
those forms.

The landing red team then evaded the pass eight analysis
in one more family, in repair pass nine, inside the
admission step the pass built. Admission reads a later
module level rebinding two ways, the assignment family
through the shared pair collector and definitions and
imports through a scan, and a binding standing in the
head of a compound statement is read by neither, because
a pattern and a with target are parts of a statement
rather than statements. A faithful helper rebound by a
match capture pattern, or by the target of a with item,
kept its certification while the name denoted a lambda
that loads nothing, where the same rebind as a plain
assignment inside the match arm or the with body was
already refused. The rebind reading now gathers the with
item targets and the match pattern names standing among
the later statements, at the same reach it gives the
assignments inside their arms. The pins below cover
those forms, plus the boundary control that keeps the
line between a head binding and a body assignment
honest.

The landing red team then evaded the pass nine analysis
in one more family, in repair pass ten, inside the
admission step again. Every reading admission performs
reads the statements standing after a candidate for the
binding positions it knows, and none of them enters a
definition standing among them, so a faithful helper
followed by a definition that assigns its name under a
global declaration, and by a module level call that
runs that definition as the module loads, kept its
certification while the name denoted a lambda that
loads nothing. Admission now gathers the names each
later definition assigns under a global declaration
and refuses the candidate when a later module level
statement calls such a definition, the refusal keying
on the call, so an installer that is never called
refuses nothing and the name keeps the body it was
certified on. The pins below cover the form and the
boundary that keeps the refusal honest.

The landing red team then evaded the pass ten analysis
in one more family, in repair pass eleven, inside the
execution reading the pass added. That reading followed
a module level call exactly one body deep and only
into the plain definitions standing after a candidate,
so a faithful helper whose name an installer rewrote
through a second called definition, or through a call
standing in the body of a class at module level, or
through the constructor of a class the module level
constructed, or from an installer standing before it
and called after it, kept its certification while the
name denoted a lambda that loads nothing. Admission
now gathers the write sets from every module level
definition and from the constructor method of every
module level class, wherever they stand, and reads
the executions standing after a candidate as a reach
that closes over the calls those executions make,
counting the bodies of classes standing at module
level among the executing statements and a call
naming a class as a call into its constructor. The
refusal still keys on the execution, so a chain no
statement calls and a class no statement constructs
refuse nothing. The pins below cover those forms and
the reachability boundaries that keep the refusal
honest.

The landing red team then evaded the pass eleven
analysis in one more family, in repair pass twelve,
inside the call collection of the execution reading.
That collection returned whole at every definition
and every lambda it met, and the stop discarded more
than bodies, because a definition statement performs
its decorator expressions and its default values and
its annotations as it runs, and a lambda a statement
invokes on the spot runs its body as part of that
statement, so an installer call standing in any of
those places was never collected, while the same
decorator expression standing on a class was already
read. Two construction shapes stood beside the
family at the same distance, a dunder new method
that assigns the name under a global declaration and
a constructor inherited from a module level base
class, each one step past a construction reading
that consulted the dunder init method defined in the
class itself alone. The call collection now reads
the header of a definition standing in an executing
position, without entering its body, and reads the
body of a lambda a call invokes where it stands,
while a lambda no statement invokes contributes only
its defaults, and the construction write set of a
class gathers from its dunder new method beside its
dunder init method and through the module level base
classes it names. The pins below cover those forms,
plus the control that keeps the uninvoked lambda
honest.

The landing red team then evaded the pass twelve
analysis in one more family, in repair pass thirteen,
in the executions a class statement performs
implicitly. Creating a class runs the subclass hook
of every base it names and the construction of the
metaclass it names, and neither execution wears the
shape of a call standing in the source, so an
installer called from a hook on a module level base,
and a name rewritten by a metaclass at class
creation, were never collected, though the write set
of the metaclass stood gathered among the targets
the reach consults and only the invocation was
missing. And a class standing inside a body the
reach has entered was stepped over whole, so a
decorator expression on such a class was discarded
with its body, though the header of a function
definition in the same position was already read and
the header of a class at module level was read
before it. A class creation now counts beside the
header and body readings, as a call into the
subclass hooks of the module level bases the class
names, resolved through the base chain, and, when
its metaclass keyword names a module level class, as
a call into the construction gathered for that name,
and a class in any executing position contributes
its header parts while its body inside a reached
body stays deferred. The pins below cover those
forms, plus the boundary control that marks where
the family ended.

The landing red team then evaded the pass thirteen
analysis in one more family, in repair pass fourteen,
in two further executions of class creation the
counting still did not name. Creating a class calls
the set name method of every descriptor standing in
the namespace its body builds, so an installer called
from the set name hook of a descriptor class a class
body instantiates ran as the creation ran, though no
reading gathered that method at all. And a class
whose statement names no metaclass is constructed by
the metaclass it inherits from its bases, so a name
rewritten by a metaclass reached only through a base
class was never counted, though the construction of
that metaclass stood gathered from the base that
named it. A class creation now counts as a call into
the set name methods of the descriptor classes whose
instances stand assigned in its body, resolved by
plain name through their base chains, and, when its
keywords name no metaclass, as a call into the
construction of the most derived metaclass its bases
stand under, counting every candidate the base chains
leave unordered between themselves. The pins below
cover those forms, plus the control that keeps a
hookless descriptor honest.
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


def test_loader_derivation_refuses_a_helper_that_loads_a_fixed_name_on_a_raised_path(
    tmp_path,
):
    # Repair pass seven, red team form 14a. The helper loads
    # a fixed name on the branch written for the claimed name
    # and raises off that branch, returning the handed name
    # on the fall through. The proof judged the completing
    # paths alone, and the raised path contributed no entry,
    # so the helper was adopted and a suppressing caller
    # could lend the claimed name its credit. The proof now
    # counts the raised paths beside the completing ones,
    # and the raised path here holds the fixed name, which
    # is not the symbolic name of the proven parameter, so
    # the helper is refused.
    loaders = _derived_loaders(
        tmp_path,
        f"""
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def replay(client, raw_response, name):
            return reader(name)


        def shadow_search(client, raw_response, name):
            if name == "{CLAIMED}":
                replay(client, raw_response, "{OTHER}")
                raise RuntimeError("boom")
            return replay(client, raw_response, name)
        """,
    )
    assert loaders == {"reader", "replay"}


def test_loader_derivation_refuses_a_seed_reader_that_reads_a_fixed_name_on_a_raised_path(
    tmp_path,
):
    # Repair pass seven, red team form 14b. The same shape
    # at the root of the derivation. The reader reads a
    # fixed name into a value nothing returns on the branch
    # written for the claimed name and raises, reading the
    # handed name faithfully on the completing path, so the
    # seed proof, judging the completing paths alone, seeded
    # the set with a poisoned reader every faithful helper
    # above it derived through. The seed proof counts the
    # raised paths beside the completing ones, the raised
    # path holds the fixed name, and the reader is refused,
    # so the helper above it derives nothing without it.
    loaders = _derived_loaders(
        tmp_path,
        f"""
        ROOT = None


        def fixture_bytes(name):
            if name == "{CLAIMED}":
                (ROOT / "{OTHER}").read_bytes()
                raise RuntimeError("boom")
            return (ROOT / name).read_bytes()


        def fixture_payload(name):
            return fixture_bytes(name)
        """,
    )
    assert loaders == set()


def test_loader_derivation_admits_a_helper_whose_raised_path_loads_the_handed_name(
    tmp_path,
):
    # Positive control for the raised counting. The helper
    # loads the name it was handed on the branch it abandons
    # with a raise and returns the handed name on the fall
    # through, so its raised path holds credit for the
    # handed name alone, which the counting allows, and the
    # helper derives and credits a test that calls it. A
    # repair that refused every candidate carrying a raised
    # path would fail this pin, and so would one that
    # refused the raise's own load.
    loaders = _derived_loaders(
        tmp_path,
        f"""
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def replay(client, raw_response, name):
            return reader(name)


        def faithful_search(client, raw_response, name):
            if name == "{CLAIMED}":
                replay(client, raw_response, name)
                raise RuntimeError("boom")
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


def test_loader_derivation_refuses_a_generator_function_helper(tmp_path):
    # Repair pass eight, red team form 15a. The helper's
    # whole body is a yield wrapping the loading call, so
    # the definition is a generator function and calling it
    # runs none of its body, returning a generator nothing
    # iterates. The proof credited the wrapped call as
    # straight line code and adopted the helper, so a test
    # calling it with the claimed name earned credit for a
    # fixture no call ever opens. Admission now refuses a
    # candidate whose own body holds a yield outside a
    # nested definition, deferred code of the kind the
    # guard refuses everywhere else.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            yield reader(name)
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rebound_at_module_level(tmp_path):
    # Repair pass eight, red team form 15c. The helper's
    # body is faithful, and a module level assignment
    # standing after the definition hands its name to a
    # lambda that loads nothing, so the name a test calls
    # denotes the lambda and never the certified body. The
    # derivation collected its candidates from the
    # definitions alone and never reconciled the name
    # against the module's later statements. Admission now
    # refuses a candidate whose name any later module
    # level statement rebinds.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        shadow_search = lambda client, raw_response, name: None
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_decorated_helper(tmp_path):
    # Repair pass eight, red team form 15d. The same
    # unexamined binding through the definition time door.
    # The decorator replaces the function with a lambda
    # that loads nothing when the definition runs, and the
    # proof judged the undecorated body alone, because a
    # decorator is no part of the body it walks. Admission
    # now refuses a candidate carrying any decorator, whose
    # return the walk cannot see.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def swallower(function):
            return lambda client, raw_response, name: None


        @swallower
        def shadow_search(client, raw_response, name):
            return reader(name)
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_an_async_helper(tmp_path):
    # Repair pass eight, red team form 15b, the boundary
    # of the family. An async helper's body is deferred in
    # the same way, a call returning a coroutine nothing
    # awaits, and it is refused today because the candidate
    # collection gathers plain function definitions alone
    # and never hands an async definition to a proof. The
    # proof handed the node directly would admit the body,
    # so the refusal rests on the collection and nowhere
    # else. This pin names the shape, so a widening of the
    # collection made for any innocent reason fails here
    # instead of opening the door in silence.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        async def shadow_search(client, raw_response, name):
            return reader(name)
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rebound_by_a_match_capture(tmp_path):
    # Repair pass nine, red team form 16a. The helper's
    # body is faithful, and a module level match statement
    # standing after the definition captures its name onto
    # a lambda that loads nothing, so the name a test calls
    # denotes the lambda and never the certified body. The
    # rebind reading gathered the assignment family and the
    # definitions and imports standing in a statement, and
    # a pattern is neither, so the capture standing in the
    # head of the match was never read. Admission now reads
    # the names a match pattern captures beside the
    # assignments inside its arms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        match (lambda client, raw_response, name: None,):
            case (shadow_search,):
                pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rebound_by_a_with_item_target(tmp_path):
    # Repair pass nine, red team form 16b. The same
    # unexamined binding through the other compound head.
    # The with statement enters its box as the module
    # loads, and its item target binds the helper name to
    # the lambda the enter method returns, so the name
    # denotes that lambda from load time onward. The pair
    # collector has no with case among the assignment
    # shapes it gathers, and the definition and import scan
    # finds nothing it counts in a with, so the target
    # standing in the head of the statement was never read.
    # Admission now reads the target of a with item beside
    # the assignments inside its body.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        class _ShadowBox:
            def __enter__(self):
                return lambda client, raw_response, name: None

            def __exit__(self, *exc):
                return False


        with _ShadowBox() as shadow_search:
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rebound_inside_a_with_body(tmp_path):
    # Repair pass nine, the boundary control, red team
    # form 16d. The same rebind as a plain assignment
    # standing inside the with body rather than in its
    # head. The pair collector has always read the
    # assignments standing in the arms of a compound
    # statement, so this shape refused before the head
    # reading existed, and the pin holds the line the
    # family turned on, between the binding in the head,
    # which the new reading gathers, and the assignment in
    # the body, which the collector already gathered.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        from contextlib import suppress

        with suppress(RuntimeError):
            shadow_search = lambda client, raw_response, name: None
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_a_called_installer(tmp_path):
    # Repair pass ten, red team form 17a. The helper's
    # body is faithful, and a definition standing after
    # it assigns its name under a global declaration, and
    # a bare module level call runs that definition as
    # the module loads, so the name a test calls denotes
    # the lambda the installer leaves behind and never
    # the certified body. Every reading admission
    # performs reads the statements standing after a
    # candidate for the binding positions it knows, and
    # none of them enters a definition standing among
    # them, and a bare call is an execution no reading
    # counted. Admission now gathers the names each later
    # definition assigns under a global declaration and
    # refuses the candidate when a later module level
    # statement calls such a definition.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        _install_shadow()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_admits_a_helper_beside_an_uncalled_installer(tmp_path):
    # Repair pass ten, the boundary, red team form 17c.
    # The same installer definition standing after the
    # helper and never called. The name still denotes
    # the faithful body, because the definition alone
    # rewrites nothing until a call runs it, so the
    # refusal keys on the call and not on the presence
    # of the installer, and the helper derives beside
    # the reader it loads through.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_intermediary(tmp_path):
    # Repair pass eleven, red team form 18a. The module
    # level calls a second definition whose body calls
    # the installer, so the execution reaches the global
    # write through two bodies. The pass ten reading
    # followed a module level call exactly one body deep,
    # and the call that names the installer stands inside
    # the intermediary, behind the definition boundary
    # its call gathering would not cross. The reach now
    # closes over the calls a called body makes in turn.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _run_installer():
            _install_shadow()


        _run_installer()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_from_a_class_body(tmp_path):
    # Repair pass eleven, red team form 18b. A class
    # standing at module level holds the installer call
    # in its body, and a class body executes as the
    # module loads, in source order, exactly as a bare
    # statement does. The pass ten call gathering
    # returned at the class definition without entering
    # its body. The bodies of classes standing at module
    # level now count among the executing statements the
    # reach is read from.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _LoadTrigger:
            _install_shadow()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_constructor(tmp_path):
    # Repair pass eleven, red team form 18c. The
    # rewriting definition is the constructor method of
    # a class the module level constructs, and the pass
    # ten installer gathering consulted the write sets
    # of plain definitions alone, so the constructor
    # write set was never gathered. The write set of the
    # constructor method now stands for the class name,
    # and a call naming the class counts as a call into
    # it.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        class _ShadowInstaller:
            def __init__(self):
                global shadow_search
                shadow_search = lambda client, raw_response, name: None


        _ShadowInstaller()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_installer_standing_before_it(tmp_path):
    # Repair pass eleven, the spec review sibling of
    # form 17a. The installer stands before the helper
    # in the module and the call stands after it, and
    # the pass ten gathering was scoped to definitions
    # standing after the candidate, so the installer was
    # never gathered even though the call runs after the
    # helper is defined and leaves the name denoting the
    # lambda. The write sets are now gathered from the
    # whole module, wherever a definition stands, while
    # the reach is still read from the executions
    # standing after the candidate alone.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def shadow_search(client, raw_response, name):
            return reader(name)


        _install_shadow()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_admits_a_helper_beside_a_chain_never_called(tmp_path):
    # Repair pass eleven, the boundary. The intermediary
    # and the installer of form 18a stand in the module
    # and no statement calls the intermediary, so nothing
    # executes the installer and the name still denotes
    # the faithful body. The reach begins at a statement
    # that executes and not at the presence of the chain,
    # so the helper derives beside the reader it loads
    # through.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _run_installer():
            _install_shadow()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_admits_a_helper_beside_a_class_never_constructed(tmp_path):
    # Repair pass eleven, the boundary. The class of
    # form 18c stands in the module and no statement
    # constructs it, so its constructor never runs and
    # the name still denotes the faithful body. The
    # refusal keys on the execution and not on the
    # presence of the class, so the helper derives
    # beside the reader it loads through.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        class _ShadowInstaller:
            def __init__(self):
                global shadow_search
                shadow_search = lambda client, raw_response, name: None
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_decorator_call(tmp_path):
    # Repair pass twelve, red team form 19a. The helper
    # is faithful, and a definition standing after it
    # carries the installer call in its decorator
    # expression, which the definition statement
    # evaluates as the module loads, so the name a test
    # calls denotes the lambda the installer leaves
    # behind. The pass eleven call collection returned
    # whole at the definition node and never visited
    # its decorator list, while the same expression
    # standing on a class was already read. The
    # collection now reads the header of a definition
    # standing in an executing position, its decorator
    # expressions, its default values, and its
    # annotations, without entering its body.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _wrap(value):
            return lambda function: function


        @_wrap(_install_shadow())
        def _decoy():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_default_value_call(tmp_path):
    # Repair pass twelve, red team form 19b. A default
    # value is evaluated when its definition statement
    # executes, as the module loads, so a definition
    # standing after the helper and carrying the
    # installer call as a default value runs the
    # installer as it is defined, and the name denotes
    # the lambda before any test is collected. The pass
    # eleven call collection returned whole at the
    # definition node, and the arguments standing on
    # that node, where the default value lives, were
    # never visited. The header reading the repair adds
    # covers the default values beside the decorators.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _decoy(marker=_install_shadow()):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_on_the_spot_lambda(tmp_path):
    # Repair pass twelve, red team form 19c. A module
    # level statement invokes a lambda on the spot, and
    # the lambda body runs the installer as part of
    # that very statement, on the module's own time.
    # The pass eleven call collection returned whole at
    # the lambda node, so the one body the statement
    # actually runs was never read, and the outer call
    # names no definition, so nothing entered the reach
    # at all. A call whose callee is a lambda now reads
    # as a call into that lambda body.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        (lambda: _install_shadow())()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_dunder_new_method(tmp_path):
    # Repair pass twelve, the spec review sibling of
    # form 18c. The rewriting method of the constructed
    # class is its dunder new method, which a
    # construction runs beside its dunder init method,
    # and the pass eleven gathering consulted the
    # dunder init method defined in the class itself
    # alone, so the write set of the class stood empty
    # and the helper was certified. The construction
    # write set of a class now gathers from both
    # methods.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        class _ShadowInstaller:
            def __new__(cls):
                global shadow_search
                shadow_search = lambda client, raw_response, name: None


        _ShadowInstaller()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_inherited_constructor(tmp_path):
    # Repair pass twelve, the spec review sibling of
    # form 18c. The constructed class defines no
    # construction method of its own and inherits its
    # constructor from a module level base class whose
    # method assigns the helper name under a global
    # declaration, and a construction runs the inherited
    # method all the same. The pass eleven gathering
    # read the methods defined in the class itself
    # alone, so the write set of the constructed class
    # stood empty. The construction write set now
    # resolves the module level base classes a class
    # names, by plain name and to the end of the chain.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        class _ShadowBase:
            def __init__(self):
                global shadow_search
                shadow_search = lambda client, raw_response, name: None


        class _ShadowInstaller(_ShadowBase):
            pass


        _ShadowInstaller()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_admits_a_helper_beside_an_uninvoked_lambda(tmp_path):
    # Repair pass twelve, the boundary. A lambda whose
    # body holds the installer call stands bound to a
    # name at module level and no statement invokes it,
    # so its body never runs and the name still denotes
    # the faithful body. The invoked lambda reading
    # keys on the invocation and not on the presence of
    # the lambda, and an uninvoked lambda contributes
    # nothing past its defaults, so the helper derives
    # beside the reader it loads through.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        _trigger = lambda: _install_shadow()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_subclass_hook(tmp_path):
    # Repair pass thirteen, red team form 20a. Defining
    # a subclass calls the dunder init subclass method
    # of each base it names, so a subclass standing
    # after the helper runs the hook its base defines,
    # the hook runs the installer, and the name a test
    # calls denotes the lambda the installer leaves
    # behind. The pass twelve reach collected a call
    # only where a call stands in the source, and the
    # hook execution wears no call shape, so it was
    # never collected, and the hook method was gathered
    # by no reading at all. A class creation now counts
    # as a call into the subclass hooks of the module
    # level bases the class names, resolved through the
    # base chain, whose bodies join the reach.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _HookBase:
            def __init_subclass__(cls, **kwargs):
                _install_shadow()


        class _HookChild(_HookBase):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_a_metaclass(tmp_path):
    # Repair pass thirteen, red team form 20b. Defining
    # a class under a metaclass calls that metaclass to
    # construct the class, and here the metaclass init
    # method assigns the helper name under a global
    # declaration as the class is created, so the name
    # denotes the lambda before any test is collected.
    # The pass twelve reading already gathered the
    # write set of that method as the construction
    # write set of the metaclass, and the metaclass
    # stood among the targets the reach consults, but
    # the metaclass keyword standing in the class
    # header was visited as a bare name and never as
    # the invocation it performs, so no call into the
    # metaclass was ever recorded. The keyword naming a
    # module level class now counts as a call into the
    # construction gathered for that name.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        class _ShadowMeta(type):
            def __init__(cls, name, bases, namespace):
                global shadow_search
                shadow_search = lambda client, raw_response, name: None


        class _ShadowMarked(metaclass=_ShadowMeta):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_decorator_in_a_reached_body(
    tmp_path,
):
    # Repair pass thirteen, red team form 20c. A
    # definition the module level calls defines a
    # decorated class in its body, and the class
    # statement evaluates its decorator expression as
    # the body runs it, so the installer call standing
    # in that expression runs and the name denotes the
    # lambda. The pass twelve visitor entered the
    # enclosing body and returned whole at the class
    # node, discarding the header with the body, though
    # the header of a function definition in the same
    # position was already read and the header of a
    # class at module level was read before it. A class
    # in any executing position now contributes its
    # header parts, while its body inside a reached
    # body stays deferred on the terms a definition
    # body stands on.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _wrap(value):
            return lambda cls: cls


        def _run_at_load():
            @_wrap(_install_shadow())
            class _Inner:
                pass


        _run_at_load()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_in_a_subclass_body(tmp_path):
    # Repair pass thirteen, the boundary control, red
    # team form 20d. The same hook base and the same
    # installer as form 20a stand here, with the
    # subclass carrying the installer call plainly in
    # its own body. This shape was already refused
    # before this pass, on the pass eleven ground that
    # the bodies of classes standing at module level
    # are executing statements whose plain calls are
    # collected, and it is pinned here as the boundary
    # of family 20, marking that the family turned on
    # the invocation being implicit and not on the
    # class being created. The call in the body bit
    # while the call in the hook evaded, until the
    # creation reading of this pass counted the hook
    # with it.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _HookBase:
            def __init_subclass__(cls, **kwargs):
                _install_shadow()


        class _HookChild(_HookBase):
            _install_shadow()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook(tmp_path):
    # Repair pass fourteen, red team form 21a. Creating
    # a class calls the dunder set name method of every
    # descriptor standing in the namespace its body
    # builds, so the marked class standing after the
    # helper runs the hook of the descriptor its body
    # instantiates, the hook runs the installer, and
    # the name a test calls denotes the lambda the
    # installer leaves behind. The pass thirteen
    # counting named the subclass hooks of the bases
    # and the construction of a keyword named
    # metaclass, and the creation counting consulted
    # neither the namespace the body built nor the
    # descriptor it names, so the installer call inside
    # the hook body was never read, and the set name
    # method was gathered by no reading at all. A class
    # creation now counts as a call into the set name
    # methods of the descriptor classes whose instances
    # stand assigned in the created class body, resolved
    # by plain name through their base chains, whose
    # bodies join the reach.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        class _DescriptorMarked:
            marker = _ShadowDescriptor()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_inherited_metaclass(
    tmp_path,
):
    # Repair pass fourteen, red team form 21b. A class
    # whose statement names no metaclass keyword is
    # constructed by the most derived metaclass among
    # its bases, so the child standing after the helper
    # is constructed by the metaclass its base stands
    # under, and that construction runs the installer
    # and leaves the name denoting the lambda. The
    # pass thirteen counting consulted only the
    # keyword, so a class naming none counted no
    # construction call at all, though the metaclass
    # and its construction stood gathered from the
    # base definition. The creation of the base
    # standing before the helper runs the same
    # construction and is honestly overwritten when
    # the helper definition binds the name after it,
    # which is why the segment orders its definitions
    # as it does and why the refusal keys on the child
    # creation after the candidate. A class creation
    # naming no metaclass now counts as a call into
    # the construction gathered for the metaclass it
    # inherits, resolved through its bases by plain
    # name.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        class _ShadowMeta(type):
            def __init__(cls, name, bases, namespace):
                _install_shadow()


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _MetaBase(metaclass=_ShadowMeta):
            pass


        def shadow_search(client, raw_response, name):
            return reader(name)


        class _MetaChild(_MetaBase):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_keeps_a_helper_beside_a_hookless_descriptor(tmp_path):
    # Repair pass fourteen, the boundary control. The
    # same marked class shape as form 21a stands here,
    # with a descriptor class that defines no set name
    # method at all. Creating the marked class still
    # runs the instantiation standing in its body, and
    # that call was already read before this pass, but
    # no hook execution follows it, so the counting
    # this pass adds refuses nothing here and the
    # faithful helper keeps its derivation beside the
    # reader. The control marks the family turning on
    # the hook the creation performs and not on the
    # descriptor merely standing in the namespace.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        class _PlainDescriptor:
            def __get__(self, instance, owner):
                return None


        class _DescriptorMarked:
            marker = _PlainDescriptor()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_prepare_method(
    tmp_path,
):
    # Repair pass fifteen, red team form 22a. Creating
    # a class calls the prepare method of its metaclass
    # before the class body runs, so the marked class
    # standing after the helper runs the prepare method
    # of the metaclass its keyword names, the prepare
    # method runs the installer, and the name a test
    # calls denotes the lambda the installer leaves
    # behind. The pass fourteen counting named the
    # subclass hooks, the set name hooks, and the
    # construction of the metaclass, and the
    # construction gathering it consulted read the
    # dunder new and dunder init methods alone, so the
    # prepare method standing in the same method
    # position was gathered under no name at all and
    # the installer call inside it was never read. The
    # prepare method now stands in the construction
    # gathering beside the dunder new and dunder init
    # methods, so the names it assigns under a global
    # declaration are counted in the construction write
    # set and its body joins the reach.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _PrepareMeta(type):
            @classmethod
            def __prepare__(mcls, name, bases, **kwargs):
                _install_shadow()
                return {}


        class _PreparedMarked(metaclass=_PrepareMeta):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_inherited_prepare_method(
    tmp_path,
):
    # Repair pass fifteen, red team form 22b. A class
    # whose statement names no metaclass keyword is
    # constructed by the metaclass its bases stand
    # under, and creating it calls that metaclass
    # prepare method before its body runs, so the child
    # standing after the helper runs the prepare method
    # of the metaclass it inherits, the prepare method
    # runs the installer, and the name denotes the
    # lambda. The pass fourteen counting resolved the
    # inherited metaclass and counted the creation as
    # a call into its construction, and the construction
    # it arrived at was the same empty gathering as in
    # form 22a, because the prepare method was gathered
    # under no name on either path. The creation of the
    # base standing before the helper runs the same
    # prepare method and is honestly overwritten when
    # the helper definition binds the name after it,
    # which is why the segment orders its definitions
    # as it does and why the refusal keys on the child
    # creation after the candidate. The prepare method
    # now stands in the construction gathering, so the
    # inherited path counts it with the construction.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        class _PrepareMeta(type):
            @classmethod
            def __prepare__(mcls, name, bases, **kwargs):
                _install_shadow()
                return {}


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _MetaBase(metaclass=_PrepareMeta):
            pass


        def shadow_search(client, raw_response, name):
            return reader(name)


        class _MetaChild(_MetaBase):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_name_bound_descriptor(
    tmp_path,
):
    # Repair pass fifteen, red team form 23a. The set
    # name hook runs for every descriptor standing in
    # the namespace a class body builds, however the
    # instance arrived there, so an instance bound at
    # module level under its own name and placed in the
    # marked class body by that name runs its hook as
    # the marked class is created, the hook runs the
    # installer, and the name a test calls denotes the
    # lambda. The pass fourteen counting read each
    # class body assignment whose value is a call and
    # credited no other arrival shape, so a body
    # assignment whose value is a plain name resolved
    # to nothing and the hook method was never
    # consulted. A body assignment whose value is a
    # plain name now resolves through the module level
    # bindings of that name, and where a binding value
    # is a call naming a module level class the
    # creation counts as a call into the set name
    # methods of that class on the same terms as a
    # direct instantiation, keeping the refusal keyed
    # on the execution, since a name bound to no
    # descriptor instance refuses nothing extra.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        _SHARED_DESCRIPTOR = _ShadowDescriptor()


        class _DescriptorMarked:
            marker = _SHARED_DESCRIPTOR
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_in_a_class_body_inside_a_called_function(
    tmp_path,
):
    # Repair pass fifteen, red team form 24a. A class
    # body runs at its statement, so when a function
    # the module level calls holds a class definition,
    # the class body statements run as part of that
    # call, and the plain installer call standing in
    # the class body leaves the name denoting the
    # lambda. The counting read the header of a class
    # standing inside a body it had entered and counted
    # the executions its creation performs, and stopped
    # at the class body itself, on the ground that such
    # calls run on their own time, the ground the
    # eleventh repair pass falsified and removed at
    # module level, where the same body was already
    # read. A class standing inside a body the reach
    # has entered is now read on the terms of a class
    # at module level, its body statements read for the
    # calls standing in them, while the body of a
    # further definition standing in it stays
    # deferred, since a definition alone performs none
    # of its body.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _run_at_load():
            class _Inner:
                _install_shadow()


        _run_at_load()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_subclass_hook_on_a_subscripted_base(
    tmp_path,
):
    # Repair pass fifteen, red team form 25a. A base
    # standing in a subscript expression performs the
    # same subclass hook execution as the same base in
    # bare name form, where the base defines a class
    # get item method that returns the class itself,
    # the standard generic alias idiom, so the child
    # standing after the helper under a subscription of
    # its base runs the base subclass hook, the hook
    # runs the installer, and the name denotes the
    # lambda. Every base resolution the counting
    # performed took bases in bare name form only, so a
    # creation under a subscripted base counted no hook
    # at all and the hook body was never read. Every
    # base reading now unwraps a subscript base to the
    # plain name standing in its value position, so one
    # base counts the same in either of its two
    # grammatical forms, while a base whose value
    # position holds no plain name counts nothing.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _HookBase:
            def __init_subclass__(cls, **kwargs):
                _install_shadow()

            @classmethod
            def __class_getitem__(cls, item):
                return cls


        class _HookChild(_HookBase[int]):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_a_metaclass_behind_a_subscripted_base(
    tmp_path,
):
    # Repair pass fifteen, red team form 25b. A child
    # standing under a subscription of a base stands
    # under the base itself where the base class get
    # item method returns the class, and inherits the
    # metaclass the base stands under, so creating the
    # child standing after the helper runs that
    # metaclass construction again and leaves the name
    # denoting the lambda. The pass fourteen counting
    # resolved the inherited metaclass through the
    # bases the child names, in bare name form only, so
    # before a subscript it resolved nothing and
    # counted no construction, though the base and its
    # keyword stood in the open in the same module. The
    # metaclass candidate resolution now unwraps a
    # subscript base to the plain name in its value
    # position with every other base reading, so the
    # child creation counts as a call into the
    # construction it inherits. The creation of the
    # base standing before the helper runs the same
    # construction and is honestly overwritten when the
    # helper definition binds the name after it, as in
    # form 21b.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        class _ShadowMeta(type):
            def __init__(cls, name, bases, namespace):
                _install_shadow()


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _MetaBase(metaclass=_ShadowMeta):
            @classmethod
            def __class_getitem__(cls, item):
                return cls


        def shadow_search(client, raw_response, name):
            return reader(name)


        class _MetaChild(_MetaBase[int]):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_keeps_a_helper_beside_a_quiet_prepare_method(tmp_path):
    # Repair pass fifteen, the boundary control beside
    # family 22. The same marked class shape as form
    # 22a stands here under a metaclass whose prepare
    # method only returns an empty namespace and calls
    # nothing. Creating the marked class still runs the
    # prepare method, and its body is now read with the
    # construction, but it reaches no installer and
    # assigns nothing under a global declaration, so
    # the counting this pass adds refuses nothing here
    # and the faithful helper keeps its derivation
    # beside the reader. The control marks the family
    # turning on the prepare execution performing the
    # rewrite and not on the method merely standing in
    # the metaclass.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        class _QuietMeta(type):
            @classmethod
            def __prepare__(mcls, name, bases, **kwargs):
                return {}


        class _PreparedMarked(metaclass=_QuietMeta):
            pass
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_a_class_body_in_an_uncalled_function(
    tmp_path,
):
    # Repair pass fifteen, the boundary control beside
    # family 24. The same class body shape as form 24a
    # stands here inside a function no statement calls,
    # so the enclosing body never runs, the class
    # statement inside it never runs, and the class
    # body is never read, because the reach enters a
    # body only through a call that reaches it. The
    # counting this pass adds reads class bodies only
    # inside bodies the reach has entered, so it
    # refuses nothing here and the faithful helper
    # keeps its derivation beside the reader. The
    # control marks the family turning on the enclosing
    # body executing and not on the class merely
    # standing in the module.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _never_run():
            class _Inner:
                _install_shadow()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_in_an_arm_of_a_class_body(
    tmp_path,
):
    # Repair pass sixteen, red team form 26a. The set
    # name hook runs for every descriptor standing in
    # the namespace a class body builds, however the
    # body placed it there, so a descriptor instance
    # placed by an assignment standing in the arm of a
    # conditional statement in the marked class body
    # runs its hook as the class is created, the hook
    # runs the installer, and the name a test calls
    # denotes the lambda. The pass fifteen scan read a
    # statement only where it stood directly in the
    # body as an assignment or an annotated assignment,
    # so the conditional statement standing in the body
    # was read and the assignment in its arm was never
    # asked for its value, though the reach itself
    # reads the statements of a class body in their
    # arms for the calls standing in them. The scan now
    # reads the placements of a created class body on
    # the reach statement terms through the shared
    # assignment pair collector, so a placement in an
    # arm counts beside a direct one, and the creation
    # counts as a call into the set name methods of the
    # class the arm instantiates.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        class _DescriptorMarked:
            if True:
                marker = _ShadowDescriptor()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_tuple_placed_descriptor(
    tmp_path,
):
    # Repair pass sixteen, red team form 26b. A tuple
    # assignment in a class body unpacks its elements
    # into the namespace the body builds, so a
    # descriptor instance held as one element of the
    # tuple stands in the namespace and its set name
    # hook runs as the class is created, the hook runs
    # the installer, and the name denotes the lambda.
    # The pass fifteen scan read the statement, since
    # it is a direct assignment in the body, and asked
    # its value for a call, and the value is a tuple,
    # so no descriptor was credited, though the tuple
    # holds the very instantiation call the scan looks
    # for as its first element. The placement reading
    # now resolves the elements of a tuple or a list an
    # assignment unpacks to the instantiations they
    # hold, so the creation counts as a call into the
    # set name methods of the class the element
    # instantiates.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        class _DescriptorMarked:
            marker, _pad = _ShadowDescriptor(), None
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_subscript_instantiated_descriptor(
    tmp_path,
):
    # Repair pass sixteen, red team form 26c. A class
    # whose class get item method returns the class
    # itself can be instantiated through a subscription
    # of its name, the standard generic idiom, so a
    # descriptor instantiated that way in a marked
    # class body stands in the namespace and its set
    # name hook runs as the class is created, the hook
    # runs the installer, and the name denotes the
    # lambda. The pass fifteen scan read the statement
    # and found its value is a call and asked the
    # callee for a plain name, and the callee is a
    # subscript expression, so no descriptor class was
    # resolved, though the fifteenth repair taught
    # every base reading to take a subscript as the
    # plain name in its value position. The placement
    # reading now resolves a callee standing in a
    # subscript to the class in its value position on
    # the same terms, so the creation counts as a call
    # into the set name methods of that class.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()

            @classmethod
            def __class_getitem__(cls, item):
                return cls


        class _DescriptorMarked:
            marker = _ShadowDescriptor[int]()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_assigned_subclass_hook(
    tmp_path,
):
    # Repair pass sixteen, red team form 27a. A
    # subclass hook dispatches on the entry standing in
    # the base class namespace under the hook name,
    # whatever statement bound it there, so a base
    # whose body binds a module level function to the
    # hook name by plain assignment runs that function
    # when a child is defined under it, the function
    # runs the installer, and the name a test calls
    # denotes the lambda. The pass fifteen gathering
    # collected a hook only where a member of the class
    # body is a definition statement carrying the hook
    # name, so it asked the base body for definitions
    # and found an assignment instead, and no hook body
    # and no hook write set was ever collected. A class
    # body assignment binding a designated name now
    # counts as the method standing there, a plain name
    # value resolving through the module level
    # definitions on the same terms as the descriptor
    # resolution of the fourteenth repair, so the
    # assigned hook is gathered with the defined ones
    # and its body joins the reach.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _shadow_hook(cls, **kwargs):
            _install_shadow()


        class _HookBase:
            __init_subclass__ = _shadow_hook


        class _HookChild(_HookBase):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_assigned_set_name_method(
    tmp_path,
):
    # Repair pass sixteen, red team form 27b. A set
    # name method dispatches on the entry standing in
    # the descriptor class namespace under the set name
    # name, whatever statement bound it there, so a
    # descriptor class whose body binds a module level
    # function to that name by plain assignment runs
    # that function for every class that carries an
    # instance of it, the function runs the installer,
    # and the name denotes the lambda. The placement is
    # the direct instantiation the earlier counting
    # credits in full, so the scan resolved the
    # descriptor class and consulted its set name
    # methods, and the gathering asked that class body
    # for definition statements under the set name name
    # and found an assignment instead, and returned no
    # body and no write set, so the hook stood
    # installed in the open and was read as no hook at
    # all. An assignment binding the set name name now
    # counts as the method standing there on the same
    # terms as in form 27a, so the creation counts the
    # assigned method with the defined ones.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _shadow_set_name(self, owner, name):
            _install_shadow()


        class _ShadowDescriptor:
            __set_name__ = _shadow_set_name


        class _DescriptorMarked:
            marker = _ShadowDescriptor()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_assigned_construction_method(
    tmp_path,
):
    # Repair pass sixteen, red team form 27c. A
    # construction method dispatches on the entry
    # standing in the metaclass namespace under its
    # name, whatever statement bound it there, so a
    # metaclass whose body binds a module level
    # function to the dunder init name by plain
    # assignment runs that function as a class defined
    # under it is created, the function runs the
    # installer, and the name a test calls denotes the
    # lambda. The pass fifteen reach followed the
    # keyword to the metaclass and counted the creation
    # as a call into its construction, and the
    # construction gathering asked that class body for
    # definition statements under the construction
    # names and found an assignment instead, so the
    # write set gathered for the metaclass name was
    # empty and no callee body stood behind it. An
    # assignment binding a construction name now counts
    # as the method standing there, so the construction
    # of the metaclass gathers the assigned method with
    # the defined ones on either metaclass path.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _shadow_meta_init(cls, name, bases, namespace):
            _install_shadow()


        class _ShadowMeta(type):
            __init__ = _shadow_meta_init


        class _MetaMarked(metaclass=_ShadowMeta):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_a_definition_called_from_its_class_body(
    tmp_path,
):
    # Repair pass sixteen, red team form 28b. A class
    # body runs at its statement, so a plain function
    # defined in a marked class body and called by a
    # plain statement standing in the same body runs as
    # the class is created, and where its body assigns
    # the certified name under a global declaration the
    # name a test calls denotes the lambda it leaves
    # behind. The pass fifteen gathering walked the
    # module from its top level statements and recorded
    # a class definition into the class tables without
    # descending into it, consulting the class body
    # only for members carrying a designated name, so
    # the plain definition stood in no table anywhere
    # and the call standing beside it in the same body
    # was a call the reach recorded and could not
    # resolve. The gathering now enters a class body on
    # the same terms as the module level, so a plain
    # definition standing in one is gathered into the
    # module tables under its name, its global write
    # set counted and its body read when the reach
    # calls it, while a definition the reach never
    # calls refuses nothing.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        class _RunAtLoad:
            def _install_nested():
                global shadow_search
                shadow_search = lambda client, raw_response, name: None

            _install_nested()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_keeps_a_helper_beside_a_hookless_descriptor_in_an_arm(
    tmp_path,
):
    # Repair pass sixteen, the boundary control beside
    # family 26. The same conditional placement as form
    # 26a stands here with a descriptor class defining
    # a get method and no set name method at all.
    # Creating the marked class still builds its
    # namespace with the instance standing in it, and
    # the widened scan now reads the placement in the
    # arm and resolves the class it instantiates, but
    # the class carries no hook for the creation to
    # call, so the counting this pass adds refuses
    # nothing here and the faithful helper keeps its
    # derivation beside the reader. The control marks
    # the family turning on the placement hiding a hook
    # that exists, the refusal staying keyed on the
    # execution and not on the placement alone.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _QuietDescriptor:
            def __get__(self, instance, owner):
                return None


        class _DescriptorMarked:
            if True:
                marker = _QuietDescriptor()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_an_assigned_hook_that_calls_nothing(
    tmp_path,
):
    # Repair pass sixteen, the boundary control beside
    # family 27. The same base and child shape as form
    # 27a stands here with the hook name bound to a
    # module level function whose body only returns.
    # Defining the child still dispatches on the entry
    # under the hook name, and the assigned function is
    # now gathered with the defined hooks and its body
    # joins the reach, but it reaches no installer and
    # assigns nothing under a global declaration, so
    # the counting this pass adds refuses nothing here
    # and the faithful helper keeps its derivation
    # beside the reader. The control marks the family
    # turning on the assigned callable performing the
    # rewrite, the repair reading the assigned callable
    # on the same terms as the defined method rather
    # than treating every assignment to a designated
    # name as a rewrite.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _quiet_hook(cls, **kwargs):
            return None


        class _HookBase:
            __init_subclass__ = _quiet_hook


        class _HookChild(_HookBase):
            pass
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_an_alias_instantiated_descriptor(
    tmp_path,
):
    # Repair pass seventeen, red team form 29a. A
    # descriptor class can stand under a second name
    # bound to it by a plain module level assignment,
    # and instantiating the descriptor through that
    # alias places the same instance in the namespace a
    # class body builds, so creating the marked class
    # runs the set name hook, the hook runs the
    # installer, and the name a test calls denotes the
    # lambda. The pass sixteen placement reading asked
    # the callee of the instantiation for the plain
    # name it carries and looked that name up in the
    # class tables, and the alias stands in no table,
    # so no descriptor class was credited and the hook
    # was never consulted. A name now resolves through
    # the module level assignment bindings standing
    # behind it at every point the counting turns a
    # name into a class, a name bound to a class name
    # denoting that class, so the creation counts as a
    # call into the set name methods of the class the
    # alias denotes.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        _AliasDescriptor = _ShadowDescriptor


        class _DescriptorMarked:
            marker = _AliasDescriptor()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_subclass_hook_behind_an_aliased_base(
    tmp_path,
):
    # Repair pass seventeen, red team form 29b. A base
    # class can stand under a second name bound to it
    # by a plain module level assignment, and a child
    # defined under the alias stands under the same
    # class, so creating the child runs the subclass
    # hook of the class the alias denotes, the hook
    # runs the installer, and the name denotes the
    # lambda. The pass sixteen base reading resolved
    # the base to the plain name standing in its value
    # position and followed that name through the class
    # tables, and the alias stands in no table, so the
    # hook gathering followed no base at all and
    # collected no hook. The base readings now resolve
    # the name they carry through the module level
    # assignment bindings standing behind it, so the
    # hooks of the class the alias denotes are counted
    # for the child as they are under the definition
    # name.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _HookBase:
            def __init_subclass__(cls, **kwargs):
                _install_shadow()


        _AliasBase = _HookBase


        class _HookChild(_AliasBase):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_aliased_metaclass_keyword(
    tmp_path,
):
    # Repair pass seventeen, red team form 29c. A
    # metaclass can stand under a second name bound to
    # it by a plain module level assignment, and a
    # class defined under that alias by keyword is
    # constructed by the same metaclass, so its
    # construction runs, the construction runs the
    # installer, and the name denotes the lambda. The
    # pass sixteen counting counted a creation as a
    # call into the construction of the metaclass its
    # keyword names only where the keyword value is a
    # plain name standing in the class tables, and the
    # alias stands in none, so the creation counted as
    # a call into nothing and the construction write
    # set gathered for the metaclass was never
    # consulted. The keyword value now resolves
    # through the module level assignment bindings
    # standing behind it, so the creation counts as a
    # call into the construction gathered for the class
    # the alias denotes.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowMeta(type):
            def __init__(cls, name, bases, namespace):
                _install_shadow()


        _AliasMeta = _ShadowMeta


        class _MetaMarked(metaclass=_AliasMeta):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_subscript_alias_descriptor(
    tmp_path,
):
    # Repair pass seventeen, red team form 29d. An
    # alias can be bound not to a class name but to a
    # subscript of one, the standard generic idiom
    # where the class get item method returns the class
    # itself, and instantiating through that alias
    # places the same descriptor instance in the
    # namespace a class body builds, so creating the
    # marked class runs the set name hook and the name
    # denotes the lambda. The pass sixteen counting
    # performed its two neighbouring resolutions at
    # other loci only, taking a subscript as the class
    # in its value position for the base readings and
    # following a plain name through its module level
    # binding where an instance stood placed, and a
    # callee that is a bound name denoting a subscript
    # of the class was resolved by neither. The alias
    # resolution now follows a name bound to a
    # subscript of a class name to the class in its
    # value position, so the creation counts as a call
    # into the set name methods of that class.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()

            @classmethod
            def __class_getitem__(cls, item):
                return cls


        _AliasDescriptor = _ShadowDescriptor[int]


        class _DescriptorMarked:
            marker = _AliasDescriptor()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_metaclass_call_method(
    tmp_path,
):
    # Repair pass seventeen, red team form 30a.
    # Calling a class dispatches on the dunder call
    # method of its metaclass, and that method is the
    # execution that performs the construction at all,
    # since the dunder new and dunder init methods run
    # only because a call method invokes them, so a
    # metaclass whose call method runs the installer
    # before delegating rewrites the name at every
    # instantiation of every class standing under it.
    # The pass sixteen construction gathering collected
    # the dunder prepare, dunder new, and dunder init
    # methods and no fourth, so the reach read the
    # instantiation after the candidate as a call into
    # an empty construction and the one body performing
    # the rewrite stood gathered as a plain definition
    # under a name no statement calls. The dunder call
    # method of the metaclass a class stands under is
    # now gathered beside its construction methods, and
    # a call naming a class counts as a call into it
    # beside the construction, counted at the call and
    # not at the creation of the class, since the
    # method fires at instantiation and not at
    # creation.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _CallMeta(type):
            def __call__(cls, *args, **kwargs):
                _install_shadow()
                return super().__call__(*args, **kwargs)


        class _InstanceMarked(metaclass=_CallMeta):
            pass


        _InstanceMarked()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_inherited_metaclass_call_method(
    tmp_path,
):
    # Repair pass seventeen, red team form 30b. A
    # class naming no metaclass stands under the
    # metaclass its bases stand under, and calling it
    # dispatches on the dunder call method of that
    # inherited metaclass exactly as the keyword path
    # does, so instantiating the child runs the call
    # method of the metaclass its base was defined
    # under, the method runs the installer, and the
    # name denotes the lambda. The pass sixteen
    # counting resolved the inherited metaclass of the
    # child and counted its construction, and the
    # gathered construction was empty for the same
    # reason as on the keyword path, the call method
    # standing under a name no gathering collected.
    # The call method gathering follows the metaclass
    # on either path, so the instantiation counts as a
    # call into the call method of the inherited
    # metaclass beside its construction.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _CallMeta(type):
            def __call__(cls, *args, **kwargs):
                _install_shadow()
                return super().__call__(*args, **kwargs)


        class _MetaBase(metaclass=_CallMeta):
            pass


        class _InstanceChild(_MetaBase):
            pass


        _InstanceChild()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_subclass_hook_defined_in_an_arm(
    tmp_path,
):
    # Repair pass seventeen, red team form 31a. A
    # subclass hook defined inside an arm of a compound
    # statement in a base class body stands in the
    # namespace that body builds under the hook name,
    # and the interpreter dispatches on the entry
    # standing there, so creating a child under the
    # base runs the hook, the hook runs the installer,
    # and the name denotes the lambda. The pass sixteen
    # widening read the placements of a class body on
    # the reach statement terms, arms of compound
    # statements among them, on the ground that the
    # namespace a body builds is built by every
    # statement it executes, but the designated method
    # gatherings never took the same widening and
    # collected a hook only from the direct members of
    # the body, so the conditional statement standing
    # in the body was the only member the gathering
    # saw. The installations of a class body are now
    # read on the same statement terms as its
    # placements, so a definition standing in an arm
    # counts as the method standing there.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _HookBase:
            if True:
                def __init_subclass__(cls, **kwargs):
                    _install_shadow()


        class _HookChild(_HookBase):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_subclass_hook_assigned_in_an_arm(
    tmp_path,
):
    # Repair pass seventeen, red team form 31b. A
    # subclass hook can be installed by an assignment
    # standing in an arm of a compound statement in a
    # base class body, the arm binding a module level
    # function to the hook name as the body builds its
    # namespace, so creating a child under the base
    # runs that function and the name denotes the
    # lambda. This shape composes the two settlements
    # of the last two repairs and was closed by
    # neither, since an assignment binding a designated
    # name installs the method and a statement standing
    # in an arm of the body stands in the body for the
    # counting, while the installation reading performed
    # the first only on direct members and the
    # placement widening performed the second only for
    # descriptors. The installation reading now gathers
    # its pairs through the shared assignment pair
    # collector on the widened statement terms, so the
    # assignment in the arm counts as the hook standing
    # there, its plain name value resolving through the
    # module level definitions as a direct assignment
    # does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _shadow_hook(cls, **kwargs):
            _install_shadow()


        class _HookBase:
            if True:
                __init_subclass__ = _shadow_hook


        class _HookChild(_HookBase):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_subclass_hook_bound_by_a_walrus(
    tmp_path,
):
    # Repair pass seventeen, red team form 31c. A
    # walrus statement standing directly in a base
    # class body binds its target in the namespace that
    # body builds, so a hook name bound that way to a
    # module level function installs the function as
    # the hook, and creating a child under the base
    # runs it and the name denotes the lambda. The
    # statement stands directly in the body, so no arm
    # stands between the gathering and the binding, and
    # the pass sixteen gathering still read nothing,
    # because the member is an expression statement and
    # the installation reading collected only
    # definitions and assignments. The placement
    # reading standing beside it already counted a
    # walrus binding as a placement through the shared
    # assignment pair collector, and the installation
    # reading now reads its pairs through the same
    # collector, so the walrus binding counts as the
    # hook standing there.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _shadow_hook(cls, **kwargs):
            _install_shadow()


        class _HookBase:
            (__init_subclass__ := _shadow_hook)


        class _HookChild(_HookBase):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_keeps_a_helper_beside_an_aliased_descriptor_without_a_set_name_hook(
    tmp_path,
):
    # Repair pass seventeen, the boundary control
    # beside family 29. The same alias shape as form
    # 29a stands here with a descriptor class defining
    # a get method and no set name method at all, bound
    # to a second name and instantiated through it.
    # Creating the marked class still builds its
    # namespace with the instance standing in it, and
    # the alias now resolves to the class it denotes,
    # but the class carries no hook for the creation to
    # call, so the counting this pass adds refuses
    # nothing here and the faithful helper keeps its
    # derivation beside the reader. The control marks
    # the family turning on the alias hiding a
    # designated execution that exists, the repair
    # resolving the alias to the class it denotes and
    # counting that class on the same terms as its
    # definition name rather than refusing any name
    # bound to a class.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _QuietDescriptor:
            def __get__(self, instance, owner):
                return None


        _AliasDescriptor = _QuietDescriptor


        class _DescriptorMarked:
            marker = _AliasDescriptor()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_a_delegating_metaclass_call_method(
    tmp_path,
):
    # Repair pass seventeen, the boundary control
    # beside family 30. The same keyword shape as form
    # 30a stands here with a metaclass whose dunder
    # call method only returns the result of the
    # default construction, and the class standing
    # under it is instantiated after the candidate. The
    # instantiation now counts as a call into that call
    # method beside the construction, and its body
    # joins the reach, but it reaches no installer and
    # assigns nothing under a global declaration, so
    # the counting this pass adds refuses nothing here
    # and the faithful helper keeps its derivation
    # beside the reader. The control marks the family
    # turning on the call method performing a rewrite,
    # the repair reading the method body on the same
    # terms as a construction method rather than
    # treating the presence of the method as a rewrite.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _CallMeta(type):
            def __call__(cls, *args, **kwargs):
                return super().__call__(*args, **kwargs)


        class _InstanceMarked(metaclass=_CallMeta):
            pass


        _InstanceMarked()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_a_quiet_subclass_hook_defined_in_an_arm(
    tmp_path,
):
    # Repair pass seventeen, the boundary control
    # beside family 31. The same arm shape as form 31a
    # stands here with a subclass hook whose body only
    # returns, defined inside a conditional arm of the
    # base class body. Creating the child still
    # dispatches on the entry under the hook name, and
    # the hook is now gathered from the arm with the
    # direct members, but it reaches no installer and
    # assigns nothing under a global declaration, so
    # the counting this pass adds refuses nothing here
    # and the faithful helper keeps its derivation
    # beside the reader. The control marks the family
    # turning on the method standing in the arm
    # performing the rewrite, the repair reading the
    # installations on the widened statement terms
    # while keeping the refusal keyed on what the
    # installed body does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _HookBase:
            if True:
                def __init_subclass__(cls, **kwargs):
                    return None


        class _HookChild(_HookBase):
            pass
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_installer_called_through_a_bound_name(
    tmp_path,
):
    # Repair pass eighteen, red team form 32a. A plain
    # assignment can bind a second name to the installer
    # itself, and a module level call bearing that name
    # runs the installer body exactly as a call bearing
    # its definition name does, so the name a test calls
    # denotes the lambda. The pass seventeen reach
    # resolved the callee of a plain call by the name a
    # definition statement carries alone, and the bound
    # name stands in no callee table and no write set
    # table, so the call closed over nothing although
    # the module level bindings the same reading gathers
    # hold the alias in the open. The reach now resolves
    # a callee name through those bindings, a name bound
    # to a plain name counting as a call into the
    # definition standing at the end of the chain.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        _alias_installer = _install_shadow


        _alias_installer()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_a_wrapper_called_through_a_bound_name(
    tmp_path,
):
    # Repair pass eighteen, red team form 32b. A wrapper
    # whose body calls the installer can stand under a
    # second name bound to it by a plain assignment, and
    # a call bearing that name runs the wrapper, whose
    # own call into the installer is a plain name call
    # the counting would close over at once if the
    # wrapper body ever joined the reach. It never
    # joined, because the call that would bring it in
    # bore the alias, which resolved to nothing, so the
    # stop stands in the resolution of the callee name
    # itself and not in any property of the body behind
    # it. The bound name now counts as a call into the
    # wrapper on the terms of a direct call, and the
    # reach closes over the installer call inside it.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _wrap():
            _install_shadow()


        _alias_wrap = _wrap


        _alias_wrap()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_installer_called_from_a_bound_lambda(
    tmp_path,
):
    # Repair pass eighteen, red team form 32c. A name
    # can be bound to a lambda whose body calls the
    # installer, and a call bearing that name runs the
    # lambda body where it stands in the binding. The
    # counting read a lambda body where a call invokes
    # the lambda where it stands and where an assignment
    # installs one under a designated name, but at the
    # call locus the callee is a name, the name resolved
    # to nothing, and the lambda standing behind the
    # binding was a body the reach never entered although
    # it stands in the open in the same module. A name
    # bound to a lambda now counts as a call into the
    # lambda body read where it stands in the binding.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        _alias_lambda = lambda: _install_shadow()


        _alias_lambda()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_a_decorator_applied_to_a_definition(
    tmp_path,
):
    # Repair pass eighteen, red team form 33a. A
    # decorator whose body calls the installer, standing
    # in bare name form on a decoy definition after the
    # candidate, is applied to the decoy as the decoy
    # statement completes, and that application runs the
    # decorator body and with it the installer. The pass
    # seventeen header reading visited the decorator
    # expression and found a name standing in it and
    # nothing else, no call node to collect, so the one
    # body that performs the rewrite never joined the
    # reach. The application of a decorator standing in
    # bare name form now counts as a call into the value
    # the name denotes, resolved as the reach resolves
    # its callees.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _deco(value):
            _install_shadow()
            return value


        @_deco
        def _decoy():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_a_decorator_applied_to_a_class(
    tmp_path,
):
    # Repair pass eighteen, red team form 33b. The same
    # decorator standing in bare name form on a decoy
    # class after the candidate is applied to the class
    # as the class statement completes, after a creation
    # whose body is empty and counts nothing, and the
    # decorator body runs the installer the same way.
    # The creation counting met the class in full and
    # counted the five executions a creation performs,
    # and the sixth execution the statement performs,
    # the application of its decorator, stood outside
    # the five and was counted nowhere, although it is
    # designated by the same grammar on the same
    # statement. The application now counts beside the
    # five as a call into the decorator definition.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _deco(value):
            _install_shadow()
            return value


        @_deco
        class _Decoy:
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_a_class_standing_as_a_decorator(
    tmp_path,
):
    # Repair pass eighteen, red team form 33c. A class
    # whose dunder init method calls the installer can
    # stand in bare name form as the decorator on a decoy
    # definition, and applying the decorator calls the
    # class with the decoy as its argument, so the
    # construction runs and its init method runs the
    # installer. A call naming this class standing in an
    # expression statement would count its construction
    # at once, and the application performs exactly that
    # call, designated by the decorator position rather
    # than by a call node, while the counting read the
    # position as an expression to search for calls and
    # never as the call it is. The application now counts
    # as the call it performs, into the construction
    # gathered for the class the name denotes.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Deco:
            def __init__(self, value):
                _install_shadow()
                self.value = value


        @_Deco
        def _decoy():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_instance_standing_as_a_decorator(
    tmp_path,
):
    # Repair pass eighteen, red team form 33d. An
    # instance of a class whose dunder call method calls
    # the installer can stand in bare name form as the
    # decorator on a decoy definition, and applying the
    # decorator calls the instance, which dispatches on
    # the call method of its class and runs the
    # installer. The shape composes the two stops of
    # this pass, the application of the decorator counted
    # nowhere and the call the application performs
    # bearing an instance name whose dispatch the call
    # counting resolved to nothing, so it is closed only
    # by counting the application as a call and resolving
    # the instance name the call bears to the call
    # methods of the class it stands in.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Runner:
            def __call__(self, value):
                _install_shadow()
                return value


        _runner = _Runner()


        @_runner
        def _decoy():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_instance_called_through_its_bound_name(
    tmp_path,
):
    # Repair pass eighteen, red team form 34a. An
    # instance of a class whose dunder call method calls
    # the installer, bound at module level after the
    # candidate and called by its bound name, dispatches
    # the call on the call method of its class, and the
    # method runs the installer. The counting resolved
    # the callee name to no body, not to a definition,
    # not to a class, and not through the bindings to the
    # instantiation the placement reading would resolve
    # it by, although the instantiation statement itself
    # was counted in full as a construction that rewrites
    # nothing. The call locus asks which body a call
    # runs, so the name now resolves through the bindings
    # to the instantiation it denotes and the call counts
    # into the dunder call methods gathered for that
    # class.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Runner:
            def __call__(self):
                _install_shadow()


        _runner = _Runner()


        _runner()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_instance_reached_through_a_second_name(
    tmp_path,
):
    # Repair pass eighteen, red team form 34b. The same
    # instance can be reached through a second name bound
    # to the first, and a call bearing the second name
    # dispatches on the same call method of the same
    # class. The placement reading follows a name bound
    # to a further name in turn when it resolves what a
    # placed name puts in a namespace, so the chain of
    # two plain bindings is a chain that reading already
    # walks at its locus, while the call counting walked
    # it at none, resolving neither name to the
    # instantiation or to the class. The instance
    # resolution at the call locus now follows the chain
    # the same way, so the stop is closed at the
    # resolution of the callee name and not at the
    # directness of the binding.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Runner:
            def __call__(self):
                _install_shadow()


        _runner = _Runner()


        _runner2 = _runner


        _runner2()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_keeps_a_helper_beside_a_call_through_a_name_bound_to_a_quiet_definition(
    tmp_path,
):
    # Repair pass eighteen, the boundary control beside
    # family 32. The same alias shape as form 32a stands
    # here with the bound definition a function whose
    # body only returns, called through its alias after
    # the candidate. The callee name now resolves through
    # the bindings to the body it denotes and that body
    # joins the reach, but it calls nothing and assigns
    # nothing under a global declaration, so the counting
    # this pass adds refuses nothing here and the
    # faithful helper keeps its derivation beside the
    # reader. The control marks the family turning on
    # the body behind the bound name performing the
    # rewrite, the repair resolving the name to that body
    # and keeping the refusal keyed on what the body
    # does rather than on the presence of a bound name
    # call.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _quiet():
            return None


        _alias_quiet = _quiet


        _alias_quiet()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_a_returning_decorator_in_bare_name_form(
    tmp_path,
):
    # Repair pass eighteen, the boundary control beside
    # family 33. The same decorator shape as form 33a
    # stands here with a decorator whose body only
    # returns the value it is handed, standing on a decoy
    # definition after the candidate. The application of
    # the decorator now counts as a call into the
    # decorator definition and its body joins the reach,
    # but it calls nothing and assigns nothing under a
    # global declaration, so the counting this pass adds
    # refuses nothing here and the faithful helper keeps
    # its derivation beside the reader. The control marks
    # the family turning on the application performing
    # the rewrite, the repair counting the application as
    # the call it is while keeping the refusal keyed on
    # what the applied body does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _deco(value):
            return value


        @_deco
        def _decoy():
            pass
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_a_quiet_instance_called_through_its_bound_name(
    tmp_path,
):
    # Repair pass eighteen, the boundary control beside
    # family 34. The same instance shape as form 34a
    # stands here with a class whose dunder call method
    # only returns, the instance bound and called after
    # the candidate. The call now resolves the instance
    # name to the class it stands in and reads that class
    # its call methods on the same terms as the metaclass
    # seat, but the method calls nothing and assigns
    # nothing under a global declaration, so the counting
    # this pass adds refuses nothing here and the faithful
    # helper keeps its derivation beside the reader. The
    # control marks the family turning on the call method
    # performing the rewrite, the repair keeping the
    # refusal keyed on what the method body does rather
    # than on the presence of an instance call.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Runner:
            def __call__(self):
                return None


        _runner = _Runner()


        _runner()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_by_a_walrus_bound_installer_alias(
    tmp_path,
):
    # Repair pass nineteen, red team form 35a. A walrus
    # statement after the candidate binds a plain name to
    # the installer itself, and a call bearing that name
    # dispatches on the installer exactly as a call
    # bearing a name a plain assignment bound does. The
    # resolution at the call locus followed the chain of
    # such bindings for a name an assignment bound, while
    # the collector standing behind every name resolution
    # recorded only plain and annotated assignments, so
    # the walrus bound name resolved to nothing and the
    # call counted nothing. The collector now gathers
    # its bindings through the shared assignment pair
    # collector on the same statement terms, so a name
    # bound in either form resolves as the same name.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        (_alias_installer := _install_shadow)


        _alias_installer()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_a_walrus_bound_lambda(
    tmp_path,
):
    # Repair pass nineteen, red team form 35b. A walrus
    # statement binds a plain name to a lambda whose body
    # calls the installer, and a call bearing that name
    # runs the lambda body exactly as a call bearing a
    # name an assignment bound to the same lambda does.
    # The call counting read a lambda standing behind a
    # bound name in place for a name the collector held,
    # while the collector never recorded the walrus
    # binding, so the call resolved to no body. The
    # bindings now stand gathered through the pair
    # collector, so the lambda behind a walrus bound name
    # is read where it stands in the binding, on the
    # terms of an assigned lambda.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        (_alias_lambda := lambda: _install_shadow())


        _alias_lambda()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_subclass_hook_behind_a_walrus_bound_base(
    tmp_path,
):
    # Repair pass nineteen, red team form 35c. A walrus
    # statement binds a plain name to a class carrying a
    # subclass hook whose body calls the installer, and a
    # subclass defined on that name runs the hook of the
    # class the name denotes exactly as a subclass
    # defined on a name an assignment bound does. The
    # base resolution turned a name into a class through
    # the bindings standing behind it, while the
    # collector never recorded the walrus binding, so
    # the base resolved to no class and no hook was
    # counted. The bindings now stand gathered through
    # the pair collector, so the aliased class resolves
    # at the base locus on the terms of an assigned
    # alias.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _HookBase:
            def __init_subclass__(cls, **kwargs):
                _install_shadow()


        (_AliasBase := _HookBase)


        class _HookChild(_AliasBase):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_a_walrus_bound_instance_called_by_name(
    tmp_path,
):
    # Repair pass nineteen, red team form 35d. A walrus
    # statement binds a plain name to an instance of a
    # class whose dunder call method calls the
    # installer, and a call bearing that name dispatches
    # on the dunder call method of its class
    # exactly as a call bearing a name an assignment
    # bound to the same instantiation does. The instance
    # resolution at the call locus resolved a name
    # through the bindings to the instantiation it
    # denotes, while the collector never recorded the
    # walrus binding, so the name resolved to no
    # instantiation and no call method was counted. The
    # bindings now stand gathered through the pair
    # collector, so the instance behind a walrus bound
    # name resolves on the terms of an assigned
    # instance.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Runner:
            def __call__(self):
                _install_shadow()


        (_runner := _Runner())


        _runner()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_descriptor_bound_by_a_loop_target(
    tmp_path,
):
    # Repair pass nineteen, red team form 35e. A loop
    # target after the candidate binds a plain name to an
    # element of the list it walks, an instance of a
    # descriptor class whose set name method calls the
    # installer, and a class body placing that name puts
    # the instance in the namespace the body builds, so
    # the creation of the class dispatches the set name
    # method on it exactly as a body placing a name an
    # assignment bound to the instantiation does. The
    # pair collection already gathered a loop target as
    # a binding of the iterable it walks, and the
    # placement reading accepted a derivation of the
    # same shape inside a class body, while the
    # placement reading at the creation locus resolved a
    # placed name only against bindings whose value
    # instantiates a class or names a further name, so
    # the target bound name placed nothing. A name a
    # loop target binds denotes an element of the
    # iterable rather than the iterable itself, and the
    # placement reading now reads such a name on those
    # terms, through the bindings the pair collector
    # gathers.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        for _placed in [_ShadowDescriptor()]:
            pass


        class _DescriptorMarked:
            marker = _placed
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_with_managers_enter_method(
    tmp_path,
):
    # Repair pass nineteen, red team form 36a. A with
    # statement after the candidate over an inline
    # manager whose dunder enter method calls the
    # installer performs the enter method as the
    # statement runs, before the guarded body, whether
    # the body completes, raises, or is abandoned, so
    # the rewrite stands before any guarded statement
    # completes. The reach counted the construction of
    # the manager at that statement in full and read the
    # guarded body beside it, while no reading gathered
    # a method under the enter or exit names, so the
    # protocol execution the statement performs counted
    # nothing. The protocol methods of module level
    # classes now stand gathered on the installation
    # reading's terms, and a with statement in an
    # executing position counts as a call into them.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _EnterCtx:
            def __enter__(self):
                _install_shadow()
                return self

            def __exit__(self, *exc):
                return False


        with _EnterCtx():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_with_managers_exit_method(
    tmp_path,
):
    # Repair pass nineteen, red team form 36b. The exit
    # side of the same protocol. A with statement over a
    # manager whose dunder exit method calls the
    # installer performs the exit method as the statement
    # completes, on the normal path and on the raised
    # path alike, and the counting gathered no method
    # under the exit name either, so the execution
    # counted nothing beside the construction. The exit
    # method now stands gathered with the enter method
    # on the installation reading's terms, and the with
    # statement counts as a call into both.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ExitCtx:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                _install_shadow()
                return False


        with _ExitCtx():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_bound_with_managers_enter_method(
    tmp_path,
):
    # Repair pass nineteen, red team form 36c. The
    # manager stands bound to a plain name ahead of the
    # with statement, and the statement performs the
    # enter method of the class the bound instantiation
    # denotes exactly as the inline form does. The
    # counting counted the construction where the
    # binding stands and nothing at the statement, while
    # the manager position is the operand the statement
    # dispatches on. The statement now resolves its
    # manager as an instantiation standing in the
    # statement or through the bindings to the
    # instantiation its name denotes, on the terms the
    # instance resolution of the call locus reads a name
    # by.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _EnterCtx:
            def __enter__(self):
                _install_shadow()
                return self

            def __exit__(self, *exc):
                return False


        _mgr = _EnterCtx()


        with _mgr:
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_inherited_with_managers_enter_method(
    tmp_path,
):
    # Repair pass nineteen, red team form 36d. The enter
    # method stands on a base class and the manager
    # instantiates a subclass that inherits it, so the
    # statement dispatches on the inherited method
    # exactly as it dispatches on the class its own.
    # The gathering of the protocol methods follows the
    # base chains on the installation reading's terms,
    # counting installations in a base as installations
    # of the class that names it, so the inherited
    # method stands gathered for the subclass beside
    # its construction methods.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _EnterBase:
            def __enter__(self):
                _install_shadow()
                return self

            def __exit__(self, *exc):
                return False


        class _EnterChild(_EnterBase):
            pass


        with _EnterChild():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_in_a_base_expression(
    tmp_path,
):
    # Repair pass nineteen, red team form 37a. A class
    # definition after the candidate names a base in a
    # subscript whose value position is a module level
    # class carrying a dunder class getitem method, a
    # classmethod whose body calls the installer, and
    # evaluating the subscript performs that method as
    # the header of the definition runs, ahead of the
    # creation itself. The base reading took the
    # subscript as the plain name in its value position
    # for every purpose it turned a name into a class,
    # which is the resolution of the base and not an
    # account of the evaluation the subscript performs,
    # and no reading gathered a method under the class
    # getitem name. The method now stands gathered on
    # the installation reading's terms, and a subscript
    # whose value position resolves to such a class
    # counts as a call into it wherever the reach reads
    # the subscript as an execution, the base position
    # among them.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _GIBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        class _GIChild(_GIBase[int]):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_in_an_annotation(
    tmp_path,
):
    # Repair pass nineteen, red team form 37b. The same
    # subscript stands in the annotation of a definition
    # after the candidate, and the header reading
    # performs the annotations of a definition as its
    # statement runs, so the subscript evaluation and
    # the class getitem execution it dispatches stand
    # counted in full while the counting read the header
    # and counted nothing for the subscript standing in
    # it. The counting now stands at the subscript
    # itself, in any expression standing in an executing
    # position alike, so the annotation position counts
    # on the same terms as the base position.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _GIBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        def _annotated(value: _GIBase[int]):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_for_loops_iter_method(
    tmp_path,
):
    # Repair pass nineteen, red team form 38a. A for
    # statement after the candidate over an inline
    # iterable whose dunder iter method calls the
    # installer performs the iter method as the
    # statement begins, before the first element is
    # drawn, whether the loop body then runs or not.
    # The reach read the construction of the iterable at
    # that statement and the calls standing in the loop
    # body beside it, while no reading gathered a method
    # under the iter name, so the protocol execution the
    # statement performs counted nothing. The iteration
    # methods of module level classes now stand gathered
    # on the installation reading's terms, and a for
    # statement in an executing position counts as a
    # call into them.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Iter:
            def __iter__(self):
                _install_shadow()
                return iter([])


        for _ in _Iter():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_self_iterators_next_method(
    tmp_path,
):
    # Repair pass nineteen, red team form 38b. The
    # iterable is its own iterator, its dunder iter
    # method returning the instance itself, so the loop
    # draws its elements by performing the dunder next
    # method of the same class, whose body calls the
    # installer on the first element drawn. A next
    # method dispatches on the value an iter method
    # returns, and return values stand on the ground the
    # counting does not model, while the shape whose
    # iter method returns the instance itself names its
    # iterator in the open, in the one return shape the
    # statement itself determines. The counting claims
    # exactly that width, counting the next method of
    # the class the statement starts from where the
    # gathered iter method returns its first parameter,
    # and no wider shape.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _SelfIter:
            def __iter__(self):
                self._done = False
                return self

            def __next__(self):
                if self._done:
                    raise StopIteration
                self._done = True
                _install_shadow()
                return 0


        for _ in _SelfIter():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_bound_iterables_iter_method(
    tmp_path,
):
    # Repair pass nineteen, red team form 38c. The
    # iterable stands bound to a plain name ahead of the
    # for statement, and the statement performs the iter
    # method of the class the bound instantiation
    # denotes exactly as the inline form does. The
    # counting counted the construction where the
    # binding stands and nothing at the statement, while
    # the iterable position is the operand the statement
    # dispatches on. The statement now resolves its
    # iterable as an instantiation standing in the
    # statement or through the bindings to the
    # instantiation its name denotes, on the terms the
    # instance resolution of the call locus reads a name
    # by.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Iter:
            def __iter__(self):
                _install_shadow()
                return iter([])


        _it = _Iter()


        for _ in _it:
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_descriptor_selected_from_a_tuple(
    tmp_path,
):
    # Repair pass nineteen, red team form 39a. A class
    # body after the candidate places a descriptor by a
    # subscript selecting the element out of a tuple
    # standing in the assignment, and the creation of
    # the class dispatches the set name method of the
    # class that element instantiates exactly as a body
    # placing the instantiation itself does. The
    # placement reading resolved an instantiation
    # standing in the value position, an element of a
    # tuple an assignment unpacks, and a name the module
    # level bound to an instantiation, while a subscript
    # standing in the value position resolved to no
    # class, although the subscript is an indexing the
    # counting can perform, over a literal the source
    # carries in full. The reading now resolves a
    # subscript selecting an element of a literal tuple
    # or list, the element read from a constant index
    # where the subscript carries one and every element
    # where it does not.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        class _TupleMarked:
            marker = (_ShadowDescriptor(),)[0]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_descriptor_in_a_conditional_arm(
    tmp_path,
):
    # Repair pass nineteen, red team form 39b. A class
    # body after the candidate places a descriptor by an
    # instantiation standing in an arm of a conditional
    # expression, and the creation dispatches the set
    # name method of the class the taken arm
    # instantiates. The reach reads both arms of a
    # conditional expression standing in an executing
    # position, on the ground that an expression the
    # counting cannot fold is read in full rather than
    # missed, while the placement reading read neither
    # arm, so the placement resolved to no class. The
    # reading now resolves an instantiation standing in
    # either arm on the reach's own terms, so a
    # condition the counting cannot fold over refuses
    # here rather than missing the placement, and the
    # repair does not go data dependent to do it.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        class _CondMarked:
            marker = _ShadowDescriptor() if True else None
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_keeps_a_helper_beside_a_walrus_bound_quiet_name(
    tmp_path,
):
    # Repair pass nineteen, the boundary control beside
    # family 35. The same walrus shape as form 35a
    # stands here with the bound name denoting a quiet
    # definition whose body only returns, the name bound
    # and called after the candidate. The call now
    # resolves the walrus bound name through the pair
    # collected bindings exactly as an assigned name,
    # and its body joins the reach, but it calls nothing
    # and assigns nothing under a global declaration, so
    # the counting this pass adds refuses nothing here
    # and the faithful helper keeps its derivation
    # beside the reader. The control marks the family
    # turning on the bound value performing the rewrite,
    # the repair counting the binding as the binding it
    # is while keeping the refusal keyed on what the
    # resolved body does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _quiet():
            return None


        (_alias_quiet := _quiet)


        _alias_quiet()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_a_quiet_with_manager(
    tmp_path,
):
    # Repair pass nineteen, the boundary control beside
    # family 36. The same manager shape as form 36a
    # stands here with a class whose dunder enter method
    # only returns the instance and whose dunder exit
    # method only returns false, the manager entered by
    # a with statement after the candidate. The statement
    # now counts as a call into both protocol methods
    # and their bodies join the reach, but they call
    # nothing and assign nothing under a global
    # declaration, so the counting this pass adds
    # refuses nothing here and the faithful helper keeps
    # its derivation beside the reader. The control
    # marks the family turning on a protocol method
    # performing the rewrite, the repair counting the
    # protocol execution as the call it is while keeping
    # the refusal keyed on what the method body does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _QuietCtx:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False


        with _QuietCtx():
            pass
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_a_delegating_class_getitem(
    tmp_path,
):
    # Repair pass nineteen, the boundary control beside
    # family 37. The same subscript shape as form 37a
    # stands here with a dunder class getitem method
    # that only returns the class it stands on, the
    # subscript standing in the base expression of a
    # class defined after the candidate. The subscript
    # now counts as a call into the method and its body
    # joins the reach, but it calls nothing and assigns
    # nothing under a global declaration, so the
    # counting this pass adds refuses nothing here and
    # the faithful helper keeps its derivation beside
    # the reader. The control marks the family turning
    # on the getitem method performing the rewrite, the
    # repair counting the subscript evaluation as the
    # execution it is while keeping the refusal keyed on
    # what the method body does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _GIBase:
            @classmethod
            def __class_getitem__(cls, item):
                return cls


        class _GIChild(_GIBase[int]):
            pass
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_a_quiet_iterable(
    tmp_path,
):
    # Repair pass nineteen, the boundary control beside
    # family 38. The same iterable shape as form 38a
    # stands here with a class whose dunder iter method
    # only returns an empty iterator, the iterable
    # walked by a for statement after the candidate. The
    # statement now counts as a call into the iter
    # method and its body joins the reach, but it calls
    # nothing and assigns nothing under a global
    # declaration, so the counting this pass adds refuses
    # nothing here and the faithful helper keeps its
    # derivation beside the reader. The control marks
    # the family turning on a protocol method performing
    # the rewrite, the repair counting the iteration as
    # the execution it is while keeping the refusal
    # keyed on what the method body does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Iter:
            def __iter__(self):
                return iter([])


        for _ in _Iter():
            pass
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_local_name(
    tmp_path,
):
    # Repair pass twenty, red team form 40a. A class
    # whose dunder iter method binds its first parameter
    # to a local name and returns that name is its own
    # iterator exactly as the direct return is, so the
    # for statement after the candidate draws its
    # elements by performing the dunder next method of
    # the same class, whose body calls the installer.
    # The next counting read the gathered iter method's
    # return at the one shape of the parameter name
    # standing alone as the returned value, so the
    # return through the local name counted nothing.
    # The self return reading now follows a name the
    # method's body binds to its first parameter, on
    # the ground the shipped sentence predicates the
    # counting on the method returning the instance
    # itself, and the return value ground stays fenced
    # for a method returning any other value.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterLocal:
            def __iter__(self):
                result = self
                return result

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterLocal():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_conditional_arm(
    tmp_path,
):
    # Repair pass twenty, red team form 40b. The dunder
    # iter method returns the instance through one arm
    # of a conditional expression whose other arm
    # returns an empty iterator, the condition a
    # literal the counting cannot fold being read at
    # full width as the counting reads both arms of
    # such an expression at every other locus. The loop
    # performs the dunder next method of the class on
    # the arm the expression yields at runtime, and
    # the counting that took only the parameter name
    # standing alone read the conditional return as
    # returning another value and counted nothing. A
    # return of a conditional expression now counts
    # where either arm returns the instance, over
    # reading an unfoldable condition in the safe
    # direction as the placement reading already does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterCond:
            def __iter__(self):
                return self if True else iter(())

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterCond():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_sequence_fallback_getitem_method(
    tmp_path,
):
    # Repair pass twenty, red team form 41a. A class
    # defining no dunder iter method is still iterated
    # by a for statement, through the sequence protocol
    # the data model designates as the fallback,
    # calling the dunder getitem method with successive
    # integer indices until it raises IndexError. The
    # statement after the candidate iterates such a
    # class whose getitem method calls the installer
    # on its first index. No reading gathered a getitem
    # method as a statement protocol, so the fallback
    # execution counted nothing. The getitem methods
    # of module level classes now stand gathered on
    # the same installation terms as the iteration
    # methods, and a for statement counts them where
    # no iter method stands anywhere in the chain of
    # the class its iterable denotes, the fallback
    # firing only in the iter method's absence.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _SeqIter:
            def __getitem__(self, index):
                if index == 0:
                    _install_shadow()
                    return "x"
                raise IndexError(index)


        for _ in _SeqIter():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_augmented_assignments_iadd_method(
    tmp_path,
):
    # Repair pass twenty, red team form 43a. An
    # augmented assignment performs a designated
    # dispatch on the class of the value its target
    # name denotes, and the assignment standing after
    # the candidate performs the dunder iadd method of
    # a class whose method calls the installer. The
    # reach walked the statement for the calls standing
    # inside it and counted no protocol at it, although
    # the pair collection's own shipped terms gather
    # the augmented assignment as a binding form, so
    # the statement stands inside the modelled grammar.
    # The iadd and add methods of module level classes
    # now stand gathered on the same installation
    # terms, and an augmented assignment whose target
    # is a plain name counts as a call into the method
    # the chain of the class the name's value denotes
    # carries.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Accum:
            def __iadd__(self, other):
                _install_shadow()
                return self


        _acc = _Accum()


        _acc += 1
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_augmented_assignments_add_fallback(
    tmp_path,
):
    # Repair pass twenty, red team form 43b. The same
    # augmented assignment shape stands here with a
    # class carrying no dunder iadd method, so the
    # statement performs the dunder add method as the
    # in place method's designated fallback, and that
    # method calls the installer. The counting now
    # takes the fallback on the same terms, counting
    # the plain method where the chain carries no in
    # place method, since the fallback fires only in
    # the in place method's absence.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _AccumAdd:
            def __add__(self, other):
                _install_shadow()
                return self


        _acc = _AccumAdd()


        _acc += 1
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_call_bearing_an_unpacked_installer_alias(
    tmp_path,
):
    # Repair pass twenty, red team form 45a. A single
    # assignment unpacks the installer and a second
    # copy of it into two names, and a call standing
    # after the candidate bears the first of them. The
    # statement itself pairs each target element with
    # the value element at its place, but the bindings
    # table recorded every unpacked name against the
    # whole tuple value, and a name bound to a tuple
    # resolved to nothing at the call seat. The
    # bindings now pair tuple and list target elements
    # with the elements of a literal tuple or list
    # value element by element where the shapes allow
    # it, so an unpacked name resolves to its own
    # element on the same terms as any other binding,
    # and a shape the pairing cannot fix keeps the
    # whole value recording, which resolves nothing.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        _alias_installer, _other = _install_shadow, _install_shadow


        _alias_installer()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_subclass_hook_behind_an_unpacked_base_alias(
    tmp_path,
):
    # Repair pass twenty, red team form 45b. The same
    # unpacking stands here with the elements standing
    # as a class whose subclass hook calls the
    # installer, the first unpacked name then standing
    # as the base of a subclass defined after the
    # candidate, so the hook fires at the subclass
    # definition. The base seat turned the unpacked
    # name into a class through the same bindings
    # table, and the name bound to the whole tuple
    # denoted no class there either. The element by
    # element pairing fixes the base seat on the same
    # terms as the call seat.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _HookBase:
            def __init_subclass__(cls, **kwargs):
                _install_shadow()


        _alias, _other = _HookBase, _HookBase


        class _HookChild(_alias):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_instance_call_on_an_unpacked_instance(
    tmp_path,
):
    # Repair pass twenty, red team form 45c. The same
    # unpacking stands here with the elements standing
    # as instantiations of a class whose dunder call
    # method calls the installer, one unpacked name
    # then called after the candidate, dispatching on
    # the call method of its class. The instance call
    # seat resolved the called name through the same
    # bindings table, and the name bound to the whole
    # tuple denoted no instance there. The element by
    # element pairing fixes the instance call seat on
    # the same terms as the other seats.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Runner:
            def __call__(self):
                _install_shadow()


        _r1, _r2 = _Runner(), _Runner()


        _r1()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_with_statements_conditional_manager(
    tmp_path,
):
    # Repair pass twenty, red team form 46a. A with
    # statement standing after the candidate manages a
    # conditional expression whose literal arm
    # instantiates a context class whose dunder enter
    # method calls the installer, the other arm
    # instantiating a quiet class. The statement
    # evaluates its manager position to the loud
    # instance and performs its protocol, and the
    # constructions standing inside both arms were
    # already read for their calls as the statement
    # was walked, but the operand resolution took an
    # inline instantiation or a name and nothing else,
    # so the protocol counted nothing. A conditional
    # expression operand now contributes the classes
    # of both arms, resolved on the same instantiation
    # and name terms, over reading the condition in
    # the safe direction as the counting does at every
    # other locus.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _EnterCtx:
            def __enter__(self):
                _install_shadow()
                return self

            def __exit__(self, *exc):
                return False


        class _QuietCtx:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False


        with (_EnterCtx() if True else _QuietCtx()):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_for_statements_conditional_iterable(
    tmp_path,
):
    # Repair pass twenty, red team form 46b. The same
    # conditional operand stands here as the iterable
    # of a for statement, its literal arm instantiating
    # an iterable class whose dunder iter method calls
    # the installer and its other arm a quiet class.
    # The statement performs the iter method of the
    # class its iterable position evaluates to, and
    # the operand resolution that took two forms read
    # the conditional as denoting nothing, so the
    # iteration protocol counted nothing while the
    # constructions inside the arms counted. The
    # widened operand resolution fixes the for seat on
    # the same terms as the with seat.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Iter:
            def __iter__(self):
                _install_shadow()
                return iter([])


        class _QuietIter:
            def __iter__(self):
                return iter([])


        for _ in (_Iter() if True else _QuietIter()):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_for_statements_walrus_iterable(
    tmp_path,
):
    # Repair pass twenty, red team form 46c. A for
    # statement standing after the candidate iterates
    # a walrus expression whose value instantiates an
    # iterable class whose dunder iter method calls
    # the installer. The pair collection reads the
    # walrus form as a binding of the very value it
    # evaluates to, so the operand's denotation is one
    # the counting itself records elsewhere, but the
    # operand resolution took the inline call and the
    # name alone and read the walrus form as denoting
    # nothing. A walrus expression operand now
    # contributes the classes of its value, resolved
    # on the same terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Iter:
            def __iter__(self):
                _install_shadow()
                return iter([])


        for _ in (_it := _Iter()):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_with_statements_walrus_manager(
    tmp_path,
):
    # Repair pass twenty, red team form 46d. The same
    # walrus operand stands here as the manager of a
    # with statement, its value instantiating a
    # context class whose dunder enter method calls
    # the installer. The statement performs the enter
    # method of the instance the walrus binds as it
    # manages it, and the operand resolution read the
    # form as denoting nothing, so the with protocol
    # counted nothing. The walrus widening fixes the
    # with seat on the same terms as the for seat.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _EnterCtx:
            def __enter__(self):
                _install_shadow()
                return self

            def __exit__(self, *exc):
                return False


        with (_mgr := _EnterCtx()):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_descriptor_placed_by_a_boolean_left_operand(
    tmp_path,
):
    # Repair pass twenty, red team form 47a. A class
    # defined after the candidate places a descriptor
    # as the selected value of a boolean or expression
    # whose left operand instantiates the descriptor
    # class, the descriptor defining only a set name
    # method that calls the installer and no bool or
    # len method, so no truth testing dispatch is
    # involved and the placement itself fires the hook
    # at class creation. The placement reading resolved
    # an enumerated set of value forms and took no
    # boolean operator form, while the reach reads both
    # operands of the expression for the calls standing
    # inside them, the family 39 asymmetry at this
    # value form. A boolean operator value now resolves
    # through its operands on the conditional arm
    # terms, and the truth testing protocol stays
    # outside the fence beside it.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        class _DescriptorMarked:
            marker = _ShadowDescriptor() or None
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_descriptor_placed_by_a_boolean_right_operand(
    tmp_path,
):
    # Repair pass twenty, red team form 47b. The same
    # boolean placement stands here with the descriptor
    # instantiation in the right operand and None in
    # the left, so the expression yields the right
    # operand and the placement fires the same hook.
    # The widened reading takes the placed classes of
    # both operands whichever one the expression
    # selects, on the same terms as the left operand
    # form.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        class _DescriptorMarked:
            marker = None or _ShadowDescriptor()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_descriptor_selected_through_a_bound_name(
    tmp_path,
):
    # Repair pass twenty, red team form 47c. A class
    # defined after the candidate places an element
    # selected by subscript from a tuple standing
    # behind a module level name rather than in the
    # assignment itself, the tuple holding an instance
    # of the descriptor class whose set name method
    # calls the installer. The placement reading
    # performed both halves of the composition at this
    # locus, resolving a placed name through the
    # bindings and selecting an element from a literal,
    # but no branch resolved a name to the literal it
    # denotes and then selected through it. A subscript
    # whose value is a name the module level bindings
    # resolve to a tuple or list literal now selects
    # through the resolved literal on the same index
    # terms the direct subscript form uses.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        _pair = (_ShadowDescriptor(),)


        class _DescriptorMarked:
            marker = _pair[0]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_boolean_placed_descriptor_inside_a_called_body(
    tmp_path,
):
    # Repair pass twenty, red team form 47d. The same
    # boolean placement as form 47a stands here inside
    # a class body inside a function the module level
    # calls after the candidate, so the gap stands in
    # the value resolution and not in the locus. The
    # reach reads the class body inside the called
    # body on module terms, the placement reading
    # consults the same widened resolution there, and
    # the hook fires as the creation runs inside the
    # call.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        def _build():
            class _DescriptorMarked:
                marker = _ShadowDescriptor() or None


        _build()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_keeps_a_helper_beside_a_next_method_behind_a_distinct_iterator_return(
    tmp_path,
):
    # Repair pass twenty, the boundary control beside
    # family 40. The same class shape as form 40a
    # stands here with a dunder iter method returning
    # a distinct iterator object, an empty list
    # iterator, while its dunder next method calls the
    # installer. The loop draws its elements from the
    # returned iterator and never performs the class's
    # own next method, so the next counting stays
    # fenced on the return value ground for a method
    # returning any value but the instance itself,
    # through a local name or a conditional arm alike,
    # and the faithful helper keeps its derivation
    # beside the reader. The control marks the family
    # turning on the iter method returning the instance
    # itself, the repair widening the reading of that
    # return while keeping the refusal keyed on the
    # class the statement starts from performing its
    # own next method.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _DistinctIter:
            def __iter__(self):
                return iter([])

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _DistinctIter():
            pass
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_a_getitem_method_displaced_by_an_iter_method(
    tmp_path,
):
    # Repair pass twenty, the boundary control beside
    # family 41. The same class shape as form 41a
    # stands here with a quiet dunder iter method
    # beside the loud dunder getitem method on one
    # class, the for statement after the candidate
    # iterating it. The statement dispatches on the
    # iter method and the sequence fallback never
    # fires, so the getitem method never runs and the
    # counting this pass adds refuses nothing here,
    # the faithful helper keeping its derivation beside
    # the reader. The control marks the family turning
    # on the fallback standing alone in the chain, the
    # repair counting the getitem method only where
    # no iter method stands anywhere in it.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _BothProtocols:
            def __iter__(self):
                return iter(())

            def __getitem__(self, index):
                _install_shadow()
                raise IndexError(index)


        for _ in _BothProtocols():
            pass
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_a_hookless_descriptor_placed_by_a_boolean_expression(
    tmp_path,
):
    # Repair pass twenty, the boundary control beside
    # family 47. The same boolean placement as form
    # 47a stands here with a descriptor class carrying
    # no set name method at all, placed in a class body
    # after the candidate. The placement now resolves
    # through both operands of the expression and finds
    # the descriptor's class, but the class carries no
    # hook whose body could run at the creation, so the
    # counting this pass adds refuses nothing here and
    # the faithful helper keeps its derivation beside
    # the reader. The control marks the family turning
    # on the placed descriptor carrying the hook, the
    # repair widening the placement reading while
    # keeping the refusal keyed on what the resolved
    # hook does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _HooklessDescriptor:
            pass


        class _DescriptorMarked:
            marker = _HooklessDescriptor() or None
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_enter_method_installed_by_unpacking(
    tmp_path,
):
    # Repair pass twenty one, red team form 48a. A
    # class defined after the candidate installs its
    # enter and exit methods by unpacking a tuple of
    # two module level functions, the enter method
    # calling the installer, and a with statement
    # after the candidate manages an instance of the
    # class. The installation reading consumed the
    # assignment pairs uncorrected, pairing each
    # designated name with the whole tuple value,
    # which gathers neither a plain name nor a lambda
    # and so installed nothing. The installations are
    # now read with the element pairing applied on
    # the bindings table's terms, so the designated
    # name is paired with the element standing at its
    # own place and the method it denotes is gathered.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _loud_enter(self):
            _install_shadow()
            return self


        def _quiet_exit(self, *exc):
            return False


        class _Ctx:
            __enter__, __exit__ = _loud_enter, _quiet_exit


        with _Ctx():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_iter_method_installed_by_unpacking(
    tmp_path,
):
    # Repair pass twenty one, red team form 48b. The
    # same unpacking installation stands here under
    # the iter name of an iterable class, the paired
    # element a module level function whose body
    # calls the installer, and a for statement after
    # the candidate walks an instance of the class.
    # The installation reading paired the designated
    # name with the whole tuple and gathered nothing,
    # so the iteration counting never saw the method
    # the statement performs. The element pairing now
    # serves every gathering the installation reading
    # feeds, the protocol tables among them.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _loud_iter(self):
            _install_shadow()
            return iter(())


        class _IterPacked:
            __iter__, _other = _loud_iter, _loud_iter


        for _ in _IterPacked():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_an_unpacking_bound_name(
    tmp_path,
):
    # Repair pass twenty one, red team form 49a. A
    # class whose dunder iter method binds a local
    # name to its first parameter by unpacking, the
    # name standing against the parameter in a two
    # element tuple, and returns that name is its own
    # iterator exactly as the direct binding is, so
    # the for statement after the candidate performs
    # the dunder next method of the same class, whose
    # body calls the installer. The self return
    # reading's own alias collector flattened the
    # unpacking target against the whole value, so
    # the returned name counted as bound to the tuple
    # and not to the parameter. The collector now
    # applies the element pairing on the same terms
    # as the bindings table, and the shipped sentence
    # predicates the counting on the method returning
    # the instance itself, fencing only a return of
    # any other value.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterUnpack:
            def __iter__(self):
                result, _unused = self, None
                return result

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterUnpack():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_conditionally_bound_name(
    tmp_path,
):
    # Repair pass twenty one, red team form 49b. The
    # dunder iter method binds a local name to a
    # conditional expression whose arms are both its
    # first parameter and returns that name, so the
    # instance itself comes back through the binding
    # and the loop performs the class's dunder next
    # method, whose body calls the installer. The
    # alias collector's fixed point followed only
    # bindings whose value is a name node, although
    # the same reading follows a conditional arm at
    # full width at the return expression itself. The
    # fixed point now follows a name bound to a
    # conditional expression either of whose arms is
    # a name already in the set, beside the plain
    # name values it followed before.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterCondAlias:
            def __iter__(self):
                result = self if True else self
                return result

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterCondAlias():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_enter_method_behind_a_boolean_manager(
    tmp_path,
):
    # Repair pass twenty one, red team form 50a. A
    # with statement after the candidate manages a
    # boolean expression whose left operand
    # instantiates a context class whose enter method
    # calls the installer and whose right operand
    # instantiates a quiet one, the expression
    # evaluating to the loud instance at runtime. The
    # operand resolution took a call, a name, a
    # conditional expression, and a walrus expression
    # and nothing else, so the statement's
    # construction was counted while its protocol was
    # not, the asymmetry of the earlier operand
    # families at the same locus. A boolean operand
    # now resolves through its operands on the same
    # terms, as the placement reading has read boolean
    # values since the pass twenty repair.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _EnterCtx:
            def __enter__(self):
                _install_shadow()
                return self

            def __exit__(self, *exc):
                return False


        class _QuietCtx:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False


        with (_EnterCtx() or _QuietCtx()):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_iter_method_behind_a_boolean_iterable(
    tmp_path,
):
    # Repair pass twenty one, red team form 50b. The
    # same boolean operand stands here at the iterable
    # position of a for statement after the candidate,
    # its left operand instantiating an iterable class
    # whose iter method calls the installer. The
    # operand resolution returned nothing for a
    # boolean expression, so the loop's construction
    # was counted and its iteration protocol was not.
    # The widened resolution serves both statement
    # positions, the manager and the iterable alike,
    # because the two positions share the one reading.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Iter:
            def __iter__(self):
                _install_shadow()
                return iter(())


        class _QuietIter:
            def __iter__(self):
                return iter(())


        for _ in (_Iter() or _QuietIter()):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_enter_method_behind_a_subscripted_manager(
    tmp_path,
):
    # Repair pass twenty one, red team form 50c. A
    # with statement after the candidate manages a
    # subscript selecting the single element of a
    # literal tuple standing behind a module level
    # name, the element an instance of a context class
    # whose enter method calls the installer. The
    # operand resolution took no subscript form, while
    # the placement reading at the neighbouring locus
    # selects through a name bound to a literal at
    # full width. A subscript operand now resolves
    # through the elements the literal selection picks
    # out, on the selection terms that reading uses,
    # each resolved element read on the same
    # instantiation and name terms as the other forms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _EnterCtx:
            def __enter__(self):
                _install_shadow()
                return self

            def __exit__(self, *exc):
                return False


        _ctxs = (_EnterCtx(),)


        with _ctxs[0]:
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_behind_a_conditional_value_position(
    tmp_path,
):
    # Repair pass twenty one, red team form 51a. A
    # module level assignment after the candidate
    # evaluates a subscript whose value position
    # stands as a conditional expression, one arm
    # naming a class whose class getitem method calls
    # the installer and the other a class carrying
    # none. Evaluating the subscript performs the arm
    # class's method at runtime. The value position
    # reading behind the subscript counting took a
    # bare name or a subscript and nothing else, so
    # the conditional resolved to no class although
    # the shipped sentence predicates the counting on
    # the value position resolving to a module level
    # class and the reach resolves conditional arms at
    # full width at every other locus. The value
    # position is now resolved on the reach's
    # expression terms for the execution counting,
    # the denotation reading keeping its own width
    # for the base and annotation positions it serves.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _GIBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        class _GIOther:
            pass


        _selected = (_GIBase if True else _GIOther)[int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_descriptor_placed_by_a_name_bound_to_a_conditional(
    tmp_path,
):
    # Repair pass twenty one, red team form 52a. A
    # class defined after the candidate places a plain
    # name the module level bound to a conditional
    # expression whose taken arm instantiates a
    # descriptor class whose set name method calls the
    # installer, so class creation fires the hook at
    # runtime. The placement reading followed a placed
    # name through bound values standing as a call, a
    # further name, or a sequence, and through no
    # expression form, while its own top level
    # resolves a conditional expression standing in
    # the assignment itself. The name branch now
    # follows the bound value on the reading's own
    # terms, a conditional bound value resolving
    # through its arms as the form standing alone
    # does, with one binding between the halves of
    # the composition and no data dependence.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        _d = _ShadowDescriptor() if True else None


        class _DescriptorMarked:
            marker = _d
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_descriptor_placed_by_a_name_bound_to_a_subscript_selection(
    tmp_path,
):
    # Repair pass twenty one, red team form 52b. The
    # placed name stands here bound to a subscript
    # selecting the descriptor instance out of a
    # literal tuple, the same composition as form 52a
    # through the selection form. The placement
    # reading resolves a subscript selection standing
    # in the assignment itself and follows a placed
    # name through the bindings, but no branch of the
    # name reading resolved the selected element
    # standing behind the binding. A name bound to a
    # subscript now resolves through the subscript
    # branch's own selection, so the name denotes
    # what its binding denotes on the forms the
    # reading takes standing alone.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        _d = (_ShadowDescriptor(),)[0]


        class _DescriptorMarked:
            marker = _d
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_descriptor_placed_by_an_unpacking_target_against_a_bound_literal(
    tmp_path,
):
    # Repair pass twenty one, red team form 53. A
    # class defined after the candidate unpacks a
    # name the module level bound to a literal tuple
    # whose first element instantiates a descriptor
    # class whose set name method calls the
    # installer, the element name standing against
    # the descriptor in the namespace the body
    # builds, so class creation fires the hook at
    # runtime. The set name counting handed the
    # placement reading each body pair's value alone,
    # the pair for the unpacking assignment recording
    # the whole name, and the name branch read a name
    # bound to a tuple as denoting the tuple itself,
    # so the element the statement places was never
    # read as an element although the creation
    # passage claims an element of a tuple or a list
    # the assignment unpacks with no qualification on
    # where the tuple stands. The set name seat now
    # reads the element each target name stands
    # against on the element pairing terms, the value
    # standing as a literal in the assignment or
    # denoted by a plain name the bindings resolve to
    # a literal, while the same pairing at the
    # bindings seats stays as the pairing sentence
    # leaves it.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        _pair = (_ShadowDescriptor(), None)


        class _DescriptorMarked:
            marker, _other = _pair
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_keeps_a_helper_beside_an_enter_method_installed_by_unpacking_that_calls_nothing(
    tmp_path,
):
    # Repair pass twenty one, the boundary control
    # beside family 48. The same unpacking
    # installation as form 48a stands here with enter
    # and exit methods that call nothing and assign
    # nothing under a global declaration, the with
    # statement after the candidate managing an
    # instance of the class. The installations are now
    # gathered with the element pairing applied and
    # their bodies join the reach, but the counting
    # this pass adds refuses nothing here and the
    # faithful helper keeps its derivation beside the
    # reader. The control marks the family turning on
    # the installed method performing the rewrite,
    # the repair widening the installation reading
    # while keeping the refusal keyed on what the
    # gathered method body does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _quiet_enter(self):
            return self


        def _quiet_exit(self, *exc):
            return False


        class _Ctx:
            __enter__, __exit__ = _quiet_enter, _quiet_exit


        with _Ctx():
            pass
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_a_hookless_descriptor_placed_by_a_name_bound_to_a_conditional(
    tmp_path,
):
    # Repair pass twenty one, the boundary control
    # beside family 52. The same name bound
    # conditional placement as form 52a stands here
    # with a descriptor class carrying no set name
    # method at all, placed in a class body after the
    # candidate through a name bound to a conditional
    # expression whose taken arm instantiates it. The
    # placement now follows the name through the
    # conditional binding and resolves the
    # descriptor's class, but the class carries no
    # hook whose body could run at the creation, so
    # the counting this pass adds refuses nothing
    # here and the faithful helper keeps its
    # derivation beside the reader. The control marks
    # the family turning on the placed descriptor
    # carrying the hook, the repair widening the name
    # reading while keeping the refusal keyed on what
    # the resolved hook does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _HooklessDescriptor:
            pass


        _d = _HooklessDescriptor() if True else None


        class _DescriptorMarked:
            marker = _d
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_call_bearing_the_name_of_a_loop_target(
    tmp_path,
):
    # Repair pass twenty two, red team family 57,
    # form A1. A loop after the candidate binds the
    # installer itself as an element of a one element
    # literal, and a call after the loop bears the
    # loop target's name, so the call runs the
    # installer at runtime. The pair collection pairs
    # a loop target with the iterable its header
    # walks, and the call resolution consumed that
    # recording whole, so the name resolved to
    # nothing at the call seat although the placement
    # passage states the name denotes an element. A
    # loop target name now denotes an element of its
    # iterable at every seat that resolves a name to
    # a value, the elements read where the iterable
    # stands as a literal or as a plain name the
    # bindings resolve to one.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        for _installer in [_install_shadow]:
            pass


        _installer()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_subclass_hook_behind_a_base_a_loop_target_bound(
    tmp_path,
):
    # Repair pass twenty two, red team family 57,
    # form A2. A loop after the candidate binds a
    # class carrying a subclass hook as an element,
    # and a class definition after the loop names
    # the loop variable as its base, so the hook
    # fires at the child class creation and calls
    # the installer. The base reading turned the
    # name into a class through the same iterable
    # recording and resolved it to nothing, so no
    # hook was gathered. The element standing now
    # serves the class turning points beside the
    # other seats, through the one alias resolution
    # every base reading consults.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _HookBase:
            def __init_subclass__(cls, **kwargs):
                _install_shadow()


        for _base in [_HookBase]:
            pass


        class _HookChild(_base):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_decorator_application_of_an_instance_a_loop_target_bound(
    tmp_path,
):
    # Repair pass twenty two, red team family 57,
    # form A3. A loop after the candidate binds an
    # instance of a callable class as an element,
    # and a definition after the loop stands the
    # loop name as a bare name decorator, so the
    # instance call method runs the installer as the
    # decoration is applied. The decorator seat
    # counts the application as a call into the
    # value the name denotes, resolved as the reach
    # resolves its callees, and that resolution
    # consumed the iterable recording whole and
    # named no instance. The element standing now
    # serves the instance resolution the application
    # counting consults.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Runner:
            def __call__(self, fn):
                _install_shadow()
                return fn


        for _deco in [_Runner()]:
            pass


        @_deco
        def _decoy():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_instance_call_bearing_the_name_of_a_loop_target(
    tmp_path,
):
    # Repair pass twenty two, red team family 57,
    # form A4. A loop after the candidate binds an
    # instance of a callable class as an element,
    # and a call after the loop bears the loop
    # target's name, so the call dispatches on the
    # class's call method, whose body calls the
    # installer. The instance resolution of the call
    # locus read the name through the iterable
    # recording and named no instance, so the call
    # counted nothing. An element the iterable
    # denotes that instantiates a class now counts
    # at that resolution as an instance of the
    # class, on the same element terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Runner:
            def __call__(self):
                _install_shadow()


        for _runner in [_Runner()]:
            pass


        _runner()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_enter_method_behind_a_manager_a_loop_target_bound(
    tmp_path,
):
    # Repair pass twenty two, red team family 57,
    # form A5. A loop after the candidate binds a
    # context manager instance as an element, and a
    # with statement after the loop opens over the
    # loop name, so the enter method of the
    # manager's class runs the installer. The
    # manager position denotes its instance through
    # the instance resolution of the call locus,
    # which consumed the iterable recording whole,
    # so the statement's construction was the only
    # execution the counting saw and its protocol
    # went uncounted. The element standing now
    # serves the operand resolution beside the
    # other seats.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _EnterCtx:
            def __enter__(self):
                _install_shadow()
                return self

            def __exit__(self, *exc):
                return False


        for _mgr in [_EnterCtx()]:
            pass


        with _mgr:
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_augmented_assignments_isub_method(
    tmp_path,
):
    # Repair pass twenty two, red team family 58,
    # form B1. An augmented assignment after the
    # candidate subtracts from a name bound to an
    # instance of a class carrying only the in place
    # subtract method, whose body calls the
    # installer, and the statement performs that
    # dispatch at runtime. The augmented passage
    # claims the dispatch of the statement's
    # operation, but the counting gathered the
    # additive pair alone and consulted it whatever
    # operator the statement carried. The counting
    # now gathers the in place and plain pair of
    # every operator the grammar carries and counts
    # the pair the statement's operator names.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _AccumSub:
            def __isub__(self, other):
                _install_shadow()
                return self


        _acc = _AccumSub()


        _acc -= 1
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_augmented_assignments_sub_fallback(
    tmp_path,
):
    # Repair pass twenty two, red team family 58,
    # form B2. The same subtractive statement stands
    # here against a class carrying only the plain
    # subtract method, the fallback the runtime
    # performs in the in place method's absence, and
    # its body calls the installer. The fallback
    # standing is designated per operator as the
    # additive pair's was, so the widened gathering
    # counts the plain method of the statement's own
    # operation where its chain carries no in place
    # method, and the statement is refused on the
    # same terms as the additive fallback form.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _AccumSubOnly:
            def __sub__(self, other):
                _install_shadow()
                return self


        _acc = _AccumSubOnly()


        _acc -= 1
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_augmented_assignments_imul_method(
    tmp_path,
):
    # Repair pass twenty two, red team family 58,
    # form B3. A multiplicative augmented assignment
    # after the candidate stands against a class
    # carrying only the in place multiply method,
    # whose body calls the installer. The operator
    # width is the family's ground rather than the
    # additive pair's, so the counting dispatches on
    # the operator the statement carries across the
    # whole family the grammar carries, and this
    # form marks a second operator beside the
    # subtractive forms so the repair cannot stand
    # as a widening to two pairs alone.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _AccumMul:
            def __imul__(self, other):
                _install_shadow()
                return self


        _acc = _AccumMul()


        _acc *= 2
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_behind_a_boolean_value_position(
    tmp_path,
):
    # Repair pass twenty two, red team family 59,
    # form C1. A subscript at module level after the
    # candidate stands its value position as a
    # boolean expression whose first operand is a
    # class whose class getitem method calls the
    # installer, and the expression evaluates to
    # that class, so the subscript performs its
    # getitem as it evaluates. The subscript value
    # reading resolved a conditional expression
    # standing in the position and no other
    # expression form, although the passage
    # predicates the counting on the value position
    # resolving to a module level class. The reading
    # now resolves a boolean expression through its
    # operands on the same terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _GIBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        class _GIOther:
            pass


        _selected = (_GIBase or _GIOther)[int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_behind_a_walrus_value_position(
    tmp_path,
):
    # Repair pass twenty two, red team family 59,
    # form C2. The same subscript stands here with a
    # walrus expression in its value position,
    # binding the class as it yields it, so the
    # subscript performs the class's getitem method
    # as it evaluates and the method calls the
    # installer. A walrus is read through at the
    # operand, placement, and return loci, and the
    # subscript value reading now reads it through
    # at this locus too, resolving to the class of
    # the value the walrus yields, completing the
    # expression width the passage claims on its
    # resolution predicate.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _GIBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        _selected = (_chosen := _GIBase)[int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_subscript_selection(
    tmp_path,
):
    # Repair pass twenty two, red team family 60,
    # form D1. A class whose dunder iter method
    # returns the instance through a subscript
    # selecting it out of a one element literal
    # tuple is its own iterator by construction, so
    # the for statement after the candidate performs
    # the dunder next method of the same class,
    # whose body calls the installer. The self
    # return scan read the parameter standing bare,
    # through a walrus, as a boolean operand, and
    # through a conditional arm, and had no
    # subscript branch, although literal selection
    # is a form the guard reads at full width at
    # the placement and operand loci. The scan now
    # reads a subscript selecting an element of a
    # literal on the index terms the placement
    # reading selects on.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterSubscript:
            def __iter__(self):
                return (self,)[0]

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterSubscript():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_an_aliased_subscript_selection(
    tmp_path,
):
    # Repair pass twenty two, red team family 60,
    # form D2. The same selection stands here behind
    # a local name the iter body binds to it, the
    # alias form the earlier self return repair
    # covered for plain bindings, and the method
    # returns that name. The alias collector's value
    # reading had no subscript branch either, so
    # the bound name counted as bound to no value
    # the reading follows. The value reading now
    # resolves a subscript selection on the same
    # index terms, so a name bound to a selection of
    # the instance counts as the instance through
    # the binding as it does standing in the return.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterSubscriptAlias:
            def __iter__(self):
                result = (self,)[0]
                return result

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterSubscriptAlias():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_plain_loop_target_name(
    tmp_path,
):
    # Repair pass twenty two, red team family 61,
    # form G1. A class whose dunder iter method
    # binds a local name through a plain loop target
    # over a one element literal holding the
    # instance and returns that name is its own
    # iterator, so the for statement after the
    # candidate performs the class's dunder next
    # method, whose body calls the installer. The
    # self return passage claims the loop target
    # pairing with an element of the literal, but
    # the alias collector's loop branch reused the
    # unpacking element pairing helper, whose bare
    # name branch pairs the target with the whole
    # value it stands against, a pairing written
    # for unpacking targets. A plain loop target in
    # the collector now pairs with the elements of
    # a literal its header walks, the unpacking
    # target pairing standing as the earlier passes
    # settled it.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterLoopAlias:
            def __iter__(self):
                for result in [self]:
                    pass
                return result

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterLoopAlias():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_descriptor_placed_by_a_name_bound_to_a_walrus(
    tmp_path,
):
    # Repair pass twenty two, red team family 62,
    # form F1. A descriptor instance is created
    # inside a walrus expression at module level
    # after the candidate, a second name is bound
    # to the walrus name by plain assignment, and
    # that second name stands in a class body after
    # the candidate, so the descriptor's set name
    # method fires at the class creation and calls
    # the installer. The placement reading's name
    # branch followed a bound call, a bound name, a
    # bound sequence, a bound conditional, a bound
    # subscript, and a bound boolean expression,
    # and not a bound walrus, the one expression
    # form every sibling reading in the module reads
    # through. The branch now follows the value the
    # walrus yields on the same terms it reads a
    # bound call.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        _d = (_held := _ShadowDescriptor())


        class _DescriptorMarked:
            marker = _d
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_keeps_a_helper_beside_a_quiet_function_called_through_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty two, the boundary control
    # beside family 57. A loop after the candidate
    # binds a quiet module level function as an
    # element and a call after the loop bears the
    # loop target's name, the same shape as form A1
    # with a function whose body calls nothing and
    # assigns nothing under a global declaration.
    # The loop target name now denotes the element
    # at the call seat and the call is counted into
    # the quiet body, but the counting this pass
    # adds refuses nothing here and the faithful
    # helper keeps its derivation beside the reader.
    # The control marks the family turning on the
    # element the loop binds performing the rewrite,
    # the repair widening the resolution while
    # keeping the refusal keyed on what the resolved
    # body does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _quiet():
            return None


        for _fn in [_quiet]:
            pass


        _fn()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_a_hookless_descriptor_placed_by_a_name_bound_to_a_walrus(
    tmp_path,
):
    # Repair pass twenty two, the boundary control
    # beside family 62. The same walrus bound
    # placement as form F1 stands here with a
    # descriptor class carrying no set name method
    # at all, placed in a class body after the
    # candidate through a name bound to the name a
    # walrus bound to its instantiation. The
    # placement now follows the name through the
    # walrus binding and resolves the descriptor's
    # class, but the class carries no hook whose
    # body could run at the creation, so the
    # counting this pass adds refuses nothing here
    # and the faithful helper keeps its derivation
    # beside the reader. The control marks the
    # family turning on the placed descriptor
    # carrying the hook, the repair widening the
    # name reading while keeping the refusal keyed
    # on what the resolved hook does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _HooklessDescriptor:
            pass


        _d = (_held := _HooklessDescriptor())


        class _DescriptorMarked:
            marker = _d
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_instance_call_bearing_the_name_of_an_unpacking_loop_target(
    tmp_path,
):
    # Repair pass twenty three, red team family 67,
    # form 67a. A loop whose target unpacks its
    # element binds each name the target carries to
    # a component of the element, so the name here
    # denotes the callable instance standing at its
    # place in the one element tuple, and the call
    # after the candidate runs its dunder call
    # method, whose body calls the installer. The
    # element reading handed every seat the element
    # whole, because the unpacking pairing the
    # earlier passes settled read assignment targets
    # and no reading paired a loop target. The
    # element reading now pairs an unpacking loop
    # target against each element its header walks
    # on the same element pairing terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Runner:
            def __call__(self):
                _install_shadow()


        for _inst, _other in [(_Runner(), None)]:
            pass


        _inst()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_subclass_hook_behind_a_base_an_unpacking_loop_target_bound(
    tmp_path,
):
    # Repair pass twenty three, red team family 67,
    # form 67b. The same unpacking header binds a
    # class carrying a subclass hook at its place
    # in the element, and a class definition after
    # the candidate names the unpacking name as a
    # base, so the hook fires at the child class
    # creation and calls the installer. The alias
    # resolution read the name as denoting the
    # element tuple and resolved no class behind
    # it. The pairing the element reading now
    # performs for loop targets hands the base seat
    # the component the name denotes.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _HookBase:
            def __init_subclass__(cls, **kwargs):
                _install_shadow()


        for _base, _other in [(_HookBase, None)]:
            pass


        class _HookChild(_base):
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_behind_a_nested_selection_in_the_value_position(
    tmp_path,
):
    # Repair pass twenty three, red team family 68.
    # A subscript whose value position itself stands
    # as a subscript selecting a class out of a one
    # element literal performs the dunder class
    # getitem method of the class the selection
    # yields, whose body calls the installer. The
    # subscript value reading fell through to the
    # class denotation reading for such a subscript,
    # and the denotation reading resolves nothing
    # behind a literal, so the counting named no
    # class at the execution seat. The subscript
    # value reading now resolves a subscript
    # standing in the value position through the
    # elements it selects, on the index terms the
    # placement reading selects on, while the
    # denotation reading keeps its own width for
    # the base and annotation positions it serves.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _GIBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        _selected = (_GIBase,)[0][int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_selection_behind_a_local_name(
    tmp_path,
):
    # Repair pass twenty three, red team family 69,
    # form 69a. A class whose dunder iter method
    # binds a local name to a one element literal
    # holding the instance and returns a subscript
    # selecting through that name is its own
    # iterator by construction, so the for statement
    # after the candidate performs the dunder next
    # method of the same class, whose body calls the
    # installer. The selection helper read a
    # subscript only where the literal stood in the
    # node itself, although following a body local
    # name to the value it denotes is the alias
    # collector's own office. The selection reading
    # now resolves the literal a selection stands on
    # through the local bindings the collector
    # gathers for the body.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterNamedSelection:
            def __iter__(self):
                pair = (self,)
                return pair[0]

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterNamedSelection():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_selection_behind_a_loop_paired_name(
    tmp_path,
):
    # Repair pass twenty three, red team family 69,
    # form 69b. The same mediation stands here one
    # binding further in, through a plain loop
    # target over a list carrying one tuple holding
    # the instance, the target paired with that
    # tuple on the family 61 terms, and the return
    # selecting through the target name. The scan
    # could not read the selection because the name
    # the subscript stands on is a body local the
    # selection helper never resolved. The
    # selection reading now resolves such a name
    # through the pairs the collector gathers,
    # loop pairings among them.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterLoopNamedSelection:
            def __iter__(self):
                for result in [(self,)]:
                    pass
                return result[0]

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterLoopNamedSelection():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_name_bound_to_a_selection(
    tmp_path,
):
    # Repair pass twenty three, red team family 69,
    # form 69c. A local name bound to the selection
    # itself, out of a literal a second local name
    # denotes, is returned bare, so the evasion
    # stands in the alias collector's value reading
    # alone, the return standing as a plain name
    # the collector never admitted. The value
    # reading shares the widened selection reading,
    # so a name bound to a selection of the instance
    # counts as the instance through the binding as
    # it does standing in the return.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterAliasedSelection:
            def __iter__(self):
                pair = (self,)
                result = pair[0]
                return result

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterAliasedSelection():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_loop_target_over_a_bound_literal(
    tmp_path,
):
    # Repair pass twenty three, red team family 69,
    # form 69d. A plain loop target inside the iter
    # body walks a name the body binds to a list
    # literal holding the instance, and the method
    # returns the target name. The collector's loop
    # branch read literal headers only and paired
    # the target with the name itself, whose
    # denotation is the list and not the instance,
    # so the element step the earlier passes settled
    # for literal headers was missing behind the
    # name. The collector now pairs a loop target
    # whose header stands as a name with the
    # elements of the literal that name denotes in
    # the body.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterNamedLoop:
            def __iter__(self):
                pair = [self]
                for result in pair:
                    pass
                return result

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterNamedLoop():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_call_bearing_the_name_of_a_second_loop_target(
    tmp_path,
):
    # Repair pass twenty three, red team family 70.
    # Two loops chain in the open, the first binding
    # a name to the one element of a literal of one
    # list, the installer itself standing as that
    # list's only element, and the second walking
    # the first name and binding the installer to
    # its target, which the segment then calls. The
    # element reading recursed into what the middle
    # name denotes, the elements of its own
    # iterable, where the second loop asks what the
    # middle name is worth, one level short. The
    # element reading now composes, reading an
    # element for what it is worth where a further
    # loop's iterable stands as a loop target name,
    # so the chain resolves at every level.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        for _inner in [[_install_shadow]]:
            pass


        for _fn in _inner:
            pass


        _fn()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_call_naming_an_instance_bound_to_a_selection(
    tmp_path,
):
    # Repair pass twenty three, red team family 71,
    # form 71a. A name bound to a subscript selecting
    # an instantiation out of a one element literal
    # denotes that instance by construction, and a
    # call by that name after the candidate runs the
    # instance's dunder call method, whose body
    # calls the installer. The instance resolution
    # took no subscript value at all, although its
    # own passage states it resolves on the terms
    # the placement reading resolves a placed name
    # by, and the placement reading has followed
    # such a name since pass twenty one. The
    # instance resolution now reads a subscript
    # binding value through the elements it
    # selects, on the placement reading's index
    # terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Runner:
            def __call__(self):
                _install_shadow()


        _acc = (_Runner(),)[0]


        _acc()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_augmented_assignments_isub_method_on_an_instance_bound_to_a_selection(
    tmp_path,
):
    # Repair pass twenty three, red team family 71,
    # form 71b. The augmented seat resolves its
    # target name through the same instance
    # resolution, so a name bound to a selection of
    # an accumulator instance out of a literal
    # performs the dunder isub dispatch the
    # augmented counting gathers, on a value the
    # resolution never named. The widened instance
    # resolution hands the augmented seat the
    # selected instance on the same terms as the
    # call seat.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _AccumSub:
            def __isub__(self, other):
                _install_shadow()
                return self


        _acc = (_AccumSub(),)[0]


        _acc -= 1
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_keeps_a_helper_beside_a_quiet_function_called_through_an_unpacking_loop_target_name(
    tmp_path,
):
    # Repair pass twenty three, the boundary control
    # beside family 67. The same unpacking header
    # binds a quiet module level function as a
    # component of its element, and a call after the
    # loop bears the unpacking name, the same shape
    # as form 67a with a function whose body calls
    # nothing and assigns nothing under a global
    # declaration. The element reading now pairs the
    # name with its component and the call is counted
    # into the quiet body, but the counting this pass
    # adds refuses nothing here and the faithful
    # helper keeps its derivation beside the reader.
    # The control marks the family turning on the
    # component the target binds performing the
    # rewrite, the repair widening the resolution
    # while keeping the refusal keyed on what the
    # resolved body does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _quiet():
            return None


        for _fn, _other in [(_quiet, None)]:
            pass


        _fn()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_an_iter_returning_a_distinct_iterator_through_a_named_selection(
    tmp_path,
):
    # Repair pass twenty three, the boundary control
    # beside family 69. The same name mediated
    # selection stands here returning a distinct
    # iterator object out of the literal a local
    # name denotes, with a loud dunder next method
    # that never fires because the returned iterator
    # is a different object from the instance. The
    # selection reading now resolves the literal
    # behind the name and reads the selected
    # element, which is the distinct iterator and
    # not the instance, so the next method counting
    # stays silent and the faithful helper keeps its
    # derivation beside the reader. The control
    # marks the family turning on the value the
    # selection returns, the repair widening the
    # mediation while keeping the return value
    # ground fenced for values that are not the
    # instance itself.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterDistinct:
            def __iter__(self):
                pair = (iter([]),)
                return pair[0]

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterDistinct():
            pass
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_selection_whose_value_stands_as_a_walrus(
    tmp_path,
):
    # Repair pass twenty four, red team family 75,
    # form 75a. A class whose dunder iter method
    # binds a local name to the element a subscript
    # selects out of a literal the subscript reaches
    # through a walrus standing in its value
    # position, the walrus binding the literal to a
    # body name as it evaluates, and returns that
    # name is its own iterator by construction, so
    # the for statement after the candidate performs
    # the dunder next method of the same class,
    # whose body calls the installer. The selection
    # helper read the subscript's value as a literal
    # node or as a local name and nothing else, so
    # the literal standing behind the walrus went
    # unread, although the return passage admits a
    # walrus yielding the returned value standing
    # whole one clause earlier. The selection
    # reading now resolves the subscript's value
    # through the yielding forms the passage admits
    # at its other positions.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterWalrusSelectionValue:
            def __iter__(self):
                result = (pair := (self,))[0]
                return result

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterWalrusSelectionValue():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_selection_whose_value_stands_as_a_boolean_expression(
    tmp_path,
):
    # Repair pass twenty four, red team family 75,
    # form 75b. The same selection stands here with
    # the literal as an operand of a boolean
    # expression in the subscript's value position,
    # the expression yielding the literal the
    # selection stands on. The selection helper
    # read neither operand, although the return
    # passage admits a boolean expression yielding
    # the returned value through one of its
    # operands. The selection reading now follows
    # the operands of such an expression to the
    # literals they denote.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterBooleanSelectionValue:
            def __iter__(self):
                return ((self,) or ())[0]

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterBooleanSelectionValue():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_selection_whose_value_stands_as_a_conditional_expression(
    tmp_path,
):
    # Repair pass twenty four, red team family 75,
    # form 75c. The same selection stands here with
    # the literal in an arm of a conditional
    # expression in the subscript's value position.
    # The selection helper read neither arm,
    # although the return passage admits a
    # conditional expression yielding the returned
    # value through an arm. The selection reading
    # now follows both arms of such an expression
    # to the literals they denote, over reading an
    # unfoldable condition in the safe direction.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterConditionalSelectionValue:
            def __iter__(self):
                return ((self,) if True else ())[0]

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterConditionalSelectionValue():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_selection_whose_value_stands_as_a_nested_subscript(
    tmp_path,
):
    # Repair pass twenty four, red team family 75,
    # form 75d. The same selection stands here with
    # the literal behind an inner subscript in the
    # value position, the nesting the module's own
    # selection reading composes when it states
    # what a subscript evaluates to. The selection
    # helper read no subscript standing in that
    # position, so the element the inner selection
    # yields went unread. The selection reading now
    # follows an inner subscript through its own
    # selection on the same index terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterNestedSelectionValue:
            def __iter__(self):
                return ((self,),)[0][0]

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterNestedSelectionValue():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_descriptor_placed_behind_a_nested_selection(
    tmp_path,
):
    # Repair pass twenty four, red team family 76,
    # form 76a. A descriptor instance standing
    # behind a nested subscript selection in a
    # created class body places in the namespace
    # the body builds, so the class statement after
    # the candidate runs its dunder set name
    # method, whose body calls the installer. The
    # placement reading resolved a subscript through
    # the literal sequences reading alone, which
    # composes no nesting, while the selection
    # reading beside it has composed a subscript
    # standing on a subscript at the execution seat
    # since pass twenty three. The placement
    # reading now routes its subscript branch
    # through the selection reading's element
    # resolution on the same index terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        class _DescriptorMarked:
            marker = ((_ShadowDescriptor(),),)[0][0]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_descriptor_placed_by_a_name_bound_to_a_nested_selection(
    tmp_path,
):
    # Repair pass twenty four, red team family 76,
    # form 76b. The same placement stands here
    # through a module level name bound to the
    # nested selection, the class body placing the
    # instance by that name. The name branch of the
    # placement reading handed the bound subscript
    # to the same branch, which resolved nothing
    # behind the nesting. The composed selection
    # resolution now stands behind the name on the
    # same terms as behind the assignment itself.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        _held = ((_ShadowDescriptor(),),)[0][0]


        class _DescriptorMarked:
            marker = _held
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_call_naming_an_instance_bound_to_a_nested_selection(
    tmp_path,
):
    # Repair pass twenty four, red team family 76,
    # form 76c. A name bound to a nested subscript
    # selection of an instantiation denotes that
    # instance by construction, and a call by that
    # name after the candidate runs the instance's
    # dunder call method, whose body calls the
    # installer. The instance resolution read a
    # subscript binding value through the literal
    # sequences reading alone and resolved nothing
    # behind the nesting, although its own passage
    # states it resolves on the terms the placement
    # reading resolves a placed name by. The
    # instance resolution now reads a subscript
    # binding value through the composed selection
    # reading on the same index terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Runner:
            def __call__(self):
                _install_shadow()


        _acc = ((_Runner(),),)[0][0]


        _acc()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_augmented_assignments_isub_method_on_an_instance_bound_to_a_nested_selection(
    tmp_path,
):
    # Repair pass twenty four, red team family 76,
    # form 76d. The same nested selection binding
    # stands here at an augmented assignment seat,
    # a subtractive augmented assignment on the
    # bound name performing the dunder isub method
    # of the instance's class, whose body calls the
    # installer. The augmented seat resolves its
    # target name through the instance resolution,
    # so the unread nesting silenced the dispatch
    # counting with the call counting. The composed
    # selection resolution now feeds both seats.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Accumulator:
            def __isub__(self, other):
                _install_shadow()
                return self


        _acc = ((_Accumulator(),),)[0][0]


        _acc -= 1
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_enter_method_behind_a_manager_bound_to_a_nested_selection(
    tmp_path,
):
    # Repair pass twenty four, red team family 76,
    # form 76e. A manager bound to a nested
    # subscript selection of an instantiation
    # stands in a with statement after the
    # candidate, which performs the dunder enter
    # method of the manager's class, whose body
    # calls the installer. The manager position
    # resolved a subscript through the literal
    # sequences reading alone and named no class
    # behind the nesting. The manager reading now
    # routes its subscript branch through the
    # composed selection reading on the same index
    # terms as the placement reading.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _Manager:
            def __enter__(self):
                _install_shadow()
                return self

            def __exit__(self, *exc):
                return False


        _mgr = ((_Manager(),),)[0][0]


        with _mgr:
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_behind_an_inner_selection_standing_on_a_conditional_expression(
    tmp_path,
):
    # Repair pass twenty four, red team family 77,
    # form 77a. A subscript whose value position
    # itself stands as a subscript selecting a class
    # out of a literal performs the dunder class
    # getitem method of that class, and here the
    # literal the inner selection selects out of
    # stands in the inner subscript's value position
    # as an arm of a conditional expression, a form
    # the reach passage names as resolving at a
    # value position. The selection reading fed the
    # values it stands on through the literal
    # sequences reading, which followed no such
    # form, so the composition resolved nothing.
    # The literal sequences reading now yields the
    # literals an arm of a conditional expression
    # carries on the same terms as a literal
    # standing in the position itself.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _GIBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        class _GIOther:
            pass


        _selected = ((_GIBase,) if True else (_GIOther,))[0][int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_behind_an_inner_selection_standing_on_a_boolean_expression(
    tmp_path,
):
    # Repair pass twenty four, red team family 77,
    # form 77b. The same inner selection stands
    # here on a boolean expression whose first
    # operand is the literal the selection selects
    # out of. The literal sequences reading
    # followed neither operand, although the reach
    # passage names a boolean expression as
    # resolving to the classes of its operands at a
    # value position. The reading now yields the
    # literals an operand of such an expression
    # carries on the same terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _GIBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        class _GIOther:
            pass


        _selected = ((_GIBase,) or (_GIOther,))[0][int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_behind_an_inner_selection_standing_on_a_walrus_expression(
    tmp_path,
):
    # Repair pass twenty four, red team family 77,
    # form 77c. The same inner selection stands
    # here on a walrus expression yielding the
    # literal it selects out of. The literal
    # sequences reading followed no walrus, although
    # the reach passage names a walrus expression
    # as resolving to the class of the value it
    # yields at a value position. The reading now
    # yields the literal the value such an
    # expression binds carries on the same terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _GIBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        _selected = (pair := (_GIBase,))[0][int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_keeps_a_helper_beside_a_quiet_instance_called_through_a_nested_selection(
    tmp_path,
):
    # Repair pass twenty four, the boundary control
    # beside family 76. The same nested selection
    # binds an instance whose dunder call method
    # calls nothing and assigns nothing under a
    # global declaration, and a call after the
    # candidate bears the bound name, the same shape
    # as form 76c with a quiet class standing behind
    # the nesting. The composed selection resolution
    # now names the instance's class and the call is
    # counted into the quiet body, but the counting
    # this pass adds refuses nothing here and the
    # faithful helper keeps its derivation beside
    # the reader. The control marks the family
    # turning on the resolved instance's method
    # performing the rewrite, the repair widening
    # the resolution while keeping the refusal keyed
    # on what the resolved body does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _QuietRunner:
            def __call__(self):
                return None


        _acc = ((_QuietRunner(),),)[0][0]


        _acc()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_an_iter_returning_a_distinct_iterator_through_a_walrus_selection(
    tmp_path,
):
    # Repair pass twenty four, the boundary control
    # beside family 75. The same walrus mediated
    # selection stands here returning a distinct
    # iterator object out of the literal the walrus
    # yields, with a loud dunder next method that
    # never fires because the returned iterator is
    # a different object from the instance. The
    # selection reading now resolves the literal
    # behind the walrus and reads the selected
    # element, which is the distinct iterator and
    # not the instance, so the next method counting
    # stays silent and the faithful helper keeps
    # its derivation beside the reader. The control
    # marks the family turning on the value the
    # selection returns, the repair widening the
    # mediation while keeping the return value
    # ground fenced for values that are not the
    # instance itself.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterDistinctWalrus:
            def __iter__(self):
                result = (pair := (iter([]),))[0]
                return result

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterDistinctWalrus():
            pass
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_descriptor_placed_by_a_selection_out_of_a_name_bound_to_a_selection(
    tmp_path,
):
    # Repair pass twenty five, red team family 79,
    # form 79a. A class body places an element a
    # subscript selects out of a name, and the name
    # is itself bound to a subscript selecting a
    # tuple out of a literal of tuples, so the
    # placed element stands two selections from the
    # literal. The literal sequences reading
    # followed a name to a literal and read a name
    # bound to a subscript as carrying nothing, so
    # the selection out of that name resolved to no
    # elements at any seat. The reading now follows
    # a name bound to a subscript through the
    # selection reading's own resolution, and a
    # name denoting the result of a selection
    # carries the elements that selection selects.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        _pair = ((_ShadowDescriptor(),),)[0]


        class _DescriptorMarked:
            marker = _pair[0]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_set_name_hook_on_a_descriptor_placed_by_a_name_bound_to_a_selection_out_of_a_name_bound_to_a_selection(
    tmp_path,
):
    # Repair pass twenty five, red team family 79,
    # form 79b. The placed element stands behind a
    # second name bound to the selection out of the
    # name bound to a selection, the chain running
    # name to selection to name to selection to
    # literal. The literal sequences reading read
    # the first name bound to a subscript as
    # carrying nothing, so every name past it
    # resolved to no elements. The reading now
    # follows the chain through the selection
    # reading's own resolution at each link.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDescriptor:
            def __set_name__(self, owner, name):
                _install_shadow()


        _pair = ((_ShadowDescriptor(),),)[0]

        _held = _pair[0]


        class _DescriptorMarked:
            marker = _held
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_call_naming_an_instance_bound_to_a_selection_out_of_a_name_bound_to_a_selection(
    tmp_path,
):
    # Repair pass twenty five, red team family 79,
    # form 79c. The called instance name is bound
    # to a selection out of a name bound to a
    # selection, the instance call seat resolving
    # the name through the selection readings. The
    # literal sequences reading read the name bound
    # to a subscript as carrying nothing, so the
    # instance resolved to no class and the call
    # counted nothing. The reading now carries the
    # selected elements through both selections.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowRunner:
            def __call__(self):
                _install_shadow()


        _pair = ((_ShadowRunner(),),)[0]

        _inst = _pair[0]

        _inst()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_augmented_assignments_isub_method_on_an_instance_bound_to_a_selection_out_of_a_name_bound_to_a_selection(
    tmp_path,
):
    # Repair pass twenty five, red team family 79,
    # form 79d. The augmented assignment's target
    # name is bound to a selection out of a name
    # bound to a selection, the augmented seat
    # resolving the target on the call locus
    # instance terms. The literal sequences reading
    # read the name bound to a subscript as
    # carrying nothing, so the target resolved to
    # no class and the in place method counted
    # nothing. The reading now carries the selected
    # elements through both selections.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowAccumulator:
            def __isub__(self, other):
                _install_shadow()
                return self


        _pair = ((_ShadowAccumulator(),),)[0]

        _acc = _pair[0]

        _acc -= 1
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_enter_method_behind_a_manager_bound_to_a_selection_out_of_a_name_bound_to_a_selection(
    tmp_path,
):
    # Repair pass twenty five, red team family 79,
    # form 79e. The with statement's manager name
    # is bound to a selection out of a name bound
    # to a selection, the manager seat resolving
    # the name through the selection readings. The
    # literal sequences reading read the name bound
    # to a subscript as carrying nothing, so the
    # manager resolved to no class and the enter
    # method counted nothing. The reading now
    # carries the selected elements through both
    # selections.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowManager:
            def __enter__(self):
                _install_shadow()
                return self

            def __exit__(self, *exc):
                return False


        _pair = ((_ShadowManager(),),)[0]

        _mgr = _pair[0]

        with _mgr:
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_enter_method_behind_a_manager_named_by_a_selection_out_of_a_name_bound_to_a_selection(
    tmp_path,
):
    # Repair pass twenty five, red team family 79,
    # form 79f. The selection out of the name bound
    # to a selection stands directly in the with
    # statement's manager position, with no
    # intermediate name at the seat itself. The
    # literal sequences reading read the name bound
    # to a subscript as carrying nothing, so the
    # selection in the position resolved to no
    # elements and the enter method counted
    # nothing. The reading now carries the selected
    # elements through the selection the position
    # performs and the selection the name denotes.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowManager:
            def __enter__(self):
                _install_shadow()
                return self

            def __exit__(self, *exc):
                return False


        _pair = ((_ShadowManager(),),)[0]

        with _pair[0]:
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_behind_a_selection_out_of_a_name_bound_to_a_selection(
    tmp_path,
):
    # Repair pass twenty five, red team family 79,
    # form 79g. The class getitem execution stands
    # on a selection out of a name bound to a
    # selection, the outer subscript's value
    # position resolving the class through the
    # selection readings. The literal sequences
    # reading read the name bound to a subscript as
    # carrying nothing, so the value position
    # resolved to no class and the getitem method
    # counted nothing. The reading now carries the
    # selected elements through both selections.
    # The denotation reading at the class turning
    # points keeps its width, so this widening
    # reaches the execution seat only.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        _pair = ((_ShadowBase,),)[0]

        _pair[0][int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_call_naming_an_instance_bound_to_a_conditional_expression(
    tmp_path,
):
    # Repair pass twenty five, red team family 80,
    # form 80a. The called instance name is bound
    # to a conditional expression whose arms both
    # instantiate the class. The instance
    # resolution followed a call, a name, and a
    # subscript standing in a binding and no
    # yielding bound form, while the placement
    # reading's name branch follows all three bound
    # forms and the instance passage states it
    # reads a name on the placement terms. The
    # resolution now follows bound conditional
    # expressions through their arms, bound boolean
    # expressions through their operands, and bound
    # walrus expressions through their values, on
    # the placement name branch's terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowRunner:
            def __call__(self):
                _install_shadow()


        _inst = _ShadowRunner() if True else _ShadowRunner()

        _inst()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_call_naming_an_instance_bound_to_a_boolean_expression(
    tmp_path,
):
    # Repair pass twenty five, red team family 80,
    # form 80b. The called instance name is bound
    # to a boolean expression whose first operand
    # instantiates the class. The instance
    # resolution followed no yielding bound form,
    # so the name resolved to no instance and the
    # call counted nothing. The resolution now
    # follows bound boolean expressions through
    # their operands on the placement name branch's
    # terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowRunner:
            def __call__(self):
                _install_shadow()


        _inst = _ShadowRunner() or _ShadowRunner()

        _inst()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_call_naming_an_instance_bound_to_a_walrus_expression(
    tmp_path,
):
    # Repair pass twenty five, red team family 80,
    # form 80c. The called instance name is bound
    # to a walrus expression yielding an
    # instantiation of the class. The instance
    # resolution followed no yielding bound form,
    # so the name resolved to no instance and the
    # call counted nothing. The resolution now
    # follows bound walrus expressions through
    # their values on the placement name branch's
    # terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowRunner:
            def __call__(self):
                _install_shadow()


        _inst = (held := _ShadowRunner())

        _inst()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_enter_method_behind_a_manager_bound_to_a_conditional_expression(
    tmp_path,
):
    # Repair pass twenty five, red team family 80,
    # form 80d. The with statement's manager name
    # is bound to a conditional expression whose
    # arms both instantiate the class, the manager
    # seat reading the name on the call locus
    # instance terms. The instance resolution
    # followed no yielding bound form, so the
    # manager name resolved to no instance and the
    # enter method counted nothing. The resolution
    # now follows bound conditional expressions
    # through their arms on the placement name
    # branch's terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowManager:
            def __enter__(self):
                _install_shadow()
                return self

            def __exit__(self, *exc):
                return False


        _mgr = _ShadowManager() if True else _ShadowManager()

        with _mgr:
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_augmented_assignments_isub_method_on_an_instance_bound_to_a_conditional_expression(
    tmp_path,
):
    # Repair pass twenty five, red team family 80,
    # form 80e. The augmented assignment's target
    # name is bound to a conditional expression
    # whose arms both instantiate the class, the
    # augmented seat reading the target on the call
    # locus instance terms. The instance resolution
    # followed no yielding bound form, so the
    # target resolved to no instance and the in
    # place method counted nothing. The resolution
    # now follows bound conditional expressions
    # through their arms on the placement name
    # branch's terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowAccumulator:
            def __isub__(self, other):
                _install_shadow()
                return self


        _acc = _ShadowAccumulator() if True else _ShadowAccumulator()

        _acc -= 1
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_call_naming_a_decorator_instance_bound_to_a_conditional_expression(
    tmp_path,
):
    # Repair pass twenty five, red team family 80,
    # form 80f. A bare name decorator after the
    # candidate is bound to a conditional
    # expression whose arms both instantiate a
    # class whose dunder call method performs the
    # rewrite, the decorator seat reading the name
    # on the call locus instance terms. The
    # instance resolution followed no yielding
    # bound form, so the decorator name resolved
    # to no instance and its call method counted
    # nothing. The resolution now follows bound
    # conditional expressions through their arms
    # on the placement name branch's terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowDecorator:
            def __call__(self, fn):
                _install_shadow()
                return fn


        _dec = _ShadowDecorator() if True else _ShadowDecorator()


        @_dec
        def _after():
            return None
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_selection_out_of_a_name_bound_to_a_boolean_expression(
    tmp_path,
):
    # Repair pass twenty five, red team family 81,
    # form 81a. The iter method binds a body local
    # name to a boolean expression yielding the
    # literal holding the instance and returns a
    # selection out of that name. The body's own
    # literal reading followed a body name to a
    # literal node or to a further name and nothing
    # else, although the selection helper follows
    # the same forms standing in the subscript
    # itself, so the name denoted no literal and
    # the return read as handing the iteration to
    # a value the counting cannot name. The reading
    # now follows bound conditional arms, boolean
    # operands, walrus values, and subscripts on
    # the selection helper's index terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterBoolBound:
            def __iter__(self):
                held = (self,) or ()
                return held[0]

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterBoolBound():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_selection_out_of_a_name_bound_to_a_conditional_expression(
    tmp_path,
):
    # Repair pass twenty five, red team family 81,
    # form 81b. The iter method binds a body local
    # name to a conditional expression one of whose
    # arms is the literal holding the instance and
    # returns a selection out of that name. The
    # body's own literal reading followed no bound
    # conditional, so the name denoted no literal
    # and the return read as a value the counting
    # cannot name. The reading now follows bound
    # conditional arms on the selection helper's
    # index terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterConditionalBound:
            def __iter__(self):
                held = (self,) if True else ()
                return held[0]

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterConditionalBound():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_selection_out_of_a_name_bound_to_an_inner_subscript(
    tmp_path,
):
    # Repair pass twenty five, red team family 81,
    # form 81c. The iter method binds a body local
    # name to an inner subscript selecting the
    # literal holding the instance out of a further
    # literal and returns a selection out of that
    # name. The body's own literal reading followed
    # no bound subscript, so the name denoted no
    # literal and the return read as a value the
    # counting cannot name. The reading now follows
    # bound subscripts on the selection helper's
    # index terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterSubscriptBound:
            def __iter__(self):
                held = ((self,),)[0]
                return held[0]

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterSubscriptBound():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_selection_out_of_a_name_bound_by_a_walrus_to_a_boolean_expression(
    tmp_path,
):
    # Repair pass twenty five, red team family 81,
    # form 81d. The iter method binds a body local
    # name by a walrus expression whose value is a
    # boolean expression yielding the literal
    # holding the instance and returns a selection
    # out of that name. The body's own literal
    # reading followed no bound walrus and no bound
    # boolean, so the name denoted no literal and
    # the return read as a value the counting
    # cannot name. The reading now follows bound
    # walrus values and the boolean operands they
    # yield on the selection helper's index terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterWalrusBound:
            def __iter__(self):
                (held := (self,) or ())
                return held[0]

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterWalrusBound():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_loop_target_over_a_name_bound_to_a_boolean_expression(
    tmp_path,
):
    # Repair pass twenty five, red team family 81,
    # form 81e. The iter method binds a body local
    # name to a boolean expression yielding the
    # literal holding the instance, walks that name
    # in a loop header, and returns the loop
    # target. The body's own literal reading
    # followed no bound boolean, so the name
    # denoted no literal, the header paired the
    # target with no element, and the return read
    # as a value the counting cannot name. The
    # reading now follows the bound form, so the
    # header reads the literal through the name on
    # the same terms.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterLoopBound:
            def __iter__(self):
                held = (self,) or ()
                for item in held:
                    pass
                return item

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterLoopBound():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_keeps_a_helper_beside_a_quiet_instance_bound_to_a_conditional_expression(
    tmp_path,
):
    # Repair pass twenty five, the boundary control
    # beside family 80. The same conditional binding
    # stands here on an instance whose dunder call
    # method calls nothing and assigns nothing under
    # a global declaration, and a call after the
    # candidate bears the bound name. The instance
    # resolution now follows the bound conditional
    # and names the instance's class, and the call
    # is counted into the quiet body, but the
    # counting this pass adds refuses nothing here
    # and the faithful helper keeps its derivation
    # beside the reader. The control marks the
    # family turning on the resolved instance's
    # method performing the rewrite, the repair
    # widening the resolution while keeping the
    # refusal keyed on what the resolved body does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _QuietRunner:
            def __call__(self):
                return None


        _inst = _QuietRunner() if True else _QuietRunner()

        _inst()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_a_quiet_instance_bound_to_a_selection_out_of_a_name_bound_to_a_selection(
    tmp_path,
):
    # Repair pass twenty five, the boundary control
    # beside family 79. The same chained selection
    # binds an instance whose dunder call method
    # calls nothing and assigns nothing under a
    # global declaration, and a call after the
    # candidate bears the name bound to the outer
    # selection. The literal sequences reading now
    # carries the selected elements through both
    # selections and the call is counted into the
    # quiet body, but the counting this pass adds
    # refuses nothing here and the faithful helper
    # keeps its derivation beside the reader. The
    # control marks the family turning on the
    # resolved instance's method performing the
    # rewrite, the repair widening the resolution
    # while keeping the refusal keyed on what the
    # resolved body does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _QuietRunner:
            def __call__(self):
                return None


        _pair = ((_QuietRunner(),),)[0]

        _inst = _pair[0]

        _inst()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_installer_called_through_a_name_bound_to_a_subscript_selecting_it_out_of_a_literal(
    tmp_path,
):
    # Repair pass twenty six, red team family 83,
    # form 83a. A plain assignment binds a name to a
    # subscript selecting the installer out of a
    # literal, and a module level call bearing that
    # name runs the installer exactly as a call
    # bearing its definition name does. The pass
    # twenty five reach queued a call for a bound
    # value only where the value stood as a plain
    # name or as a lambda, so the selected installer
    # never joined the reach, although the callee
    # passage states a call dispatches on the
    # callable the name denotes however the name
    # came to be bound to it and carries no closing
    # refusal. The bound callee expansion now
    # follows a bound subscript through the
    # selection reading, so the call counts against
    # the definition the selection yields.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        _fn = (_install_shadow,)[0]

        _fn()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_installer_called_through_a_name_bound_to_a_subscript_selecting_it_out_of_a_name_bound_to_a_literal(
    tmp_path,
):
    # Repair pass twenty six, red team family 83,
    # form 83b. The selection stands on a further
    # name the bindings resolve to the literal, so
    # the installer reaches the called name through
    # a name, a selection, and a literal. The pass
    # twenty five expansion read neither the
    # selection nor the name standing in it, so the
    # chain resolved to no callee. The expansion now
    # reads the subscript through the selection
    # reading on its own terms, which resolves a
    # name standing in the value position through
    # the bindings to the literal it denotes.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        _pair = (_install_shadow,)

        _fn = _pair[0]

        _fn()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_installer_called_through_a_name_bound_to_a_conditional_expression(
    tmp_path,
):
    # Repair pass twenty six, red team family 83,
    # form 83c. A conditional expression yields the
    # installer on its taken arm and a quiet
    # function on the other, and a call bearing the
    # bound name runs the installer. The pass twenty
    # five expansion queued no call for a bound
    # conditional, while the instance resolution
    # beside it followed bound conditional arms on
    # the placement terms. The expansion now follows
    # a bound conditional through both arms, over
    # reading an unfoldable condition in the safe
    # direction as the counting does at its other
    # loci, so the call counts against the installer
    # either arm denotes.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _quiet():
            return None


        _fn = _install_shadow if True else _quiet

        _fn()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_installer_called_through_a_name_bound_to_a_boolean_expression(
    tmp_path,
):
    # Repair pass twenty six, red team family 83,
    # form 83d. A boolean expression yields the
    # installer as its deciding operand, and a call
    # bearing the bound name runs it. The pass
    # twenty five expansion queued no call for a
    # bound boolean expression, while the readings
    # beside it followed bound boolean operands.
    # The expansion now follows a bound boolean
    # expression through its operands, so the call
    # counts against the installer an operand
    # denotes.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _quiet():
            return None


        _fn = _install_shadow or _quiet

        _fn()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_installer_called_through_a_name_bound_to_a_walrus_expression(
    tmp_path,
):
    # Repair pass twenty six, red team family 83,
    # form 83e. A walrus expression yields the
    # installer as the value it binds, and a call
    # bearing the bound name runs it. The pass
    # twenty five expansion queued no call for a
    # bound walrus expression, while the readings
    # beside it followed the value a bound walrus
    # yields. The expansion now follows a bound
    # walrus expression through its value, so the
    # call counts against the installer the value
    # denotes.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        _fn = (_held := _install_shadow)

        _fn()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_decorator_in_bare_name_form_bound_to_a_subscript_selecting_it_out_of_a_literal(
    tmp_path,
):
    # Repair pass twenty six, red team family 83,
    # form 83f. The decorator seat. A name bound to
    # a subscript selecting a decorator out of a
    # literal stands in bare name form on a decoy
    # definition, and the application runs the
    # decorator, whose body calls the installer.
    # The decorator passage counts a bare name
    # application as a call into the value the name
    # denotes, resolved as the reach resolves its
    # callees, so the application rides the callee
    # resolution itself. The pass twenty five
    # expansion queued no call for the selected
    # decorator, so its body never joined the reach.
    # The expansion now follows the bound subscript,
    # and the application counts against the
    # decorator the selection yields.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _loud_decorator(fn):
            _install_shadow()
            return fn


        _fn = (_loud_decorator,)[0]


        @_fn
        def _decoy():
            return None
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_installer_called_through_a_name_bound_to_a_lambda_selected_out_of_a_literal(
    tmp_path,
):
    # Repair pass twenty six, red team family 83,
    # form 83g. A subscript selects a lambda out of
    # a literal, the lambda body standing as a call
    # into the installer in the open, and a call
    # bearing the bound name runs the lambda. The
    # pass twenty five expansion read neither the
    # selection nor the lambda behind it, although
    # a name bound to a lambda standing in the
    # binding counted as a call into its body. The
    # expansion now follows the selection to the
    # lambda it yields, and the lambda counts on
    # the lambda binding terms, its body read where
    # it stands.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        _fn = ((lambda: _install_shadow()),)[0]

        _fn()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_keeps_a_helper_beside_a_call_through_a_name_bound_to_a_quiet_callable_selected_out_of_a_literal(
    tmp_path,
):
    # Repair pass twenty six, the boundary control
    # beside family 83. The same selection binding
    # as form 83a stands here on a function whose
    # body only returns, called through the bound
    # name after the candidate. The expansion now
    # follows the selection and the call is counted
    # into the quiet body, but it calls nothing and
    # assigns nothing under a global declaration, so
    # the counting this pass adds refuses nothing
    # here and the faithful helper keeps its
    # derivation beside the reader. The control
    # marks the family turning on the callable
    # behind the bound name performing the rewrite,
    # the repair widening the resolution while
    # keeping the refusal keyed on what the resolved
    # body does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _quiet_fn():
            return None


        _fn = (_quiet_fn,)[0]

        _fn()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_a_quiet_decorator_selected_out_of_a_literal(
    tmp_path,
):
    # Repair pass twenty six, the boundary control
    # beside form 83f. The same decorator selection
    # stands here on a decorator whose body only
    # returns the value it is handed, applied in
    # bare name form to a decoy definition after
    # the candidate. The expansion now follows the
    # selection and the application is counted into
    # the quiet body, but it calls nothing and
    # assigns nothing under a global declaration, so
    # the counting this pass adds refuses nothing
    # here and the faithful helper keeps its
    # derivation beside the reader. The control
    # marks the decorator form of the family turning
    # on the applied body performing the rewrite.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _quiet_decorator(fn):
            return fn


        _dec = (_quiet_decorator,)[0]


        @_dec
        def _decoy():
            return None
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_installer_called_through_a_name_bound_to_a_subscript_standing_on_a_loop_target_name_over_a_tuple(
    tmp_path,
):
    # Repair pass twenty seven, red team family 84,
    # form 84a. A loop binds a name to the tuple
    # holding the installer, a further name is bound
    # to a subscript standing on the loop name, and
    # a call bearing the further name runs the
    # installer. The pass twenty six selection
    # reading resolved a name standing in a
    # subscript's value position through the module
    # level bindings alone, and the binding a loop
    # target name carries there is the iterable its
    # header walks, so the subscript selected out of
    # the iterable one level above the element the
    # name denotes and the callee expansion resolved
    # nothing from the sequence it was handed,
    # although the reach passage states a loop
    # target name denotes an element at every seat
    # that resolves a name to the value it denotes,
    # closing with among them. The selection reading
    # now resolves a loop target name beside the
    # bindings route through the loop target element
    # reading, so the subscript selects out of the
    # element the name denotes on the placement
    # index terms and the call counts against the
    # installer.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        for _elt in [(_install_shadow,)]:
            pass


        _fn = _elt[0]

        _fn()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_installer_called_through_a_name_bound_to_a_subscript_standing_on_a_loop_target_name_over_a_list(
    tmp_path,
):
    # Repair pass twenty seven, red team family 84,
    # form 84b. The loop element stands as a list
    # holding the installer rather than a tuple, and
    # the same misresolution read the subscript as
    # selecting out of the iterable the header
    # walks. The selection reading now resolves the
    # loop name through the elements it denotes on
    # the same terms, so the selection yields the
    # installer out of the denoted list and the call
    # counts against it.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        for _elt in [[_install_shadow]]:
            pass


        _fn = _elt[0]

        _fn()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_call_method_of_an_instance_bound_by_a_subscript_standing_on_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty seven, red team family 84,
    # form 84c. The loop element is a tuple holding
    # an instance of a class whose dunder call
    # method calls the installer, and a name bound
    # to the subscript standing on the loop name is
    # called. The instance resolution is one of the
    # seats the reach passage names in terms, and it
    # resolves the bound subscript through the
    # selection reading, which handed it the tuple
    # whole at the pass twenty six head, in which it
    # found no instantiation. The selection now
    # yields the instance the element denotes, so
    # the call counts into the dunder call method.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowRunner:
            def __call__(self):
                _install_shadow()


        for _elt in [(_ShadowRunner(),)]:
            pass


        _inst = _elt[0]

        _inst()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_enter_method_of_a_manager_standing_as_a_subscript_on_a_loop_target_name_in_the_with_position(
    tmp_path,
):
    # Repair pass twenty seven, red team family 84,
    # form 84d. The subscript standing on the loop
    # name stands in the with position itself, its
    # element a context manager instance whose
    # dunder enter method calls the installer. The
    # operand resolution of the with statement is
    # one of the seats the reach passage names in
    # terms, and its manager reading resolves the
    # subscript through the selection reading, which
    # handed it the tuple whole and found no class
    # in it. The selection now yields the manager
    # instance the element denotes, so the enter
    # method is counted at the statement.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowManager:
            def __enter__(self):
                _install_shadow()
                return self

            def __exit__(self, *exc):
                return False


        for _elt in [(_ShadowManager(),)]:
            pass


        with _elt[0]:
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_enter_method_of_a_manager_bound_by_a_subscript_standing_on_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty seven, red team family 84,
    # form 84e. The manager reaches the with
    # statement through a name bound to the
    # subscript standing on the loop name, so the
    # instance resolution the manager position
    # consults reads the bound selection through the
    # same misresolving selection reading and found
    # no instance in the tuple it was handed. The
    # selection now yields the instance the element
    # denotes, so the enter method is counted.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowManager:
            def __enter__(self):
                _install_shadow()
                return self

            def __exit__(self, *exc):
                return False


        for _elt in [(_ShadowManager(),)]:
            pass


        _mgr = _elt[0]

        with _mgr:
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_method_of_a_class_reached_by_a_subscript_standing_on_a_selection_on_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty seven, red team family 84,
    # form 84f. The loop element is a tuple holding
    # a base class whose dunder class getitem method
    # calls the installer, and the appended code
    # evaluates a subscript standing on a selection
    # on the loop name. The execution counting
    # resolves the inner selection through the
    # selection reading, which handed it the tuple
    # whole and found no class name in it, so the
    # getitem went uncounted. The selection now
    # yields the class the element denotes, so the
    # method is counted wherever the reach reads the
    # subscript as an execution.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        for _elt in [(_ShadowBase,)]:
            pass


        _elt[0][int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_isub_method_of_an_instance_bound_by_a_subscript_standing_on_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty seven, red team family 84,
    # form 84g. The loop element is a tuple holding
    # an accumulator instance whose dunder isub
    # method calls the installer, a name is bound to
    # the subscript standing on the loop name, and
    # the name is the target of a subtractive
    # augmented assignment. The augmented counting
    # resolves its target through the instance
    # resolution, a seat the reach passage names in
    # terms, which read the bound selection through
    # the misresolving selection reading and found
    # no instance. The selection now yields the
    # instance the element denotes, so the dispatch
    # of the operation is counted.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowAccumulator:
            def __isub__(self, other):
                _install_shadow()
                return self


        for _elt in [(_ShadowAccumulator(),)]:
            pass


        _acc = _elt[0]

        _acc -= 1
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_a_decorator_called_through_a_name_bound_to_a_subscript_standing_on_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty seven, red team family 84,
    # form 84h. The loop element is a tuple holding
    # a loud decorator function, a name is bound to
    # the subscript standing on the loop name, and
    # the name stands in bare name form on a decoy
    # definition. The decorator application counts
    # through the bound callee expansion, a seat the
    # reach passage names in terms, which read the
    # bound selection through the misresolving
    # selection reading and queued no callee for the
    # tuple it was handed. The selection now yields
    # the decorator the element denotes, so the
    # application counts against it.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _loud_decorator(fn):
            _install_shadow()
            return fn


        for _elt in [(_loud_decorator,)]:
            pass


        _dec = _elt[0]


        @_dec
        def _decoy():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_selection_out_of_a_name_bound_to_a_subscript_selecting_a_name_bound_to_the_literal(
    tmp_path,
):
    # Repair pass twenty seven, red team family 85,
    # form 85a. The iter method binds a name to the
    # tuple holding its first parameter, binds a
    # further name to a subscript selecting that
    # name out of a literal holding it, and returns
    # a selection out of the further name. The pass
    # twenty six selection helper kept only sequence
    # nodes among the elements a selection returned
    # and dropped the selected name where it stood,
    # so the further name denoted no literal although
    # the selection yields in the open the name the
    # body binds to the literal, and the self return
    # passage counts a bound value's yield through
    # the body's own binding on the same terms. The
    # helper now follows a selected element standing
    # as a name through the body's own literal
    # reading, so the selection yields the literal
    # the name denotes and the return counts as
    # returning the instance itself.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterSelectionBoundName:
            def __iter__(self):
                pair = (self,)
                held = (pair,)[0]
                return held[0]

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterSelectionBoundName():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_selection_behind_a_walrus_out_of_a_subscript_selecting_a_name_bound_to_the_literal(
    tmp_path,
):
    # Repair pass twenty seven, red team family 85,
    # form 85b. The selection stands in the return
    # itself behind a walrus, the return reading a
    # subscript on the value the walrus binds, which
    # is itself a subscript selecting the name bound
    # to the literal out of a literal holding it.
    # The helper dropped the selected name on the
    # same terms as form 85a, so the walrus value
    # denoted no literal and the return read as a
    # value the counting cannot name. The helper now
    # follows the selected name through the body's
    # own literal reading, so the return counts as
    # returning the instance itself.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterWalrusSelection:
            def __iter__(self):
                pair = (self,)
                return (held := (pair,)[0])[0]

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterWalrusSelection():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_selection_out_of_a_name_bound_to_a_conditional_selecting_a_name_bound_to_the_literal(
    tmp_path,
):
    # Repair pass twenty seven, red team family 85,
    # form 85c. The name the return selects out of
    # is bound to a conditional expression whose arms
    # each stand as the subscript selecting the name
    # bound to the literal out of a literal holding
    # it. The body's own literal reading followed
    # the bound conditional into the selection on
    # each arm, and the helper dropped the selected
    # name there on the same terms as form 85a, so
    # the name denoted no literal. The helper now
    # follows the selected name through the body's
    # own literal reading on either arm, so the
    # return counts as returning the instance
    # itself.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterConditionalSelectionBound:
            def __iter__(self):
                pair = (self,)
                held = (pair,)[0] if True else (pair,)[0]
                return held[0]

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterConditionalSelectionBound():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_next_method_behind_an_iter_returning_a_selection_out_of_a_name_bound_to_a_subscript_selecting_through_a_further_name_bound_to_the_literal(
    tmp_path,
):
    # Repair pass twenty seven, red team family 85,
    # form 85d. The name the return selects out of
    # is bound to a subscript standing on a further
    # body local name bound to the literal holding
    # the name bound to the literal holding the
    # instance, so the selection selects the inner
    # name out of a literal a further name denotes.
    # The helper read the further name to its
    # literal and then dropped the selected inner
    # name on the same terms as form 85a. The helper
    # now follows the selected name through the
    # body's own literal reading, so the selection
    # yields the literal the inner name denotes and
    # the return counts as returning the instance
    # itself.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterDenotedSelectionBound:
            def __iter__(self):
                pair = (self,)
                box = (pair,)
                held = box[0]
                return held[0]

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterDenotedSelectionBound():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_keeps_a_helper_beside_a_call_through_a_name_bound_to_a_subscript_standing_on_a_loop_target_name_selecting_a_quiet_callable(
    tmp_path,
):
    # Repair pass twenty seven, the boundary control
    # beside family 84. The same loop and selection
    # binding as form 84a stands here on a function
    # whose body only returns, called through the
    # name bound to the subscript standing on the
    # loop name after the candidate. The selection
    # reading now resolves the loop name through the
    # element it denotes and the call is counted
    # into the quiet body, but it calls nothing and
    # assigns nothing under a global declaration, so
    # the counting this pass adds refuses nothing
    # here and the faithful helper keeps its
    # derivation beside the reader. The control
    # marks the family turning on the callable
    # behind the selection performing the rewrite,
    # the repair widening the resolution while
    # keeping the refusal keyed on what the resolved
    # body does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _quiet():
            return None


        for _elt in [(_quiet,)]:
            pass


        _fn = _elt[0]

        _fn()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_an_iter_returning_a_distinct_iterator_through_a_selection_out_of_a_name_bound_to_a_subscript_selecting_a_name_bound_to_the_literal(
    tmp_path,
):
    # Repair pass twenty seven, the boundary control
    # beside family 85. The same selection binding
    # as form 85a stands here on a tuple holding a
    # distinct iterator rather than the instance
    # itself, the iter method returning a selection
    # out of the name bound to the subscript
    # selecting the name bound to that literal. The
    # helper now follows the selected name to the
    # literal it denotes, and the literal holds a
    # value that is not the instance, so the return
    # still reads as handing the iteration to a
    # value the counting cannot name as the instance
    # and the loud next method never joins the
    # reach, the faithful helper keeping its
    # derivation beside the reader. The control
    # marks the family turning on the selected name
    # denoting the instance tuple, not on the
    # selection shape alone, and keeps the fence
    # where a name whose yielded literal selects a
    # distinct value stands.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _IterDistinctSelectionBound:
            def __iter__(self):
                pair = (iter([]),)
                held = (pair,)[0]
                return held[0]

            def __next__(self):
                _install_shadow()
                raise StopIteration


        for _ in _IterDistinctSelectionBound():
            pass
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_installer_called_through_a_name_bound_to_a_subscript_standing_on_a_conditional_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty eight, red team family 86,
    # form 86a. A loop binds a name to the tuple
    # holding the installer, a further name is bound
    # to a subscript standing on a conditional
    # expression over the loop name, and the further
    # name is called. The pass twenty seven
    # selection reading consulted the loop target
    # element reading only where the subscript's
    # value stood as the loop name itself, so the
    # conditional handed the yielded name to the
    # literal sequences reading, whose name branch
    # read the module bindings alone and selected
    # out of the iterable the name walks, although
    # the literal sequences passage states the value
    # a yielding expression yields stands where the
    # expression stands. The resolution now stands
    # the loop target element reading beside the
    # bindings route at every name it reaches, so
    # the subscript selects out of the element the
    # name denotes and the call counts against the
    # installer.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        for _elt in [(_install_shadow,)]:
            pass


        _fn = (_elt if True else ())[0]

        _fn()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_installer_called_through_a_name_bound_to_a_subscript_standing_on_a_boolean_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty eight, red team family 86,
    # form 86b. The subscript stands on a boolean
    # expression over the loop name rather than a
    # conditional, and the operand handed the loop
    # name to the same bindings only name branch, so
    # the selection read the iterable one level too
    # high. The loop target element reading now
    # stands beside the bindings route at the
    # operand as at every reached name, so the
    # selection yields the installer the element
    # denotes and the call counts against it.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        for _elt in [(_install_shadow,)]:
            pass


        _fn = (_elt or ())[0]

        _fn()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_installer_called_through_a_name_bound_to_a_subscript_standing_on_a_walrus_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty eight, red team family 86,
    # form 86c. The subscript stands on a walrus
    # expression yielding the loop name, and the
    # value the walrus yields handed the name to the
    # same bindings only branch. The yielded name
    # now resolves beside that route through the
    # loop target element reading, so the subscript
    # selects the installer out of the denoted
    # element and the call counts against it.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        for _elt in [(_install_shadow,)]:
            pass


        _fn = (_held := _elt)[0]

        _fn()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_call_method_of_an_instance_bound_by_a_subscript_standing_on_a_boolean_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty eight, red team family 86,
    # form 86d. The loop element is a tuple holding
    # an instance of a class whose dunder call
    # method calls the installer, and a name bound
    # to a subscript standing on a boolean
    # expression over the loop name is called. The
    # instance resolution reads the bound subscript
    # through the selection reading, which handed
    # it the tuple whole at the pass twenty seven
    # head by the same bindings only route. The
    # selection now yields the instance the element
    # denotes, so the call counts into the dunder
    # call method.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowRunner:
            def __call__(self):
                _install_shadow()


        for _elt in [(_ShadowRunner(),)]:
            pass


        _inst = (_elt or ())[0]

        _inst()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_enter_method_of_a_manager_standing_as_a_subscript_on_a_conditional_expression_over_a_loop_target_name_in_the_with_position(
    tmp_path,
):
    # Repair pass twenty eight, red team family 86,
    # form 86e. The subscript standing on a
    # conditional expression over the loop name
    # stands in the with position itself, its
    # element a context manager instance whose
    # dunder enter method calls the installer. The
    # manager reading resolves the subscript through
    # the selection reading, which resolved the
    # yielded loop name through the bindings alone
    # and found no class in the iterable it was
    # handed. The selection now yields the manager
    # instance the element denotes, so the enter
    # method is counted at the statement.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowManager:
            def __enter__(self):
                _install_shadow()
                return self

            def __exit__(self, *exc):
                return False


        for _elt in [(_ShadowManager(),)]:
            pass


        with (_elt if True else ())[0]:
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_method_of_a_class_reached_through_a_name_bound_to_a_subscript_standing_on_a_walrus_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty eight, red team family 86,
    # form 86f. The loop element is a tuple holding
    # a base class whose dunder class getitem
    # method calls the installer, a name is bound
    # to a subscript standing on a walrus expression
    # over the loop name, and the appended code
    # evaluates that name subscripted by int. The
    # execution counting read the bound name
    # through the denotation alone, and the inner
    # selection itself stood misresolved by the
    # bindings only route behind it. The class
    # getitem reading now resolves a name bound to
    # a subscript whose own value position holds a
    # yielding form or a loop target name beside
    # the denotation, through the selection reading
    # on the same terms, so the name denotes the
    # class the selection yields and the method is
    # counted wherever the reach reads the subscript
    # as an execution, while a name bound to a
    # subscript standing on a literal still resolves
    # through the denotation alone at this seat.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        for _elt in [(_ShadowBase,)]:
            pass


        _sel = (_held := _elt)[0]

        _sel[int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_an_isub_method_of_an_instance_bound_by_a_subscript_standing_on_a_boolean_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty eight, red team family 86,
    # form 86g. The loop element is a tuple holding
    # an accumulator instance whose dunder isub
    # method calls the installer, a name is bound
    # to a subscript standing on a boolean
    # expression over the loop name, and the name
    # is the target of a subtractive augmented
    # assignment. The augmented counting resolves
    # its target through the instance resolution,
    # which read the bound selection through the
    # misresolving selection reading and found no
    # instance in the iterable it was handed. The
    # selection now yields the instance the element
    # denotes, so the dispatch of the operation is
    # counted.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowAccumulator:
            def __isub__(self, other):
                _install_shadow()
                return self


        for _elt in [(_ShadowAccumulator(),)]:
            pass


        _acc = (_elt or ())[0]

        _acc -= 1
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_a_decorator_called_through_a_name_bound_to_a_subscript_standing_on_a_conditional_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty eight, red team family 86,
    # form 86h. The loop element is a tuple holding
    # a loud decorator function, a name is bound to
    # a subscript standing on a conditional
    # expression over the loop name, and the name
    # stands in bare name form on a decoy
    # definition. The decorator application counts
    # through the bound callee expansion, which read
    # the bound selection through the misresolving
    # selection reading and queued no callee for the
    # iterable it was handed. The selection now
    # yields the decorator the element denotes, so
    # the application counts against it.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _loud_decorator(fn):
            _install_shadow()
            return fn


        for _elt in [(_loud_decorator,)]:
            pass


        _dec = (_elt if True else ())[0]


        @_dec
        def _decoy():
            pass
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_installer_called_through_a_name_bound_to_a_subscript_standing_on_a_name_bound_to_a_conditional_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty eight, red team family 86,
    # form 86i. A name is bound to the conditional
    # expression over the loop name itself, a
    # further name is bound to a subscript standing
    # on the bound name, and the further name is
    # called. The name branch read the bound name
    # through the module bindings alone, followed
    # the conditional to the loop name it yields,
    # and read that name through the bindings alone
    # in its turn, so the selection stood one level
    # too high behind two hops. The loop target
    # element reading now stands beside the bindings
    # route at the yielded name however the
    # resolution reaches it, so the subscript
    # selects the installer out of the denoted
    # element and the call counts against it.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        for _elt in [(_install_shadow,)]:
            pass


        _held = _elt if True else ()

        _fn = _held[0]

        _fn()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_by_an_installer_called_through_a_name_bound_to_a_subscript_standing_on_a_name_bound_to_a_walrus_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty eight, red team family 86,
    # form 86k. A name is bound to a walrus
    # expression yielding the loop name, a further
    # name is bound to a subscript standing on the
    # bound name, and the further name is called.
    # The walrus value handed the loop name to the
    # same bindings only branch behind the bound
    # name, so the selection read the iterable one
    # level too high. The yielded name now resolves
    # through the loop target element reading beside
    # that route, so the subscript selects the
    # installer out of the denoted element and the
    # call counts against it.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        for _elt in [(_install_shadow,)]:
            pass


        _held = (_h := _elt)

        _fn = _held[0]

        _fn()
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_keeps_a_helper_beside_a_call_through_a_name_bound_to_a_subscript_standing_on_a_conditional_expression_over_a_loop_target_name_selecting_a_quiet_callable(
    tmp_path,
):
    # Repair pass twenty eight, the boundary control
    # beside family 86 at the call seat. The same
    # loop and yielding selection binding as form
    # 86a stands here on a function whose body only
    # returns, called through the name bound to the
    # subscript standing on the conditional
    # expression over the loop name after the
    # candidate. The selection reading now resolves
    # the yielded loop name through the element it
    # denotes and the call is counted into the quiet
    # body, but it calls nothing and assigns nothing
    # under a global declaration, so the counting
    # this pass adds refuses nothing here and the
    # faithful helper keeps its derivation beside
    # the reader. The control marks the family
    # turning on the callable behind the selection
    # performing the rewrite, the repair widening
    # the resolution while keeping the refusal keyed
    # on what the resolved body does.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        def _quiet():
            return None


        for _elt in [(_quiet,)]:
            pass


        _fn = (_elt if True else ())[0]

        _fn()
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_a_manager_standing_as_a_subscript_on_a_conditional_expression_over_a_loop_target_name_selecting_a_quiet_manager_in_the_with_position(
    tmp_path,
):
    # Repair pass twenty eight, the boundary control
    # beside family 86 at the with seat. The same
    # subscript standing on a conditional expression
    # over the loop name as form 86e stands here on
    # a context manager whose dunder enter method
    # only returns, standing in the with position
    # itself after the candidate. The selection
    # reading now resolves the yielded loop name
    # through the element it denotes and the enter
    # method is counted at the statement, but it
    # calls nothing and assigns nothing under a
    # global declaration, so the counting this pass
    # adds refuses nothing here and the faithful
    # helper keeps its derivation beside the reader.
    # The control marks the family turning on the
    # manager behind the selection performing the
    # rewrite, on the same terms as the call seat
    # control beside it.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _QuietManager:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False


        for _elt in [(_QuietManager(),)]:
            pass


        with (_elt if True else ())[0]:
            pass
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_method_of_a_class_reached_through_a_name_bound_to_a_subscript_standing_on_a_name_bound_to_a_conditional_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty nine, red team family 87,
    # form 87a. The loop element is a tuple holding
    # a base class whose dunder class getitem
    # method calls the installer, a first name is
    # bound to a conditional expression over the
    # loop name, a second name is bound to a
    # subscript standing on the first name, and the
    # appended code evaluates the second name
    # subscripted by int. The pass twenty eight
    # name branch inspected the syntactic category
    # of the subscript's base, and the base here is
    # a plain name, so the branch never fired
    # although the selection reading resolves the
    # subscript itself. The branch now qualifies a
    # base standing as a name bound to a yielding
    # form, the yielded loop target name standing
    # in the value position on the yielding
    # principle, so the selection the name denotes
    # is read on the same terms and the method is
    # counted, while a name bound to a subscript
    # standing on a literal still resolves through
    # the denotation alone at this seat.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        for _elt in [(_ShadowBase,)]:
            pass


        _held = _elt if True else ()

        _sel = _held[0]

        _sel[int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_method_of_a_class_reached_through_a_name_bound_to_a_subscript_standing_on_a_name_bound_to_a_boolean_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty nine, red team family 87,
    # form 87b. The loop element is a tuple holding
    # a base class whose dunder class getitem
    # method calls the installer, a first name is
    # bound to a boolean expression over the loop
    # name, a second name is bound to a subscript
    # standing on the first name, and the appended
    # code evaluates the second name subscripted by
    # int. The base of the qualifying subscript is
    # a plain name bound to a yielding form, so the
    # pass twenty eight trigger, which inspected
    # the category of the base itself, never fired.
    # The branch now qualifies a base standing as
    # a name bound to a yielding form on the same
    # terms as form 87a, and the method is counted.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        for _elt in [(_ShadowBase,)]:
            pass


        _held = _elt or ()

        _sel = _held[0]

        _sel[int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_method_of_a_class_reached_through_a_name_bound_to_a_subscript_standing_on_a_name_bound_to_a_walrus_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty nine, red team family 87,
    # form 87c. The loop element is a tuple holding
    # a base class whose dunder class getitem
    # method calls the installer, a first name is
    # bound to a walrus expression yielding the
    # loop name, a second name is bound to a
    # subscript standing on the first name, and the
    # appended code evaluates the second name
    # subscripted by int. The base of the
    # qualifying subscript is a plain name bound to
    # a yielding form, so the pass twenty eight
    # trigger never fired. The branch now
    # qualifies a base standing as a name bound to
    # a yielding form on the same terms as form
    # 87a, and the method is counted.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        for _elt in [(_ShadowBase,)]:
            pass


        _held = (held := _elt)

        _sel = _held[0]

        _sel[int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_method_of_a_class_reached_through_a_name_bound_to_a_conditional_expression_over_a_name_bound_to_a_subscript_standing_on_a_walrus_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty nine, red team family 87,
    # form 87d. The loop element is a tuple holding
    # a base class whose dunder class getitem
    # method calls the installer, a first name is
    # bound to a subscript standing on a walrus
    # expression over the loop name, a second name
    # is bound to a conditional expression over the
    # first name, and the appended code evaluates
    # the second name subscripted by int. The pass
    # twenty eight name branch inspected the
    # syntactic category of the outer name's
    # binding, and the binding here is a yielding
    # form rather than the qualifying subscript
    # itself, so the branch never fired although
    # the value the form yields is the very name
    # the branch resolves standing unmediated. The
    # branch now follows a name bound through a
    # yielding form to the value the form yields, a
    # name so yielded resolved on the same terms in
    # turn, so the method is counted, while a name
    # bound by plain assignment to the qualifying
    # name itself, with no yielding form between it
    # and the subscript behind it, still resolves
    # through the denotation alone at this seat.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        for _elt in [(_ShadowBase,)]:
            pass


        _sel0 = (held := _elt)[0]

        _sel = _sel0 if True else _sel0

        _sel[int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_method_of_a_class_reached_through_a_name_bound_to_a_walrus_expression_over_a_name_bound_to_a_subscript_standing_on_a_walrus_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty nine, red team family 87,
    # form 87e. The loop element is a tuple holding
    # a base class whose dunder class getitem
    # method calls the installer, a first name is
    # bound to a subscript standing on a walrus
    # expression over the loop name, a second name
    # is bound to a walrus expression yielding the
    # first name, and the appended code evaluates
    # the second name subscripted by int. The outer
    # name's binding is a yielding form rather than
    # the qualifying subscript itself, so the pass
    # twenty eight trigger never fired. The branch
    # now follows a name bound through a yielding
    # form to the value the form yields on the same
    # terms as form 87d, and the method is counted.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        for _elt in [(_ShadowBase,)]:
            pass


        _sel0 = (held := _elt)[0]

        _sel = (held := _sel0)

        _sel[int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_method_of_a_class_reached_through_a_name_bound_to_a_boolean_expression_over_a_name_bound_to_a_subscript_standing_on_a_walrus_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty nine, red team family 87,
    # form 87f. The loop element is a tuple holding
    # a base class whose dunder class getitem
    # method calls the installer, a first name is
    # bound to a subscript standing on a walrus
    # expression over the loop name, a second name
    # is bound to a boolean expression over the
    # first name, and the appended code evaluates
    # the second name subscripted by int. The outer
    # name's binding is a yielding form rather than
    # the qualifying subscript itself, so the pass
    # twenty eight trigger never fired. The branch
    # now follows a name bound through a yielding
    # form to the value the form yields on the same
    # terms as form 87d, and the method is counted.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        for _elt in [(_ShadowBase,)]:
            pass


        _sel0 = (held := _elt)[0]

        _sel = _sel0 or _sel0

        _sel[int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_keeps_a_helper_beside_a_quiet_class_reached_through_a_name_bound_to_a_subscript_standing_on_a_name_bound_to_a_conditional_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass twenty nine, the boundary control
    # beside family 87 at the class getitem seat.
    # The same inner hop shape as form 87a stands
    # here on a class whose dunder class getitem
    # method only returns the class, reached
    # through a name bound to a subscript standing
    # on a name bound to a conditional expression
    # over the loop name. The widened branch now
    # resolves the name to the class the selection
    # yields and the method is counted at the
    # statement, but it calls nothing and assigns
    # nothing under a global declaration, so the
    # counting this pass adds refuses nothing here
    # and the faithful helper keeps its derivation
    # beside the reader. The control marks the
    # family turning on the method behind the
    # resolution performing the rewrite.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _QuietBase:
            @classmethod
            def __class_getitem__(cls, item):
                return cls


        for _elt in [(_QuietBase,)]:
            pass


        _held = _elt if True else ()

        _sel = _held[0]

        _sel[int]
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_a_class_getitem_method_reached_through_a_name_bound_to_a_subscript_standing_on_a_literal(
    tmp_path,
):
    # Repair pass twenty nine, the fence control
    # beside family 87 at the class getitem seat.
    # A name is bound to a subscript standing on a
    # literal holding a base class whose dunder
    # class getitem method calls the installer, and
    # the appended code evaluates the name
    # subscripted by int, so the method really runs
    # at runtime. The seat resolves the name
    # through the denotation alone where the
    # subscript it is bound to stands on a literal,
    # the fence the pass twenty eight text states
    # in terms and family 78 stands on, so the
    # counting names no class here and the faithful
    # helper keeps its derivation beside the reader.
    # The control is pinned at this pass because
    # the widening beside it follows yielding forms
    # on both sides of the qualifying subscript,
    # and the fence has to be seen holding at
    # exactly the width the shipped text states.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        _sel = (_ShadowBase,)[0]

        _sel[int]
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_method_of_a_class_reached_through_a_name_bound_by_plain_assignment_to_a_name_bound_to_a_conditional_expression_over_a_name_bound_to_a_subscript_standing_on_a_walrus_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass thirty, red team family 88, form
    # 88a. The loop element is a tuple holding a
    # base class whose dunder class getitem method
    # calls the installer, a first name is bound to
    # a subscript standing on a walrus expression
    # over the loop name, a second name is bound to
    # a conditional expression over the first name,
    # a third name is bound by plain assignment to
    # the second name, and the appended code
    # evaluates the third name subscripted by int.
    # The pass twenty nine entry dispatch followed
    # only a bound value standing as the subscript
    # itself or as a yielding form, so the plain
    # assignment in front of the conditional never
    # entered the follow, although the follow
    # itself resolves a yielded name through its
    # plain bindings once entered. The branch now
    # follows a plain name hop at the entry on the
    # fence sentence's own test, a yielding form
    # standing anywhere between the name and the
    # subscript behind it, so the method is
    # counted, while a name bound by plain
    # assignment to the qualifying name itself,
    # with no yielding form between it and the
    # subscript, still resolves through the
    # denotation alone at this seat.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        for _elt in [(_ShadowBase,)]:
            pass


        _sel0 = (held := _elt)[0]

        _sel1 = _sel0 if True else _sel0

        _sel = _sel1

        _sel[int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_method_of_a_class_reached_through_a_name_bound_by_plain_assignment_to_a_name_bound_to_a_boolean_expression_over_a_name_bound_to_a_subscript_standing_on_a_walrus_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass thirty, red team family 88, form
    # 88e. The same outer plain hop as form 88a
    # with the second name bound to a boolean
    # expression over the first name instead of a
    # conditional expression. The plain assignment
    # in front of the boolean never entered the
    # pass twenty nine follow for the same reason,
    # and the branch now follows the hop on the
    # same terms as form 88a, so the method is
    # counted.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        for _elt in [(_ShadowBase,)]:
            pass


        _sel0 = (held := _elt)[0]

        _sel1 = _sel0 or _sel0

        _sel = _sel1

        _sel[int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_method_of_a_class_reached_through_a_name_bound_to_a_subscript_standing_on_a_name_bound_by_plain_assignment_to_a_name_bound_to_a_conditional_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass thirty, red team family 88, form
    # 88c. The loop element is a tuple holding a
    # base class whose dunder class getitem method
    # calls the installer, a first name is bound to
    # a conditional expression over the loop name,
    # a second name is bound by plain assignment to
    # the first name, a third name is bound to a
    # subscript standing on the second name, and
    # the appended code evaluates the third name
    # subscripted by int. The pass twenty nine
    # qualification read the bindings of the base
    # name itself for a yielding form and stopped,
    # so the plain assignment behind the base never
    # reached the conditional the first name is
    # bound to, although the selection reading
    # resolves the subscript itself. The
    # qualification now follows a plain name hop
    # behind the base on the same test, a yielding
    # form standing anywhere between the base name
    # and the loop target name, so the method is
    # counted, while a base name bound by plain
    # assignment to the loop target name itself,
    # with no yielding form between it and that
    # name, still qualifies nothing at this seat.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        for _elt in [(_ShadowBase,)]:
            pass


        _held1 = _elt if True else ()

        _held2 = _held1

        _sel = _held2[0]

        _sel[int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_method_of_a_class_reached_through_a_name_bound_to_a_subscript_standing_on_a_name_bound_by_plain_assignment_to_a_name_bound_to_a_boolean_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass thirty, red team family 88, form
    # 88d. The same inner plain hop as form 88c
    # with the first name bound to a boolean
    # expression over the loop name instead of a
    # conditional expression. The qualification
    # stopped at the base name's own bindings for
    # the same reason, and it now follows the hop
    # on the same terms as form 88c, so the method
    # is counted.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        for _elt in [(_ShadowBase,)]:
            pass


        _held1 = _elt or ()

        _held2 = _held1

        _sel = _held2[0]

        _sel[int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_refuses_a_helper_rewritten_through_a_class_getitem_method_of_a_class_reached_through_a_name_bound_to_a_subscript_standing_on_a_name_bound_by_plain_assignment_to_a_name_bound_by_plain_assignment_to_a_name_bound_to_a_conditional_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass thirty, red team family 88, form
    # 88g. The same inner locus as form 88c with
    # two plain assignments behind the base, a
    # second name bound by plain assignment to the
    # first and a third name bound by plain
    # assignment to the second, the subscript
    # standing on the third name. The qualification
    # follows however many plain assignments
    # intervene on the same terms as form 88c, so
    # the method is counted.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        for _elt in [(_ShadowBase,)]:
            pass


        _held1 = _elt if True else ()

        _held2 = _held1

        _held3 = _held2

        _sel = _held3[0]

        _sel[int]
        """,
    )
    assert loaders == {"reader"}


def test_loader_derivation_keeps_a_helper_beside_a_class_getitem_method_reached_through_a_name_bound_by_plain_assignment_to_a_name_bound_to_a_subscript_standing_on_a_walrus_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass thirty, the fence control beside
    # family 88 at the class getitem seat. A first
    # name is bound to a subscript standing on a
    # walrus expression over the loop name, a
    # second name is bound by plain assignment to
    # the first name, and the appended code
    # evaluates the second name subscripted by int,
    # so the method really runs at runtime. No
    # yielding form stands between the second name
    # and the subscript behind it, the walrus
    # standing inside the subscript itself, so the
    # seat resolves the name through the denotation
    # alone on the fence sentence's own test, the
    # counting names no class here, and the
    # faithful helper keeps its derivation beside
    # the reader. The control is pinned at this
    # pass because the widening beside it follows
    # plain assignments at both loci, and the fence
    # has to be seen holding where no yielding form
    # stands in the chain outside the subscript
    # itself.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _ShadowBase:
            @classmethod
            def __class_getitem__(cls, item):
                _install_shadow()
                return cls


        for _elt in [(_ShadowBase,)]:
            pass


        _sel0 = (held := _elt)[0]

        _sel = _sel0

        _sel[int]
        """,
    )
    assert loaders == {"reader", "shadow_search"}


def test_loader_derivation_keeps_a_helper_beside_a_quiet_class_reached_through_a_name_bound_by_plain_assignment_to_a_name_bound_to_a_conditional_expression_over_a_name_bound_to_a_subscript_standing_on_a_walrus_expression_over_a_loop_target_name(
    tmp_path,
):
    # Repair pass thirty, the boundary control
    # beside family 88 at the class getitem seat.
    # The same outer plain hop chain as form 88a
    # stands here on a class whose dunder class
    # getitem method only returns the class,
    # reached through a name bound by plain
    # assignment to a name bound to a conditional
    # expression over the name bound to the
    # subscript. The widened branch now resolves
    # the name to the class the selection yields
    # and the method is counted at the statement,
    # but it calls nothing and assigns nothing
    # under a global declaration, so the counting
    # this pass adds refuses nothing here and the
    # faithful helper keeps its derivation beside
    # the reader. The control marks the family
    # turning on the method behind the resolution
    # performing the rewrite.
    loaders = _derived_loaders(
        tmp_path,
        """
        ROOT = None


        def reader(name):
            return (ROOT / name).read_bytes()


        def shadow_search(client, raw_response, name):
            return reader(name)


        def _install_shadow():
            global shadow_search
            shadow_search = lambda client, raw_response, name: None


        class _QuietBase:
            @classmethod
            def __class_getitem__(cls, item):
                return cls


        for _elt in [(_QuietBase,)]:
            pass


        _sel0 = (held := _elt)[0]

        _sel1 = _sel0 if True else _sel0

        _sel = _sel1

        _sel[int]
        """,
    )
    assert loaders == {"reader", "shadow_search"}
