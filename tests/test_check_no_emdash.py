"""Tests for scripts/check_no_emdash.py, the em dash guard.

The guard is exercised against a disposable staged tree, in the
idiom of the version guard tests. The staged tree carries its
own copy of the script, because the script derives its root
from its own path and lists the tree's files through git. The
clean control runs the same staging without the offender, so
the failure case cannot pass vacuously (audit round 6,
A50-109).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EM_DASH = "\u2014"
EN_DASH = "\u2013"


def make_tree(tmp_path: Path, files: dict[str, str]) -> Path:
    script_dir = tmp_path / "scripts"
    script_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "scripts" / "check_no_emdash.py", script_dir)
    for rel, text in files.items():
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    return tmp_path


def run_guard(tree: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(tree / "scripts" / "check_no_emdash.py")],
        capture_output=True,
        text=True,
    )


def test_clean_tree_passes(tmp_path):
    tree = make_tree(tmp_path, {"clean.md": "plain hyphens - only\n"})
    result = run_guard(tree)
    assert result.returncode == 0, result.stdout
    assert "zero em dashes" in result.stdout


def test_offender_is_named_and_fails(tmp_path):
    tree = make_tree(
        tmp_path,
        {
            "clean.md": "plain hyphens - only\n",
            "dirty.md": f"one {EM_DASH} dash and another {EM_DASH}\n",
        },
    )
    result = run_guard(tree)
    assert result.returncode == 1, result.stdout
    assert "dirty.md: 2 em dash(es)" in result.stdout
    assert "clean.md" not in result.stdout


def test_en_dash_is_data_not_prose(tmp_path):
    tree = make_tree(tmp_path, {"ranges.md": f"pages 3{EN_DASH}5\n"})
    result = run_guard(tree)
    assert result.returncode == 0, result.stdout
