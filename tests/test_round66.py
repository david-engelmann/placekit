"""Round 66 pins for the sdist carriage of the cargo audit record.

Round 66 taught the build to carry the cargo audit disposition
record at .cargo/audit.toml in the source distribution, through
an include entry on the [tool.maturin] table of pyproject.toml.
The build tool's standing dot path rule would otherwise leave
the file out, and an audit run from the sdist would resurface
two published advisories without the dispositions and the
reachability rationale the repository records for them. Nothing
pinned the carriage, so a later edit dropping the include entry
would regress it silently. These pins parse the manifest with
a real TOML parser on every interpreter, tomllib where the
interpreter carries it and tomli, the backport of the same
parser, on the floor interpreter that does not. A hand rolled
section scan stood in for the parser on the floor leg in an
earlier form of this pin and decided wrongly in both
directions, passing broken manifests and failing sound
respellings, so no scan stands in for a parse here. The pins
decide the carriage on the parsed structure. The include list
counts only when it is exactly one entry whose path is exactly
.cargo/audit.toml and whose format is exactly sdist, with no
second entry beside it and no extra key on the entry. The
audit record itself is read as parsed data too, and it counts
only when its ignore list names exactly the two recorded
advisories, so a record emptied to zero bytes fails the pin
the same way a missing one does. The mutation and spelling
cases beside the control case hold the pins to those
decisions, so they cannot pass on a manifest that merely
mentions the file. The pins stay static and build nothing.
The census evidence that the built sdist carries the file
lives in the round audit.
"""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
AUDIT_RECORD = ROOT / ".cargo" / "audit.toml"

AUDIT_PATH = ".cargo/audit.toml"
SDIST_FORMAT = "sdist"
EXPECTED_ENTRY = {"path": AUDIT_PATH, "format": SDIST_FORMAT}
RECORDED_ADVISORIES = ["RUSTSEC-2025-0020", "RUSTSEC-2026-0177"]
INCLUDE_LINE = 'include = [{ path = ".cargo/audit.toml", format = "sdist" }]'


def include_entries(text: str) -> object:
    """The parsed include value on the [tool.maturin] table, as data."""
    document = tomllib.loads(text)
    tool = document.get("tool", {})
    if not isinstance(tool, dict):
        return None
    maturin = tool.get("maturin", {})
    if not isinstance(maturin, dict):
        return None
    return maturin.get("include")


def carries_audit_record(text: str) -> bool:
    """Whether the include list is exactly the one sdist entry."""
    return include_entries(text) == [EXPECTED_ENTRY]


def recorded_advisories(text: str) -> object:
    """The parsed ignore list in the audit record, as data."""
    document = tomllib.loads(text)
    advisories = document.get("advisories", {})
    if not isinstance(advisories, dict):
        return None
    return advisories.get("ignore")


def audit_record_names_the_recorded_advisories(text: str) -> bool:
    """Whether the record names exactly the two recorded advisories."""
    ignore = recorded_advisories(text)
    return (
        isinstance(ignore, list)
        and len(ignore) == len(RECORDED_ADVISORIES)
        and all(isinstance(item, str) for item in ignore)
        and set(ignore) == set(RECORDED_ADVISORIES)
    )


def manifest_text() -> str:
    return PYPROJECT.read_text(encoding="utf-8")


def audit_record_text() -> str:
    return AUDIT_RECORD.read_text(encoding="utf-8")


def mutated_manifest(old: str, new: str) -> str:
    """The manifest text with one spelling swapped, checked as changed."""
    text = manifest_text()
    mutated = text.replace(old, new)
    assert mutated != text
    return mutated


def test_sdist_include_carries_the_audit_record() -> None:
    assert carries_audit_record(manifest_text())


def test_audit_record_names_the_recorded_advisories() -> None:
    assert audit_record_names_the_recorded_advisories(audit_record_text())


def test_pin_fails_without_the_include_entry() -> None:
    assert not carries_audit_record(mutated_manifest(INCLUDE_LINE, ""))


def test_pin_fails_on_an_altered_audit_path() -> None:
    mutated = mutated_manifest(AUDIT_PATH, ".cargo/audit-copy.toml")
    assert not carries_audit_record(mutated)


def test_pin_fails_on_an_altered_format() -> None:
    mutated = mutated_manifest('format = "sdist"', 'format = "wheel"')
    assert not carries_audit_record(mutated)


def test_pin_fails_when_the_include_entry_is_commented_out() -> None:
    mutated = mutated_manifest(INCLUDE_LINE, "# " + INCLUDE_LINE)
    assert not carries_audit_record(mutated)


def test_pin_fails_with_a_second_include_entry() -> None:
    widened = (
        'include = [{ path = ".cargo/audit.toml", format = "sdist" }, '
        '{ path = "rust-toolchain.toml", format = "sdist" }]'
    )
    assert not carries_audit_record(mutated_manifest(INCLUDE_LINE, widened))


def test_pin_fails_with_an_extra_key_in_the_include_entry() -> None:
    widened = 'include = [{ path = ".cargo/audit.toml", format = "sdist", note = "extra" }]'
    assert not carries_audit_record(mutated_manifest(INCLUDE_LINE, widened))


def test_pin_passes_with_format_spelled_before_path() -> None:
    respelled = 'include = [{ format = "sdist", path = ".cargo/audit.toml" }]'
    assert carries_audit_record(mutated_manifest(INCLUDE_LINE, respelled))


def test_pin_passes_with_literal_strings() -> None:
    respelled = "include = [{ path = '.cargo/audit.toml', format = 'sdist' }]"
    assert carries_audit_record(mutated_manifest(INCLUDE_LINE, respelled))


def test_pin_passes_with_the_entry_in_array_of_tables_form() -> None:
    respelled = (
        "[[tool.maturin.include]]\n"
        'path = ".cargo/audit.toml"\n'
        'format = "sdist"'
    )
    assert carries_audit_record(mutated_manifest(INCLUDE_LINE, respelled))


def test_pin_passes_with_whitespace_in_the_section_header() -> None:
    mutated = mutated_manifest("[tool.maturin]", "[ tool.maturin ]")
    assert carries_audit_record(mutated)


def test_pin_fails_on_an_emptied_audit_record() -> None:
    text = audit_record_text()
    assert text != ""
    assert not audit_record_names_the_recorded_advisories("")


def test_pin_fails_when_an_advisory_is_dropped_from_the_record() -> None:
    lines = audit_record_text().splitlines()
    kept = [line for line in lines if "RUSTSEC-2026-0177" not in line]
    assert len(kept) < len(lines)
    assert not audit_record_names_the_recorded_advisories("\n".join(kept))


def test_pin_fails_with_an_extra_advisory_in_the_record() -> None:
    text = audit_record_text()
    mutated = text.replace(
        '"RUSTSEC-2026-0177",', '"RUSTSEC-2026-0177",\n    "RUSTSEC-9999-9999",'
    )
    assert mutated != text
    assert not audit_record_names_the_recorded_advisories(mutated)
