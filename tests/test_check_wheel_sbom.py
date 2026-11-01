"""Tests for scripts/check_wheel_sbom.py, the wheel SBOM guard.

Wheels are plain zip archives, so the tests build them in a temp
directory with and without the dist-info sboms entry the guard
exists to assert. Each failure case is paired with the passing
shape, so a case cannot pass vacuously.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_wheel_sbom.py"


def load_guard():
    spec = importlib.util.spec_from_file_location("check_wheel_sbom", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_wheel(directory: Path, name: str, *, sbom: bool) -> Path:
    wheel = directory / name
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("placekit/__init__.py", "")
        archive.writestr("placekit-0.1.0.dist-info/METADATA", "")
        if sbom:
            archive.writestr(
                "placekit-0.1.0.dist-info/sboms/placekit.cyclonedx.json",
                "{}",
            )
    return wheel


def run_guard(directory: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(directory)],
        capture_output=True,
        text=True,
    )


def test_wheel_with_sbom_passes(tmp_path):
    guard = load_guard()
    make_wheel(tmp_path, "placekit-0.1.0-py3-none-any.whl", sbom=True)
    assert guard.missing_sbom(tmp_path) == []
    assert run_guard(tmp_path).returncode == 0


def test_wheel_without_sbom_is_named(tmp_path):
    guard = load_guard()
    make_wheel(tmp_path, "placekit-0.1.0-py3-none-any.whl", sbom=False)
    assert guard.missing_sbom(tmp_path) == ["placekit-0.1.0-py3-none-any.whl"]
    result = run_guard(tmp_path)
    assert result.returncode == 1
    assert "placekit-0.1.0-py3-none-any.whl" in result.stdout


def test_one_bare_wheel_fails_the_whole_directory(tmp_path):
    guard = load_guard()
    make_wheel(tmp_path, "full.whl", sbom=True)
    make_wheel(tmp_path, "bare.whl", sbom=False)
    assert guard.missing_sbom(tmp_path) == ["bare.whl"]
    assert run_guard(tmp_path).returncode == 1


def test_directory_without_wheels_fails(tmp_path):
    result = run_guard(tmp_path)
    assert result.returncode == 1
    assert "no wheels found" in result.stdout
