#!/usr/bin/env python3
"""Fail unless every place the version lives agrees.

The version is carried in the root Cargo.toml (the source maturin reads
for the Python package), in the placekit-core crate manifest, in the top
released entry of CHANGELOG.md, and in the __version__ fallback literal
in python/placekit/__init__.py. pyproject.toml declares its version
dynamic, so maturin derives it from Cargo.toml and the two cannot drift;
if a static version ever appears in pyproject.toml it is checked too.

Usage: check_version.py [EXPECTED]

With EXPECTED (for example the version from a release tag, without the
leading v) the manifest version must also equal it. The wheels workflow's
publish job uses this as its release guard.
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


def changelog_version() -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"^## \[(\d+\.\d+\.\d+)\]", text, flags=re.MULTILINE)
    if not match:
        fail("no released version entry (## [x.y.z]) found in CHANGELOG.md")
    return match.group(1)


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
        "CHANGELOG.md": changelog_version(),
        "python/placekit/__init__.py": package_fallback_version(),
    }
    static_pyproject = pyproject_version()
    if static_pyproject is not None:
        found["pyproject.toml"] = static_pyproject

    versions = set(found.values())
    if len(versions) != 1:
        for source, version in found.items():
            print(f"check_version: {source}: {version}")
        fail("versions disagree")
    version = versions.pop()

    if len(sys.argv) > 1:
        expected = sys.argv[1].removeprefix("v")
        if expected != version:
            fail(f"expected {expected} (from argument), manifests say {version}")
        print(f"check_version: OK, version {version} everywhere, matches {expected}")
    else:
        print(f"check_version: OK, version {version} everywhere")


if __name__ == "__main__":
    main()
