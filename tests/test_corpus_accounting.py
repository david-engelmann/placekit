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
    conditional, a loop, a try, or a match, the walk forks the
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
    """
    function = ast.parse(source).body[0]
    loaded = set()
    env = {}
    unbound = object()
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
        arguments = [*call.args, *(keyword.value for keyword in call.keywords)]
        for argument in arguments:
            names = value_of(argument)
            if names:
                loaded.update(names)

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

    def fork(statements, base_env, base_loaded, prepare=None):
        """Walk statements along one path, returning its end state.

        The walk starts from the given environment and credited
        set, and the optional prepare step runs once that state
        is installed, before the first statement, which is how a
        loop binds its target and a try handler binds its
        exception name. The state in force is restored before
        returning, so the caller joins the path results itself.
        """
        saved_env = dict(env)
        saved_loaded = set(loaded)
        env.clear()
        env.update(base_env)
        loaded.clear()
        loaded.update(base_loaded)
        if prepare is not None:
            prepare()
        for sub in statements:
            walk_stmt(sub)
        result = (dict(env), set(loaded))
        env.clear()
        env.update(saved_env)
        loaded.clear()
        loaded.update(saved_loaded)
        return result

    def walk_loop(body, orelse, guaranteed, prepare=None):
        """Walk one loop body and its else arm as forked paths.

        The path ends feeding the join are the end of the body
        pass, the end of the else arm walked from the body end,
        and the end of the else arm walked from the state before
        the loop. The third end is the zero trip path, and it
        joins only when the loop is not proven to run its body
        at least once, so credit recorded in a body that may
        never run earns nothing, while credit in a proven body
        pass survives the join.
        """
        pre_env = dict(env)
        pre_loaded = set(loaded)
        body_end = fork(body, pre_env, pre_loaded, prepare)
        path_states = [body_end, fork(orelse, *body_end)]
        if not guaranteed:
            path_states.append(fork(orelse, pre_env, pre_loaded))
        join_paths(path_states)

    def scan(node):
        """Walk one expression in source order.

        Loading calls are recorded as they are met, and the
        bindings a comprehension performs are applied for the
        span of its body and then restored, matching the scoping
        the interpreter itself gives them. A lambda body is
        deferred code and is never walked.
        """
        if isinstance(
            node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)
        ):
            names = []
            for generator in node.generators:
                names.extend(target_names(generator.target))
            saved = save(names)
            for generator in node.generators:
                scan(generator.iter)
                bind(generator.target, value_of(generator.iter))
                for condition in generator.ifs:
                    scan(condition)
            if isinstance(node, ast.DictComp):
                scan(node.key)
                scan(node.value)
            else:
                scan(node.elt)
            restore(saved)
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

    def walk_stmt(statement):
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
            for sub in statement.body:
                walk_stmt(sub)
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
            walk_loop(statement.body, statement.orelse, guaranteed, prepare)
            return
        if isinstance(statement, ast.While):
            scan(statement.test)
            guaranteed = (
                isinstance(statement.test, ast.Constant)
                and bool(statement.test.value)
                and not body_has_bypass(statement.body)
            )
            walk_loop(statement.body, statement.orelse, guaranteed)
            return
        if isinstance(statement, ast.If):
            scan(statement.test)
            base_env = dict(env)
            base_loaded = set(loaded)
            then_end = fork(statement.body, base_env, base_loaded)
            else_end = fork(statement.orelse, base_env, base_loaded)
            # The path ends feeding the join are the end of the
            # arm the test selects and the end of the arm it
            # rejects, with the untouched state standing in for
            # an else arm the statement does not write.
            join_paths([then_end, else_end])
            return
        if isinstance(statement, (ast.With, ast.AsyncWith)):
            for item in statement.items:
                scan(item.context_expr)
                if item.optional_vars is not None:
                    bind(item.optional_vars, None)
            for sub in statement.body:
                walk_stmt(sub)
            return
        if isinstance(statement, try_types):
            pre_env = dict(env)
            pre_loaded = set(loaded)
            body_end = fork(statement.body, pre_env, pre_loaded)

            def fork_handler(handler):
                def prepare():
                    if handler.type is not None:
                        scan(handler.type)
                    if handler.name is not None:
                        env[handler.name] = None

                return fork(handler.body, pre_env, pre_loaded, prepare)

            path_states = [fork_handler(handler) for handler in statement.handlers]
            if statement.orelse:
                path_states.append(fork(statement.orelse, *body_end))
            else:
                path_states.append(body_end)
            # The path ends feeding the join are the end of the
            # try body, or of its else arm, which runs from the
            # body end, beside the end of each handler, and each
            # handler is walked from the state before the try.
            join_paths(path_states)
            for sub in statement.finalbody:
                walk_stmt(sub)
            return
        if isinstance(statement, ast.Match):
            scan(statement.subject)
            base_env = dict(env)
            base_loaded = set(loaded)
            path_states = [(base_env, base_loaded)]

            def fork_case(case):
                def prepare():
                    for name in pattern_names(case.pattern):
                        env[name] = None
                    if case.guard is not None:
                        scan(case.guard)

                return fork(case.body, base_env, base_loaded, prepare)

            path_states.extend(fork_case(case) for case in statement.cases)
            # The path ends feeding the join are the state before
            # the match, standing in for the path where no arm
            # fits, beside the end of each arm.
            join_paths(path_states)
            return
        if isinstance(statement, ast.Delete):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    env.pop(target.id, None)
                else:
                    scan(target)
            return
        scan(statement)

    for statement in function.body:
        walk_stmt(statement)
    return loaded


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
