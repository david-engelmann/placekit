"""Accounting tests for the Round 13 fixture corpus.

The manifest at tests/fixtures/coverage_manifest.json is the in repo
accounting of provenance and coverage. It is not a single source of
truth. Provenance was proven at build time by regenerating every
recorded fixture from its cassette and matching bytes and hashes.
These tests guard drift among the shipped claims afterwards, which
is a weaker property, and the manifest preamble states the known
limit of the guard in so many words.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
RECORDED = FIXTURES / "recorded"
SYNTHESIZED = FIXTURES / "synthesized"
MANIFEST = json.loads((FIXTURES / "coverage_manifest.json").read_text())
TABLE = (FIXTURES / "coverage_table.md").read_text()

TAXONOMY = (
    [f"P{i}" for i in range(1, 16)]
    + [f"H{i}" for i in range(1, 12)]
    + [f"V{i}" for i in range(1, 12)]
    + [f"A{i}" for i in range(1, 19)]
)
STATE_VOCABULARY = {
    "recorded in session 1",
    "recorded in session 2",
    "recorded in both",
    "synthesized candidate",
    "hunted and missed in R12",
    "still open",
}
RECORDED_STATES = {"recorded in session 1", "recorded in session 2", "recorded in both"}


def _module_sources(filename: str) -> dict[str, str]:
    """Map test function names to their source text in one module."""
    path = Path(__file__).parent / filename
    tree = ast.parse(path.read_text())
    lines = path.read_text().splitlines(keepends=True)
    sources = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            sources[node.name] = "".join(lines[node.lineno - 1 : node.end_lineno])
    return sources


RECORDED_SOURCES = _module_sources("test_recorded_corpus.py")
SYNTHESIZED_SOURCES = _module_sources("test_synthesized_corpus.py")


def _builder_module():
    """Load the corpus builder script as a module, for its spec list."""
    path = Path(__file__).parent.parent / "scripts" / "build_corpus_fixtures.py"
    spec = importlib.util.spec_from_file_location("build_corpus_fixtures", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _target_names(target) -> list:
    """The local names an assignment target binds."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Starred):
        return _target_names(target.value)
    if isinstance(target, (ast.Tuple, ast.List)):
        names = []
        for element in target.elts:
            names.extend(_target_names(element))
        return names
    return []


def _assignment_pairs(statements) -> list:
    """The target and value pairs of the assignments in a body.

    The pairs are read syntactically over the whole body,
    never entering a nested definition, whose assignments
    bind in its own scope. Plain and annotated assignments,
    walrus bindings, loop targets, and augmented assignments
    all gather. Augmented assignments gather because a name
    augmented from a value derives from that value in exactly
    the way a name assigned from it does, and both readings
    the pairs serve, the names a loop body derives from its
    target and the names a seed read target derives from, are
    over readings that must not miss a derivation, since a
    missed derivation can only refuse a shape, never credit
    one.
    """
    pairs = []

    def collect(node):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            return
        if isinstance(node, ast.Assign):
            targets = []
            for target in node.targets:
                targets.extend(_target_names(target))
            pairs.append((targets, node.value))
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            pairs.append((_target_names(node.target), node.value))
        elif isinstance(node, ast.AugAssign):
            pairs.append((_target_names(node.target), node.value))
        elif isinstance(node, ast.NamedExpr):
            pairs.append((_target_names(node.target), node.value))
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            pairs.append((_target_names(node.target), node.iter))
        for child in ast.iter_child_nodes(node):
            collect(child)

    for statement in statements:
        collect(statement)
    return pairs


def _symbolic_value(parameter: str) -> str:
    """The symbolic fixture name one parameter is bound to.

    Every parameter of a helper under a derivation proof is
    bound to its own symbolic name, distinct from every other
    parameter's, so credit earned through one parameter can
    never be mistaken for credit earned through another.
    """
    return f"the symbolic fixture name bound to parameter {parameter}"


_UNRESOLVED_READ = "the fixture name a disk read may load that the walk cannot resolve"


def _parameter_names(node) -> list:
    """The names of the parameters a helper can be handed.

    Positional and keyword parameters both count. A fixture
    name arriving through a starred or a double starred
    parameter cannot be tracked to the argument that carried
    it, so those parameters stand outside the proofs, and a
    helper that loads through one fails closed.
    """
    return [
        argument.arg
        for argument in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        )
    ]


def _parameter_index(node, parameter: str) -> int | None:
    """The positional index of a parameter, or None.

    The index counts the positional parameters, the ones a
    call can fill by position. A keyword only parameter has
    no position and returns None, so a call fills its slot by
    keyword alone.
    """
    positional = [argument.arg for argument in (*node.args.posonlyargs, *node.args.args)]
    if parameter in positional:
        return positional.index(parameter)
    return None


def _seed_name_parameter(node, source) -> str | None:
    """The parameter a disk reading helper provably reads through.

    The helper body is analysed once, with a distinct
    symbolic fixture name bound to each of its parameters and
    its disk reads standing as loading calls whose name
    argument is the read target, and the helper is a seed
    through a parameter only when the credited set of every
    path that completes the analysis is exactly that
    parameter's symbolic name. A reader that diverts the name
    it is handed to another fixture on one of its paths
    credits that fixture there, a reader that reads its
    argument as a decoy and returns a fixed name credits both
    on the one path, and a reader whose read target does not
    resolve to the handed parameter credits something the
    proof cannot name. A reader that reads another fixture
    on a path it abandons with a raise credits that fixture
    on a raised path, and the proof counts the raised paths
    beside the completing ones, so a raised path may hold
    credit for nothing but the symbolic name of the handed
    parameter. Each is refused, and the derivation fails
    closed without it.
    """
    segment = ast.get_source_segment(source, node)
    if segment is None:
        return None
    parameters = _parameter_names(node)
    bindings = {
        parameter: frozenset([_symbolic_value(parameter)]) for parameter in parameters
    }
    path_credits: list = []
    raised_credits: list = []
    _fixtures_a_test_loads(
        segment,
        set(),
        bindings,
        path_credits=path_credits,
        raised_credits=raised_credits,
        credit_reads=True,
    )
    if not path_credits:
        return None
    for parameter in parameters:
        symbolic = {_symbolic_value(parameter)}
        if all(credit == symbolic for credit in path_credits) and all(
            credit <= symbolic for credit in raised_credits
        ):
            return parameter
    return None


def _helper_name_parameter(node, source, slots) -> str | None:
    """The parameter a helper provably loads a fixture name from.

    The helper body is analysed once, with a distinct
    symbolic fixture name bound to each of its parameters,
    against the loader set as it stands, and only the
    argument sitting in the name slot of a loader call can
    earn credit, never an argument in any other slot. The
    helper passes a name through the parameter whose symbolic
    name is the credited set of every path that completes the
    analysis. A helper that drops its argument earns a fixed
    name on the paths that load, a helper that hands its
    argument over on only some of its paths earns a different
    set on the others, and a helper whose credit would arrive
    through an argument that carries no fixture name earns
    that argument's own symbolic name, which is the wrong one
    unless the parameter it names is the one the loader calls
    are fed in their name position. A helper that loads a
    fixed name on a path it abandons with a raise earns that
    name on a raised path, and the proof counts the raised
    paths beside the completing ones, so a raised path may
    hold credit for nothing but the symbolic name of the
    proven parameter. Each is refused.
    """
    segment = ast.get_source_segment(source, node)
    if segment is None:
        return None
    parameters = _parameter_names(node)
    bindings = {
        parameter: frozenset([_symbolic_value(parameter)]) for parameter in parameters
    }
    path_credits: list = []
    raised_credits: list = []
    _fixtures_a_test_loads(
        segment,
        set(slots),
        bindings,
        name_slots=slots,
        path_credits=path_credits,
        raised_credits=raised_credits,
    )
    if not path_credits:
        return None
    for parameter in parameters:
        symbolic = {_symbolic_value(parameter)}
        if all(credit == symbolic for credit in path_credits) and all(
            credit <= symbolic for credit in raised_credits
        ):
            return parameter
    return None


def _body_holds_a_yield(statements) -> bool:
    """Whether a body yields outside any nested definition.

    A yield or a yield from standing in a body's own scope
    makes the function a generator function, and calling a
    generator function runs none of its body, so the body
    is deferred code of the kind the guard refuses
    everywhere else, in a lambda body, in a generator
    expression body, and in a nested definition. A yield
    inside a nested definition belongs to that definition's
    own scope and says nothing about the body holding it,
    so the search never enters one.
    """

    def visit(node):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            return False
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            return True
        return any(visit(child) for child in ast.iter_child_nodes(node))

    return any(visit(statement) for statement in statements)


