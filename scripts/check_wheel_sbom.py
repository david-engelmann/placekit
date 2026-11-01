#!/usr/bin/env python3
"""Fail unless every wheel in a directory carries its embedded SBOM.

Maturin embeds a CycloneDX SBOM in each wheel under the dist-info
sboms folder, and the README promises it to readers. Nothing
asserted that promise (R18-A8), so a toolchain change that dropped
the SBOM would have shipped silently. The wheels workflow's test
leg runs this check over the wheel it downloaded.

Usage: check_wheel_sbom.py DIRECTORY

The check also fails when the directory holds no wheel at all, so
a wrong path cannot pass vacuously.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path


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


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: check_wheel_sbom.py DIRECTORY")
        sys.exit(2)
    directory = Path(sys.argv[1])
    wheels = sorted(directory.glob("*.whl"))
    if not wheels:
        fail(f"no wheels found in {directory}")
    missing = missing_sbom(directory)
    if missing:
        fail(f"wheels without an embedded SBOM: {', '.join(missing)}")
    print(
        f"check_wheel_sbom: OK, {len(wheels)} wheel(s) carry an embedded SBOM"
    )


if __name__ == "__main__":
    main()
