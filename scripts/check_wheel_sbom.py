#!/usr/bin/env python3
"""Fail unless every wheel in a directory carries a sound SBOM.

Maturin embeds a CycloneDX SBOM in each wheel under the dist-info
sboms folder, and the README promises it to readers. The guard
asserts the promise in two parts. Presence (R18-A8): a toolchain
change that dropped the SBOM would otherwise have shipped
silently. Content (Round 28, Finding 4): the document must parse
as CycloneDX JSON, its component name set must equal the
Cargo.lock package set with the workspace root package carried
as the metadata component rather than as a component entry, and
every component must carry a licence entry, so an empty,
truncated or wrong tree SBOM cannot publish green either. The
wheels workflow's test leg runs this check over the wheel it
downloaded.

Usage: check_wheel_sbom.py DIRECTORY [LOCKFILE]

LOCKFILE defaults to the Cargo.lock of the checkout this script
sits in, which is the lockfile the test leg's own checkout
provides. The check also fails when the directory holds no wheel
at all, so a wrong path cannot pass vacuously.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message: str) -> None:
    print(f"check_wheel_sbom: FAIL: {message}")
    sys.exit(1)


def wheel_sbom_entry(wheel: Path) -> str | None:
    """The SBOM entry inside one wheel archive, or None."""
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            parts = name.split("/")
            if (
                len(parts) == 3
                and parts[0].endswith(".dist-info")
                and parts[1] == "sboms"
                and parts[2].endswith(".json")
            ):
                return name
    return None


def missing_sbom(directory: Path) -> list[str]:
    """Names of the wheels in a directory that carry no SBOM."""
    return [
        wheel.name
        for wheel in sorted(directory.glob("*.whl"))
        if wheel_sbom_entry(wheel) is None
    ]


def lock_package_names(lockfile: Path) -> set[str]:
    """The package names a Cargo.lock declares."""
    text = lockfile.read_text(encoding="utf-8")
    try:
        import tomllib

        return {package["name"] for package in tomllib.loads(text)["package"]}
    except ModuleNotFoundError:
        # Python 3.10 has no tomllib; the test leg runs this guard
        # on the abi3 floor interpreter too. A package block's own
        # name is the first name line after its [[package]] header.
        names: set[str] = set()
        in_package = False
        for line in text.splitlines():
            if line.strip() == "[[package]]":
                in_package = True
            elif in_package and line.startswith("name = "):
                names.add(line.split('"')[1])
                in_package = False
        return names


def _carries_licence(component: dict) -> bool:
    licences = component.get("licenses")
    if not isinstance(licences, list) or not licences:
        return False
    return all(
        isinstance(entry, dict) and ("license" in entry or "expression" in entry)
        for entry in licences
    )


def sbom_problems(directory: Path, lockfile: Path) -> list[str]:
    """Content problems in the SBOMs of a directory's wheels.

    Wheels without an SBOM are skipped here; the presence check
    names them separately. Every other wheel's document must
    parse as CycloneDX, carry the lockfile's root package as its
    metadata component, hold exactly the lockfile's remaining
    package names as its component set, and give every component
    a licence entry.
    """
    lock_names = lock_package_names(lockfile)
    problems: list[str] = []
    for wheel in sorted(directory.glob("*.whl")):
        entry = wheel_sbom_entry(wheel)
        if entry is None:
            continue
        with zipfile.ZipFile(wheel) as archive:
            raw = archive.read(entry)
        try:
            document = json.loads(raw)
        except ValueError:
            problems.append(f"{wheel.name}: the embedded SBOM does not parse as JSON")
            continue
        if not isinstance(document, dict) or document.get("bomFormat") != "CycloneDX":
            problems.append(f"{wheel.name}: the embedded SBOM is not a CycloneDX document")
            continue
        metadata = document.get("metadata")
        root = metadata.get("component") if isinstance(metadata, dict) else None
        root_name = root.get("name") if isinstance(root, dict) else None
        if root_name not in lock_names:
            problems.append(
                f"{wheel.name}: the SBOM root component {root_name!r} "
                "is not a Cargo.lock package"
            )
            continue
        components = document.get("components")
        if not isinstance(components, list) or not all(
            isinstance(component, dict) and isinstance(component.get("name"), str)
            for component in components
        ):
            problems.append(f"{wheel.name}: the SBOM component list is malformed")
            continue
        names = {component["name"] for component in components}
        expected = lock_names - {root_name}
        if names != expected:
            missing = ", ".join(sorted(expected - names)) or "none"
            extra = ", ".join(sorted(names - expected)) or "none"
            problems.append(
                f"{wheel.name}: SBOM components differ from Cargo.lock "
                f"(missing: {missing}; extra: {extra})"
            )
        for component in components:
            if not _carries_licence(component):
                problems.append(
                    f"{wheel.name}: SBOM component {component['name']} "
                    "carries no licence entry"
                )
    return problems


def main() -> None:
    if len(sys.argv) not in (2, 3):
        print("usage: check_wheel_sbom.py DIRECTORY [LOCKFILE]")
        sys.exit(2)
    directory = Path(sys.argv[1])
    lockfile = Path(sys.argv[2]) if len(sys.argv) == 3 else ROOT / "Cargo.lock"
    wheels = sorted(directory.glob("*.whl"))
    if not wheels:
        fail(f"no wheels found in {directory}")
    missing = missing_sbom(directory)
    if missing:
        fail(f"wheels without an embedded SBOM: {', '.join(missing)}")
    if not lockfile.is_file():
        fail(f"no Cargo.lock to compare against at {lockfile}")
    problems = sbom_problems(directory, lockfile)
    if problems:
        fail("; ".join(problems))
    print(
        f"check_wheel_sbom: OK, {len(wheels)} wheel(s) carry an embedded "
        "SBOM matching Cargo.lock"
    )


if __name__ == "__main__":
    main()