def _pattern_names(pattern) -> list:
    """The names a match pattern binds.

    A capture pattern names the value it takes, a star
    pattern names the rest of a sequence it gathers, and
    a mapping pattern names the rest of the mapping it
    keeps. Each may stand nested inside a sequence
    pattern, an or pattern, a class pattern, or a
    mapping pattern, so the whole pattern is read. A
    value pattern and a singleton bind nothing.
    """
    names = []
    for node in ast.walk(pattern):
        if isinstance(node, ast.MatchAs) and node.name is not None:
            names.append(node.name)
        elif isinstance(node, ast.MatchStar) and node.name is not None:
            names.append(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest is not None:
            names.append(node.rest)
    return names


def _later_statement_rebinds(statements, name) -> bool:
    """Whether any of the statements binds the name at module level.

    The assignment family is read through the shared pair
    collector, so a plain or annotated assignment, a walrus
    binding, and a loop target standing in the statements
    or in the arms of a compound statement among them bind
    the name in the module scope exactly as the collector
    reads derivations inside a body. A binding standing in
    the head of a compound statement binds in the same
    scope, so the target of a with item and the names a
    match pattern captures, its captures, its stars, and
    its mapping rests, standing in the statements or in
    the arms of a compound statement among them, are read
    beside the assignments the collector gathers inside
    those arms. A definition or a class standing among
    the statements, or in an arm of one, binds its own
    name where it stands, and an import binds the names
    it carries. A star import may bind any name at all,
    so it rebinds every name it follows. The search never
    enters a nested definition or a class body, whose
    assignments bind in their own scopes. A rewrite
    executed through a definition the module level calls
    is read by a separate reading beside this one, since
    it turns on an execution standing in a statement
    rather than on a binding standing in one.
    """
    if any(name in targets for targets, _value in _assignment_pairs(statements)):
        return True

    def visit(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return node.name == name
        if isinstance(node, ast.Lambda):
            return False
        if isinstance(node, ast.Import):
            return any(
                (alias.asname or alias.name.split(".")[0]) == name
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            return any(
                alias.name == "*" or (alias.asname or alias.name) == name
                for alias in node.names
            )
        if isinstance(node, (ast.With, ast.AsyncWith)):
            if any(
                name in _target_names(item.optional_vars)
                for item in node.items
                if item.optional_vars is not None
            ):
                return True
        if isinstance(node, ast.Match):
            if any(name in _pattern_names(case.pattern) for case in node.cases):
                return True
        return any(visit(child) for child in ast.iter_child_nodes(node))

    return any(visit(statement) for statement in statements)


def _global_write_set(node) -> set:
    """The names a definition assigns under a global declaration.

    A global declaration standing anywhere in the
    definition's subtree counts, at any depth, and a
    name counts only when the subtree also assigns it,
    through a plain or valued annotated assignment, a
    walrus binding, a loop target, or an augmented
    assignment. The reading is the over reading the
    walk takes for the write backs it poisons, since a
    reading cannot see which nested body a call into
    the definition reaches, and a missed write back
    could only certify a body the name no longer
    denotes once the definition has run.
    """
    declared = set()
    assigned = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Global):
            declared.update(sub.names)
        elif isinstance(sub, ast.Assign):
            for target in sub.targets:
                assigned.update(_target_names(target))
        elif isinstance(sub, ast.AnnAssign) and sub.value is not None:
            assigned.update(_target_names(sub.target))
        elif isinstance(sub, ast.AugAssign):
            assigned.update(_target_names(sub.target))
        elif isinstance(sub, ast.NamedExpr):
            assigned.update(_target_names(sub.target))
        elif isinstance(sub, (ast.For, ast.AsyncFor)):
            assigned.update(_target_names(sub.target))
    return declared & assigned


def _later_call_rewrites(module_body, position, name) -> bool:
    """Whether an execution after the candidate rewrites the name.

    The names a body can rewrite are gathered from the
    whole module, from every module level definition,
    from every definition standing in the body of a
    module level class, gathered under its own name on
    the same terms, and from the construction methods
    of every module level class, wherever they stand, a
    name counting when the body assigns it under a
    global declaration. A call naming a class runs its
    construction as the class is constructed, so the
    write set of a class gathers from its dunder
    prepare method beside its dunder new method and
    its dunder init method, each standing as a
    definition in the class body or bound there under
    the method name on the statement terms the reach
    reads a body on, an assignment standing directly
    in the body or in an arm of a compound statement
    among its statements or a walrus binding standing
    in the body, or an unpacking assignment pairing
    it with the element standing at its own place in
    the tuple or list value it unpacks, on the
    element pairing terms the bindings passage of
    this reading states, a plain name value
    resolving through the module level definitions and
    a lambda value read where it stands, and from the
    same methods of the module level base classes it
    names, each name resolving to the class it denotes
    to the end of the chain, and stands for
    the class name beside the write sets of the plain
    definitions, and the bodies a call into either can
    run stand beside them for the reach to read their
    calls from. A call naming a class also runs the
    dunder call method of the metaclass that class
    stands under, the method that performs the
    construction at all, gathered from that metaclass
    and the module level base classes it names on the
    same terms as its construction methods, and
    counted at the call rather than at the creation of
    the class, since the method fires at instantiation
    and not at creation, so the names it assigns under
    a global declaration are counted beside the
    construction the same call runs and its body joins
    the reach to be read for the calls it makes in
    turn. The subclass hooks of a class stand
    beside its construction methods for the reach, and
    its set name methods stand beside them, gathered
    from the class and the module level base classes
    it names in the same way, each hook standing as a
    definition in the class body or bound there under
    the hook name on the same terms as a construction
    method. Defining a subclass
    calls the dunder init subclass method of each base
    the subclass names, so the hooks
    a class definition can run gather from the module
    level base classes it names, resolved through the
    base chain to its end, each hook
    counting the names its body assigns under a global
    declaration and its body standing as a body the
    reach can read calls from.

    The executions that can reach such a write are the
    ones the module level performs after the candidate's
    own definition, the statements standing after it,
    bare or in an arm of a compound statement among
    them, and the bodies of the classes standing at
    module level among them, which run as their
    definitions run. The reach closes over plain name
    calls, so the body of a definition the reach calls
    is read for the calls it makes in turn, and a class
    the reach constructs brings the calls of its
    construction methods into the reach beside its
    write set. A class definition standing in an
    executing position performs five executions more
    that wear no call shape in the source. It calls the
    subclass hooks of the bases it names, whose bodies
    join the reach as the body of a called definition
    does, and when its metaclass keyword names a module
    level class it calls that class to construct it, so
    the reach counts the keyword as a call into the
    construction write set gathered for that name,
    whose method bodies join the reach the same way.
    It calls the set name method of each descriptor
    standing in the namespace its body builds, the
    method of the class whose instance the statements
    of its body place in that namespace on the same
    statement terms the reach reads a body on, an
    assignment standing directly in the body or in an
    arm of a compound statement among its statements,
    an element of a tuple or a list the assignment
    unpacks, the tuple or list standing in the
    assignment or denoted by a plain name standing
    in it through the bindings, a subscript selecting an element out of
    a tuple or a list standing in the assignment or
    denoted by a plain name standing in it through
    the bindings, or by a name bound to a subscript
    selecting it out of a further literal so denoted
    through the bindings, the selection composing through a
    further subscript standing as its value on the
    same terms, an
    instantiation standing in an arm of a conditional
    expression the assignment evaluates, an
    instantiation standing as an operand of a boolean
    expression the assignment evaluates, an
    instantiation whose callee stands in
    a subscript naming the class in its value
    position, or an instance the body places by a
    plain name the module level bound to an
    instantiation of that class, or to a value
    standing in one of the expression forms this
    passage reads standing in the assignment itself,
    an arm of a conditional expression, an operand
    of a boolean expression, an element a
    subscript selects, or the value a walrus
    expression yields, or by a plain name
    a loop target binds, the name denoting an element
    of the iterable its header walks, where an
    element the iterable carries instantiates that
    class, its own or inherited
    through that class's module level base classes,
    whose write set is counted and whose body joins
    the reach the same way. And
    when its keywords name no metaclass it is
    constructed by the metaclass its bases stand under,
    the most derived among them, resolved for each base
    through its own keyword or the bases it stands
    under in turn, so the reach counts the creation as
    a call into the construction gathered for that
    metaclass the same way, counting every candidate
    the base chains leave unordered between themselves,
    since the refusal errs in the guard's safe direction
    and a genuine conflict between incomparable
    metaclasses fails loudly at creation in any case.
    And before its body runs it calls the prepare
    method of the metaclass that constructs it, on
    either path, the prepare method standing in the
    construction gathering beside the dunder new and
    dunder init methods, so the names it assigns under
    a global declaration are counted in the construction
    write set and its body joins the reach to be read
    for the calls it makes in turn. Every base reading
    in this counting, the subclass hooks, the metaclass
    resolution, and the base chains the gatherings
    follow, takes a base standing in a subscript
    expression as the plain name standing in its value
    position, so one base counts the same in either of
    its grammatical forms, while a base whose value
    position holds no plain name counts nothing. And a
    name resolves through the module level assignment
    bindings standing behind it at every point the
    counting turns a name into a class, a base, the
    value of a metaclass keyword, the callee of an
    instantiation, and a call naming a class alike, a
    name bound to a class name denoting that class and
    a name bound to a subscript of a class name
    denoting the class in its value position,
    following a chain of such bindings to the class it
    ends at, so a class counts under every name the
    module binds to it and not only under the name its
    definition statement carries. The bindings are
    gathered on the statement terms the assignment
    pair collection reads a body on, a plain
    assignment, an annotated assignment carrying a
    value, a walrus binding standing in an expression,
    and a loop target standing in a loop header alike,
    the value standing behind a loop target there
    being the iterable the header walks, so a name
    bound in any of those forms resolves as the same
    name bound by a plain assignment does. A name a
    loop target binds denotes an element of that
    iterable at every seat that resolves a name to the
    value it denotes, the class turning points the
    alias resolution serves, the instance resolution
    of the call locus, the bound value expansion the
    reach closes over, and the operand resolution of
    the with and for statements among them, and the
    selection reading among them, a subscript whose
    value position holds such a name, the name
    standing there bare or yielded to the position
    through an arm of a conditional expression, an
    operand of a boolean expression, or the value
    a walrus expression yields, or standing behind
    a further name bound to such a yielding form,
    selecting out of the element the name denotes
    beside the module bindings route on the
    placement index terms, the
    elements read where the iterable stands as a
    literal tuple or list or as a plain name the
    bindings resolve to one, on the element terms
    the placement reading reads such a name on, a
    name an unpacking loop target binds denoting
    the component of the element standing at its
    own place in the target, paired on the same
    element pairing terms the assignment correction
    below states, and an element read for what it
    is worth where the iterable of a further loop
    stands as a loop target name, the elements of
    the element that name denotes standing here in
    turn, so a chain of loop targets resolves at
    every level on the value the runtime walks. Where a
    plain assignment unpacks, a single target standing
    as a tuple or a list against a value standing as
    a tuple or a list of the same length with no
    starred element on either side, each name the
    target binds stands against the element of the
    value standing at its own place, paired
    recursively where an element itself unpacks, so
    an unpacked name resolves to the element the
    statement pairs it with as a name assigned that
    element directly does, and a shape the pairing
    cannot fix, a value standing as no literal
    sequence or a length the two sides do not share
    or a starred element on either side, keeps the
    whole value recording the pair collection made,
    which resolves nothing through it. The reach resolves
    the callee of a plain call through the same
    bindings, because a call dispatches on the callable
    the name denotes however the name came to be bound
    to it. A name bound to a plain name counts as a
    call into the definition standing at the end of the
    chain of such bindings, its body read for the calls
    it makes in turn and its write set counted on the
    terms of a direct call, and a name bound to a
    lambda counts as a call into the lambda body read
    where it stands in the binding. A name bound to a
    subscript selecting a callable out of a literal
    standing in the binding or denoted by a plain name
    standing in it through the bindings counts as a
    call into the callable the selection yields, a
    definition name so selected counting as a call
    into that definition and a lambda so selected as
    a call into its body read where it stands, the
    selection read on the index terms the placement
    reading selects on and a name bound to such a
    selection standing for the callable it yields in
    turn, and a name bound to a conditional
    expression, a boolean expression, or a walrus
    expression counts as a call into the callable
    the value it yields denotes, each read through
    the values the expression yields on the same
    terms, the name guard the literal sequences
    reading keeps against a name resolving through
    itself standing over the whole resolution here
    too, so a name bound through selections and
    aliases back to itself ends the expansion at the
    name. A call naming an
    instance counts beside these as a call into the
    dunder call methods of the class the instance
    stands in, its own or inherited through its base
    classes, the methods gathered for every module
    level class beside the seat the metaclass counting
    consults, the instance resolved through the
    bindings to the instantiation the name denotes,
    following a name bound to a further name to its
    instantiation in turn, or to a conditional
    expression whose arms denote instances, to a
    boolean expression whose operands denote
    instances, or to a walrus expression whose
    yielded value denotes an instance, each read
    through the values the expression yields on the
    same terms, or to a subscript
    selecting an instantiation out of a literal, the
    selected element denoting the instance on the
    index terms the placement reading selects on,
    the selection composing through a further
    subscript standing behind it on the same terms,
    on the terms the placement
    reading resolves a placed name by. The alias
    resolution's sentence denying a name bound to an
    instantiation the standing of a class name governs
    the places a name is turned into a class, and the
    call locus asks which body a call runs, so an
    instance name counts at a call for the call methods
    of its class and at no class turning point. The
    parts of a statement that evaluate
    as the statement itself runs are read beside the
    calls standing in it. A definition standing in an
    executing position, at the module level, in a class
    body the reach reads, or inside a body the reach
    has entered, performs its header as its statement
    runs, so its decorator expressions, its default
    values, and its annotations are read as executions
    while its body stays deferred until a call reaches
    it, and each decorator standing on the statement in
    bare name form is applied to the object the
    statement defines as the statement completes, an
    execution the grammar designates that wears no call
    shape in the source, so the application is counted
    beside the expressions as a call into the value the
    name denotes, resolved as the reach resolves its
    callees, a definition name to its body, a class
    name to its construction and to the dunder call
    method of the metaclass it stands under, and an
    instance name to the dunder call methods of the
    class it stands in, while a decorator in any other
    form is read for the calls standing inside the
    expression alone, the value it computes being one
    the counting cannot name. A lambda standing in an executing position
    performs its default values the same way, and a
    call whose callee is a lambda runs that lambda body
    as the call runs, so the reach reads the body
    beside the call, while a lambda no statement
    invokes contributes nothing past its defaults. A
    class standing in an executing position performs
    its header the same way, its decorator expressions,
    its base expressions, and its keyword values, at
    the module level and inside a body the reach has
    entered alike, with each decorator standing on it
    in bare name form applied to the class as its
    statement completes and counted as a call into the
    value the name denotes on the same terms as a
    decorator on a definition, and its body is read on
    the same terms in both positions, on the ground the
    closing words of this reading state, only the body
    of a definition standing in either position staying
    deferred. A statement performs the protocol
    methods of the values it operates on beside the
    calls standing in it. A with statement enters and
    leaves the context its manager position evaluates
    to, so the dunder enter and dunder exit methods
    of the class whose instance that position denotes
    are counted as calls at the statement, gathered
    for every module level class as a definition
    standing anywhere in the class body on the
    statement terms the reach reads a body on or
    bound there under the method name on the same
    terms, and through the module level base classes
    the class names, beside the construction of the
    manager the evaluation of the position already
    counts. The manager position denotes an
    instantiation standing in the statement, a name
    the bindings resolve to the instantiation it
    denotes, an instantiation an arm of a conditional
    expression standing in the position evaluates to,
    each arm read on the same terms, or the
    instantiation a walrus binding standing in the
    position binds, an instantiation standing as an
    operand of a boolean expression standing in the
    position, each operand read on the same terms, or
    an element of a tuple or a list a subscript
    standing in the position selects, the literal
    standing in the subscript or denoted by a plain
    name standing in it through the bindings, or by
    a name bound to a subscript selecting it out of
    a further literal so denoted through the
    bindings, the
    element read on the index terms the placement
    reading selects on, the selection composing
    through a further subscript standing in the
    position on the same terms, on the terms the call locus resolves an
    instance name by, and the iterable position of a
    for statement denotes its instantiation on the
    same terms. A for statement iterates the
    value its iterable position evaluates to the same
    way, so the dunder iter method of the class the
    iterable denotes is counted at the statement, and
    the dunder next method of the same class is
    counted beside it where the gathered iter method
    returns the instance itself, the returned value
    standing as the parameter name alone, through a
    name the method's body binds to its first
    parameter, through a walrus expression yielding
    it, or as an operand of a boolean expression
    yielding it through one of its operands, or
    through an arm of a conditional expression one
    of whose arms returns it in any of those forms,
    or as an element a subscript selects out of a
    literal tuple or list holding it, the literal
    standing in the subscript or denoted by a name
    the body itself binds to one on the binding
    terms this passage states for the body's own
    names, a name counting as bound to one where
    the value it is bound to yields one on the same
    terms, through an arm of a conditional
    expression, an operand of a boolean expression,
    the value a walrus expression yields, or the
    selection a subscript performs, a selection
    selecting a name the body binds to one counting
    as the literal that name denotes in its turn,
    the name followed through the body's own literal
    reading on the same terms, or standing in
    the subscript as the value
    a walrus expression yields, as an operand of a
    boolean expression, in an arm of a conditional
    expression, or behind an inner subscript
    selecting it out of a further literal so
    standing, the element
    read on the index terms the placement reading
    selects on, a name counting as bound to the
    first parameter where its body binds it by a
    plain, an annotated, or a walrus assignment to
    a value counting in any of those forms, by an
    unpacking assignment pairing it with an element
    so counting on the element pairing terms, by a
    loop target, plain or unpacking, paired with
    an element of a literal holding a name so
    counting, the literal standing in the header
    or denoted by a name the body binds to one, or by an assignment to a conditional
    expression either of whose arms is a name so
    counting, or to a boolean expression one of
    whose operands is such a name, the shapes in
    which the statement performs the next method of
    the class it starts from. An iter method returning
    any other value hands the iteration to a value the
    counting cannot name from the statement, which
    stands on the return value ground this counting
    does not model, the same ground the truth testing
    dispatch at an expression position stands on.
    Where no dunder iter method stands in the chain
    of the class a for statement's iterable denotes,
    the statement iterates that class through the
    sequence protocol the data model designates as
    the fallback, so its dunder getitem method is
    counted at the statement instead, gathered for
    every module level class on the same installation
    terms, and where an iter method stands in the
    chain the fallback never fires and the getitem
    counting stays silent at the statement. An
    augmented assignment performs the dispatch of its
    operation on the value its target name denotes,
    so an augmented assignment whose target is a
    plain name counts as a call into the in place
    method its operator names, the dunder iadd
    method for the additive operator, the dunder
    isub method for the subtractive, the dunder imul
    method for the multiplicative, and their
    siblings for the remaining operators the grammar
    carries, of the class the name's value denotes
    where that class's chain carries one, and into
    the plain method of the same operation, the
    dunder add method for the additive operator and
    its siblings, of that class where it carries
    none, the plain method standing as the in place
    method's designated fallback for its operator,
    the name
    resolved through the bindings to the instantiation
    it denotes on the terms the call locus resolves
    an instance name by, both methods of every
    operator gathered for every module level class
    on the same installation terms. A
    subscript whose value position resolves to a
    module level class, a conditional expression
    standing in the value position resolving to the
    classes of both its arms, a boolean expression
    resolving to the classes of its operands, and a
    walrus expression resolving to the class of the
    value it yields, and a subscript standing in
    the value position resolving to the classes of
    the elements it selects out of a literal it
    stands on, the literal standing in the inner
    selection itself or yielded there by an arm of
    a conditional expression, an operand of a
    boolean expression, or the value a walrus
    expression yields, or denoted there by a name
    bound to a subscript selecting it out of a
    further literal so standing, and a name
    standing in the value position bound to a
    subscript whose own value position holds such
    a yielding form or a loop target name, or
    bound through such a yielding form to the
    value the form yields, a name so yielded
    resolved on the same terms in turn, or bound
    to a subscript whose own value position holds
    a name bound to such a yielding form, the
    yielded loop target name standing in the value
    position on the same principle, resolving
    beside the denotation the bare name takes to
    the classes of the elements that subscript's
    selection yields on the same terms, on the
    index terms the
    placement reading selects on, on the reach's
    expression terms beside the bare name and
    subscript forms the denotation reading takes,
    performs the dunder class
    getitem method of that class as it evaluates, so
    the method is counted wherever the reach reads
    the subscript as an execution, in a base
    expression and in an annotation under the header
    reading alike, gathered for every module level
    class on the same installation terms, while a
    subscript standing as the callee of a call stays
    a call form the counting does not read, on the
    ground recorded for subscript callees. The candidate is refused when the reach
    calls
    a definition or a construction whose write set
    holds the name, or runs a subclass hook, a set
    name hook, the dunder call method of the
    metaclass a called class stands under, or the
    dunder call method of the class an instance a call
    names stands in, or the dunder enter or dunder
    exit method of a class a with statement manages,
    the dunder iter or dunder next method of a class
    a for statement walks, the dunder getitem method
    of a class a for statement walks by the sequence
    fallback, the in place method of the operation
    an augmented assignment performs, or the plain
    method standing as its fallback, of the class of
    the value its target name denotes, or the dunder class
    getitem method of a class a subscript names,
    whose write set holds it.

    The refusal keys on the execution, so an installer
    no call reaches refuses nothing, and a call standing
    before the candidate refuses nothing, because the
    candidate's own definition binds the name after it.
    An asynchronous definition is no installer and the
    reach never enters its body, because calling it
    runs none of it, though its header performs at its
    definition exactly as a plain one does. Inside a
    body the reach has entered, the search stops at the
    body of a further definition, whose calls run on
    their own time and not on the module's, while the
    header of the further definition is read beside
    the calls around it, and a class standing in the
    same position is read on the terms of a class at
    module level, its header read beside the calls
    around it, the executions its creation performs
    counted with them, and the statements of its body
    read for the calls standing in them, because a
    class body runs at its statement, as part of the
    enclosing body running, and has no time of its own
    apart from it, while the body of a further
    definition standing inside that class body stays
    deferred like any other definition body.
    """
    writes = {}
    callees = {}
    class_nodes = {}
    definition_nodes = {}

    def gather(node, in_class_body=False):
        if isinstance(node, ast.FunctionDef):
            write_set = _global_write_set(node)
            if write_set:
                writes.setdefault(node.name, set()).update(write_set)
            callees.setdefault(node.name, []).append(node.body)
            if not in_class_body:
                definition_nodes.setdefault(node.name, []).append(node)
            return
        if isinstance(node, ast.AsyncFunctionDef):
            return
        if isinstance(node, ast.ClassDef):
            class_nodes.setdefault(node.name, []).append(node)
            for member in node.body:
                gather(member, in_class_body=True)
            return
        if isinstance(node, ast.Lambda):
            return
        for child in ast.iter_child_nodes(node):
            gather(child, in_class_body)

    for statement in module_body:
        gather(statement)

    module_bindings = {}
    for bound_names, bound_value in _assignment_pairs(module_body):
        for bound in bound_names:
            module_bindings.setdefault(bound, []).append(bound_value)

    def unpacking_element_pairs(target, value):
        """The name and element pairs an unpacking target fixes, if any.

        An unpacking assignment pairs each element of its
        target with the element of its value standing at
        the same place, so where a target standing as a
        tuple or a list meets a value standing as a tuple
        or a list of the same length, each name the target
        binds stands against the value element at its own
        place, paired recursively where an element itself
        unpacks, and a target element binding no plain
        name, an attribute or a subscript standing there,
        pairs nothing at its place. Any other shape fixes
        no pairing the reading can name, a value standing
        as no literal sequence, a length the two sides do
        not share, a starred element standing on either
        side, or an element whose two sides do not pair,
        and the whole value recording the pair collection
        made stands for such an assignment, which
        resolves nothing through it.
        """
        if isinstance(value, ast.Starred):
            return None
        if isinstance(target, ast.Name):
            return [(target.id, value)]
        if isinstance(target, (ast.Tuple, ast.List)) and isinstance(
            value, (ast.Tuple, ast.List)
        ):
            if len(target.elts) != len(value.elts):
                return None
            pairs = []
            for target_element, value_element in zip(target.elts, value.elts):
                element_pairs = unpacking_element_pairs(
                    target_element, value_element
                )
                if element_pairs is None:
                    return None
                pairs.extend(element_pairs)
            return pairs
        if isinstance(target, (ast.Attribute, ast.Subscript)):
            return []
        return None

    def apply_unpacking_pairings(node):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            return
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            element_pairs = unpacking_element_pairs(node.targets[0], node.value)
            if element_pairs is not None:
                for bound, element in element_pairs:
                    entries = module_bindings.get(bound, [])
                    for index, entry in enumerate(entries):
                        if entry is node.value:
                            entries[index] = element
                            break
        for child in ast.iter_child_nodes(node):
            apply_unpacking_pairings(child)

    for statement in module_body:
        apply_unpacking_pairings(statement)

    loop_target_names = set()
    loop_headers = []

    def collect_loop_targets(node):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            return
        if isinstance(node, (ast.For, ast.AsyncFor)):
            loop_target_names.update(_target_names(node.target))
            loop_headers.append((node.target, node.iter))
        for child in ast.iter_child_nodes(node):
            collect_loop_targets(child)

    for statement in module_body:
        collect_loop_targets(statement)

    def elements_of_value(expression, seen_names=frozenset()):
        """The element expressions of the value an expression denotes.

        A tuple or a list standing in the expression
        carries its own elements. A plain name carries
        the elements of the value it denotes, read
        through the module level bindings where the
        name stands bound to a literal or to a further
        name in turn, and where the name is one a loop
        target binds its value is one of the elements
        the loop target element reading returns for it,
        so the elements of that element stand here in
        turn, composing the two readings where a loop
        walks a name another loop bound. An expression
        standing in any other form denotes no element
        this reading can name.
        """
        if isinstance(expression, (ast.Tuple, ast.List)):
            return list(expression.elts)
        if isinstance(expression, ast.Name) and expression.id not in seen_names:
            seen = seen_names | {expression.id}
            elements = []
            if expression.id in loop_target_names:
                for denoted in loop_target_elements(expression.id, seen_names):
                    elements.extend(elements_of_value(denoted, seen))
            header_iters = {
                id(header_iter)
                for header_target, header_iter in loop_headers
                if expression.id in _target_names(header_target)
            }
            for bound_value in module_bindings.get(expression.id, []):
                if id(bound_value) in header_iters:
                    continue
                elements.extend(elements_of_value(bound_value, seen))
            return elements
        return []

    def loop_target_elements(name, seen_names=frozenset()):
        """The element expressions a loop target name denotes.

        A name a loop target binds denotes an element of
        the iterable its header walks, not the iterable
        itself, so where the iterable stands as a literal
        tuple or a list, or as a plain name the module
        level bindings resolve to one, the name denotes
        the elements that literal carries, read on the
        element terms the placement reading reads such
        a name on. A name an unpacking loop target binds
        denotes the component of the element standing at
        its own place in the target, paired against each
        element the header walks on the element pairing
        terms the assignment correction reads its targets
        on, so each name the target binds stands against
        its own component rather than the element whole.
        An element is read for what it is worth where the
        iterable stands as a name the bindings resolve,
        a name another loop target binds among them, so
        a chain of loop targets resolves at every level
        on the value the runtime walks. An iterable
        standing in any other form, a call among them,
        denotes no element this reading can name.
        """
        elements = []
        if name in seen_names:
            return elements
        seen = seen_names | {name}
        for bound_value in module_bindings.get(name, []):
            header_targets = [
                header_target
                for header_target, header_iter in loop_headers
                if header_iter is bound_value
                and name in _target_names(header_target)
            ]
            if not header_targets:
                elements.extend(elements_of_value(bound_value, seen))
                continue
            for header_target in header_targets:
                walked = elements_of_value(bound_value, seen)
                if isinstance(header_target, ast.Name):
                    elements.extend(walked)
                elif isinstance(header_target, (ast.Tuple, ast.List)):
                    for element in walked:
                        element_pairs = unpacking_element_pairs(
                            header_target, element
                        )
                        if element_pairs is None:
                            continue
                        for bound_name, component in element_pairs:
                            if bound_name == name:
                                elements.append(component)
        return elements

    def base_name(expression):
        """The plain name a base expression resolves to, if any.

        A base in bare name form names its class directly,
        and a base standing in a subscript expression
        names the class standing in the value position
        of the subscript, the standard generic alias
        shape, so the two grammatical forms of one base
        resolve to the same name in every base reading
        the counting performs. A base arriving through
        any other expression, a call or an attribute,
        names no class the reading can resolve and
        counts nothing.
        """
        if isinstance(expression, ast.Name):
            return expression.id
        if isinstance(expression, ast.Subscript):
            return base_name(expression.value)
        return None

    def aliased_class(name, seen=frozenset()):
        """The class name a name denotes through its module level bindings.

        A name bound at module level to a plain class name
        denotes that class, and a name bound to a subscript
        of a class name denotes the class standing in the
        value position of the subscript, so the resolution
        follows a chain of such bindings to the class it
        ends at and returns the definition name of that
        class. A name bound to any other value, an
        instantiation among them, denotes that value and
        not a class, and resolves to nothing here, as
        does a name bound to no class at all. A name a
        loop target binds denotes an element of the
        iterable its header walks, so the elements the
        iterable denotes stand behind the name here
        beside the values its bindings record whole.
        """
        if name in class_nodes:
            return name
        if name in seen:
            return None
        bound_values = list(module_bindings.get(name, []))
        if name in loop_target_names:
            bound_values.extend(loop_target_elements(name))
        for bound_value in bound_values:
            resolved = None
            if isinstance(bound_value, ast.Name):
                resolved = aliased_class(bound_value.id, seen | {name})
            elif isinstance(bound_value, ast.Subscript):
                inner = base_name(bound_value)
                if inner is not None:
                    resolved = aliased_class(inner, seen | {name})
            if resolved is not None:
                return resolved
        return None

    def denoted_class_name(expression):
        """The class name an expression denotes where a name becomes a class.

        The plain name the expression carries, a bare name
        or the name standing in the value position of a
        subscript, resolved through the module level
        assignment bindings standing behind it, so an
        alias counts as the class it stands for at every
        point the counting turns a name into a class, the
        base readings, the metaclass keyword and the
        candidates behind it, and the callee of an
        instantiation among them. A name no binding
        resolves to a class stands as the plain name
        itself, which the class tables hold only where a
        definition statement carries it.
        """
        plain = base_name(expression)
        if plain is None:
            return None
        resolved = aliased_class(plain)
        return resolved if resolved is not None else plain

    def subscript_selected_values(expression, seen_names=frozenset()):
        """The expressions a subscript expression evaluates to.

        A subscript selects an element out of the value
        it stands on, so where that value stands as a
        literal tuple or a list, or as a plain name the
        module level bindings resolve to one, or as an
        expression yielding one through an arm of a
        conditional expression, an operand of a boolean
        expression, or the value a walrus expression
        yields, the subscript evaluates to the element
        its index selects, the element standing at a
        constant index where the subscript carries one
        and every element where it does not, on the
        index terms the placement reading selects on.
        Where the value itself stands as a subscript,
        the subscript evaluates to what the inner
        subscript's selection evaluates to in turn, read
        on the same terms. A name standing in the value
        position resolves through the literal sequences
        reading on the same terms, so a name bound to a
        subscript stands here for what that subscript's
        selection evaluates to, the name guard the
        literal sequences reading keeps against a name
        resolving through itself standing over the
        whole resolution. A loop target name standing
        in the value position resolves beside that
        route through the loop target element reading,
        to the elements the name denotes, wherever in
        the value position the resolution reaches it,
        the name standing there bare, or yielded to
        the position through an arm of a conditional
        expression, an operand of a boolean
        expression, or the value a walrus expression
        yields, or standing behind a further name
        bound to such a yielding form in turn, so the
        subscript selects out of the element the name
        denotes on the same index terms rather than
        out of the iterable its header walks, the
        binding the pair collection records for such
        a name being that iterable and not the element
        it denotes. A subscript standing on any
        other value evaluates to nothing this reading
        can name.
        """
        if isinstance(expression.value, ast.Subscript):
            bases = subscript_selected_values(expression.value, seen_names)
        else:
            bases = [expression.value]
            if (
                isinstance(expression.value, ast.Name)
                and expression.value.id in loop_target_names
            ):
                bases.extend(
                    loop_target_elements(
                        expression.value.id, seen_names
                    )
                )
        sequences = []
        for base in bases:
            sequences.extend(literal_sequences(base, seen_names))
        index = expression.slice
        selected = []
        for elements in sequences:
            if (
                isinstance(index, ast.Constant)
                and isinstance(index.value, int)
                and not isinstance(index.value, bool)
                and -len(elements) <= index.value < len(elements)
            ):
                selected.append(elements[index.value])
            else:
                selected.extend(elements)
        return selected

    def subscript_value_class_names(expression, seen_names=frozenset()):
        """The class names a subscript's value position resolves to.

        The execution counting reads a subscript's value
        position on the reach's expression terms, so a
        conditional expression standing in the position
        resolves to the classes of both its arms, over
        reading an unfoldable condition in the safe
        direction as the counting does at its other
        loci, a boolean expression standing in the
        position resolves to the classes of its
        operands, and a walrus expression standing in
        the position resolves to the class of the value
        it yields, beside the bare name and subscript
        forms the class denotation reading takes, which
        this reading leaves at its own width for the
        base and annotation positions it serves. A
        subscript standing in the position resolves to
        the classes of the elements it selects out of a
        literal it stands on, the literal standing in
        the inner selection itself or yielded there by
        an arm of a conditional expression, an operand
        of a boolean expression, or the value a walrus
        expression yields, or denoted there by a name
        bound to a subscript selecting it out of a
        further literal so standing, the selection read on the
        index terms the placement reading selects on,
        because the outer subscript performs the class
        getitem of the class the selection yields.
        A name standing in the position bound to a
        subscript whose own value position holds a
        yielding form of those kinds, or a loop target
        name the selection reading resolves beside the
        module bindings route, resolves beside the
        denotation the bare name takes to the classes
        of the elements that subscript's selection
        yields, read through the selection reading on
        the same terms, because the name denotes the
        element the selection yields and the forms
        that subscript stands on are the selection
        reading's own ground. The qualification stands
        however the name and the subscript's base came
        to stand. A name bound through a yielding form
        of those kinds is followed to the value the
        form yields, and a name the form yields is
        resolved on the same terms in turn, because
        the value a yielding expression yields stands
        where the expression itself stands. And the
        subscript's base qualifies beside the forms
        standing in it directly where the base stands
        as a name bound to a yielding form of those
        kinds, the loop target name the form yields
        standing in the value position on the same
        principle, under the name guard the other
        name routes in this reading carry. While a
        name bound to a subscript standing on any
        other value, a literal among them, or on a
        plain name bound to a literal, resolves
        through the denotation alone, and a name
        standing in the position on a plain
        assignment alone, with no yielding form
        between it and the subscript behind it,
        resolves through the denotation alone in the
        same way.
        """
        if isinstance(expression, ast.IfExp):
            names = subscript_value_class_names(expression.body, seen_names)
            names.extend(
                subscript_value_class_names(expression.orelse, seen_names)
            )
            return names
        if isinstance(expression, ast.BoolOp):
            names = []
            for operand in expression.values:
                names.extend(
                    subscript_value_class_names(operand, seen_names)
                )
            return names
        if isinstance(expression, ast.NamedExpr):
            return subscript_value_class_names(expression.value, seen_names)
        if isinstance(expression, ast.Subscript):
            names = []
            for element in subscript_selected_values(expression):
                names.extend(
                    subscript_value_class_names(element, seen_names)
                )
            if names:
                return names
        def qualifying_base(base, seen_names):
            """Whether the base of a subscript qualifies the name branch.

            The base qualifies standing as a yielding
            form itself, standing as a loop target name,
            or standing as a name bound to a yielding
            form, the loop target name the form yields
            standing in the value position on the
            yielding principle. A base standing in any
            other form, a literal or a plain name bound
            to a literal among them, qualifies nothing
            here, and the name bound to the subscript
            resolves through the denotation alone.
            """
            if isinstance(base, (ast.IfExp, ast.BoolOp, ast.NamedExpr)):
                return True
            if isinstance(base, ast.Name):
                if base.id in loop_target_names:
                    return True
                if base.id not in seen_names:
                    for bound_value in module_bindings.get(base.id, []):
                        if isinstance(
                            bound_value,
                            (ast.IfExp, ast.BoolOp, ast.NamedExpr),
                        ):
                            return True
            return False

        def names_behind_yields(value, seen_names):
            """The class names a value standing behind a name resolves to.

            A subscript standing in the value counts
            the classes of the elements its selection
            yields where its base qualifies on the
            terms the qualification beside it states. A
            yielding form standing in the value is
            followed to the values it yields, each read
            on the same terms, and a name a form yields
            is resolved through its own bindings on the
            same terms in turn, the seen names guard
            standing over the whole resolution so a
            name resolving through itself ends the
            following at the name. A value standing in
            any other form resolves to nothing here.
            """
            if isinstance(value, ast.Subscript):
                if not qualifying_base(value.value, seen_names):
                    return []
                names = []
                for element in subscript_selected_values(value):
                    names.extend(
                        subscript_value_class_names(element, seen_names)
                    )
                return names
            if isinstance(value, ast.IfExp):
                names = names_behind_yields(value.body, seen_names)
                names.extend(names_behind_yields(value.orelse, seen_names))
                return names
            if isinstance(value, ast.BoolOp):
                names = []
                for operand in value.values:
                    names.extend(names_behind_yields(operand, seen_names))
                return names
            if isinstance(value, ast.NamedExpr):
                return names_behind_yields(value.value, seen_names)
            if isinstance(value, ast.Name) and value.id not in seen_names:
                names = []
                for bound_value in module_bindings.get(value.id, []):
                    names.extend(
                        names_behind_yields(
                            bound_value, seen_names | {value.id}
                        )
                    )
                return names
            return []

        names = []
        if isinstance(expression, ast.Name) and expression.id not in seen_names:
            seen = seen_names | {expression.id}
            for bound_value in module_bindings.get(expression.id, []):
                if isinstance(
                    bound_value,
                    (ast.Subscript, ast.IfExp, ast.BoolOp, ast.NamedExpr),
                ):
                    names.extend(names_behind_yields(bound_value, seen))
        resolved = denoted_class_name(expression)
        if resolved is not None:
            names.append(resolved)
        return names

    def unpacking_body_pairs(statements):
        """The name and element pairs the unpacking assignments of a body fix.

        An assignment standing in the body with a single
        target standing as a tuple or a list against a
        value standing as a tuple or a list pairs each
        name in the target with the element of the value
        standing at its own place, on the element pairing
        terms the bindings table correction states,
        recursively where an element itself unpacks, and
        a shape the pairing cannot fix pairs nothing here,
        the whole value recording the pair collection
        made standing for it in the readings that take
        the pairs whole. The walk reads a body on the
        statement terms the pair collection reads one on,
        never entering a nested definition.
        """
        pairs = []

        def collect(node):
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                    ast.Lambda,
                ),
            ):
                return
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                element_pairs = unpacking_element_pairs(
                    node.targets[0], node.value
                )
                if element_pairs is not None:
                    pairs.extend(element_pairs)
            for child in ast.iter_child_nodes(node):
                collect(child)

        for statement in statements:
            collect(statement)
        return pairs

    def method_installations(members, names):
        """The bodies and write sets of the designated methods a body installs.

        A designated method stands in a class body under
        its designated name, and the interpreter dispatches
        on the entry standing under the name however the
        body bound it, so the gatherings collect the method
        on the statement terms the reach reads a body on.
        A definition carrying the designated name counts
        wherever it stands in the body, directly among its
        statements or in an arm of a compound statement
        among them. An assignment binding the designated
        name counts on the same terms, standing directly
        in the body or in an arm of a compound statement
        among its statements or as a walrus binding
        standing in the body, its pairs read through the
        shared assignment pair collector the placement
        reading consults. An assignment whose value is a
        plain name resolves through the module level
        definitions of that name and gathers the body it
        resolves to on the same terms as a definition
        standing there, and an assignment whose value is
        a lambda reads the lambda body where it stands.
        An assignment that unpacks pairs each designated
        name it binds with the element standing at its
        own place where the target and the value both
        stand as a tuple or a list of the same length
        with no starred element on either side, paired
        recursively, and the element is gathered on the
        same plain name and lambda terms, so a method
        installed by unpacking installs the element it
        is paired with. An assignment binding a
        designated name to any other value installs
        nothing the reading can see, and a statement
        binding no designated name installs nothing here.
        """
        bodies = []
        write_set = set()

        def add_definition(node):
            bodies.append(node.body)
            write_set.update(_global_write_set(node))

        def add_value(value):
            if isinstance(value, ast.Name):
                for definition in definition_nodes.get(value.id, []):
                    add_definition(definition)
            elif isinstance(value, ast.Lambda):
                bodies.append([value.body])

        def collect_definitions(node):
            if isinstance(
                node, (ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
            ):
                return
            if isinstance(node, ast.FunctionDef):
                if node.name in names:
                    add_definition(node)
                return
            for child in ast.iter_child_nodes(node):
                collect_definitions(child)

        for member in members:
            collect_definitions(member)
        for targets, value in _assignment_pairs(members):
            if any(target in names for target in targets):
                add_value(value)
        for target, element in unpacking_body_pairs(members):
            if target in names:
                add_value(element)
        return bodies, write_set

    def gather_construction(class_name, node, seen):
        found_bodies, found_writes = method_installations(
            node.body, ("__init__", "__new__", "__prepare__")
        )
        if found_writes:
            writes.setdefault(class_name, set()).update(found_writes)
        for body in found_bodies:
            callees.setdefault(class_name, []).append(body)
        for base in node.bases:
            resolved = denoted_class_name(base)
            if (
                resolved is not None
                and resolved in class_nodes
                and resolved not in seen
            ):
                for base_node in class_nodes[resolved]:
                    gather_construction(class_name, base_node, seen | {resolved})

    for class_name, nodes in class_nodes.items():
        for class_node in nodes:
            gather_construction(class_name, class_node, {class_name})

    metaclass_calls = {}

    def gather_metaclass_calls(class_name, node, seen):
        found_bodies, found_writes = method_installations(
            node.body, ("__call__",)
        )
        bodies, write_set = metaclass_calls.setdefault(class_name, ([], set()))
        bodies.extend(found_bodies)
        write_set.update(found_writes)
        for base in node.bases:
            resolved = denoted_class_name(base)
            if (
                resolved is not None
                and resolved in class_nodes
                and resolved not in seen
            ):
                for base_node in class_nodes[resolved]:
                    gather_metaclass_calls(
                        class_name, base_node, seen | {resolved}
                    )

    for class_name, nodes in class_nodes.items():
        for class_node in nodes:
            gather_metaclass_calls(class_name, class_node, {class_name})

    context_methods = {}
    iteration_methods = {}
    next_methods = {}
    self_returning_iterables = set()
    class_getitem_methods = {}
    getitem_methods = {}
    augmented_inplace_methods = {}
    augmented_plain_methods = {}
    augmented_operators = (
        (ast.Add, "__iadd__", "__add__"),
        (ast.Sub, "__isub__", "__sub__"),
        (ast.Mult, "__imul__", "__mul__"),
        (ast.MatMult, "__imatmul__", "__matmul__"),
        (ast.Div, "__itruediv__", "__truediv__"),
        (ast.FloorDiv, "__ifloordiv__", "__floordiv__"),
        (ast.Mod, "__imod__", "__mod__"),
        (ast.Pow, "__ipow__", "__pow__"),
        (ast.LShift, "__ilshift__", "__lshift__"),
        (ast.RShift, "__irshift__", "__rshift__"),
        (ast.BitAnd, "__iand__", "__and__"),
        (ast.BitOr, "__ior__", "__or__"),
        (ast.BitXor, "__ixor__", "__xor__"),
    )

    def designated_bodies(table, class_name, node, seen, names):
        found_bodies, found_writes = method_installations(node.body, names)
        bodies, write_set = table.setdefault(class_name, ([], set()))
        bodies.extend(found_bodies)
        write_set.update(found_writes)
        for base in node.bases:
            resolved = denoted_class_name(base)
            if (
                resolved is not None
                and resolved in class_nodes
                and resolved not in seen
            ):
                for base_node in class_nodes[resolved]:
                    designated_bodies(
                        table, class_name, base_node, seen | {resolved}, names
                    )

    def iter_installation_nodes(members, seen_definitions=frozenset()):
        """The definition nodes a body installs under the iter name.

        The nodes stand where the installation reading
        finds the method, as a definition anywhere in the
        body on its statement terms or bound there by an
        assignment to a plain name resolving through the
        module level definitions or to a lambda standing
        there, the name bound directly or paired by an
        unpacking assignment with the element standing
        at its own place, that element standing as such
        a name or a lambda, and they are read for the
        one question the
        iteration counting asks beside the bodies and
        write sets the installation reading gathers,
        whether an iter method returns the instance
        itself, which only the node carrying its
        parameters can answer.
        """
        nodes = []

        def collect_definitions(node):
            if isinstance(
                node, (ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
            ):
                return
            if isinstance(node, ast.FunctionDef):
                if node.name == "__iter__":
                    nodes.append(node)
                return
            for child in ast.iter_child_nodes(node):
                collect_definitions(child)

        for member in members:
            collect_definitions(member)
        candidate_values = []
        for targets, value in _assignment_pairs(members):
            if "__iter__" in targets:
                candidate_values.append(value)
        for target, element in unpacking_body_pairs(members):
            if target == "__iter__":
                candidate_values.append(element)
        for value in candidate_values:
            if isinstance(value, ast.Name):
                for definition in definition_nodes.get(value.id, []):
                    if id(definition) not in seen_definitions:
                        nodes.append(definition)
            elif isinstance(value, ast.Lambda):
                nodes.append(value)
        return nodes

    def iter_returns_instance(class_name, node, seen):
        for installation in iter_installation_nodes(node.body):
            parameters = [
                *installation.args.posonlyargs,
                *installation.args.args,
            ]
            if not parameters:
                continue
            first = parameters[0].arg

            alias_pairs = []
            deferred_loops = []

            def collect_alias_pairs(node):
                if isinstance(
                    node,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                        ast.ClassDef,
                        ast.Lambda,
                    ),
                ):
                    return
                if isinstance(node, ast.Assign):
                    alias_pairs.append(
                        (
                            [
                                bound
                                for target in node.targets
                                for bound in _target_names(target)
                            ],
                            node.value,
                        )
                    )
                    for target in node.targets:
                        element_pairs = unpacking_element_pairs(
                            target, node.value
                        )
                        if element_pairs is not None:
                            for bound_name, element in element_pairs:
                                alias_pairs.append(([bound_name], element))
                elif isinstance(node, ast.AnnAssign) and node.value is not None:
                    alias_pairs.append(
                        (_target_names(node.target), node.value)
                    )
                elif isinstance(node, ast.NamedExpr):
                    alias_pairs.append(
                        (_target_names(node.target), node.value)
                    )
                elif isinstance(node, (ast.For, ast.AsyncFor)):
                    if isinstance(node.target, ast.Name) and isinstance(
                        node.iter, (ast.Tuple, ast.List)
                    ):
                        for element in node.iter.elts:
                            alias_pairs.append(([node.target.id], element))
                    else:
                        element_pairs = unpacking_element_pairs(
                            node.target, node.iter
                        )
                        if element_pairs is not None:
                            for bound_name, element in element_pairs:
                                alias_pairs.append(([bound_name], element))
                        if isinstance(node.iter, ast.Name):
                            deferred_loops.append((node.target, node.iter))
                for child in ast.iter_child_nodes(node):
                    collect_alias_pairs(child)

            if not isinstance(installation, ast.Lambda):
                for statement in installation.body:
                    collect_alias_pairs(statement)

            def local_literal_nodes(name, seen_names=frozenset()):
                """The literal sequence nodes a body local name denotes.

                A name the body binds to a tuple or a list
                denotes that literal, and a name bound to a
                further name denotes what that name denotes
                in turn, read over the pairs the collector
                gathered for the body, the pairs pairing a
                name with the element it unpacks or the
                element a loop target walks among them. A
                name bound to a conditional expression
                denotes the literals its arms denote, a
                name bound to a boolean expression the
                literals its operands denote, a name bound
                to a walrus expression the literal the
                value it yields denotes, and a name bound
                to a subscript the literal standing among
                the elements the subscript's selection
                yields, each read through the selection
                literal reading on the same terms that
                reading resolves a value standing in a
                subscript itself, because the value each
                such form yields is the literal the name
                stands for. A name bound to any other
                value denotes no literal this reading can
                name.
                """
                if name in seen_names:
                    return []
                nodes = []
                for targets, bound_value in alias_pairs:
                    if len(targets) == 1 and targets[0] == name:
                        nodes.extend(
                            selection_literal_nodes(
                                bound_value, seen_names | {name}
                            )
                        )
                return nodes

            def selection_literal_nodes(value, seen_names=frozenset()):
                """The literal sequence nodes a selection value denotes.

                The literal standing in the subscript
                itself, a name the body binds to one on
                the terms the body's own literal reading
                follows, the literal the value a walrus
                expression yields denotes, a literal an
                operand of a boolean expression denotes,
                a literal an arm of a conditional
                expression denotes, or a literal an inner
                subscript selects out of a further
                literal so denoted, or the literal a
                name an inner subscript selects out of
                a literal denotes in its turn, that name
                followed through the body's own literal
                reading on the same terms, each read on
                the same terms, because the value each
                such form yields is the sequence the
                selection stands on. A value standing in
                any other form denotes no literal this
                reading can name.
                """
                if isinstance(value, (ast.Tuple, ast.List)):
                    return [value]
                if isinstance(value, ast.Name):
                    return local_literal_nodes(value.id, seen_names)
                if isinstance(value, ast.NamedExpr):
                    return selection_literal_nodes(value.value, seen_names)
                if isinstance(value, ast.BoolOp):
                    nodes = []
                    for operand in value.values:
                        nodes.extend(
                            selection_literal_nodes(operand, seen_names)
                        )
                    return nodes
                if isinstance(value, ast.IfExp):
                    nodes = selection_literal_nodes(value.body, seen_names)
                    nodes.extend(
                        selection_literal_nodes(value.orelse, seen_names)
                    )
                    return nodes
                if isinstance(value, ast.Subscript):
                    nodes = []
                    for element in selected_elements(value, seen_names):
                        if isinstance(element, (ast.Tuple, ast.List)):
                            nodes.append(element)
                        elif isinstance(element, ast.Name):
                            nodes.extend(
                                local_literal_nodes(
                                    element.id, seen_names
                                )
                            )
                    return nodes
                return []

            def selected_elements(expression, seen_names=frozenset()):
                selected = []
                index = expression.slice
                for literal in selection_literal_nodes(
                    expression.value, seen_names
                ):
                    elements = literal.elts
                    if (
                        isinstance(index, ast.Constant)
                        and isinstance(index.value, int)
                        and not isinstance(index.value, bool)
                        and -len(elements) <= index.value < len(elements)
                    ):
                        selected.append(elements[index.value])
                    else:
                        selected.extend(elements)
                return selected

            for deferred_target, deferred_iter in deferred_loops:
                for literal in local_literal_nodes(deferred_iter.id):
                    if isinstance(deferred_target, ast.Name):
                        for element in literal.elts:
                            alias_pairs.append(([deferred_target.id], element))
                    elif isinstance(deferred_target, (ast.Tuple, ast.List)):
                        element_pairs = unpacking_element_pairs(
                            deferred_target, literal
                        )
                        if element_pairs is not None:
                            for bound_name, element in element_pairs:
                                alias_pairs.append(([bound_name], element))

            def returns_instance(expression, instance_names):
                if isinstance(expression, ast.Name):
                    return expression.id in instance_names
                if isinstance(expression, ast.IfExp):
                    return returns_instance(
                        expression.body, instance_names
                    ) or returns_instance(expression.orelse, instance_names)
                if isinstance(expression, ast.NamedExpr):
                    return returns_instance(expression.value, instance_names)
                if isinstance(expression, ast.BoolOp):
                    return any(
                        returns_instance(operand, instance_names)
                        for operand in expression.values
                    )
                if isinstance(expression, ast.Subscript):
                    return any(
                        returns_instance(element, instance_names)
                        for element in selected_elements(expression)
                    )
                return False

            def value_counts_as_instance(bound_value):
                if isinstance(bound_value, ast.Name):
                    return bound_value.id in instance_names
                if isinstance(bound_value, ast.IfExp):
                    return value_counts_as_instance(
                        bound_value.body
                    ) or value_counts_as_instance(bound_value.orelse)
                if isinstance(bound_value, ast.NamedExpr):
                    return value_counts_as_instance(bound_value.value)
                if isinstance(bound_value, ast.BoolOp):
                    return any(
                        value_counts_as_instance(operand)
                        for operand in bound_value.values
                    )
                if isinstance(bound_value, ast.Subscript):
                    return any(
                        value_counts_as_instance(element)
                        for element in selected_elements(bound_value)
                    )
                return False

            if isinstance(installation, ast.Lambda):
                if returns_instance(installation.body, {first}):
                    return True
                continue
            instance_names = {first}
            growing = True
            while growing:
                growing = False
                for targets, bound_value in alias_pairs:
                    if value_counts_as_instance(bound_value):
                        for target in targets:
                            if target not in instance_names:
                                instance_names.add(target)
                                growing = True

            def scan_returns(node):
                if isinstance(
                    node,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                        ast.ClassDef,
                        ast.Lambda,
                    ),
                ):
                    return False
                if isinstance(node, ast.Return) and returns_instance(
                    node.value, instance_names
                ):
                    return True
                return any(
                    scan_returns(child) for child in ast.iter_child_nodes(node)
                )

            if any(scan_returns(statement) for statement in installation.body):
                return True
        for base in node.bases:
            resolved = denoted_class_name(base)
            if (
                resolved is not None
                and resolved in class_nodes
                and resolved not in seen
            ):
                for base_node in class_nodes[resolved]:
                    if iter_returns_instance(
                        class_name, base_node, seen | {resolved}
                    ):
                        return True
        return False

    for class_name, nodes in class_nodes.items():
        for class_node in nodes:
            designated_bodies(
                context_methods,
                class_name,
                class_node,
                {class_name},
                ("__enter__", "__exit__"),
            )
            designated_bodies(
                iteration_methods,
                class_name,
                class_node,
                {class_name},
                ("__iter__",),
            )
            designated_bodies(
                next_methods,
                class_name,
                class_node,
                {class_name},
                ("__next__",),
            )
            designated_bodies(
                class_getitem_methods,
                class_name,
                class_node,
                {class_name},
                ("__class_getitem__",),
            )
            designated_bodies(
                getitem_methods,
                class_name,
                class_node,
                {class_name},
                ("__getitem__",),
            )
            for _operator, inplace_name, plain_name in augmented_operators:
                designated_bodies(
                    augmented_inplace_methods.setdefault(inplace_name, {}),
                    class_name,
                    class_node,
                    {class_name},
                    (inplace_name,),
                )
                designated_bodies(
                    augmented_plain_methods.setdefault(plain_name, {}),
                    class_name,
                    class_node,
                    {class_name},
                    (plain_name,),
                )
            if iter_returns_instance(class_name, class_node, {class_name}):
                self_returning_iterables.add(class_name)

    def subclass_hooks(node, seen):
        bodies = []
        write_set = set()
        for base in node.bases:
            resolved = denoted_class_name(base)
            if (
                resolved is not None
                and resolved in class_nodes
                and resolved not in seen
            ):
                for base_node in class_nodes[resolved]:
                    hook_bodies, hook_writes = method_installations(
                        base_node.body, ("__init_subclass__",)
                    )
                    bodies.extend(hook_bodies)
                    write_set.update(hook_writes)
                    child_bodies, child_writes = subclass_hooks(
                        base_node, seen | {resolved}
                    )
                    bodies.extend(child_bodies)
                    write_set.update(child_writes)
        return bodies, write_set

    def set_name_methods(node, seen):
        bodies, write_set = method_installations(node.body, ("__set_name__",))
        bodies = list(bodies)
        write_set = set(write_set)
        for base in node.bases:
            resolved = denoted_class_name(base)
            if (
                resolved is not None
                and resolved in class_nodes
                and resolved not in seen
            ):
                for base_node in class_nodes[resolved]:
                    child_bodies, child_writes = set_name_methods(
                        base_node, seen | {resolved}
                    )
                    bodies.extend(child_bodies)
                    write_set.update(child_writes)
        return bodies, write_set

    def metaclass_candidates(node, seen):
        for keyword in node.keywords:
            if keyword.arg == "metaclass":
                resolved = denoted_class_name(keyword.value)
                if resolved is not None and resolved in class_nodes:
                    return {resolved}
                return set()
        candidates = set()
        for base in node.bases:
            resolved = denoted_class_name(base)
            if (
                resolved is not None
                and resolved in class_nodes
                and resolved not in seen
            ):
                for base_node in class_nodes[resolved]:
                    candidates.update(
                        metaclass_candidates(base_node, seen | {resolved})
                    )
        return candidates

    def class_ancestors(class_name, seen):
        ancestors = set()
        for node in class_nodes.get(class_name, []):
            for base in node.bases:
                resolved = denoted_class_name(base)
                if (
                    resolved is not None
                    and resolved in class_nodes
                    and resolved not in seen
                ):
                    ancestors.add(resolved)
                    ancestors.update(
                        class_ancestors(resolved, seen | {resolved})
                    )
        return ancestors

    def counted_metaclasses(node):
        candidates = metaclass_candidates(node, frozenset())
        return {
            candidate
            for candidate in candidates
            if not any(
                other != candidate
                and candidate in class_ancestors(other, frozenset())
                for other in candidates
            )
        }

    def metaclass_call_executions(class_name):
        bodies = []
        write_set = set()
        resolved = aliased_class(class_name)
        for node in class_nodes.get(resolved or class_name, []):
            for metaclass_name in counted_metaclasses(node):
                call_bodies, call_writes = metaclass_calls.get(
                    metaclass_name, ([], set())
                )
                bodies.extend(call_bodies)
                write_set.update(call_writes)
        return bodies, write_set

    targets = {key for key, write_set in writes.items() if name in write_set}

    def literal_sequences(expression, seen_names=frozenset()):
        """The element lists of the literals an expression selects through.

        A tuple or a list standing in the expression
        carries its own elements. A plain name carries
        the elements of every tuple or list the module
        level bindings resolve it to, following a name
        bound to a further name to the literal it ends
        at, so a subscript selecting through the name
        selects through the denoted literal on the same
        terms as a literal standing in the assignment
        itself. A name a loop target binds carries
        beside that route the elements of the literals
        the elements it denotes carry, read through
        the loop target element reading on the same
        terms, because the binding the bindings record
        for such a name is the iterable its header
        walks and not the element it denotes, so the
        name carries the denoted element wherever the
        resolution reaches it, standing bare in the
        expression, yielded through an arm of a
        conditional expression, an operand of a boolean
        expression, or the value a walrus expression
        yields, or standing behind a further name bound
        to such a yielding form in turn. A conditional
        expression carries the
        elements of the literals its arms carry, a
        boolean expression the elements of the literals
        its operands carry, and a walrus expression the
        elements of the literal the value it yields
        carries, each read on the same terms, because
        the value such an expression yields stands
        where the expression itself stands. A name
        bound to a subscript carries the elements of
        the literals standing among what the subscript
        evaluates to through the selection reading, on
        the same terms, because the name denotes the
        element the selection yields, so a further
        selection through the name selects out of that
        element in turn, and a subscript standing in
        the expression itself carries the same elements
        directly. A name bound to any other value, and
        an expression standing in any other form,
        carries nothing the selection can read.
        """
        if isinstance(expression, (ast.Tuple, ast.List)):
            return [expression.elts]
        if isinstance(expression, ast.IfExp):
            sequences = literal_sequences(expression.body, seen_names)
            sequences.extend(
                literal_sequences(expression.orelse, seen_names)
            )
            return sequences
        if isinstance(expression, ast.BoolOp):
            sequences = []
            for operand in expression.values:
                sequences.extend(literal_sequences(operand, seen_names))
            return sequences
        if isinstance(expression, ast.NamedExpr):
            return literal_sequences(expression.value, seen_names)
        if isinstance(expression, ast.Subscript):
            sequences = []
            for element in subscript_selected_values(expression, seen_names):
                if isinstance(element, (ast.Tuple, ast.List)):
                    sequences.append(element.elts)
            return sequences
        if isinstance(expression, ast.Name) and expression.id not in seen_names:
            sequences = []
            seen = seen_names | {expression.id}
            for bound_value in module_bindings.get(expression.id, []):
                sequences.extend(literal_sequences(bound_value, seen))
            if expression.id in loop_target_names:
                for element in loop_target_elements(
                    expression.id, seen_names
                ):
                    sequences.extend(literal_sequences(element, seen))
            return sequences
        return []

    def placed_descriptor_classes(
        value, seen_names=frozenset(), element_of=False
    ):
        """The class names whose instances a placed value puts in a namespace.

        A call names the class it instantiates, its callee
        standing in bare name form or in a subscript naming
        the class in its value position, as the base
        readings resolve one, the name it carries resolved
        through the module level bindings standing behind
        it, so a callee bound to a class or to a subscript
        of one names that class. An element of a tuple or a
        list an assignment unpacks places what the element
        places. A subscript selecting an element out of a
        tuple or a list standing in the assignment, or out
        of a tuple or a list a plain name standing in the
        assignment denotes through the module level
        bindings, places what the selected element places,
        the element read from a constant index where the
        subscript carries one and every element where it
        does not. An
        instantiation standing in an arm of a conditional
        expression places what it places in either arm, as
        the reach reads both arms of such an expression,
        so a condition the counting cannot fold over
        refuses here rather than missing the placement. An
        instantiation standing as an operand of a boolean
        expression places what it places in either
        operand, as the reach reads both operands of such
        an expression and the value the expression yields
        is one of its operands. An element a subscript
        selects through a further subscript standing as
        its value places what the element the composed
        selection yields places, the selections composing
        on the same index terms, because a subscript
        evaluates to what its own selection evaluates to.
        A
        plain name places what the module level
        bound to it where a binding value instantiates a
        class, and a name bound to a further name places
        what that name places in turn, and a name bound
        to a conditional expression places what its arms
        place, a name bound to a boolean expression
        places what its operands place, a name bound to
        a subscript places what the element the
        subscript selects places, and a name bound to a
        walrus expression places what the value the
        walrus yields places, each read on the same
        terms the reading reads the form standing in the
        assignment itself, while a name bound
        to a tuple or a list denotes that value itself and
        places nothing through it. A name the target of a
        loop binds denotes an element of the iterable it
        walks rather than the iterable itself, so such a
        name places what an element of the iterable places,
        through the bindings on the same terms.
        """
        if isinstance(value, ast.Call):
            if element_of:
                return []
            resolved = denoted_class_name(value.func)
            return [resolved] if resolved is not None else []
        if isinstance(value, (ast.Tuple, ast.List)):
            classes = []
            for element in value.elts:
                classes.extend(placed_descriptor_classes(element, seen_names))
            return classes
        if isinstance(value, ast.Subscript):
            classes = []
            for element in subscript_selected_values(value):
                classes.extend(
                    placed_descriptor_classes(element, seen_names)
                )
            return classes
        if isinstance(value, ast.IfExp):
            classes = placed_descriptor_classes(value.body, seen_names)
            classes.extend(placed_descriptor_classes(value.orelse, seen_names))
            return classes
        if isinstance(value, ast.BoolOp):
            classes = []
            for operand in value.values:
                classes.extend(placed_descriptor_classes(operand, seen_names))
            return classes
        if isinstance(value, ast.NamedExpr):
            return placed_descriptor_classes(value.value, seen_names)
        if isinstance(value, ast.Name) and value.id not in seen_names:
            classes = []
            walks_elements = element_of or value.id in loop_target_names
            for bound_value in module_bindings.get(value.id, []):
                if isinstance(bound_value, ast.Call):
                    if walks_elements:
                        continue
                    resolved = denoted_class_name(bound_value.func)
                    if resolved is not None:
                        classes.append(resolved)
                elif isinstance(bound_value, ast.Name):
                    classes.extend(
                        placed_descriptor_classes(
                            bound_value,
                            seen_names | {value.id},
                            element_of=walks_elements,
                        )
                    )
                elif isinstance(bound_value, (ast.Tuple, ast.List)):
                    if walks_elements:
                        classes.extend(
                            placed_descriptor_classes(
                                bound_value, seen_names | {value.id}
                            )
                        )
                elif isinstance(bound_value, (ast.IfExp, ast.Subscript)):
                    classes.extend(
                        placed_descriptor_classes(
                            bound_value,
                            seen_names | {value.id},
                            element_of=element_of,
                        )
                    )
                elif isinstance(bound_value, ast.BoolOp):
                    if walks_elements:
                        continue
                    classes.extend(
                        placed_descriptor_classes(
                            bound_value,
                            seen_names | {value.id},
                            element_of=element_of,
                        )
                    )
                elif isinstance(bound_value, ast.NamedExpr):
                    classes.extend(
                        placed_descriptor_classes(
                            bound_value.value,
                            seen_names | {value.id},
                            element_of=element_of,
                        )
                    )
            return classes
        return []

    def instance_call_classes(callee_name, seen_names=frozenset()):
        """The classes a called name's instances stand in, through its bindings.

        A call naming an instance dispatches on the dunder
        call method of the class the instance stands in, so
        the counting resolves the callee name through the
        module level bindings to the instantiation it
        denotes, on the terms the placement reading
        resolves a placed name by. A binding value that
        instantiates a class denotes an instance of the
        class the instantiation names, resolved through
        the bindings standing behind that name as at every
        class turning point, and a name bound to a further
        name denotes what that name denotes in turn. A
        name bound to a conditional expression denotes
        the instances its arms denote, a name bound to a
        boolean expression the instances its operands
        denote, and a name bound to a walrus expression
        the instance the value it yields denotes, each
        read on the same terms the placement reading
        reads a name bound to such a form on, because
        the value each such expression yields stands
        where the name stands. A name bound to any
        other value denotes no instance whose class
        the counting can name. The alias
        resolution's sentence denying a name bound to an
        instantiation the standing of a class name governs
        the places a name is turned into a class, and the
        call locus asks which body a call runs, so a name
        counts here for the call methods of a class while
        counting for nothing at the class turning points.
        A name a loop target binds denotes an element of
        the iterable its header walks, so an element the
        iterable denotes that instantiates a class counts
        here as an instance of that class, and an element
        standing as a further name denotes what that name
        denotes in turn, on the same element terms. A
        name bound to a subscript selecting an element
        out of a tuple or a list standing in the binding
        or denoted by a plain name standing in it denotes
        the instance the selected element denotes, the
        element read on the index terms the placement
        reading selects on, and a subscript standing on
        a further subscript denotes the instance the
        element the composed selection yields denotes,
        the selections composing on the same terms.
        """
        def value_instance_classes(value, seen_names):
            """The classes the instances one binding value denotes stand in.

            A value that instantiates a class denotes an
            instance of the class the instantiation
            names, and a name denotes what it denotes
            through the resolution itself in turn. A
            subscript denotes the instances its selected
            elements denote, read through the selection
            reading on the placement index terms, the
            selection composing through a further
            subscript standing behind it on the same
            terms. A conditional expression denotes the
            instances its arms denote, a boolean
            expression the instances its operands denote,
            and a walrus expression the instance the
            value it yields denotes, because the value
            each such expression yields is the value the
            binding holds. A value standing in any other
            form denotes no instance this reading can
            name.
            """
            if isinstance(value, ast.Call):
                resolved = denoted_class_name(value.func)
                return [resolved] if resolved is not None else []
            if isinstance(value, ast.Name):
                return instance_call_classes(value.id, seen_names)
            if isinstance(value, ast.Subscript):
                classes = []
                for element in subscript_selected_values(value, seen_names):
                    classes.extend(
                        value_instance_classes(element, seen_names)
                    )
                return classes
            if isinstance(value, ast.IfExp):
                classes = value_instance_classes(value.body, seen_names)
                classes.extend(
                    value_instance_classes(value.orelse, seen_names)
                )
                return classes
            if isinstance(value, ast.BoolOp):
                classes = []
                for operand in value.values:
                    classes.extend(
                        value_instance_classes(operand, seen_names)
                    )
                return classes
            if isinstance(value, ast.NamedExpr):
                return value_instance_classes(value.value, seen_names)
            return []

        classes = []
        if callee_name in seen_names:
            return classes
        bound_values = list(module_bindings.get(callee_name, []))
        if callee_name in loop_target_names:
            bound_values.extend(loop_target_elements(callee_name))
        for bound_value in bound_values:
            classes.extend(
                value_instance_classes(
                    bound_value, seen_names | {callee_name}
                )
            )
        return classes

    def calls(statements):
        found = []
        created = []
        dispatched = []

        def manager_classes(expression):
            """The classes a with manager or a for iterable denotes.

            The value stands as an instantiation in the
            statement, as a name the bindings resolve to
            an instantiation, as an arm of a conditional
            expression standing in the position, each arm
            read on the same terms, or as the value a
            walrus binding standing in the position binds,
            on the terms the instance
            resolution of the call locus reads a name by,
            as an operand of a boolean expression standing
            in the position, each operand read on the same
            terms, or as an element of a tuple or a list
            a subscript standing in the position selects,
            the literal standing in the subscript or
            denoted by a plain name standing in it through
            the bindings, or by a name bound to a
            subscript selecting it out of a further
            literal so denoted through the bindings, the element read on the index
            terms the placement reading selects on, the
            selection composing through a further subscript
            standing in the position on the same terms,
            and the class the instantiation names is the
            class whose protocol methods the statement
            performs.
            """
            if isinstance(expression, ast.Call):
                resolved = denoted_class_name(expression.func)
                return [resolved] if resolved is not None else []
            if isinstance(expression, ast.Name):
                return instance_call_classes(expression.id)
            if isinstance(expression, ast.IfExp):
                classes = manager_classes(expression.body)
                classes.extend(manager_classes(expression.orelse))
                return classes
            if isinstance(expression, ast.NamedExpr):
                return manager_classes(expression.value)
            if isinstance(expression, ast.BoolOp):
                classes = []
                for operand in expression.values:
                    classes.extend(manager_classes(operand))
                return classes
            if isinstance(expression, ast.Subscript):
                classes = []
                for element in subscript_selected_values(expression):
                    classes.extend(manager_classes(element))
                return classes
            return []

        def visit_decorator(expression):
            """Read one decorator standing on a definition or a class.

            A decorator standing in bare name form holds no
            call inside it to read, and its application to
            the object the statement defines as the statement
            completes is the execution the statement performs
            with it, so the name is counted as a call into
            the value it denotes, resolved in the reach as
            its callees resolve. A decorator in any other
            form is read for the calls standing inside the
            expression, and the value the expression computes
            is one the counting cannot name, so its
            application counts nothing here.
            """
            if isinstance(expression, ast.Name):
                found.append(expression.id)
            else:
                visit(expression)

        def visit_arguments(arguments):
            for default in arguments.defaults:
                visit(default)
            for default in arguments.kw_defaults:
                if default is not None:
                    visit(default)
            parameters = [
                *arguments.posonlyargs,
                *arguments.args,
                *arguments.kwonlyargs,
            ]
            if arguments.vararg is not None:
                parameters.append(arguments.vararg)
            if arguments.kwarg is not None:
                parameters.append(arguments.kwarg)
            for parameter in parameters:
                if parameter.annotation is not None:
                    visit(parameter.annotation)

        def visit(node):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    visit_decorator(decorator)
                visit_arguments(node.args)
                if node.returns is not None:
                    visit(node.returns)
                return
            if isinstance(node, ast.Lambda):
                for default in node.args.defaults:
                    visit(default)
                for default in node.args.kw_defaults:
                    if default is not None:
                        visit(default)
                return
            if isinstance(node, ast.ClassDef):
                created.append(node)
                for decorator in node.decorator_list:
                    visit_decorator(decorator)
                for part in (*node.bases, *node.keywords):
                    visit(part)
                for member in node.body:
                    visit(member)
                return
            if isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    for manager_class in manager_classes(item.context_expr):
                        if manager_class in context_methods:
                            dispatched.append(context_methods[manager_class])
                for child in ast.iter_child_nodes(node):
                    visit(child)
                return
            if isinstance(node, (ast.For, ast.AsyncFor)):
                for iterable_class in manager_classes(node.iter):
                    if iterable_class in iteration_methods:
                        dispatched.append(iteration_methods[iterable_class])
                    if iterable_class in self_returning_iterables:
                        dispatched.append(next_methods[iterable_class])
                    iter_bodies = iteration_methods.get(
                        iterable_class, ([], set())
                    )[0]
                    if iterable_class in getitem_methods and not iter_bodies:
                        dispatched.append(getitem_methods[iterable_class])
                for child in ast.iter_child_nodes(node):
                    visit(child)
                return
            if isinstance(node, ast.AugAssign):
                if isinstance(node.target, ast.Name):
                    for (
                        operator_type,
                        inplace_name,
                        plain_name,
                    ) in augmented_operators:
                        if not isinstance(node.op, operator_type):
                            continue
                        inplace_table = augmented_inplace_methods.get(
                            inplace_name, {}
                        )
                        plain_table = augmented_plain_methods.get(
                            plain_name, {}
                        )
                        for value_class in instance_call_classes(
                            node.target.id
                        ):
                            inplace_bodies = inplace_table.get(
                                value_class, ([], set())
                            )[0]
                            plain_bodies = plain_table.get(
                                value_class, ([], set())
                            )[0]
                            if inplace_bodies:
                                dispatched.append(inplace_table[value_class])
                            elif plain_bodies:
                                dispatched.append(plain_table[value_class])
                for child in ast.iter_child_nodes(node):
                    visit(child)
                return
            if isinstance(node, ast.Subscript):
                for resolved in subscript_value_class_names(node.value):
                    if resolved in class_getitem_methods:
                        dispatched.append(class_getitem_methods[resolved])
                for child in ast.iter_child_nodes(node):
                    visit(child)
                return
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    found.append(node.func.id)
                elif isinstance(node.func, ast.Lambda):
                    visit(node.func)
                    visit(node.func.body)
                else:
                    visit(node.func)
                for argument in node.args:
                    visit(argument)
                for keyword in node.keywords:
                    visit(keyword)
                return
            for child in ast.iter_child_nodes(node):
                visit(child)

        for statement in statements:
            visit(statement)
        return found, created, dispatched

    seen = set()
    queue = [calls(module_body[position + 1 :])]

    def count_placed_descriptors(placed_value):
        """Count the set name executions one placed value performs.

        Each descriptor class the placement reading
        resolves the value to contributes the set name
        methods gathered for it, and the seat answers
        true when one of those methods assigns the
        candidate name under a global declaration, the
        refusal the reach looks for, queueing the method
        bodies beside the executions already queued
        either way.
        """
        for descriptor_class in placed_descriptor_classes(placed_value):
            if descriptor_class in class_nodes:
                for descriptor_node in class_nodes[descriptor_class]:
                    set_bodies, set_writes = set_name_methods(
                        descriptor_node, {descriptor_class}
                    )
                    if name in set_writes:
                        return True
                    for body in set_bodies:
                        queue.append(calls(body))
        return False

    def count_unpacking_placements(node):
        """Count the placements the unpacking assignments of a class body make.

        The pair input the set name seat reads hands it
        each assignment's value alone, so an element an
        unpacking target binds is never read as an
        element through it. Where an assignment standing
        in the body has a single target standing as a
        tuple or a list, this reading reads the element
        each target element stands against on the
        element pairing terms, the value standing as a
        literal in the assignment or denoted by a plain
        name the bindings resolve to a literal on the
        literal sequences terms, and counts what that
        element places for the element name's class
        entries. The walk reads the body on the
        statement terms the pair collection reads one
        on, never entering a nested definition.
        """
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
                ast.Lambda,
            ),
        ):
            return False
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], (ast.Tuple, ast.List))
        ):
            sequences = []
            if isinstance(node.value, (ast.Tuple, ast.List)):
                sequences.append(list(node.value.elts))
            elif isinstance(node.value, ast.Name):
                sequences.extend(literal_sequences(node.value))
            for elements in sequences:
                if len(elements) != len(node.targets[0].elts):
                    continue
                for target_element, value_element in zip(
                    node.targets[0].elts, elements
                ):
                    element_pairs = unpacking_element_pairs(
                        target_element, value_element
                    )
                    if element_pairs is None:
                        continue
                    for _element_name, element_value in element_pairs:
                        if count_placed_descriptors(element_value):
                            return True
        for child in ast.iter_child_nodes(node):
            if count_unpacking_placements(child):
                return True
        return False

    def queue_bound_callees(bound_value, seen_names):
        """Queue the callees one bound value of a called name denotes.

        A plain name standing in the value counts as a
        called name in its turn, queued beside the calls
        already gathered, and a lambda standing in the
        value counts as a call into its body read where
        it stands in the binding. A subscript standing
        in the value denotes the callees its selected
        elements denote, read through the selection
        reading on the index terms the placement
        reading selects on, so a definition name or a
        lambda selected out of a literal standing in
        the binding or denoted by a plain name standing
        in it counts here as it counts standing in the
        binding itself, and a name bound to such a
        selection stands for the callable it yields in
        turn. A conditional expression denotes the
        callees its arms denote, a boolean expression
        the callees its operands denote, and a walrus
        expression the callee the value it yields
        denotes, because the value each such expression
        yields stands where the name stands. The name
        guard the literal sequences reading keeps
        against a name resolving through itself stands
        over the whole resolution here too, so the
        called name the expansion resolves is not
        queued again through its own bound values, and
        a name bound through selections and aliases
        back to itself ends the expansion at the name
        rather than looping it. A value standing in
        any other form denotes no callee this seat can
        name.
        """
        if isinstance(bound_value, ast.Name):
            if bound_value.id not in seen_names:
                queue.append(([bound_value.id], [], []))
        elif isinstance(bound_value, ast.Lambda):
            queue.append(calls([bound_value.body]))
        elif isinstance(bound_value, ast.Subscript):
            for element in subscript_selected_values(
                bound_value, seen_names
            ):
                queue_bound_callees(element, seen_names)
        elif isinstance(bound_value, ast.IfExp):
            queue_bound_callees(bound_value.body, seen_names)
            queue_bound_callees(bound_value.orelse, seen_names)
        elif isinstance(bound_value, ast.BoolOp):
            for operand in bound_value.values:
                queue_bound_callees(operand, seen_names)
        elif isinstance(bound_value, ast.NamedExpr):
            queue_bound_callees(bound_value.value, seen_names)

    while queue:
        found, created, dispatched = queue.pop()
        for protocol_bodies, protocol_writes in dispatched:
            if name in protocol_writes:
                return True
            for body in protocol_bodies:
                queue.append(calls(body))
        for node in created:
            hook_bodies, hook_writes = subclass_hooks(node, frozenset())
            if name in hook_writes:
                return True
            for body in hook_bodies:
                queue.append(calls(body))
            for _placed_targets, placed_value in _assignment_pairs(node.body):
                if count_placed_descriptors(placed_value):
                    return True
            for member in node.body:
                if count_unpacking_placements(member):
                    return True
            named_metaclass = None
            names_a_metaclass = False
            for keyword in node.keywords:
                if keyword.arg == "metaclass":
                    names_a_metaclass = True
                    resolved = denoted_class_name(keyword.value)
                    if resolved is not None and resolved in class_nodes:
                        named_metaclass = resolved
            if named_metaclass is not None:
                queue.append(([named_metaclass], [], []))
            elif not names_a_metaclass:
                for candidate in counted_metaclasses(node):
                    queue.append(([candidate], [], []))
        for called in found:
            resolved = aliased_class(called)
            counted = resolved if resolved is not None else called
            if counted in targets:
                return True
            if called in seen:
                continue
            seen.add(called)
            for body in callees.get(counted, []):
                queue.append(calls(body))
            call_bodies, call_writes = metaclass_call_executions(counted)
            if name in call_writes:
                return True
            for body in call_bodies:
                queue.append(calls(body))
            for instance_class in instance_call_classes(called):
                instance_bodies, instance_writes = metaclass_calls.get(
                    instance_class, ([], set())
                )
                if name in instance_writes:
                    return True
                for body in instance_bodies:
                    queue.append(calls(body))
            bound_values = list(module_bindings.get(called, []))
            if called in loop_target_names:
                bound_values.extend(loop_target_elements(called))
            for bound_value in bound_values:
                queue_bound_callees(bound_value, frozenset({called}))
    return False


