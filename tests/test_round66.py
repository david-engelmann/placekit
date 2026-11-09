"""Round 66 pins for the sdist carriage of the cargo audit record.

Round 66 taught the build to carry the cargo audit disposition
record at .cargo/audit.toml in the source distribution, through
an include entry on the [tool.maturin] table of pyproject.toml.
The build tool's standing dot path rule would otherwise leave
the file out, and an audit run from the sdist would resurface
two published advisories without the dispositions and the
reachability rationale the repository records for them. Nothing
pinned the carriage, so a later edit dropping the include entry
would regress it silently. These pins read the manifest the way
the repo's own guards read it, through tomllib where the
interpreter carries it and a section scan on the floor
interpreter that does not, and they decide the carriage on the
parsed structure. An entry counts only when one entry's path is
exactly .cargo/audit.toml and its format is exactly sdist. The
mutation cases beside the control case hold the pin to that
decision, so it cannot pass on a manifest that merely mentions
the file. The pin stays static and builds nothing. The census
evidence that the built sdist carries the file lives in the
round audit.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
AUDIT_RECORD = ROOT / ".cargo" / "audit.toml"

AUDIT_PATH = ".cargo/audit.toml"
SDIST_FORMAT = "sdist"


def include_entries_scan(text: str) -> list[tuple[object, object]]:
    """The [tool.maturin] include (path, format) pairs, by section scan.

    Python 3.10 has no tomllib, and the test leg runs on the
    abi3 floor interpreter too, the same split the wheel SBOM
    guard makes. The scan reads only the [tool.maturin] section
    and takes each include entry's path and format in the order
    the manifest writes them.
    """
    pairs: list[tuple[object, object]] = []
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_section = stripped == "[tool.maturin]"
            continue
        if in_section:
            for match in re.finditer(
                r'path\s*=\s*"([^"]+)"\s*,\s*format\s*=\s*"([^"]+)"', line
            ):
                pairs.append((match.group(1), match.group(2)))
    return pairs


def include_entries(text: str) -> list[tuple[object, object]]:
    """The (path, format) pairs the [tool.maturin] include list declares."""
    try:
        import tomllib
    except ModuleNotFoundError:
        return include_entries_scan(text)
    document = tomllib.loads(text)
    maturin = document.get("tool", {}).get("maturin", {})
    entries: list[tuple[object, object]] = []
    for entry in maturin.get("include", []):
        if isinstance(entry, dict):
            entries.append((entry.get("path"), entry.get("format")))
    return entries


def carries_audit_record(text: str) -> bool:
    """Whether the include list carries the audit record in the sdist."""
    return (AUDIT_PATH, SDIST_FORMAT) in include_entries(text)


def manifest_text() -> str:
    return PYPROJECT.read_text(encoding="utf-8")


def test_sdist_include_carries_the_audit_record() -> None:
    assert carries_audit_record(manifest_text())


def test_audit_record_exists_in_the_tree() -> None:
    assert AUDIT_RECORD.is_file()


def test_pin_fails_without_the_include_entry() -> None:
    lines = manifest_text().splitlines()
    kept = [line for line in lines if not line.startswith("include =")]
    assert len(kept) < len(lines)
    assert not carries_audit_record("\n".join(kept))


def test_pin_fails_on_an_altered_audit_path() -> None:
    text = manifest_text()
    mutated = text.replace(AUDIT_PATH, ".cargo/audit-copy.toml")
    assert mutated != text
    assert not carries_audit_record(mutated)


def test_pin_fails_on_an_altered_format() -> None:
    text = manifest_text()
    mutated = text.replace('format = "sdist"', 'format = "wheel"')
    assert mutated != text
    assert not carries_audit_record(mutated)
