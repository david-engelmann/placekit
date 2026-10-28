#!/usr/bin/env python3
"""Fail if any tracked text file contains an em dash (U+2014).

Public copy and docs in this repo use plain hyphens. The scan is a
codepoint scan, not a grep: a shell grep for the character silently
matches nothing and once certified hundreds of real em dashes as zero.
Binary files (anything that does not decode as UTF-8) are skipped, and
en dashes in recorded API fixtures are data, not prose, so only the em
dash codepoint is checked.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EM_DASH = "\u2014"


def main() -> None:
    listing = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    offenders = []
    for rel in listing:
        path = ROOT / rel
        try:
            text = path.read_bytes().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        count = text.count(EM_DASH)
        if count:
            offenders.append((rel, count))

    if offenders:
        for rel, count in offenders:
            print(f"check_no_emdash: {rel}: {count} em dash(es)")
        print("check_no_emdash: FAIL")
        sys.exit(1)
    print(f"check_no_emdash: OK, zero em dashes in {len(listing)} tracked files")


if __name__ == "__main__":
    main()