def _derive_loaders(filename: str) -> dict:
    """The loader name slots derived from a module, by name.

    Each member maps to the slot of its fixture name
    argument, the positional index and the parameter name a
    call fills when it hands a fixture name over. The reader
    at the bottom of the module seeds the set through the
    seed proof, and a helper that calls a loader joins
    through the caller proof against the slots as they
    stand. Admission is iterated to a fixed point and then
    verified against the finished set, the seed members by
    re-running the seed proof and the caller members by
    re-running the caller proof against the finished slots
    without their own, so every member still provably loads
    the fixture it is handed beside the other members, and a
    member whose proof depended on a member the verification
    refused is refused in turn. Before any of that, a
    candidate passes an admission step of its own, which
    refuses a definition whose body holds a yield outside a
    nested definition, a definition carrying a decorator,
    a definition whose name a later module level
    statement rebinds, and a definition whose name an
    execution the module level reaches after it
    rewrites, the write sets gathered from every module
    level definition, from every definition standing
    in a class body on the same terms, and from the
    construction methods of module level classes
    wherever they stand, the dunder prepare method
    beside the dunder new method and the dunder init
    method, each designated method counting where it
    stands as a definition anywhere in the class body
    on the statement terms the body is read on and
    where an assignment in the body binds its name on
    the same terms, the assignment binding it
    directly or pairing it by an unpacking assignment
    with the element standing at its own place in a
    tuple or list value of the same length, a plain name value
    resolving through the module level definitions and
    a lambda value read where it stands, and all three
    inherited through the module level base classes a
    class names, each name resolving through the
    module level assignment bindings to the class it
    denotes, a name bound to a class name or to a
    subscript of one counting as that class wherever a
    name is turned into a class, the bindings
    themselves gathered on the statement terms the
    assignment pair collection reads a body on, a
    plain assignment, an annotated assignment
    carrying a value, a walrus binding standing in an
    expression, and a loop target standing in a loop
    header alike, the value standing behind a loop
    target being the iterable the header walks, a
    name a loop target binds denoting an element of
    that iterable at the seats that resolve a name
    to a value, a subscript standing on such a
    name, or on a value yielding such a name
    through an arm of a conditional expression, an
    operand of a boolean expression, or the value
    a walrus expression yields, or on a further
    name bound to such a yielding form, selecting
    out of that element beside the module bindings
    route on the placement index terms, a name an
    unpacking loop target
    binds denoting the component standing at its
    own place in the element it unpacks, paired on
    the same terms, and the elements of an element
    standing behind a loop target name a further
    loop walks, so a chain of loop targets resolves
    at every level, an
    assignment unpacking a single tuple or list
    target against a tuple or list value of the same
    length pairing each name it binds with the
    element standing at its place, recursively where
    an element itself unpacks, and a call naming a
    class counting through the reach as a call into
    the dunder call method of the metaclass it stands
    under beside its construction, counted at the call
    and not at the creation of the class, a plain call
    resolving its callee name through the module level
    assignment bindings standing behind it, a name
    bound to a plain name counting as a call into the
    definition standing at the end of the chain of
    such bindings and a name bound to a lambda
    counting as a call into the lambda body read where
    it stands in the binding, a name bound to a
    subscript selecting a callable out of a literal
    standing in the binding or denoted by a plain
    name standing in it counting as a call into the
    callable the selection yields, a definition name
    so selected counting as a call into that
    definition and a lambda so selected as a call
    into its body read where it stands, and a name
    bound to a conditional expression, a boolean
    expression, or a walrus expression counting as a
    call into the callable the value it yields
    denotes, the name guard against a name resolving
    through itself standing over the resolution, a
    call naming an instance
    counting as a call into the dunder call methods of
    the class the instance stands in, resolved through
    the bindings to the instantiation the name denotes
    and following a name bound to a further name to
    its instantiation in turn, or bound to a
    conditional expression, a boolean expression, or
    a walrus expression whose yielded values denote
    instances in turn, or bound to a
    subscript selecting an instantiation out of a
    literal, the selection composing through a
    further subscript standing behind it on the same
    terms, and each decorator
    standing on a definition or a class in an executing
    position in bare name form counting as a call into
    the value the name denotes, resolved as the reach
    resolves its callees, and the
    reach closing over the calls
    the statements after it make, through the bodies
    those calls run, the headers a definition statement
    performs as it runs, the headers a class statement
    performs as it runs, the executions a class creation
    performs through the subclass hooks of the bases it
    names, a base standing in a subscript counting as
    the plain name in its value position in that
    reading and in every base reading the admission
    performs, through the set name hooks of the
    descriptor classes whose instances stand assigned
    in its body, placed there on the statement terms
    of the body itself, by an assignment standing
    directly in the body or in an arm of a compound
    statement among its statements, by an element of
    a tuple or a list the assignment unpacks, the
    tuple or list standing in the assignment or
    denoted by a plain name standing in it through
    the bindings, by a
    subscript selecting an element out of a tuple or
    a list standing in the assignment or denoted by
    a plain name standing in it through the bindings,
    or by a name bound to a subscript selecting it
    out of a further literal so denoted through the
    bindings, the selection composing through a further
    subscript standing as its value on the same
    terms, by an
    instantiation standing in an arm of a conditional
    expression the assignment evaluates, by an
    instantiation standing as an operand of a boolean
    expression the assignment evaluates, by an
    instantiation whose callee stands in a subscript
    naming the class in its value position, or by a
    plain name the module level bound to an
    instantiation of the class, or to a value
    standing in one of the expression forms this
    passage reads standing in the assignment itself,
    the value a walrus expression yields among
    them, or a loop target
    bound to an element of the iterable it walks
    where an element instantiates the class, the
    bodies of classes standing inside the bodies those
    calls run read on the same terms as the bodies of
    classes at module level, and through the
    construction of the metaclass its keyword names
    or, where it names none, of the most derived
    metaclass its bases stand under, the prepare
    method of that metaclass standing in its
    construction gathering beside its construction
    methods, and through the protocol executions a
    statement performs as it runs, a with statement
    counting as a call into the dunder enter and
    dunder exit methods of the class whose instance
    its manager position denotes, an inline
    instantiation, a name the bindings resolve to
    one, an instantiation an arm of a conditional
    expression standing in the position evaluates to,
    or the instantiation a walrus binding standing in
    the position binds, an instantiation standing as
    an operand of a boolean expression standing in
    the position, or an element of a tuple or list a
    subscript standing in the position selects, the
    literal standing in the subscript or denoted by
    a plain name standing in it through the bindings,
    or by a name bound to a subscript selecting it
    out of a further literal so denoted through the
    bindings, the selection composing through a further
    subscript standing in the position on the same
    terms,
    gathered on the same installation terms
    through the base classes the class names, a for
    statement counting as a call into the dunder iter
    method of the class its iterable denotes on the
    same widened resolution and into the dunder next method
    of the same class where the gathered iter method
    returns the instance itself, standing as the
    parameter name alone, through a name its body
    binds to its first parameter on the binding terms
    the reach states, through a walrus expression
    yielding it, as an operand of a boolean
    expression yielding it, or through an arm
    of a conditional expression returning it in
    any of those forms, or as an element a
    subscript selects out of a literal tuple or
    list holding it, the literal standing in the
    subscript or denoted by a name the body binds
    to one, directly or through an expression
    yielding one on the same terms, an arm of a
    conditional expression, an operand of a boolean
    expression, the value a walrus expression
    yields, or the selection a subscript performs,
    a selection selecting a name the body binds
    to one counting as the literal that name
    denotes in its turn, the name followed through
    the body's own literal reading on the same
    terms, or standing in the subscript as the
    value a walrus expression yields, as an operand
    of a boolean expression, in an arm of a
    conditional expression, or behind an inner
    subscript selecting it out of a further literal,
    and into the dunder
    getitem method of the same class where no dunder
    iter method stands in its chain, the sequence
    fallback the statement performs in the iter
    method's absence, other shapes of iter
    return standing on the return value ground this
    reading does not model, an augmented assignment
    counting as a call into the in place method its
    operator names, the dunder iadd method for the
    additive operator and its siblings for the
    remaining operators, of the class the value its
    target name denotes
    stands in, or into the plain method of the same
    operation of that class where no in place
    method stands in its
    chain, and a subscript whose
    value position resolves to a module level class,
    a conditional expression standing in the value
    position resolving to the classes of both its
    arms, a boolean expression resolving to the
    classes of its operands, and a walrus
    expression resolving to the class of the value
    it yields, and a subscript standing in the
    value position resolving to the classes of the
    elements it selects out of a literal, the
    literal standing in the inner selection itself
    or yielded there by an arm of a conditional
    expression, an operand of a boolean expression,
    or the value a walrus expression yields, or
    denoted there by a name bound to a subscript
    selecting it out of a further literal so
    standing, and a name standing in the value
    position bound to a subscript whose own value
    position holds such a yielding form or a loop
    target name, or bound through such a yielding
    form to the value the form yields, a name so
    yielded resolved on the same terms in turn, or
    bound to a subscript whose own value position
    holds a name bound to such a yielding form,
    the yielded loop target name standing in the
    value position on the same principle,
    resolving beside the denotation
    the bare name takes to the classes of the
    elements that subscript's selection yields on
    the same terms,
    counting as a call into the dunder class getitem
    method of that class wherever the reach reads the
    subscript as an execution, and the bodies of the lambdas a statement
    invokes, because
    the proofs judge one body and each of those shapes
    can leave the name denoting a callable that body
    never runs in.
    """
    path = Path(__file__).parent / filename
    source = path.read_text()
    tree = ast.parse(source)
    helpers = {}
    for position, node in enumerate(tree.body):
        if not isinstance(node, ast.FunctionDef) or node.name.startswith("test_"):
            continue
        if node.decorator_list:
            continue
        if _body_holds_a_yield(node.body):
            continue
        if _later_statement_rebinds(tree.body[position + 1 :], node.name):
            continue
        if _later_call_rewrites(tree.body, position, node.name):
            continue
        helpers[node.name] = node
    seeds = {}
    for name, node in helpers.items():
        parameter = _seed_name_parameter(node, source)
        if parameter is not None:
            seeds[name] = parameter
    slots = {
        name: (_parameter_index(helpers[name], parameter), parameter)
        for name, parameter in seeds.items()
    }
    while True:
        growing = True
        while growing:
            growing = False
            for name, node in helpers.items():
                if name not in slots:
                    parameter = _helper_name_parameter(node, source, slots)
                    if parameter is not None:
                        slots[name] = (_parameter_index(node, parameter), parameter)
                        growing = True
        refused = set()
        for name in slots:
            if name in seeds:
                parameter = _seed_name_parameter(helpers[name], source)
            else:
                others = {key: slot for key, slot in slots.items() if key != name}
                parameter = _helper_name_parameter(helpers[name], source, others)
            if parameter is None or slots[name][1] != parameter:
                refused.add(name)
        if not refused:
            return slots
        for name in refused:
            slots.pop(name, None)


