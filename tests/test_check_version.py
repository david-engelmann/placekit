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


def run_guard(tree: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(tree / "scripts" / "check_version.py"), *args],
        capture_output=True,
        text=True,
    )


def standing_version(tree: Path) -> str:
    """The version a tree stands at, read from its root manifest.

    The tests name the standing release through this reader instead
    of a literal, so a version bump moves them with the tree rather
    than silently unmooring them from it.
    """
    for line in (tree / "Cargo.toml").read_text().splitlines():
        if line.startswith('version = "'):
            return line.split('"')[1]
    raise AssertionError("no version line in the tree's Cargo.toml")


def make_release_ready(tree: Path) -> Path:
    """Fold the copied changelog into the shape tag day expects.

    The entries under the Unreleased heading move under the
    release heading for the standing version and the Unreleased
    heading is left empty, which is the fold the release
    checklist asks for before the tag is cut. A copy that already
    carries a release heading for the standing version keeps that
    heading and its date, and the Unreleased entries join its
    section, so the fold lands exactly one release heading either
    way. The fold has to move the entries themselves, not just
    add a heading. While Unreleased held nothing the heading
    alone sufficed, but entries parked there for a future release
    (the audit programme's, for one) are exactly what the publish
    guard refuses to tag over.
    """
    changelog = tree / "CHANGELOG.md"
    lines = changelog.read_text().splitlines(keepends=True)
    current = standing_version(tree)
    unreleased_at = next(
        i for i, line in enumerate(lines) if line.startswith("## [Unreleased]")
    )
    section_end = next(
        (
            i
            for i in range(unreleased_at + 1, len(lines))
            if lines[i].startswith("## [")
        ),
        len(lines),
    )
    entries = lines[unreleased_at + 1 : section_end]
    release_at = next(
        (
            i
            for i in range(section_end, len(lines))
            if lines[i].startswith(f"## [{current}]")
        ),
        None,
    )
    if release_at is None:
        heading = f"## [{current}] - 2026-11-01\n"
        release_entries: list[str] = []
        rest = lines[section_end:]
    else:
        heading = lines[release_at]
        release_end = next(
            (
                i
                for i in range(release_at + 1, len(lines))
                if lines[i].startswith("## [")
            ),
            len(lines),
        )
        release_entries = lines[release_at + 1 : release_end]
        rest = lines[section_end:release_at] + lines[release_end:]

    def trimmed(block: list[str]) -> list[str]:
        while block and not block[0].strip():
            block = block[1:]
        while block and not block[-1].strip():
            block = block[:-1]
        return block

    out = lines[: unreleased_at + 1]
    out.append("\n")
    out.append(heading)
    out.append("\n")
    out.extend(trimmed(entries))
    if entries and release_entries:
        out.append("\n")
    out.extend(trimmed(release_entries))
    out.append("\n")
    out.extend(rest)
    changelog.write_text("".join(out))
    return tree


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
    # Move every carrier to the same prerelease version, with the
    # prerelease release heading taking the Unreleased entries.
    text = changelog.read_text()
    text = text.replace(
        "## [Unreleased]", "## [Unreleased]\n\n## [0.2.0-rc.1] - 2026-11-01", 1
    )
    changelog.write_text(text)
    current = standing_version(tree)
    for rel in ("Cargo.toml", "crates/placekit-core/Cargo.toml"):
        path = tree / rel
        path.write_text(path.read_text().replace(f'version = "{current}"', 'version = "0.2.0-rc.1"'))
    lock = tree / "Cargo.lock"
    lock.write_text(mutate_lock_version(lock.read_text(), "0.2.0-rc.1"))
    init = tree / "python" / "placekit" / "__init__.py"
    init.write_text(init.read_text().replace(f'"{current}"', '"0.2.0-rc.1"'))
    result = run_guard(tree)
    assert result.returncode == 0, result.stdout + result.stderr


def test_guard_refuses_a_tag_over_a_nonempty_unreleased_section(
    tmp_path: Path,
) -> None:
    tree = make_copy(tmp_path)
    changelog = tree / "CHANGELOG.md"
    # The copy is given an entry of its own under the Unreleased
    # heading, so the section holds an entry whatever state the
    # real changelog stands in when the suite runs.
    changelog.write_text(
        changelog.read_text().replace(
            "## [Unreleased]\n",
            "## [Unreleased]\n\n- An entry that has not been released yet.\n",
            1,
        )
    )
    result = run_guard(tree, "v" + standing_version(tree))
    assert result.returncode == 1
    assert "Unreleased" in result.stdout


