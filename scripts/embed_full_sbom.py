#!/usr/bin/env python3
"""Embed a full-tree SBOM into every wheel in a directory.

Maturin builds each wheel for one target and feeds its SBOM
generator the dependency graph filtered to that target, so a
released wheel carries only its own platform branch of the tree.
The README promises the full locked tree in every wheel, and the
SBOM guard asserts exactly that promise, so the release workflow
generates one full-tree document with cargo cyclonedx over all
targets and runs this script on each build job's wheels before
upload. The script replaces the single embedded SBOM entry in
every wheel with the supplied document and regenerates that
entry's RECORD line, copying every other entry and every other
RECORD line untouched.

The script fails closed. A wheel with zero or several SBOM
entries, a RECORD without exactly one line for the entry, a
replacement that does not parse as a CycloneDX document, or a
replacement whose root component name does not match the SBOM
entry's file name each refuse the whole run, and a refused
wheel is left byte-untouched, because each wheel is rewritten
through a temporary file in its own directory and moved into
place only once complete.

Usage. embed_full_sbom.py DIRECTORY SBOM_FILE
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path


def fail(message: str) -> None:
    print(f"embed_full_sbom: FAIL: {message}")
    sys.exit(1)


def sbom_entries(names: list[str]) -> list[str]:
    """Every SBOM entry in one wheel's name list.

    The matcher is the guard's own (scripts/check_wheel_sbom.py),
    so the entry this script replaces is exactly the entry the
    guard reads.
    """
    entries: list[str] = []
    for name in names:
        parts = name.split("/")
        if (
            len(parts) == 3
            and parts[0].endswith(".dist-info")
            and parts[1] == "sboms"
            and parts[2].endswith(".json")
        ):
            entries.append(name)
    return entries


def record_entry_name(names: list[str]) -> str | None:
    """The dist-info RECORD entry of a wheel, when it carries one."""
    for name in names:
        parts = name.split("/")
        if (
            len(parts) == 2
            and parts[0].endswith(".dist-info")
            and parts[1] == "RECORD"
        ):
            return name
    return None


def record_line(name: str, raw: bytes) -> str:
    """The RECORD line for one entry, in the wheel format.

    The digest is the SHA-256 of the entry bytes, urlsafe base64
    with the padding stripped, and the size is the byte count.
    """
    digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
    return f"{name},sha256={digest.decode('ascii').rstrip('=')},{len(raw)}"


def load_replacement(path: Path) -> tuple[bytes, str]:
    """Read and judge the replacement document before any wheel opens."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        fail(f"the replacement SBOM at {path} cannot be read: {exc}")
        raise AssertionError  # unreachable, fail exits
    try:
        document = json.loads(raw)
    except ValueError:
        fail(f"the replacement SBOM at {path} does not parse as JSON")
        raise AssertionError  # unreachable, fail exits
    if not isinstance(document, dict) or document.get("bomFormat") != "CycloneDX":
        fail(f"the replacement SBOM at {path} is not a CycloneDX document")
        raise AssertionError  # unreachable, fail exits
    metadata = document.get("metadata")
    root = metadata.get("component") if isinstance(metadata, dict) else None
    root_name = root.get("name") if isinstance(root, dict) else None
    if not isinstance(root_name, str) or not root_name:
        fail(f"the replacement SBOM at {path} carries no root component name")
        raise AssertionError  # unreachable, fail exits
    return raw, root_name


def embed(wheel: Path, replacement: bytes, root_name: str) -> None:
    """Replace one wheel's SBOM entry, or refuse leaving it untouched."""
    with zipfile.ZipFile(wheel) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(set(names)) != len(names):
            fail(
                f"{wheel.name}: the wheel carries duplicate entry "
                "names, which this rewrite will not normalise"
            )
        archive_comment = archive.comment
        entries = sbom_entries(names)
        if len(entries) != 1:
            fail(
                f"{wheel.name}: expected exactly one embedded SBOM "
                f"entry, found {len(entries)}"
            )
        entry = entries[0]
        expected_file = f"{root_name}.cyclonedx.json"
        if entry.split("/")[2] != expected_file:
            fail(
                f"{wheel.name}: the replacement root {root_name!r} does "
                f"not match the embedded SBOM entry {entry!r}"
            )
        record = record_entry_name(names)
        if record is None:
            fail(f"{wheel.name}: the wheel carries no RECORD entry")
        payloads = {info.filename: archive.read(info.filename) for info in infos}
    try:
        record_text = payloads[record].decode("utf-8")
    except UnicodeDecodeError:
        fail(f"{wheel.name}: the RECORD entry is not UTF-8 text")
    lines = record_text.splitlines(keepends=True)
    matches = [
        index
        for index, line in enumerate(lines)
        if line.rstrip("\r\n").split(",", 1)[0] == entry
    ]
    if len(matches) != 1:
        fail(
            f"{wheel.name}: RECORD holds {len(matches)} lines for "
            f"{entry}, not exactly one"
        )
    index = matches[0]
    ending = lines[index][len(lines[index].rstrip("\r\n")):]
    lines[index] = record_line(entry, replacement) + ending
    payloads[record] = "".join(lines).encode("utf-8")
    payloads[entry] = replacement
    handle, temp_name = tempfile.mkstemp(
        dir=wheel.parent, prefix=wheel.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "wb") as stream:
            with zipfile.ZipFile(stream, "w") as out:
                for info in infos:
                    clone = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                    clone.compress_type = info.compress_type
                    clone.external_attr = info.external_attr
                    clone.internal_attr = info.internal_attr
                    clone.create_system = info.create_system
                    clone.comment = info.comment
                    clone.extra = info.extra
                    out.writestr(clone, payloads[info.filename])
                out.comment = archive_comment
        os.replace(temp_name, wheel)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: embed_full_sbom.py DIRECTORY SBOM_FILE")
        sys.exit(2)
    directory = Path(sys.argv[1])
    replacement, root_name = load_replacement(Path(sys.argv[2]))
    wheels = sorted(directory.glob("*.whl"))
    if not wheels:
        fail(f"no wheels found in {directory}")
    for wheel in wheels:
        embed(wheel, replacement, root_name)
    print(
        f"embed_full_sbom: OK, embedded the full SBOM in "
        f"{len(wheels)} wheel(s)"
    )


if __name__ == "__main__":
    main()