def _loader_function_names(filename: str) -> set[str]:
    """Names of the module level helpers that load a fixture by name.

    The set is derived from the module itself, and membership
    is a claim about faithfulness as much as about
    reachability. The reader at the bottom is the helper whose
    own body reads a file from disk, and it joins only when a
    proof of the same strength as the caller proof, run with
    a distinct symbolic fixture name bound to each of its
    parameters and its reads standing as loading calls, credits
    exactly the symbolic name of the parameter it was handed
    on every path, so a reader that diverts the name it is
    handed or reads its argument as a decoy is refused. A
    helper that calls a loader joins only when it hands over
    the name it was given on every path, proven by the same
    single analysis, in which only the argument sitting in
    the name slot of a loader call can earn credit, so the
    payload helper and the search and details replayers join
    through the readers they call, while a helper that drops
    its argument, loads a fixed name of its own, passes its
    argument on only some paths, or earns its credit through
    an argument that carries no fixture name is refused.
    Admission is iterated to a fixed point and then verified
    against the finished set, so every member still provably
    loads the fixture it is handed beside the other members.
    Test functions never join, because nothing loads a fixture
    through a test.

    Admission to the proofs is itself guarded, because a
    proof judges the body of one definition and two things
    can leave a call into the name running something else.
    A candidate whose own body holds a yield or a yield
    from outside any nested definition is a generator
    function, and calling it runs none of its body, so it
    is refused as deferred code of the kind the guard
    refuses everywhere else. A candidate carrying a
    decorator is refused, because the decorator may
    replace the function at definition time with a callable
    the walk cannot see. And a candidate whose name a
    later module level statement rebinds, by a plain or
    annotated assignment, by a binding standing in the
    head of a compound statement, the target of a with
    item or a name a match pattern captures, by a further
    definition or class of the same name, or by an import,
    is refused, because the name a test calls then denotes
    the later binding and not the body the proof would
    judge. And a candidate whose name an execution
    the module level reaches after it assigns under a
    global declaration is refused. The write sets are
    gathered from every module level definition, from
    every definition standing in a class body on the
    same terms, and from the construction methods of
    every module level class, wherever they stand, the
    dunder prepare method beside the dunder new method
    and the dunder init method, each designated
    method, the construction methods, the subclass
    hooks, and the set name methods alike, counting
    where it stands as a definition anywhere in the
    class body on the statement terms the body is read
    on and where an assignment in the body binds its
    name on the same terms, directly or paired by an
    unpacking assignment with the element standing
    at its own place in a tuple or list value of the
    same length, to a plain name
    resolving through the module level definitions or
    to a lambda read where it stands, and all three
    gathered through the module level base classes a
    class names, each name resolving through the
    module level assignment bindings to the class it
    denotes to the end of the chain, the bindings
    themselves gathered on the statement terms the
    assignment pair collection reads a body on, a
    plain assignment, an annotated assignment
    carrying a value, a walrus binding standing in an
    expression, and a loop target standing in a loop
    header alike, the value standing behind a loop
    target being the iterable the header walks, a
    name a loop target binds denoting an element of
    that iterable at the seats that resolve a name
    to a value, a subscript standing on such a
    name, or on a value yielding such a name
    through an arm of a conditional expression, an
    operand of a boolean expression, or the value
    a walrus expression yields, or on a further
    name bound to such a yielding form, selecting
    out of that element beside the module bindings
    route on the placement index terms, a name an
    unpacking loop target
    binds denoting the component standing at its
    own place in the element it unpacks, paired on
    the same terms, and the elements of an element
    standing behind a loop target name a further
    loop walks, so a chain of loop targets resolves
    at every level, an
    assignment unpacking a single tuple or list
    target against a tuple or list value of the same
    length pairing each name it binds with the
    element standing at its place, recursively where
    an element itself unpacks, a call naming a
    class counting as a call
    into its construction and into the dunder call
    method of the metaclass it stands under, counted
    at the call and not at the creation of the class,
    a plain call resolving its callee name through
    the module level assignment bindings standing
    behind it, a name bound to a plain name counting
    as a call into the definition standing at the end
    of the chain of such bindings and a name bound to
    a lambda counting as a call into the lambda body
    read where it stands in the binding, a name bound
    to a subscript selecting a callable out of a
    literal standing in the binding or denoted by a
    plain name standing in it counting as a call into
    the callable the selection yields, a definition
    name so selected counting as a call into that
    definition and a lambda so selected as a call
    into its body read where it stands, and a name
    bound to a conditional expression, a boolean
    expression, or a walrus expression counting as a
    call into the callable the value it yields
    denotes, the name guard against a name resolving
    through itself standing over the resolution, a
    call naming
    an instance counting as a call into the dunder
    call methods of the class the instance stands in,
    resolved through the bindings to the instantiation
    the name denotes and following a name bound to a
    further name to its instantiation in turn, or
    bound to a conditional expression, a boolean
    expression, or a walrus expression whose yielded
    values denote instances in turn, or
    bound to a subscript selecting an instantiation
    out of a literal, the selection composing through
    a further subscript standing behind it on the
    same terms, and
    each decorator standing on a definition or a class
    in an executing position in bare name form counting
    as a call into the value the name denotes, resolved
    as the reach resolves its callees, and the reach is read from
    the statements standing after the candidate, bare
    or in an arm of a compound statement among them,
    counting the bodies of the classes standing at
    module level among them, which run as their
    definitions run, and closing over the calls those
    statements make into the bodies of the definitions
    they call and the construction methods of the
    classes they construct, reading beside those calls
    the parts of a definition that evaluate as its
    statement runs, its decorator expressions and its
    default values and its annotations, the parts of
    a class that evaluate as its statement runs, its
    decorator expressions and its base expressions and
    its keyword values, in any executing position, the
    bodies of classes standing inside a body the reach
    has entered read on the same terms as the bodies
    of classes at module level, and the executions a
    class creation performs, a call into the subclass
    hooks of the module level bases the class names,
    resolved through the base chain, a
    base standing in a subscript counting as the plain
    name in its value position in that reading and in
    every base reading beside it, and a name bound at
    module level to a class name or to a subscript of
    one counting as that class wherever a name is
    turned into a class, a call into the set
    name hooks of the descriptor classes whose
    instances stand assigned in the class body, placed
    there on the statement terms of the body itself,
    by an assignment standing directly in the body or
    in an arm of a compound statement among its
    statements, by an element of a tuple or a list the
    assignment unpacks, the tuple or list standing in
    the assignment or denoted by a plain name
    standing in it through the bindings, by a subscript selecting an
    element out of a tuple or a list standing in the
    assignment or denoted by a plain name standing in
    it through the bindings, or by a name bound to a
    subscript selecting it out of a further literal
    so denoted through the bindings, the selection composing
    through a further subscript standing as its value
    on the same terms, by an instantiation standing in an arm
    of a conditional expression the assignment
    evaluates, by an instantiation standing as an
    operand of a boolean expression the assignment
    evaluates, by an instantiation whose callee stands
    in a subscript naming the class in its value
    position, or by a plain name the module level
    bound to an instantiation of the class, or to a
    value standing in one of the expression forms
    this passage reads standing in the assignment
    itself, the value a walrus expression yields
    among them, or a loop
    target bound to an element of the iterable it
    walks where an element instantiates the class,
    their own or inherited through their module level
    base classes resolved in the same
    way, and a call into the
    construction of the metaclass its keyword names
    or, where it names none, of the most derived
    metaclass its bases stand under, the prepare
    method of that metaclass gathered beside its
    construction methods in the same way, and a call
    into the protocol methods a statement performs as
    it runs, the dunder enter and dunder exit methods
    of the class a with statement's manager position
    denotes, the position denoting an inline
    instantiation, a name the bindings resolve to
    one, an instantiation an arm of a conditional
    expression in the position evaluates to, or the
    instantiation a walrus binding in the position
    binds, an instantiation standing as an operand
    of a boolean expression in the position, or an
    element of a tuple or list a subscript in the
    position selects, the literal standing in the
    subscript or denoted by a plain name through the
    bindings, or by a name bound to a subscript
    selecting it out of a further literal so denoted
    through the bindings, the selection composing through a
    further subscript standing in the position on
    the same terms, the dunder iter method of the class a
    for statement's iterable denotes on the same
    terms and the dunder next method of the same
    class where its gathered iter method returns the
    instance itself, standing as the parameter name
    alone, through a name its body binds to its first
    parameter on the binding terms the reach states,
    through a walrus expression yielding it, as an
    operand of a boolean expression yielding it, or
    through an arm of a conditional expression
    returning it in any of those forms, or as an
    element a subscript selects out of a literal
    tuple or list holding it, the literal standing
    in the subscript or denoted by a name the body
    binds to one, directly or through an expression
    yielding one on the same terms, an arm of a
    conditional expression, an operand of a boolean
    expression, the value a walrus expression
    yields, or the selection a subscript performs,
    a selection selecting a name the body binds
    to one counting as the literal that name
    denotes in its turn, the name followed through
    the body's own literal reading on the same
    terms, or standing in the subscript as
    the value a walrus expression yields, as an
    operand of a boolean expression, in an arm of
    a conditional expression, or behind an inner
    subscript selecting it out of a further literal,
    the dunder getitem method of the same class
    where no dunder iter method stands in its chain,
    the in place method of the operation an
    augmented assignment performs, the dunder iadd
    method for the additive operator and its
    siblings for the remaining operators, of the
    class the value its target name denotes
    stands in, or the plain method of the same
    operation of that class where no in place
    method stands, and the
    dunder class getitem method of a class a
    subscript's value position resolves to, a
    conditional expression standing in the value
    position resolving to the classes of both its
    arms, a boolean expression resolving to the
    classes of its operands, and a walrus
    expression resolving to the class of the value
    it yields, and a subscript standing in the
    value position resolving to the classes of the
    elements it selects out of a literal, the
    literal standing in the inner selection itself
    or yielded there by an arm of a conditional
    expression, an operand of a boolean expression,
    or the value a walrus expression yields, or
    denoted there by a name bound to a subscript
    selecting it out of a further literal so
    standing, and a name standing in the value
    position bound to a subscript whose own value
    position holds such a yielding form or a loop
    target name, or bound through such a yielding
    form to the value the form yields, a name so
    yielded resolved on the same terms in turn, or
    bound to a subscript whose own value position
    holds a name bound to such a yielding form,
    the yielded loop target name standing in the
    value position on the same principle,
    resolving beside the denotation
    the bare name takes to the classes of the
    elements that subscript's selection yields on
    the same terms, each
    gathered on the same installation terms through
    the base classes the class names, and the body
    of a lambda a call invokes where it stands, because
    the name then denotes what the execution leaves
    behind rather than the body under proof. The refusal
    keys on the execution, so an installer no execution
    reaches refuses nothing, since the name still
    denotes the body it was certified on. Each refusal
    stands in the admission step, before any proof runs,
    and fails closed.
    """
    return set(_derive_loaders(filename))