def test_guard_refuses_a_tag_with_no_release_heading(tmp_path: Path) -> None:
    tree = make_copy(tmp_path)
    changelog = tree / "CHANGELOG.md"
    # A changelog with an empty Unreleased section and no release
    # heading at all, so only the missing heading can fail the guard.
    changelog.write_text("# Changelog\n\n## [Unreleased]\n")
    result = run_guard(tree, "v" + standing_version(tree))
    assert result.returncode == 1
    assert "no released version entry" in result.stdout


def test_guard_passes_on_a_folded_changelog_with_a_tag(tmp_path: Path) -> None:
    tree = make_release_ready(make_copy(tmp_path))
    result = run_guard(tree, "v" + standing_version(tree))
    assert result.returncode == 0, result.stdout + result.stderr
    assert ("matches " + standing_version(tree)) in result.stdout


def test_guard_fails_on_a_duplicate_release_heading(tmp_path: Path) -> None:
    tree = make_release_ready(make_copy(tmp_path))
    changelog = tree / "CHANGELOG.md"
    changelog.write_text(
        changelog.read_text()
        + f"\n## [{standing_version(tree)}] - 2026-11-02\n\n### Added\n\n- A second entry section.\n"
    )
    result = run_guard(tree, "v" + standing_version(tree))
    assert result.returncode == 1
    assert "more than one release heading" in result.stdout


def test_guard_ignores_a_release_heading_inside_a_fenced_block(
    tmp_path: Path,
) -> None:
    tree = make_release_ready(make_copy(tmp_path))
    changelog = tree / "CHANGELOG.md"
    text = changelog.read_text()
    text = text.replace(
        "## [Unreleased]\n",
        "## [Unreleased]\n\n```markdown\n## [9.9.9]\n```\n",
        1,
    )
    changelog.write_text(text)
    result = run_guard(tree, "v" + standing_version(tree))
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "spelling",
    [
        "### [Unreleased]",
        "##  [Unreleased]",
        "## [unreleased]",
        "## [Unreleased] <!-- release notes -->",
    ],
)
def test_guard_refuses_a_tag_over_a_restyled_unreleased_heading(
    tmp_path: Path, spelling: str
) -> None:
    tree = make_copy(tmp_path)
    changelog = tree / "CHANGELOG.md"
    # The copy is given an entry of its own under the Unreleased
    # heading before the heading is respelled, so the section holds
    # an entry whatever state the real changelog stands in when the
    # suite runs. Only the respelled heading can let the publish
    # guard past that entry. Recognition is tolerant, so each
    # spelling still refuses.
    text = changelog.read_text().replace(
        "## [Unreleased]\n",
        "## [Unreleased]\n\n- An entry that has not been released yet.\n",
        1,
    )
    changelog.write_text(text.replace("## [Unreleased]", spelling, 1))
    result = run_guard(tree, "v" + standing_version(tree))
    assert result.returncode == 1
    assert "still holds entries under Unreleased" in result.stdout


def test_guard_fails_on_a_duplicate_release_heading_at_level_three(
    tmp_path: Path,
) -> None:
    tree = make_release_ready(make_copy(tmp_path))
    changelog = tree / "CHANGELOG.md"
    changelog.write_text(
        changelog.read_text()
        + f"\n### [{standing_version(tree)}] - 2026-11-02\n\n### Added\n\n- A second entry section.\n"
    )
    for args in (("v" + standing_version(tree),), ()):
        result = run_guard(tree, *args)
        assert result.returncode == 1
        assert "more than one release heading" in result.stdout


def test_guard_ignores_a_release_heading_inside_a_longer_fence(
    tmp_path: Path,
) -> None:
    tree = make_release_ready(make_copy(tmp_path))
    changelog = tree / "CHANGELOG.md"
    # A three backtick line inside a four backtick fence is content,
    # not a closing marker, so the sample heading stays inside the
    # fence and is ignored.
    text = changelog.read_text()
    text = text.replace(
        "## [Unreleased]\n",
        f"## [Unreleased]\n\n````markdown\n```\n## [{standing_version(tree)}]\n````\n",
        1,
    )
    changelog.write_text(text)
    result = run_guard(tree, "v" + standing_version(tree))
    assert result.returncode == 0, result.stdout + result.stderr


CURRENT = standing_version(ROOT)


@pytest.mark.parametrize(
    "argument,expected_code",
    [
        (CURRENT, 0),
        ("v" + CURRENT, 0),
        (CURRENT.rsplit(".", 1)[0], 1),
        (CURRENT + ".1", 1),
        ("vv" + CURRENT, 1),
        (CURRENT + "-rc.1", 1),
        ("V" + CURRENT, 1),
    ],
)
def test_guard_argument_shapes(
    tmp_path: Path, argument: str, expected_code: int
) -> None:
    result = run_guard(make_release_ready(make_copy(tmp_path)), argument)
    assert result.returncode == expected_code, result.stdout + result.stderr
