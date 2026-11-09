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
mentions the file. The pins stay static. The guard at the
end of this module goes one step further and builds the
real source distribution with maturin, then asserts on the
artifact itself. It names the audit record member under the
package root, compares that member byte for byte with the
record in the repository, and names the standing members a
sound sdist carries, so a build that stopped honouring the
include entry, or one that produced a hollow archive, fails
in the suite instead of waiting for a manual census. The
guard builds from a plain copy of the tree, with no version
control state in it, for a measured reason. In a checkout,
cargo's own package listing carries tracked dot path files
whether or not the include entry stands, so a build there
cannot see the entry dropped. A plain tree is also the shape
the round's artifact drives build from, and the shape a
tarball consumer builds from.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

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


# The artifact guard. The pins above decide the manifest and the
# record as data. The tests below decide the built artifact itself,
# because a build tool change could stop honouring the include
# entry while the manifest still reads sound. The expected members
# are literals here, independent of the configuration under test,
# so the guard never certifies the configuration against itself.

STANDING_SDIST_MEMBERS = (
    "python/placekit/__init__.py",
    "Cargo.toml",
    "Cargo.lock",
    "pyproject.toml",
    "src/lib.rs",
    "crates/placekit-core/Cargo.toml",
    "crates/placekit-core/src/lib.rs",
    "python/placekit/client.py",
    "python/placekit/models.py",
    "python/placekit/_placekit.pyi",
    "python/placekit/py.typed",
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "rust-toolchain.toml",
    "scripts/check_version.py",
    "tests/test_client.py",
)

# The standing members name one carrier per family the sdist
# holds, so an archive that dropped a whole family fails on the
# missing name. The floor below watches the bulk the names cannot
# reach. The census at the head this guard landed with counted
# 138 file members, and the floor sits at 130, under that count
# with headroom for small removals a later round might make on
# purpose, and far above the handful of members a hollow archive
# carries. An exact member list would rot instead, because rounds
# add test modules and documents as a matter of course.
SDIST_MEMBER_COUNT_FLOOR = 130


def find_maturin() -> Path:
    """The maturin beside the running interpreter, else the one on PATH."""
    sibling = Path(sys.executable).parent / "maturin"
    if sibling.is_file():
        return sibling
    found = shutil.which("maturin")
    assert found is not None, "no maturin beside the interpreter or on PATH"
    return Path(found)


STAGE_IGNORE_NAMES = frozenset(
    {".git", ".venv", ".pytest_cache", "__pycache__", "target"}
)


def ignore_stage_noise(directory: str, names: list[str]) -> list[str]:
    """The copy exclusions for the staged tree.

    The version control entry goes so the staged tree is a plain
    tree, the shape whose build the include entry decides. Build
    output, caches, and a virtual environment go because the sdist
    never carries them and copying a target directory could dwarf
    the tree itself.
    """
    return [name for name in names if name in STAGE_IGNORE_NAMES]


@pytest.fixture(scope="module")
def built_sdist_members(tmp_path_factory) -> dict[str, bytes]:
    """The real sdist, built once, as member bytes keyed by relative path.

    The build runs in a factory temp directory unique to the worker
    and the module, so parallel workers never share an output path,
    and it assembles files only, with no compilation. It builds
    from a plain copy of the repository tree staged in that
    directory, never from the checkout itself.
    """
    base = tmp_path_factory.mktemp("round66-sdist")
    stage = base / "tree"
    shutil.copytree(ROOT, stage, ignore=ignore_stage_noise)
    out = base / "dist"
    out.mkdir()
    env = dict(os.environ)
    if shutil.which("cargo") is None:
        # Maturin reads cargo metadata even for a pure assembly build.
        # Fall back to the standard rustup location so the guard does
        # not depend on the caller's PATH carrying it.
        cargo_bin = Path.home() / ".cargo" / "bin"
        if (cargo_bin / "cargo").is_file():
            env["PATH"] = str(cargo_bin) + os.pathsep + env.get("PATH", "")
    result = subprocess.run(
        [
            str(find_maturin()),
            "sdist",
            "--manifest-path",
            str(stage / "Cargo.toml"),
            "--out",
            str(out),
        ],
        cwd=stage,
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    archives = sorted(out.glob("*.tar.gz"))
    assert len(archives) == 1, f"expected one sdist in {out}, found {archives}"
    members: dict[str, bytes] = {}
    with tarfile.open(archives[0]) as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            parts = member.name.split("/", 1)
            assert len(parts) == 2, f"sdist member outside a package root, {member.name}"
            handle = archive.extractfile(member)
            assert handle is not None
            members[parts[1]] = handle.read()
    return members


def test_built_sdist_carries_the_audit_record(built_sdist_members) -> None:
    assert AUDIT_PATH in built_sdist_members


def test_built_sdist_audit_record_matches_the_repository_record(
    built_sdist_members,
) -> None:
    assert built_sdist_members[AUDIT_PATH] == AUDIT_RECORD.read_bytes()


def test_built_sdist_carries_the_standing_members(built_sdist_members) -> None:
    for name in STANDING_SDIST_MEMBERS:
        assert name in built_sdist_members, f"standing sdist member missing, {name}"


def test_built_sdist_carries_at_least_the_member_count_floor(
    built_sdist_members,
) -> None:
    assert len(built_sdist_members) >= SDIST_MEMBER_COUNT_FLOOR, (
        f"sdist carries {len(built_sdist_members)} file members, "
        f"under the floor of {SDIST_MEMBER_COUNT_FLOOR}"
    )