def _fixtures_a_test_loads(
    source: str,
    loaders: set[str],
    initial_bindings: dict | None = None,
    name_slots: dict | None = None,
    path_credits: list | None = None,
    raised_credits: list | None = None,
    credit_reads: bool = False,
) -> set[str]:
    """Fixture file names one test hands to a loading helper.

    The test body is walked in program order, tracking the fixture
    names each local name is bound to as the walk reaches each
    statement. A name counts when a loading call hands over the
    literal itself, or hands over a local name whose binding in
    effect at that call carries the literal, alone or inside a
    tuple or list, or hands over a loop variable whose binding in
    effect at the call carries it. A name bound and then rebound
    before the call earns credit only for the binding the call
    actually reads, so a shadowed binding earns nothing. A name
    that only sits in a comment, in a docstring, or in an
    assignment no loading call consumes is not in the returned
    set, and neither is a value the walk cannot resolve to fixture
    name literals, such as the return of a call into another
    module. Unresolvable shapes earn no credit, so a test shaped
    that way fails the accounting check rather than passing it.

    Control flow regions combine by a conservative join. At a
    conditional, a loop, a try, a with, or a match, the walk forks the
    environment and the credited set together, walks each arm
    or body from the fork, and joins the results. A name keeps
    a resolved binding after the region only when every path
    through the region ends holding the identical binding for
    it. The untouched path of a conditional without an else arm
    counts as one of the paths, and so does the path where a
    loop body never runs and the path where no arm of a match
    fits, so a name bound inside one arm or inside a loop body
    reads as unresolvable after the region unless every path
    binds it to the same fixture names. The body of a try, each
    of its handlers, and its else arm are separate paths into
    the join, and its finally arm walks from the joined
    environment because it runs on every path. A walrus binding
    inside an expression applies at its position in the walk,
    so a name rebound by a walrus resolves to the walrus value
    from that point on, and a walrus that hands a fixture name
    to a loading call earns the credit for it.

    The credited set joins by intersection over the same paths,
    so a fixture counts as loaded only when a loading call
    resolving to it runs on every path through a region, and a
    call sitting in an arm, a handler, or a loop body that may
    never run earns nothing. One loop shape is exempt from the
    path where its body never runs. A loop over a literal
    sequence with at least one element, or a while loop on a
    true constant, whose body carries no break, continue,
    return, or raise that could carry control past its calls
    runs its body on every path, so credit recorded in such a
    body survives the join, and the shipped loop variable loads
    run through exactly that shape.

    The state a loop leaves behind is modelled as the
    interpreter leaves it. Inside the body the target resolves
    to every element of its literal iterable, because the body
    runs once per element and loads each in turn. The loop
    ends holding the last element alone, and a name the body
    derived from the target ends holding the value the last
    pass left in it, so the fall through end of a loop over a
    literal sequence is taken from a final pass over the body
    with the target narrowed to its last element, and a
    loading call after the loop resolves the target, and any
    name derived from it, to that element and no other. A loop
    whose body carries a bypass can stop at any pass, and a
    loop whose iterable is not an ordered literal has no last
    element the walk can name, so the target and the names
    derived from it read as unresolvable in the end state of
    such a loop instead, while the credit the body itself
    recorded stands either way. Credit in a finally arm is
    ordinary straight line credit, because the finally arm runs
    on every path. A loading call inside a nested function
    definition or a lambda earns no credit at all, because such
    a body runs only when it is called and a call into it is one
    the walk cannot see into, the same helper treatment a call
    into another module receives, though the decorators and
    default values of a definition are scanned because they
    evaluate when the definition does.

    A nested definition is not inert for bindings, though. A
    name it declares nonlocal or global is a name it may write
    into a scope outside itself when it is called, and the
    walk cannot see when or whether the write lands, so such a
    name reads as unresolvable from the statement of the
    definition onward, in a test body and in a helper under a
    derivation proof alike. A definition inside a class body
    writes back the same way, because a method's nonlocal
    declaration names the enclosing function scope, past the
    class namespace its other assignments land in.

    The walk also models a path ending. A return ends its
    path where it stands, and the credit it holds stands
    frozen toward the whole test, because a returned test has
    run to completion and the code after the return runs on
    no path at all. A raise, a break, or a continue ends the
    path of the block holding it in the same way, and the
    statements after any of them in the same block are dead
    code, earning no credit and no binding effects. Code
    after a region extends only the paths that fell through
    it, so when every path through a region ends, the rest
    of the block holding it is dead too. A try carries a
    raised path onward through its handlers, and a with
    body forks like any other region, its raised paths
    resuming after the with holding their state at the
    raise, because a context manager may suppress the
    exception. A raise nothing catches ends the test in
    failure rather than in completion, so the walk counts
    only the paths that complete. The with model covers
    abandonment by a raise statement, which is the
    abandonment the walk can see. An exception raised while
    an expression inside a with body evaluates abandons the
    body in the same way at runtime, silently under a
    suppressing manager, and whether such an expression
    raises can turn on data no static reading of the test
    source carries, so that abandonment stands as a named
    residual outside the guard's static contract, and a
    loading call standing after an expression in a with
    body is credited as the fall through path credits it.

    The expression scan carries the same discipline. A
    comprehension body earns credit only under the loop
    exemption, on a provably nonempty literal sequence,
    and the body of a generator expression earns nothing
    at all, because whether it is ever consumed is
    unprovable and its body is deferred code. The right
    operand of a boolean operation earns credit only when
    every operand before it is a constant that guarantees
    its evaluation. A conditional expression forks its two
    branches and joins them by intersection, with a name
    resolving differently across them reading as
    unresolvable. The message of an assert evaluates only
    on the path where the test fails, so it earns nothing.
    A class body walks in a forked environment whose
    bindings are discarded when the definition ends, so
    its assignments stay in the class namespace the
    interpreter gives them, while a loading call written
    in the body still earns credit, because the body runs
    when the class is defined. Every construct the walk
    touches is modelled in these terms or refused, apart
    from the one named residual above, and a shape it
    cannot model resolves to no credit and fails the
    accounting check closed.

    Three further modes serve the loader derivation proofs
    and are never used on a test body. With a slot table in
    force, a loading call credits only the argument standing
    in the name slot of the loader it calls, so credit traces
    to the one parameter in that position. With the credited
    set of every completing path collected beside the walk,
    a proof can require one credited set on all of them
    rather than the intersection the walk returns. With disk
    reads credited, a read stands as a loading call whose
    name argument is its target, so the reader at the bottom
    of a module is proven in the same terms as a helper that
    calls a loader. The proofs also collect the credited set
    of every path that ends in a raise, and a candidate is
    refused when a raised path holds credit for anything but
    the one symbolic name its completing paths proved,
    because a caller can suppress the raise and run on
    whatever the path loaded before it ended, so a load
    standing on such a path is a load the candidate can lend
    its name to. That counting belongs to the proofs alone.
    The walk of a test body collects no raised ends, because
    a path that raises in a test body is a test that failed,
    and its fixtures earn nothing toward the result either
    way.
    """
    function = ast.parse(source).body[0]
    loaded = set()
    env = dict(initial_bindings) if initial_bindings else {}
    own_parameters = {
        argument.arg
        for argument in (
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
            *([function.args.vararg] if function.args.vararg is not None else []),
            *([function.args.kwarg] if function.args.kwarg is not None else []),
        )
    }
    read_pairs = _assignment_pairs(function.body) if credit_reads else []
    unbound = object()
    # The walk state record holds whether the path being
    # walked is still alive, the credit frozen by the paths
    # that have already returned, and the depth of credit
    # suppression in force, one record every branch shares.
    flow = {"alive": True, "finished": None, "suppress": 0}
    try_types = (ast.Try,)
    if hasattr(ast, "TryStar"):
        try_types = try_types + (ast.TryStar,)

    def value_of(expression):
        """The fixture names an expression may evaluate to.

        The result is a frozenset of names, or None when the walk
        cannot resolve the expression to fixture name literals. A
        name with no binding in effect, a call, and every other
        expression form resolve to None, so a loading call fed
        such a value earns no fixture name.
        """
        if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
            return frozenset([expression.value])
        if isinstance(expression, (ast.Tuple, ast.List)):
            names = set()
            for element in expression.elts:
                part = value_of(element)
                if part is None:
                    return None
                names.update(part)
            return frozenset(names)
        if isinstance(expression, ast.Name):
            return env.get(expression.id)
        if isinstance(expression, ast.Starred):
            return value_of(expression.value)
        if isinstance(expression, ast.NamedExpr):
            result = value_of(expression.value)
            bind(expression.target, result)
            return result
        return None

    def bind(target, value):
        """Record one binding, with value a name set or None."""
        if isinstance(target, ast.Name):
            env[target.id] = value
        elif isinstance(target, ast.Starred):
            bind(target.value, value)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                bind(element, None)

    def pattern_names(pattern):
        """The local names a match pattern binds."""
        names = []
        for node in ast.walk(pattern):
            if isinstance(node, (ast.MatchAs, ast.MatchStar)):
                if node.name is not None:
                    names.append(node.name)
            elif isinstance(node, ast.MatchMapping):
                if node.rest is not None:
                    names.append(node.rest)
        return names

    def writeback_names(node):
        """The names a definition subtree declares global or nonlocal.

        A declaration anywhere in the subtree counts, at any
        depth, because the walk cannot see which nested body
        a call reaches, and every such name is one a call into
        the definition may write in a scope outside the body
        that declares it.
        """
        names = set()
        for sub in ast.walk(node):
            if isinstance(sub, (ast.Global, ast.Nonlocal)):
                names.update(sub.names)
        return names

    def body_has_bypass(statements):
        """Whether a loop body can carry control past its calls.

        A break or a continue at the loop's own level, or a
        return or a raise anywhere in the body outside a nested
        definition, can carry control past a loading call the
        body holds, so a body carrying any of them proves
        nothing about the calls it holds. A break or a continue
        inside a nested loop binds to that loop and does not
        count, and a nested definition is never entered.
        """

        def visit(node, depth):
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
            ):
                return False
            if isinstance(node, (ast.Break, ast.Continue)):
                return depth == 0
            if isinstance(node, (ast.Return, ast.Raise)):
                return True
            child_depth = depth
            if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
                child_depth = depth + 1
            return any(
                visit(child, child_depth) for child in ast.iter_child_nodes(node)
            )

        return any(visit(statement, 0) for statement in statements)

    def target_derived_names(statements, seed):
        """The names a loop body derives from the loop target.

        A name is derived when some assignment in the body
        binds it from a value that mentions a derived name,
        read syntactically over the whole body, so the set is
        a safe over reading that also covers derivations on
        paths the walked pass may not take. It serves the loop
        end state, where a value left by a pass the walk
        cannot name must read as unresolvable. Nested
        definitions are not entered, because their assignments
        bind in their own scope and the walk never enters them
        either.
        """
        pairs = _assignment_pairs(statements)
        derived = {seed}
        growing = True
        while growing:
            growing = False
            for targets, value in pairs:
                if any(
                    isinstance(sub, ast.Name) and sub.id in derived
                    for sub in ast.walk(value)
                ):
                    for name in targets:
                        if name not in derived:
                            derived.add(name)
                            growing = True
        return derived

    def record_call(call):
        if flow["suppress"]:
            # The call sits where the interpreter may skip its
            # evaluation, so it earns no credit.
            return
        arguments = [*call.args, *(keyword.value for keyword in call.keywords)]
        for argument in arguments:
            names = value_of(argument)
            if names:
                loaded.update(names)

    def fold_returned(credit):
        """Freeze the credit of a path that returned.

        A returned test has run to completion, so the fixtures
        the path loaded are one of the sets the whole test is
        intersected against, and a fixture it never loaded can
        earn no credit from code it never reaches. The set is
        also recorded whole in the path credits when a
        derivation proof is collecting them, so the proof can
        judge every completing path on its own set rather
        than on the intersection alone.
        """
        if path_credits is not None:
            path_credits.append(set(credit))
        if flow["finished"] is None:
            flow["finished"] = set(credit)
        else:
            flow["finished"].intersection_update(credit)

    def record_slot_call(call, slot):
        """Credit a loading call through its name slot alone.

        The slot is the position and the parameter name of the
        fixture name argument of the loader being called, as
        the derivation recorded them when the loader was
        itself proven. Only the argument standing in that slot
        earns credit, by keyword when the call names it and
        otherwise by position, and a call whose slot a starred
        argument leaves unplaceable earns nothing, so credit
        in a derivation proof can arrive only through the
        parameter that occupies the name position.
        """
        if flow["suppress"]:
            return
        index, parameter = slot
        argument = None
        for keyword in call.keywords:
            if keyword.arg == parameter:
                argument = keyword.value
                break
        if argument is None and index is not None and index < len(call.args):
            if not any(
                isinstance(arg, ast.Starred) for arg in call.args[: index + 1]
            ):
                argument = call.args[index]
        if argument is None:
            return
        names = value_of(argument)
        if names:
            loaded.update(names)

    def dependence_names(name):
        """The fixture names an unresolvable local may derive from.

        The local's assignments in the walked body are traced
        through the shared assignment pair reading, so a read
        target built in a local from a handed parameter still
        resolves to that parameter. The result is the set of
        fixture names the trace reaches, or None when the
        trace reaches a name bound from a value the pairs do
        not explain, or a handed parameter the walk never
        bound, because a read fed by such a local earns a name
        the proof cannot credit. A name the trace meets that
        the body never assigns and the function was never
        handed is module level furniture a path is built
        from, and it carries no fixture name.
        """
        credited = set()
        seen = set()
        frontier = [name]
        while frontier:
            current = frontier.pop()
            if current in seen:
                continue
            seen.add(current)
            explained = False
            for targets, value in read_pairs:
                if current not in targets:
                    continue
                explained = True
                for sub in ast.walk(value):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        credited.add(sub.value)
                    elif isinstance(sub, ast.Name):
                        if sub.id in env and env[sub.id] is not None:
                            credited.update(env[sub.id])
                        elif any(
                            sub.id in pair_targets for pair_targets, _ in read_pairs
                        ):
                            frontier.append(sub.id)
                        elif sub.id in env or sub.id in own_parameters:
                            return None
            if not explained:
                return None
        return frozenset(credited)

    def read_values(expression):
        """The fixture names a disk read target may denote.

        The name a path expression denotes stands in its
        final component, so a division chain resolves through
        its right operand alone, the components before it
        being the folders the path is built from, and any
        other target is read whole. A string constant in the
        component is a fixture name the read may load, and a
        local name contributes the binding in effect for it,
        or, when that binding does not resolve, the names its
        assignments in the body derive it from. A component
        holding a call, or a local whose derivation the trace
        cannot see through, resolves to None, and a read fed
        by it earns a name the proof cannot credit.
        """
        if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Div):
            return read_values(expression.right)
        names = set()
        for sub in ast.walk(expression):
            if isinstance(sub, ast.Call):
                return None
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                names.add(sub.value)
            elif isinstance(sub, ast.Name) and sub.id in env:
                resolved = env[sub.id]
                if resolved is not None:
                    names.update(resolved)
                else:
                    traced = dependence_names(sub.id)
                    if traced is None:
                        return None
                    names.update(traced)
        return frozenset(names)

    def record_read(call):
        """Credit a disk read as a loading call in a seed proof.

        The read target stands in for the name argument, and
        the fixture names it may denote are credited. A target
        the walk cannot resolve earns the unresolved read
        name instead, which no proof can mistake for the
        symbolic name of a parameter, so the reader under
        proof is refused.
        """
        if flow["suppress"]:
            return
        values = read_values(call.func.value)
        if values is None:
            loaded.add(_UNRESOLVED_READ)
        else:
            loaded.update(values)

    def scan_suppressed(node):
        """Scan an expression whose calls earn no credit.

        The expression is still walked, so the names it binds
        are accounted for, and a walrus met under suppression
        leaves its name unresolvable, because the binding may
        never happen.
        """
        flow["suppress"] += 1
        try:
            scan(node)
        finally:
            flow["suppress"] -= 1

    def save(names):
        return {name: env.get(name, unbound) for name in names}

    def restore(saved):
        for name, value in saved.items():
            if value is unbound:
                env.pop(name, None)
            else:
                env[name] = value

    def merge_envs(path_envs):
        """Join path environments under the identical binding rule.

        A name keeps a binding only when every path ends
        holding the identical binding for it. A name bound on
        some paths only, or bound to different values on
        different paths, becomes unresolvable, so a fixture
        name bound inside a region that may not run earns no
        credit after the region.
        """
        names = set()
        for path_env in path_envs:
            names.update(path_env)
        merged = {}
        for name in names:
            outcomes = [path_env.get(name, unbound) for path_env in path_envs]
            first = outcomes[0]
            if all(
                outcome is first or (first is not unbound and outcome == first)
                for outcome in outcomes
            ):
                if first is not unbound:
                    merged[name] = first
            else:
                merged[name] = None
        return merged

    def join_paths(path_states):
        """Fold the path states of a region into the live state.

        Each path state is the environment and the credited set
        one path through the region ends holding. The
        environments merge under the identical binding rule of
        merge_envs. The credited set becomes the intersection
        of the path sets, so a fixture counts as loaded only
        when a loading call resolving to it ran on every path.
        """
        env.clear()
        env.update(merge_envs([path_env for path_env, _ in path_states]))
        credited = set(path_states[0][1])
        for _path_env, path_loaded in path_states[1:]:
            credited.intersection_update(path_loaded)
        loaded.clear()
        loaded.update(credited)

    def walk_paths(statements, base_env, base_loaded, prepare=None):
        """Walk statements along one forked path, returning its ends.

        The walk starts from the given environment and credited
        set, and the optional prepare step runs once that state
        is installed, before the first statement, which is how a
        loop binds its target and a try handler binds its
        exception name. Each end is the environment, the
        credited set, and the way the path ended, one of falling
        through, returning, raising, breaking, or continuing,
        and a block that meets a statement ending its path
        walks no further statements on it. The state in force
        is restored before returning, so the caller joins the
        path results itself.
        """
        saved_env = dict(env)
        saved_loaded = set(loaded)
        saved_alive = flow["alive"]
        env.clear()
        env.update(base_env)
        loaded.clear()
        loaded.update(base_loaded)
        flow["alive"] = True
        if prepare is not None:
            prepare()
        completed = []
        for sub in statements:
            if not flow["alive"]:
                break
            walk_stmt(sub, completed)
        ends = list(completed)
        if flow["alive"]:
            ends.append((dict(env), set(loaded), "fall"))
        env.clear()
        env.update(saved_env)
        loaded.clear()
        loaded.update(saved_loaded)
        flow["alive"] = saved_alive
        return ends

    def fork_scan(expression, base_env, base_loaded):
        """Scan one expression from a forked state, returning its end.

        The end is the environment and the credited set the
        expression leaves behind, and the state in force is
        restored before returning, so the caller joins the
        branch results itself.
        """
        saved_env = dict(env)
        saved_loaded = set(loaded)
        env.clear()
        env.update(base_env)
        loaded.clear()
        loaded.update(base_loaded)
        scan(expression)
        result = (dict(env), set(loaded))
        env.clear()
        env.update(saved_env)
        loaded.clear()
        loaded.update(saved_loaded)
        return result

    def join_ends(ends, completed):
        """Join the path ends of a region into the live state.

        The paths that fell through the region merge by the
        binding and credit rules of join_paths, and the merged
        state is live for the code after the region. A path
        that broke or continued out of the region is handed to
        the enclosing block as an ended path of its own, and a
        path that returned was already frozen toward the whole
        test when it ended, while a path that raised is one
        the region itself carries onward or drops. When no
        path fell through, the live state is dead and the
        rest of the enclosing block walks nothing.
        """
        fall = [
            (path_env, path_loaded)
            for path_env, path_loaded, kind in ends
            if kind == "fall"
        ]
        for end in ends:
            if end[2] in ("break", "continue"):
                completed.append(end)
        if fall:
            join_paths(fall)
            flow["alive"] = True
        else:
            flow["alive"] = False

    def walk_loop(
        body, orelse, guaranteed, prepare, completed, end_prepare=None, poison=()
    ):
        """Walk one loop body and its else arm as forked paths.

        The path ends feeding the join are the ends of the
        body passes that fall through or continue, each beside
        the end of the else arm walked from it, the ends of
        the body passes that break out of the loop, which
        reach the code after the loop without the else arm,
        and the end of the else arm walked from the state
        before the loop. The last end is the zero trip path,
        and it joins only when the loop is not proven to run
        its body at least once, so credit recorded in a body
        that may never run earns nothing, while credit in a
        proven body pass survives the join.

        The environment a body end carries into the join is
        the state the interpreter leaves behind, not the state
        the walked pass ends holding. When the caller supplies
        an end prepare step, every body end takes its
        environment from a final pass walked with that step
        and joined on its own, which is how a loop target
        narrowed to its last element, and the names derived
        from it at their last pass values, reach the code
        after the loop. When the caller names bindings to
        poison, those names read as unresolvable in every
        body end instead, because the pass that left them
        cannot be named. The credited sets are untouched
        either way, because every pass of the body genuinely
        runs the calls it holds.
        """
        pre_env = dict(env)
        pre_loaded = set(loaded)
        narrowed = None
        if end_prepare is not None:
            end_envs = [
                end_env
                for end_env, _end_loaded, kind in walk_paths(
                    body, pre_env, pre_loaded, end_prepare
                )
                if kind in ("fall", "continue")
            ]
            if end_envs:
                narrowed = merge_envs(end_envs)

        def end_state(end_env):
            if narrowed is not None:
                return dict(narrowed)
            if poison:
                return {
                    name: (None if name in poison else value)
                    for name, value in end_env.items()
                }
            return end_env

        path_ends = []
        for end_env, end_loaded, kind in walk_paths(
            body, pre_env, pre_loaded, prepare
        ):
            if kind in ("fall", "continue"):
                end_env = end_state(end_env)
                path_ends.append((end_env, end_loaded, "fall"))
                path_ends.extend(walk_paths(orelse, end_env, end_loaded))
            elif kind == "break":
                path_ends.append((end_state(end_env), end_loaded, "fall"))
        if not guaranteed:
            path_ends.extend(walk_paths(orelse, pre_env, pre_loaded))
        join_ends(path_ends, completed)

    def scan(node):
        """Walk one expression in source order.

        Loading calls are recorded as they are met, and the
        bindings a comprehension performs are applied for the
        span of its body and then restored, matching the scoping
        the interpreter itself gives them. A lambda body is
        deferred code and is never walked. The parts of an
        expression the interpreter may skip are scanned with
        credit suppressed, so a call inside them earns nothing.
        """
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
            generators = node.generators
            names = []
            for generator in generators:
                names.extend(_target_names(generator.target))
            saved = save(names)
            exempt = isinstance(
                generators[0].iter, (ast.Tuple, ast.List, ast.Set)
            ) and len(generators[0].iter.elts) >= 1
            for index, generator in enumerate(generators):
                if index == 0 or exempt:
                    scan(generator.iter)
                else:
                    scan_suppressed(generator.iter)
                bind(generator.target, value_of(generator.iter))
                for condition in generator.ifs:
                    if exempt:
                        scan(condition)
                    else:
                        scan_suppressed(condition)
            if isinstance(node, ast.DictComp):
                parts = (node.key, node.value)
            else:
                parts = (node.elt,)
            for part in parts:
                if exempt:
                    scan(part)
                else:
                    scan_suppressed(part)
            restore(saved)
            return
        if isinstance(node, ast.GeneratorExp):
            # A generator expression is lazy, and only the
            # outermost iterable evaluates when the expression
            # is created. The rest is deferred code, scanned
            # with credit suppressed, so a loading call in its
            # body earns nothing, as a call in a lambda body
            # earns nothing.
            generators = node.generators
            names = []
            for generator in generators:
                names.extend(_target_names(generator.target))
            saved = save(names)
            scan(generators[0].iter)
            for index, generator in enumerate(generators):
                if index > 0:
                    scan_suppressed(generator.iter)
                bind(generator.target, value_of(generator.iter))
                for condition in generator.ifs:
                    scan_suppressed(condition)
            scan_suppressed(node.elt)
            restore(saved)
            return
        if isinstance(node, ast.BoolOp):
            # An operand after the first evaluates only when
            # every operand before it holds the truth the
            # operation needs, so it earns credit only when
            # every one of them is a constant guaranteeing
            # exactly that, and is otherwise scanned with
            # credit suppressed.
            guaranteed = True
            for index, value in enumerate(node.values):
                if index == 0 or guaranteed:
                    scan(value)
                else:
                    scan_suppressed(value)
                if isinstance(node.op, ast.And):
                    guaranteed = (
                        guaranteed
                        and isinstance(value, ast.Constant)
                        and bool(value.value)
                    )
                else:
                    guaranteed = (
                        guaranteed
                        and isinstance(value, ast.Constant)
                        and not bool(value.value)
                    )
            return
        if isinstance(node, ast.IfExp):
            # A conditional expression evaluates its test and
            # then exactly one of its branches, so the branches
            # fork and join by intersection, and a name bound
            # differently across them reads as unresolvable.
            scan(node.test)
            base_env = dict(env)
            base_loaded = set(loaded)
            body_end = fork_scan(node.body, base_env, base_loaded)
            else_end = fork_scan(node.orelse, base_env, base_loaded)
            join_paths([body_end, else_end])
            return
        if isinstance(node, ast.Lambda):
            # A lambda body is deferred code and is never walked,
            # so a loading call inside it earns no credit. Only
            # the default values evaluate when the lambda is
            # created, so only they are scanned.
            for default in node.args.defaults:
                scan(default)
            for default in node.args.kw_defaults:
                if default is not None:
                    scan(default)
            return
        if isinstance(node, ast.NamedExpr):
            scan(node.value)
            if flow["suppress"]:
                bind(node.target, None)
            else:
                bind(node.target, value_of(node.value))
            return
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in loaders:
                if name_slots is None:
                    record_call(node)
                elif node.func.id in name_slots:
                    record_slot_call(node, name_slots[node.func.id])
            elif (
                credit_reads
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("read_bytes", "read_text")
            ):
                record_read(node)
        for child in ast.iter_child_nodes(node):
            scan(child)

    def walk_stmt(statement, completed):
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # A nested definition is deferred code. Its body runs
            # only if the test calls it, and a call into it is one
            # the walk cannot see into, so the body is never
            # walked and a loading call inside it earns no credit,
            # the helper treatment. The decorators and the default
            # values are scanned because they evaluate when the
            # definition does. The definition is not inert for
            # bindings, though, because a name it declares global
            # or nonlocal is one a call into it may write in the
            # enclosing scope, so every such name reads as
            # unresolvable from the definition onward.
            for decorator in statement.decorator_list:
                scan(decorator)
            for default in statement.args.defaults:
                scan(default)
            for default in statement.args.kw_defaults:
                if default is not None:
                    scan(default)
            for name in writeback_names(statement):
                env[name] = None
            return
        if isinstance(statement, ast.ClassDef):
            # A class body runs when the definition does, so a
            # loading call written in it earns credit, but its
            # assignments land in the class namespace and never
            # bind in the enclosing scope, so the body walks in
            # the live environment and the environment is
            # restored when the definition ends. A raise inside
            # the body abandons the definition and ends the
            # enclosing path with it.
            for decorator in statement.decorator_list:
                scan(decorator)
            for base in statement.bases:
                scan(base)
            for keyword in statement.keywords:
                scan(keyword.value)
            saved_env = dict(env)
            saved_alive = flow["alive"]
            inner_completed = []
            for sub in statement.body:
                if not flow["alive"]:
                    break
                walk_stmt(sub, inner_completed)
            raised = any(end[2] == "raise" for end in inner_completed)
            env.clear()
            env.update(saved_env)
            # A method of the class can declare a name nonlocal
            # and write it in the enclosing function scope, past
            # the class namespace, so the write back names of
            # the whole definition are poisoned in the restored
            # environment even though its bindings are discarded.
            for name in writeback_names(statement):
                env[name] = None
            flow["alive"] = False if raised else saved_alive
            return
        if isinstance(statement, ast.Return):
            # The value of a return evaluates before the path
            # ends, so it is scanned first. The path then ends
            # and its credit stands frozen toward the whole
            # test, and the statements after it in the block
            # are dead, so the block walk stops before them.
            if statement.value is not None:
                scan(statement.value)
            fold_returned(loaded)
            completed.append((dict(env), set(loaded), "return"))
            flow["alive"] = False
            return
        if isinstance(statement, ast.Raise):
            if statement.exc is not None:
                scan(statement.exc)
            if statement.cause is not None:
                scan(statement.cause)
            completed.append((dict(env), set(loaded), "raise"))
            if raised_credits is not None:
                # A derivation proof counts the paths that end
                # in a raise beside the paths that complete, so
                # the credit this path holds is collected for
                # the proof to judge. A test body never collects
                # it, because a raised path there is a failed
                # test and earns nothing either way.
                raised_credits.append(set(loaded))
            flow["alive"] = False
            return
        if isinstance(statement, ast.Break):
            completed.append((dict(env), set(loaded), "break"))
            flow["alive"] = False
            return
        if isinstance(statement, ast.Continue):
            completed.append((dict(env), set(loaded), "continue"))
            flow["alive"] = False
            return
        if isinstance(statement, ast.Assert):
            # The message of an assert evaluates only on the
            # path where the test fails, so it is scanned with
            # credit suppressed.
            scan(statement.test)
            if statement.msg is not None:
                scan_suppressed(statement.msg)
            return
        if isinstance(statement, ast.Assign):
            scan(statement.value)
            value = value_of(statement.value)
            for target in statement.targets:
                bind(target, value)
            return
        if isinstance(statement, ast.AnnAssign):
            if statement.value is not None:
                scan(statement.value)
                bind(statement.target, value_of(statement.value))
            return
        if isinstance(statement, ast.AugAssign):
            scan(statement.value)
            if isinstance(statement.target, ast.Name):
                env[statement.target.id] = None
            return
        if isinstance(statement, (ast.For, ast.AsyncFor)):
            scan(statement.iter)
            iter_value = value_of(statement.iter)

            def prepare(target=statement.target, value=iter_value):
                bind(target, value)

            bypass = body_has_bypass(statement.body)
            guaranteed = (
                isinstance(statement.iter, (ast.Tuple, ast.List))
                and len(statement.iter.elts) >= 1
                and not bypass
            )
            # The end state of the loop is settled here. A loop
            # over an ordered literal whose body carries no
            # bypass ends holding its last element, so its body
            # ends take their environment from a final pass with
            # the target narrowed to that element. Any other
            # loop whose iterable resolves leaves the target at
            # a pass the walk cannot name, so the target and
            # the names the body derived from it are poisoned in
            # its ends instead.
            end_prepare = None
            poison = ()
            if isinstance(statement.target, ast.Name) and iter_value is not None:
                if guaranteed:
                    last = statement.iter.elts[-1]
                    if isinstance(last, ast.Constant) and isinstance(last.value, str):
                        last_value = frozenset([last.value])
                    elif isinstance(last, ast.Name):
                        held = env.get(last.id)
                        last_value = (
                            held if held is not None and len(held) == 1 else None
                        )
                    else:
                        last_value = None

                    def end_prepare(target=statement.target, value=last_value):
                        bind(target, value)

                else:
                    poison = target_derived_names(
                        statement.body, statement.target.id
                    )
            walk_loop(
                statement.body,
                statement.orelse,
                guaranteed,
                prepare,
                completed,
                end_prepare,
                poison,
            )
            return
        if isinstance(statement, ast.While):
            scan(statement.test)
            guaranteed = (
                isinstance(statement.test, ast.Constant)
                and bool(statement.test.value)
                and not body_has_bypass(statement.body)
            )
            # A while loop binds no target, so there is no end
            # state to settle here the way the for branch
            # settles its target. The names its body binds meet
            # the identical binding join inside the loop walk,
            # against the path where the body never runs.
            walk_loop(statement.body, statement.orelse, guaranteed, None, completed)
            return
        if isinstance(statement, ast.If):
            scan(statement.test)
            base_env = dict(env)
            base_loaded = set(loaded)
            ends = walk_paths(statement.body, base_env, base_loaded)
            ends.extend(walk_paths(statement.orelse, base_env, base_loaded))
            # The path ends feeding the join are the ends of
            # the arm the test selects and the ends of the arm
            # it rejects, with the untouched state standing in
            # for an else arm the statement does not write.
            # Only the ends that fell through merge into the
            # live state, so when both arms end their paths
            # the code after the conditional is dead.
            join_ends(ends, completed)
            return
        if isinstance(statement, (ast.With, ast.AsyncWith)):
            for item in statement.items:
                scan(item.context_expr)
                if item.optional_vars is not None:
                    bind(item.optional_vars, None)
            base_env = dict(env)
            base_loaded = set(loaded)
            ends = []
            for end_env, end_loaded, kind in walk_paths(
                statement.body, base_env, base_loaded
            ):
                if kind == "raise":
                    # A context manager may suppress the
                    # exception, so the abandoned path resumes
                    # after the with holding its state at the
                    # raise. The statements after the raise
                    # inside the body are dead on every path,
                    # which is what the fork buys here.
                    ends.append((end_env, end_loaded, "fall"))
                else:
                    ends.append((end_env, end_loaded, kind))
            # The path ends feeding the join are the ends of
            # the body that fell through and the resumed ends
            # of the body paths a raise abandoned, while an
            # end that breaks or continues out of an enclosing
            # loop is handed on unchanged.
            join_ends(ends, completed)
            return
        if isinstance(statement, try_types):
            pre_env = dict(env)
            pre_loaded = set(loaded)
            ends = []
            for end_env, end_loaded, kind in walk_paths(
                statement.body, pre_env, pre_loaded
            ):
                if kind == "fall":
                    if statement.orelse:
                        ends.extend(
                            walk_paths(statement.orelse, end_env, end_loaded)
                        )
                    else:
                        ends.append((end_env, end_loaded, "fall"))
                elif kind in ("break", "continue"):
                    ends.append((end_env, end_loaded, kind))
                # An end that returned was frozen toward the
                # whole test when it ended. An end that raised
                # is carried onward by the handlers below, and
                # the statements after the raise in the body
                # were dead on it.
            for handler in statement.handlers:

                def prepare(handler=handler):
                    if handler.type is not None:
                        scan(handler.type)
                    if handler.name is not None:
                        env[handler.name] = None

                ends.extend(walk_paths(handler.body, pre_env, pre_loaded, prepare))
            # The path ends feeding the join are the ends of
            # the try body that fell through, or of its else
            # arm, which runs from a body end, beside the ends
            # of each handler, and each handler is walked from
            # the state before the try.
            join_ends(ends, completed)
            for sub in statement.finalbody:
                if not flow["alive"]:
                    break
                walk_stmt(sub, completed)
            return
        if isinstance(statement, ast.Match):
            scan(statement.subject)
            base_env = dict(env)
            base_loaded = set(loaded)
            ends = [(base_env, base_loaded, "fall")]

            for case in statement.cases:

                def prepare(case=case):
                    for name in pattern_names(case.pattern):
                        env[name] = None
                    if case.guard is not None:
                        scan(case.guard)

                ends.extend(walk_paths(case.body, base_env, base_loaded, prepare))
            # The path ends feeding the join are the state before
            # the match, standing in for the path where no arm
            # fits, beside the ends of each arm.
            join_ends(ends, completed)
            return
        if isinstance(statement, ast.Delete):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    env.pop(target.id, None)
                else:
                    scan(target)
            return
        scan(statement)

    completed = []
    for statement in function.body:
        if not flow["alive"]:
            break
        walk_stmt(statement, completed)
    if path_credits is not None and flow["alive"]:
        path_credits.append(set(loaded))
    result = set(loaded) if flow["alive"] else None
    if flow["finished"] is not None:
        if result is None:
            result = flow["finished"]
        else:
            result.intersection_update(flow["finished"])
    return result if result is not None else set()


