"""Pins for the Round 45 PhotoMedia.save disclosure.

Round 45 characterised what a save refused part way leaves at the
target and found the behaviour stated in no shipped text. The repair
is disclosure only, so these pins hold both halves in place. The
behaviour pins drive the real save path with the open patched so the
write fails after a fixed number of bytes, and the text pins hold
the docstring and the README to the disclosure wording.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from placekit.models import PhotoMedia

REPO_ROOT = Path(__file__).resolve().parents[1]

CONTENT = bytes(range(256)) * 8


class _RefusingWriter:
    """Wrap a real binary file and refuse its write past a budget.

    The bytes inside the budget land on disk before the refusal, the
    same shape an operating system refusal part way through a write
    leaves behind.
    """

    def __init__(self, real, budget):
        self._real = real
        self._budget = budget

    def write(self, data):
        head = bytes(data[: self._budget])
        if head:
            self._real.write(head)
            self._real.flush()
        raise OSError(27, "File too large")

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self._real.close()
        return False

    def close(self):
        self._real.close()


@pytest.fixture()
def refuse_after(monkeypatch):
    """Install an open whose write mode files refuse past a budget."""
    real_open = io.open

    def install(budget):
        def open_then_refuse(file, mode="r", *args, **kwargs):
            handle = real_open(file, mode, *args, **kwargs)
            if mode == "wb":
                return _RefusingWriter(handle, budget)
            return handle

        monkeypatch.setattr(io, "open", open_then_refuse)

    return install


def test_save_refused_part_way_leaves_the_written_prefix(
    tmp_path, refuse_after
):
    refuse_after(100)
    media = PhotoMedia(content=CONTENT, content_type="image/jpeg")
    target = tmp_path / "photo.jpg"
    with pytest.raises(OSError):
        media.save(target)
    assert target.read_bytes() == CONTENT[:100]


def test_save_refused_before_any_bytes_leaves_a_zero_byte_file(
    tmp_path, refuse_after
):
    refuse_after(0)
    media = PhotoMedia(content=CONTENT, content_type="image/jpeg")
    target = tmp_path / "photo.jpg"
    with pytest.raises(OSError):
        media.save(target)
    assert target.exists()
    assert target.read_bytes() == b""


def test_refused_save_over_an_existing_file_truncates_it_first(
    tmp_path, refuse_after
):
    target = tmp_path / "photo.jpg"
    target.write_bytes(b"s" * 231)
    refuse_after(100)
    media = PhotoMedia(content=CONTENT, content_type="image/jpeg")
    with pytest.raises(OSError):
        media.save(target)
    # The sentinel is gone and the target holds only the written
    # prefix, shorter than the file the save replaced.
    assert target.read_bytes() == CONTENT[:100]


def test_plain_save_writes_the_whole_payload(tmp_path):
    media = PhotoMedia(content=CONTENT, content_type="image/jpeg")
    target = tmp_path / "photo.jpg"
    saved = media.save(target)
    assert saved == target
    assert target.read_bytes() == CONTENT


def _squeezed(text):
    # Docstrings wrap their lines, so the wording pins match on text
    # with every whitespace run folded to one space.
    return " ".join(text.split())


def test_save_docstring_states_the_leftover_behaviour():
    doc = _squeezed(PhotoMedia.save.__doc__ or "")
    assert "non-atomic" in doc
    assert "zero byte" in doc
    assert "truncated before the write begins" in doc
    assert "shorter than the file it replaced" in doc


def test_readme_states_the_leftover_behaviour():
    readme = _squeezed((REPO_ROOT / "README.md").read_text(encoding="utf-8"))
    assert "zero byte or partial file" in readme
    assert "truncated before the write begins" in readme
    assert "shorter than the file it replaced" in readme
