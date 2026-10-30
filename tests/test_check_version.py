"""Tests for scripts/check_version.py, the version coherence guard.

The guard is exercised against a disposable copy of the repo layout, so
a test can mutate one carrier of the version and assert the guard fails.
The control case runs the same copy unmutated and asserts it passes, so
the failure cases cannot pass vacuously.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

LAYOUT = [
    "scripts/check_version.py",
    "Cargo.toml",
    "crates/placekit-core/Cargo.toml",
    "Cargo.lock",
    "CHANGELOG.md",
    "pyproject.toml",
    "python/placekit/__init__.py",
]


def make_copy(tmp_path: Path) -> Path:
    for rel in LAYOUT:
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, dest)
    return tmp_path


def run_guard(tree: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(tree / "scripts" / "check_version.py")],
        capture_output=True,
        text=True,
    )


def mutate_lock_version(lock_text: str, new_version: str) -> str:
    blocks = lock_text.split("[[package]]")
    for i, block in enumerate(blocks):
        if 'name = "placekit"' in block.split("dependencies")[0]:
            lines = block.splitlines(keepends=True)
            for j, line in enumerate(lines):
                if line.startswith("version ="):
                    lines[j] = f'version = "{new_version}"\n'
                    blocks[i] = "".join(lines)
                    return "[[package]]".join(blocks)
            raise AssertionError("placekit block in Cargo.lock has no version")
    raise AssertionError("no placekit package block found in Cargo.lock")


def test_guard_passes_on_the_real_layout(tmp_path: Path) -> None:
    result = run_guard(make_copy(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_guard_fails_when_cargo_lock_disagrees(tmp_path: Path) -> None:
    tree = make_copy(tmp_path)
    lock = tree / "Cargo.lock"
    lock.write_text(mutate_lock_version(lock.read_text(), "9.9.9"))
    result = run_guard(tree)
    assert result.returncode == 1
    assert "Cargo.lock: 9.9.9" in result.stdout


def test_guard_accepts_a_prerelease_changelog_heading(tmp_path: Path) -> None:
    tree = make_copy(tmp_path)
    changelog = tree / "CHANGELOG.md"
    # Move every carrier to the same prerelease version.
    text = changelog.read_text()
    text = text.replace("## [0.1.0]", "## [0.2.0-rc.1]")
    changelog.write_text(text)
    for rel in ("Cargo.toml", "crates/placekit-core/Cargo.toml"):
        path = tree / rel
        path.write_text(path.read_text().replace('version = "0.1.0"', 'version = "0.2.0-rc.1"'))
    lock = tree / "Cargo.lock"
    lock.write_text(mutate_lock_version(lock.read_text(), "0.2.0-rc.1"))
    init = tree / "python" / "placekit" / "__init__.py"
    init.write_text(init.read_text().replace('"0.1.0"', '"0.2.0-rc.1"'))
    result = run_guard(tree)
    assert result.returncode == 0, result.stdout + result.stderr