RECORDED_LOADERS = _loader_function_names("test_recorded_corpus.py")


def _case_map():
    return {case["id"]: case for case in MANIFEST["cases"]}


def _fixture_payload_ids(path: Path, endpoint: str) -> list[str]:
    payload = json.loads(path.read_bytes())
    if endpoint in ("searchText", "searchNearby"):
        return [place["id"] for place in payload["places"]]
    return [payload["id"]]


def test_accounting_taxonomy_is_exactly_the_55_cases():
    assert [case["id"] for case in MANIFEST["cases"]] == TAXONOMY
    assert all(case["state"] in STATE_VOCABULARY for case in MANIFEST["cases"])


def test_accounting_state_counts_match_the_program_record():
    counts = {}
    for case in MANIFEST["cases"]:
        counts[case["state"]] = counts.get(case["state"], 0) + 1
    assert counts == {
        "recorded in session 1": 2,
        "recorded in session 2": 30,
        "recorded in both": 3,
        "synthesized candidate": 4,
        "hunted and missed in R12": 12,
        "still open": 4,
    }
    recorded = sum(1 for case in MANIFEST["cases"] if case["state"] in RECORDED_STATES)
    assert recorded == 35


def test_accounting_preamble_carries_the_filename_templates():
    preamble = MANIFEST["preamble"]
    assert preamble["recorded_filename_template"] == "recorded_<CASE>_<slug>.json"
    assert preamble["observation_filename_template"] == "recorded_<OBS>_<slug>.json"
    assert preamble["synthesized_filename_template"] == "synthesized_<CASE>_<slug>.json"


