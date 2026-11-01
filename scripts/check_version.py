#!/usr/bin/env python3
"""Fail unless every place the version lives agrees.

The version is carried in the root Cargo.toml (the source maturin reads
for the Python package), in the placekit-core crate manifest, in
Cargo.lock's entry for the placekit package, in the top released entry
of CHANGELOG.md, and in the __version__ fallback literal in
python/placekit/__init__.py. pyproject.toml declares its version
dynamic, so maturin derives it from Cargo.toml and the two cannot drift;
if a static version ever appears in pyproject.toml it is checked too.

Usage: check_version.py [EXPECTED]

With EXPECTED (for example the version from a release tag, without the
leading v) the manifest version must also equal it. The wheels workflow's
publish job uses this as its release guard.

When EXPECTED is given, which is the publish path, the guard also
refuses a changelog whose Unreleased section still holds entries and
a changelog with no release heading at all, because a tag pushed over
unpromoted work would ship a changelog that mislabels the release.
In both modes a changelog holding two release headings for the same
version fails, and headings inside fenced code blocks are examples
rather than entries and are ignored. Heading recognition is tolerant
of level, spacing, case, and trailing matter, so a restyled heading
cannot slip past the guard unread.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message: str) -> None:
    print(f"check_version: FAIL: {message}")
    sys.exit(1)


def cargo_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    try:
        import tomllib

        return tomllib.loads(text)["package"]["version"]
    except ModuleNotFoundError:
        match = re.search(
            r"\[package\][^\[]*?^version\s*=\s*\"([^\"]+)\"",
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
        if not match:
            fail(f"no [package] version found in {path}")
        return match.group(1)


def pyproject_version() -> str | None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    try:
        import tomllib

        project = tomllib.loads(text)["project"]
    except ModuleNotFoundError:
        return None
    if "version" in project:
        return project["version"]
    if "version" in project.get("dynamic", []):
        return None
    fail("pyproject.toml has neither a static version nor a dynamic one")
    return None


def cargo_lock_version() -> str:
    text = (ROOT / "Cargo.lock").read_text(encoding="utf-8")
    try:
        import tomllib

        packages = tomllib.loads(text)["package"]
    except ModuleNotFoundError:
        packages = None
    if packages is not None:
        for package in packages:
            if package.get("name") == "placekit":
                return package["version"]
        fail("no package entry named placekit found in Cargo.lock")
    for block in text.split("[[package]]"):
        name = re.search(r'^name\s*=\s*"([^"]+)"', block, flags=re.MULTILINE)
        version = re.search(r'^version\s*=\s*"([^"]+)"', block, flags=re.MULTILINE)
        if name and version and name.group(1) == "placekit":
            return version.group(1)
    fail("no package entry named placekit found in Cargo.lock")
    return ""


def _outside_fences(text: str) -> list[str]:
    """Return the lines of a markdown file outside its fenced code blocks.

    A fence closes only on a marker of the same character at least as
    long as the marker that opened it, matching how markdown renders,
    so a shorter marker inside a longer fence stays content.
    """
    lines = []
    fence_char = None
    fence_len = 0
    for line in text.splitlines():
        stripped = line.strip()
        if fence_char is None:
            match = re.match(r"(`{3,}|~{3,})", stripped)
            if match:
                fence_char = match.group(1)[0]
                fence_len = len(match.group(1))
            else:
                lines.append(line)
        else:
            match = re.fullmatch(r"(`+|~+)", stripped)
            if (
                match
                and match.group(1)[0] == fence_char
                and len(match.group(1)) >= fence_len
            ):
                fence_char = None
    return lines


_HEADING = re.compile(r"(#{1,6})\s+(.*)")
_RELEASE_HEADING = re.compile(r"\[(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)\]")


def _heading(line: str) -> tuple[int, str] | None:
    """Return the level and text of an ATX heading line, or None.

    Recognition is tolerant for the guard's purposes. Any heading
    level counts, the spacing after the hash marks is flexible, and
    the text keeps any trailing matter for the caller to allow for,
    so a heading restyled in any of those ways is still read.
    """
    match = _HEADING.match(line.strip())
    if not match:
        return None
    return len(match.group(1)), match.group(2).strip()


def changelog_state() -> tuple[list[str], bool]:
    """Return the changelog release headings and its Unreleased state.

    The first value is every numeric release heading in file order.
    The second is True when the Unreleased section still holds entries,
    meaning a line that is neither blank nor a heading. Both readings
    ignore fenced code blocks, so an example heading inside a fence is
    never taken for a release entry, and both read headings tolerantly
    (see _heading), so a restyled heading is still a heading here.
    """
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = []
    unreleased_nonempty = False
    in_unreleased = False
    for line in _outside_fences(text):
        heading = _heading(line)
        if heading is not None:
            level, heading_text = heading
            is_unreleased = heading_text.lower().startswith("[unreleased]")
            release = _RELEASE_HEADING.match(heading_text)
            if release:
                headings.append(release.group(1))
            # A deeper subheading never ends the Unreleased section,
            # so the entries under an Added or Fixed subheading still
            # count. A release heading at any level does, and so does
            # any other heading at level two or above.
            if is_unreleased:
                in_unreleased = True
            elif release or level <= 2:
                in_unreleased = False
            continue
        if in_unreleased and line.strip() and not line.strip().startswith("#"):
            unreleased_nonempty = True
    return headings, unreleased_nonempty


def package_fallback_version() -> str:
    text = (ROOT / "python" / "placekit" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^\s*__version__\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    if not match:
        fail("no __version__ fallback literal found in python/placekit/__init__.py")
    return match.group(1)


def main() -> None:
    found = {
        "Cargo.toml": cargo_version(ROOT / "Cargo.toml"),
        "crates/placekit-core/Cargo.toml": cargo_version(
            ROOT / "crates" / "placekit-core" / "Cargo.toml"
        ),
        "Cargo.lock": cargo_lock_version(),
        "python/placekit/__init__.py": package_fallback_version(),
    }
    headings, unreleased_nonempty = changelog_state()
    if headings:
        found["CHANGELOG.md"] = headings[0]
    static_pyproject = pyproject_version()
    if static_pyproject is not None:
        found["pyproject.toml"] = static_pyproject

    versions = set(found.values())
    if len(versions) != 1:
        for source, version in found.items():
            print(f"check_version: {source}: {version}")
        fail("versions disagree")
    version = versions.pop()

    if headings.count(version) > 1:
        fail(f"CHANGELOG.md has more than one release heading for version {version}")

    if len(sys.argv) > 1:
        if unreleased_nonempty:
            fail(
                "CHANGELOG.md still holds entries under Unreleased, "
                "fold them into the release entry before tagging"
            )
        if not headings:
            fail("no released version entry (## [x.y.z]) found in CHANGELOG.md")
        expected = sys.argv[1].removeprefix("v")
        if expected != version:
            fail(f"expected {expected} (from argument), manifests say {version}")
        print(f"check_version: OK, version {version} everywhere, matches {expected}")
    else:
        print(f"check_version: OK, version {version} everywhere")


if __name__ == "__main__":
    main()
