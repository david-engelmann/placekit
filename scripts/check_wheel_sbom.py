#!/usr/bin/env python3
"""Fail unless every wheel in a directory carries a sound SBOM.

Maturin embeds a CycloneDX SBOM in each wheel under the dist-info
sboms folder, and the README promises it to readers. The guard
asserts the promise in two parts. Presence (R18-A8) means a
toolchain change that dropped the SBOM would otherwise have
shipped silently. Content (Round 28, Finding 4, and its repair
pass) means every embedded document must parse as CycloneDX JSON
at the spec version the build emits, must carry the wheel's own
package as its metadata component, must hold exactly the
Cargo.lock packages with that root entry removed, compared as
name and version pairs so duplicate versions and scrambled
versions both show, and must give every component a licence
entry carrying content, so an empty, truncated or wrong tree
SBOM cannot publish green either. The wheels workflow's test leg
runs this check over the wheel it downloaded.

Usage. check_wheel_sbom.py DIRECTORY [LOCKFILE]

LOCKFILE defaults to the Cargo.lock of the checkout this script
sits in, which is the lockfile the test leg's own checkout
provides. The check also fails when the directory holds no wheel
at all, so a wrong path cannot pass vacuously.
"""

from __future__ import annotations

import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The CycloneDX spec version the SBOM generator emits, read from
# the document inside the wheel built from this tree during the
# Round 28 guard repair. A generator change that moves the
# emitted version fails here until the pin is updated on purpose.
EXPECTED_SPEC_VERSION = "1.5"


class LockfileError(Exception):
    """The comparison Cargo.lock cannot be read or parsed."""


def fail(message: str) -> None:
    print(f"check_wheel_sbom: FAIL: {message}")
    sys.exit(1)


def wheel_sbom_entries(wheel: Path) -> list[str]:
    """Every SBOM entry inside one wheel archive."""
    entries: list[str] = []
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            parts = name.split("/")
            if (
                len(parts) == 3
                and parts[0].endswith(".dist-info")
                and parts[1] == "sboms"
                and parts[2].endswith(".json")
            ):
                entries.append(name)
    return entries


def wheel_package_name(wheel: Path) -> str | None:
    """The distribution name a wheel declares for itself.

    The Name header of the dist-info METADATA entry is the
    wheel's own statement of its package. The first segment of
    the wheel file name carries the same name when no METADATA
    entry can be read.
    """
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            parts = name.split("/")
            if (
                len(parts) == 2
                and parts[0].endswith(".dist-info")
                and parts[1] == "METADATA"
            ):
                text = archive.read(name).decode("utf-8", "replace")
                for line in text.splitlines():
                    if line.lower().startswith("name:"):
                        value = line.partition(":")[2].strip()
                        if value:
                            return value
    return wheel.name.split("-", 1)[0] or None


def missing_sbom(directory: Path) -> list[str]:
    """Names of the wheels in a directory that carry no SBOM."""
    return [
        wheel.name
        for wheel in sorted(directory.glob("*.whl"))
        if not wheel_sbom_entries(wheel)
    ]


def _quoted_value(line: str, lockfile: Path) -> str:
    parts = line.split('"')
    if len(parts) < 3:
        raise LockfileError(
            f"the Cargo.lock at {lockfile} holds a malformed value "
            f"on the line {line.strip()!r}"
        )
    return parts[1]