def test_accounting_recorded_fixtures_exist_match_hashes_and_carry_selectors():
    for case in MANIFEST["cases"]:
        if case["state"] not in RECORDED_STATES:
            continue
        for entry in case["fixtures"]:
            path = RECORDED / entry["file"]
            assert path.exists(), entry["file"]
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest == entry["fixture_sha256"], entry["file"]
            assert entry["size_bytes"] == path.stat().st_size
            payload_ids = _fixture_payload_ids(path, entry["endpoint"])
            for place_id in entry["selector_place_ids"]:
                assert place_id in payload_ids, (entry["file"], place_id)


def test_accounting_named_tests_exist_and_load_their_fixtures():
    # The linkage proof. The named test must exist, and the test must
    # hand every fixture file the case claims to one of the recorded
    # module loading helpers, as the literal argument of the call or
    # through a local name whose binding in effect at the call
    # carries the literal, so a test that silently stopped loading
    # its fixture fails here. A fixture name
    # resting in a comment, a docstring, or an assignment no loading
    # call consumes does not satisfy the proof.
    for case in MANIFEST["cases"]:
        if case["state"] not in RECORDED_STATES:
            continue
        assert case["tests"], case["id"]
        for test_name in case["tests"]:
            assert test_name in RECORDED_SOURCES, test_name
            loaded = _fixtures_a_test_loads(
                RECORDED_SOURCES[test_name], RECORDED_LOADERS
            )
            for entry in case["fixtures"]:
                assert entry["file"] in loaded, (test_name, entry["file"])


