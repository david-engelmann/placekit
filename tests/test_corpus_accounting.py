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
    # The linkage proof. The named test must exist, and its own source
    # must name every fixture file the case claims, so a test that
    # silently stopped loading its fixture fails here.
    for case in MANIFEST["cases"]:
        if case["state"] not in RECORDED_STATES:
            continue
        assert case["tests"], case["id"]
        for test_name in case["tests"]:
            assert test_name in RECORDED_SOURCES, test_name
            source = RECORDED_SOURCES[test_name]
            for entry in case["fixtures"]:
                assert entry["file"] in source, (test_name, entry["file"])


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