def lock_packages_scan(text: str, lockfile: Path) -> list[tuple[str, str]]:
    """The (name, version) pairs a Cargo.lock declares, by block scan.

    Python 3.10 has no tomllib, and the test leg runs this guard
    on the abi3 floor interpreter too. A package block's own name
    and version are the first name and version lines after its
    [[package]] header.
    """
    pairs: list[tuple[str, str]] = []
    name: str | None = None
    version: str | None = None
    in_package = False

    def flush() -> None:
        nonlocal name, version
        if in_package:
            if name is None or version is None:
                raise LockfileError(
                    f"the Cargo.lock at {lockfile} holds a package "
                    "block without a name and a version"
                )
            pairs.append((name, version))
        name = None
        version = None

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[["):
            flush()
            in_package = stripped == "[[package]]"
        elif stripped.startswith("["):
            flush()
            in_package = False
        elif in_package and name is None and line.startswith("name = "):
            name = _quoted_value(line, lockfile)
        elif in_package and version is None and line.startswith("version = "):
            version = _quoted_value(line, lockfile)
    flush()
    return pairs


def lock_packages(lockfile: Path) -> list[tuple[str, str]]:
    """The (name, version) pairs a Cargo.lock declares, in file order."""
    try:
        text = lockfile.read_text(encoding="utf-8")
    except OSError as exc:
        raise LockfileError(
            f"cannot read the Cargo.lock at {lockfile} ({exc.strerror or exc})"
        ) from exc
    try:
        import tomllib
    except ModuleNotFoundError:
        return lock_packages_scan(text, lockfile)
    try:
        document = tomllib.loads(text)
    except ValueError as exc:
        raise LockfileError(
            f"the Cargo.lock at {lockfile} does not parse as TOML ({exc})"
        ) from exc
    packages = document.get("package")
    if not isinstance(packages, list):
        raise LockfileError(
            f"the Cargo.lock at {lockfile} declares no package list"
        )
    pairs: list[tuple[str, str]] = []
    for package in packages:
        if (
            not isinstance(package, dict)
            or not isinstance(package.get("name"), str)
            or not isinstance(package.get("version"), str)
        ):
            raise LockfileError(
                f"the Cargo.lock at {lockfile} holds a package entry "
                "without a name and a version"
            )
        pairs.append((package["name"], package["version"]))
    return pairs


def lock_package_names(lockfile: Path) -> set[str]:
    """The package names a Cargo.lock declares."""
    return {name for name, _version in lock_packages(lockfile)}


def _licence_entry_has_content(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    expression = entry.get("expression")
    if isinstance(expression, str) and expression.strip():
        return True
    licence = entry.get("license")
    if isinstance(licence, dict):
        return any(
            isinstance(licence.get(key), str) and bool(licence[key].strip())
            for key in ("id", "name")
        )
    return False


def _carries_licence(component: dict) -> bool:
    licences = component.get("licenses")
    if not isinstance(licences, list) or not licences:
        return False
    return all(_licence_entry_has_content(entry) for entry in licences)


def _format_pair(pair: tuple[str, str | None]) -> str:
    name, version = pair
    return f"{name} {version}" if version else f"{name} (no version)"


def _document_problems(
    label: str,
    raw: bytes,
    package_name: str | None,
    lock_counter: Counter,
) -> list[str]:
    """Content problems in one embedded SBOM document."""
    try:
        document = json.loads(raw)
    except ValueError:
        return [f"{label}: the embedded SBOM does not parse as JSON"]
    if not isinstance(document, dict) or document.get("bomFormat") != "CycloneDX":
        return [f"{label}: the embedded SBOM is not a CycloneDX document"]
    spec_version = document.get("specVersion")
    if spec_version != EXPECTED_SPEC_VERSION:
        return [
            f"{label}: the embedded SBOM declares spec version "
            f"{spec_version!r}, not the {EXPECTED_SPEC_VERSION} "
            "the build emits"
        ]
    metadata = document.get("metadata")
    root = metadata.get("component") if isinstance(metadata, dict) else None
    root_name = root.get("name") if isinstance(root, dict) else None
    if not any(pair[0] == root_name for pair in lock_counter):
        return [
            f"{label}: the SBOM root component {root_name!r} "
            "is not a Cargo.lock package"
        ]
    if package_name is not None and root_name != package_name:
        return [
            f"{label}: the SBOM root component {root_name!r} is not "
            f"the wheel's own package {package_name!r}"
        ]
    root_pairs = [pair for pair in lock_counter if pair[0] == root_name]
    if len(root_pairs) != 1:
        return [
            f"{label}: the SBOM root component {root_name!r} matches "
            f"{len(root_pairs)} Cargo.lock entries, not the one root entry"
        ]
    components = document.get("components")
    if not isinstance(components, list) or not all(
        isinstance(component, dict) and isinstance(component.get("name"), str)
        for component in components
    ):
        return [f"{label}: the SBOM component list is malformed"]
    pairs: Counter = Counter(
        (
            component["name"],
            component.get("version")
            if isinstance(component.get("version"), str)
            else None,
        )
        for component in components
    )
    expected = lock_counter - Counter({root_pairs[0]: 1})
    problems: list[str] = []
    if pairs != expected:
        missing = (
            ", ".join(
                sorted(_format_pair(pair) for pair in (expected - pairs).elements())
            )
            or "none"
        )
        extra = (
            ", ".join(
                sorted(_format_pair(pair) for pair in (pairs - expected).elements())
            )
            or "none"
        )
        problems.append(
            f"{label}: SBOM components differ from Cargo.lock "
            f"(missing: {missing}; extra: {extra})"
        )
    for component in components:
        if not _carries_licence(component):
            problems.append(
                f"{label}: SBOM component {component['name']} "
                "carries no licence entry"
            )
    return problems


def sbom_problems(directory: Path, lockfile: Path) -> list[str]:
    """Content problems in the SBOMs of a directory's wheels.

    Wheels without an SBOM are skipped here, since the presence
    check names them separately. Every SBOM entry a wheel carries
    must pass every stage. A document must parse as CycloneDX at
    the emitted spec version, carry the wheel's own package as
    its metadata component, hold exactly the lockfile's remaining
    packages as name and version pairs, and give every component
    a licence entry carrying content.
    """
    lock_counter: Counter = Counter(lock_packages(lockfile))
    problems: list[str] = []
    for wheel in sorted(directory.glob("*.whl")):
        entries = wheel_sbom_entries(wheel)
        if not entries:
            continue
        package_name = wheel_package_name(wheel)
        with zipfile.ZipFile(wheel) as archive:
            documents = [(entry, archive.read(entry)) for entry in entries]
        for entry, raw in documents:
            label = wheel.name if len(documents) == 1 else f"{wheel.name} ({entry})"
            problems.extend(
                _document_problems(label, raw, package_name, lock_counter)
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
    try:
        problems = sbom_problems(directory, lockfile)
    except LockfileError as exc:
        fail(str(exc))
    if problems:
        fail("; ".join(problems))
    print(
        f"check_wheel_sbom: OK, {len(wheels)} wheel(s) carry an embedded "
        "SBOM matching Cargo.lock"
    )


if __name__ == "__main__":
    main()