def test_accounting_synthesized_fixtures_are_enveloped_and_tested():
    for case in MANIFEST["cases"]:
        if case["state"] != "synthesized candidate":
            continue
        (entry,) = case["fixtures"]
        path = SYNTHESIZED / entry["file"]
        assert path.exists(), entry["file"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == entry["fixture_sha256"], entry["file"]
        data = json.loads(path.read_bytes())
        assert set(data) == {"fixtureMark", "payload"}
        assert data["fixtureMark"]["origin"] == "synthesized"
        assert data["fixtureMark"]["case"] == case["id"]
        for test_name in case["tests"]:
            assert test_name in SYNTHESIZED_SOURCES, test_name
            assert entry["file"] in SYNTHESIZED_SOURCES[test_name]


def test_accounting_fixture_folders_hold_exactly_the_claimed_files():
    # Each folder on disk holds exactly the files the manifest claims
    # across its cases, its observations, and its synthesized entries,
    # no more and no fewer. A stripped synthesized payload planted
    # under a recorded name is an unlisted resident and fails here,
    # and so does any other file the manifest never claimed.
    claimed_recorded = set()
    for case in MANIFEST["cases"]:
        if case["state"] in RECORDED_STATES:
            claimed_recorded.update(entry["file"] for entry in case["fixtures"])
    for obs in MANIFEST["observations"]:
        if obs.get("fixture"):
            claimed_recorded.add(obs["fixture"])
        claimed_recorded.update(obs.get("host_fixtures", []))
    claimed_synthesized = set()
    for case in MANIFEST["cases"]:
        if case["state"] == "synthesized candidate":
            claimed_synthesized.update(entry["file"] for entry in case["fixtures"])
    on_disk_recorded = {path.name for path in RECORDED.iterdir() if path.is_file()}
    on_disk_synthesized = {path.name for path in SYNTHESIZED.iterdir() if path.is_file()}
    assert on_disk_recorded == claimed_recorded
    assert on_disk_synthesized == claimed_synthesized


def test_accounting_hunted_and_open_cases_claim_no_fixtures():
    recorded_tokens = {path.name.split("_")[1] for path in RECORDED.glob("*.json")}
    for case in MANIFEST["cases"]:
        if case["state"] in ("hunted and missed in R12", "still open"):
            assert case["fixtures"] == []
            assert case["tests"] == []
            assert case["id"] not in recorded_tokens
        if case["state"] == "hunted and missed in R12":
            assert case.get("hunt_note"), case["id"]
        if case["state"] == "still open":
            assert case.get("open_note"), case["id"]


def test_accounting_observation_fixtures_and_hosts_exist():
    for obs in MANIFEST["observations"]:
        candidates = ([obs["fixture"]] if obs.get("fixture") else []) + obs.get(
            "host_fixtures", []
        )
        assert candidates, obs["id"]
        for name in candidates:
            path = RECORDED / name
            assert path.exists(), name
        for test_name in obs["tests"]:
            assert test_name in RECORDED_SOURCES, test_name
        if obs.get("fixture"):
            entry_path = RECORDED / obs["fixture"]
            digest = hashlib.sha256(entry_path.read_bytes()).hexdigest()
            assert digest == obs["fixture_sha256"]


def test_accounting_observation_tests_load_their_fixtures():
    # The linkage proof for the observation half, at the same strength
    # as the case linkage above. The named test must exist, and the
    # test must hand every fixture the observation claims, its own
    # fixture and its host fixtures alike, to one of the recorded
    # module loading helpers in the same way, so an observation test
    # that silently stopped loading the fixture it pins fails here.
    for obs in MANIFEST["observations"]:
        claimed = ([obs["fixture"]] if obs.get("fixture") else []) + obs.get(
            "host_fixtures", []
        )
        assert claimed, obs["id"]
        assert obs["tests"], obs["id"]
        for test_name in obs["tests"]:
            assert test_name in RECORDED_SOURCES, test_name
            loaded = _fixtures_a_test_loads(
                RECORDED_SOURCES[test_name], RECORDED_LOADERS
            )
            for name in claimed:
                assert name in loaded, (test_name, name)


def test_accounting_builder_specs_match_the_manifest_recorded_set():
    # The regeneration proof is only as wide as the builder spec list.
    # The builder verify walks its own specs, so a fixture dropped from
    # the list would narrow the proof while every other guard stayed
    # green. The spec list is therefore pinned here against the
    # manifest recorded set, file for file, and each spec must agree
    # with its manifest entry on session, exchange and selector.
    specs = _builder_module().SPECS
    spec_files = [spec["file"] for spec in specs]
    assert len(spec_files) == len(set(spec_files))
    entries = {}
    for case in MANIFEST["cases"]:
        if case["state"] in RECORDED_STATES:
            for entry in case["fixtures"]:
                entries[entry["file"]] = entry
    for obs in MANIFEST["observations"]:
        if obs.get("fixture"):
            entries[obs["fixture"]] = obs
    assert set(spec_files) == set(entries)
    for spec in specs:
        entry = entries[spec["file"]]
        assert spec["session"] == entry["session"], spec["file"]
        assert spec["exchange"] == entry["exchange"], spec["file"]
        assert list(spec["ids"]) == list(entry["selector_place_ids"]), spec["file"]


def test_accounting_coverage_table_rows_match_the_manifest():
    rows = {}
    for line in TABLE.splitlines():
        match = re.match(r"\| ((?:P|H|V|A)\d+) \|", line)
        if match:
            rows[match.group(1)] = [cell.strip() for cell in line.split("|")]
    assert sorted(rows) == sorted(TAXONOMY)
    for case in MANIFEST["cases"]:
        cells = rows[case["id"]]
        # The columns run case, label, state, fixtures, pinning tests,
        # notes, inside the leading and trailing pipes.
        assert cells[3] == case["state"], case["id"]
        fixtures_cell = cells[4]
        claimed_fixtures = [entry["file"] for entry in case["fixtures"]]
        table_fixtures = [] if fixtures_cell == "none" else fixtures_cell.split(", ")
        assert table_fixtures == claimed_fixtures, case["id"]
        tests_cell = cells[5]
        table_tests = [] if tests_cell == "none" else tests_cell.split(", ")
        assert table_tests == case["tests"], case["id"]


def test_accounting_size_limits_hold():
    limits = MANIFEST["preamble"]["guard_limits"]
    per_file = limits["per_file_ceiling_bytes"]
    exceptions = {}
    for case in MANIFEST["cases"]:
        for entry in case["fixtures"]:
            if entry.get("size_exception"):
                exceptions[entry["file"]] = entry["size_exception"]
    total = 0
    for folder in (RECORDED, SYNTHESIZED):
        for path in sorted(folder.glob("*.json")):
            size = path.stat().st_size
            total += size
            if path.name not in exceptions:
                assert size <= per_file, (path.name, size)
    assert total <= limits["set_total_ceiling_bytes"], total


def test_accounting_absence_pins_rest_on_requesting_masks():
    # Each absence pin in the conformance module is only as good as
    # the mask behind it. The manifest mask is the evidence, so the
    # pairs are asserted here against literal field names.
    cases = _case_map()

    def mask_of(case_id, index=0):
        return cases[case_id]["fixtures"][index]["request_mask"]

    assert "attributions" in mask_of("A2")
    assert "attributions" in mask_of("P15", 0)
    assert "places.photos" in mask_of("P7")
    assert "reviews" in mask_of("P8", 1)
    assert "rating" in mask_of("P8", 1)
    assert "places.addressComponents" in mask_of("P1")
    observations = {obs["id"]: obs for obs in MANIFEST["observations"]}
    assert "places.priceLevel" in observations["OBS1"]["request_mask"]
    assert "places.pureServiceAreaBusiness" in observations["OBS2"]["request_mask"]


def test_accounting_legacy_fixture_classification_is_recorded():
    legacy = {entry["file"]: entry for entry in MANIFEST["legacy_fixtures"]}
    assert "place_details.json" in legacy
    note = legacy["place_details.json"]["note"]
    assert "authored decode coverage" in note
    # The recorded count of 35 never includes the legacy fixture.
    recorded_files = {
        entry["file"]
        for case in MANIFEST["cases"]
        if case["state"] in RECORDED_STATES
        for entry in case["fixtures"]
    }
    assert "place_details.json" not in recorded_files
