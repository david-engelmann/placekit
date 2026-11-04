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


def _loader_function_names(filename: str) -> set[str]:
    """Names of the module level helpers that load a fixture by name.

    The set is derived from the module itself. The reader at the
    bottom is the helper whose own body reads a file from disk, and a
    helper joins the set when it calls a helper already in the set,
    so the payload helper and the search and details replayers join
    through the readers they call. Test functions never join, because
    nothing loads a fixture through a test.
    """
    path = Path(__file__).parent / filename
    tree = ast.parse(path.read_text())
    helpers = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("test_")
    }
    calls = {}
    loaders = set()
    for name, node in helpers.items():
        called = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                called.add(sub.func.id)
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr in ("read_bytes", "read_text")
            ):
                loaders.add(name)
        calls[name] = called
    growing = True
    while growing:
        growing = False
        for name, called in calls.items():
            if name not in loaders and called & loaders:
                loaders.add(name)
                growing = True
    return loaders


RECORDED_LOADERS = _loader_function_names("test_recorded_corpus.py")


def _fixtures_a_test_loads(source: str, loaders: set[str]) -> set[str]:
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
    run through exactly that shape. Credit in a finally arm is
    ordinary straight line credit, because the finally arm runs
    on every path. A loading call inside a nested function
    definition or a lambda earns no credit at all, because such
    a body runs only when it is called and a call into it is one
    the walk cannot see into, the same helper treatment a call
    into another module receives, though the decorators and
    default values of a definition are scanned because they
    evaluate when the definition does.

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
    only the paths that complete.

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
    touches is modelled in these terms or refused, and a
    shape it cannot model resolves to no credit and fails
    the accounting check closed.
    """
    function = ast.parse(source).body[0]
    loaded = set()
    env = {}
    unbound = object()
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

    def target_names(target):
        if isinstance(target, ast.Name):
            return [target.id]
        if isinstance(target, ast.Starred):
            return target_names(target.value)
        if isinstance(target, (ast.Tuple, ast.List)):
            names = []
            for element in target.elts:
                names.extend(target_names(element))
            return names
        return []

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
        earn no credit from code it never reaches.
        """
        if flow["finished"] is None:
            flow["finished"] = set(credit)
        else:
            flow["finished"].intersection_update(credit)

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

    def join_paths(path_states):
        """Fold the path states of a region into the live state.

        Each path state is the environment and the credited set
        one path through the region ends holding. A name keeps a
        binding only when every path ends holding the identical
        binding for it. A name bound on some paths only, or bound
        to different values on different paths, becomes
        unresolvable, so a fixture name bound inside a region
        that may not run earns no credit after the region. The
        credited set becomes the intersection of the path sets,
        so a fixture counts as loaded only when a loading call
        resolving to it ran on every path.
        """
        names = set()
        for path_env, _path_loaded in path_states:
            names.update(path_env)
        merged = {}
        for name in names:
            outcomes = [path_env.get(name, unbound) for path_env, _ in path_states]
            first = outcomes[0]
            if all(
                outcome is first or (first is not unbound and outcome == first)
                for outcome in outcomes
            ):
                if first is not unbound:
                    merged[name] = first
            else:
                merged[name] = None
        env.clear()
        env.update(merged)
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

    def walk_loop(body, orelse, guaranteed, prepare, completed):
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
        """
        pre_env = dict(env)
        pre_loaded = set(loaded)
        path_ends = []
        for end_env, end_loaded, kind in walk_paths(
            body, pre_env, pre_loaded, prepare
        ):
            if kind in ("fall", "continue"):
                path_ends.append((end_env, end_loaded, "fall"))
                path_ends.extend(walk_paths(orelse, end_env, end_loaded))
            elif kind == "break":
                path_ends.append((end_env, end_loaded, "fall"))
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
                names.extend(target_names(generator.target))
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
                names.extend(target_names(generator.target))
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
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in loaders
        ):
            record_call(node)
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
            # definition does.
            for decorator in statement.decorator_list:
                scan(decorator)
            for default in statement.args.defaults:
                scan(default)
            for default in statement.args.kw_defaults:
                if default is not None:
                    scan(default)
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

            guaranteed = (
                isinstance(statement.iter, (ast.Tuple, ast.List))
                and len(statement.iter.elts) >= 1
                and not body_has_bypass(statement.body)
            )
            walk_loop(statement.body, statement.orelse, guaranteed, prepare, completed)
            return
        if isinstance(statement, ast.While):
            scan(statement.test)
            guaranteed = (
                isinstance(statement.test, ast.Constant)
                and bool(statement.test.value)
                and not body_has_bypass(statement.body)
            )
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
    result = set(loaded) if flow["alive"] else None
    if flow["finished"] is not None:
        if result is None:
            result = flow["finished"]
        else:
            result.intersection_update(flow["finished"])
    return result if result is not None else set()


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
