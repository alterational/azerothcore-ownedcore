#!/usr/bin/env python3
"""Create exactly one release ZIP from a downloaded, unpacked artifact root.

GitHub's artifact download is already a ZIP. Uploading an inner ZIP from the
build job therefore produced a ZIP inside a ZIP. This script instead treats the
downloaded artifact contents as the package root and rebuilds a single archive
whose entry names are relative to that root, then verifies the namelist before
the release step publishes it.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from package_runtime import create_package_archive, verify_package_archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True, help="unpacked artifact directory")
    parser.add_argument("--output", type=Path, required=True, help="release ZIP path outside the package root")
    parser.add_argument("--show-entries", type=int, default=6, help="number of leading ZIP entries to print")
    args = parser.parse_args()

    package_root = args.package_root.resolve()
    output = args.output.resolve()
    if not package_root.is_dir():
        raise RuntimeError(f"Package root directory is missing: {package_root}")
    if output.is_relative_to(package_root):
        raise RuntimeError(f"The release ZIP must be created outside the package root: {output}")
    if output.exists():
        output.unlink()

    entries = create_package_archive(package_root, output)
    names = verify_package_archive(output)
    print(f"Created {output} with {len(entries)} entries relative to {package_root}.")
    for name in names[: args.show_entries]:
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
