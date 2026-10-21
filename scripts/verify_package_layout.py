#!/usr/bin/env python3
"""Validate an unpacked Windows runtime package root and report its contents.

The Windows build uploads the *unpacked* package staging contents so that the
Actions artifact is a single ZIP whose root holds the release files. This script
checks the downloaded/unpacked tree against that layout instead of assuming the
artifact tool stripped the staging-folder prefix correctly. It can also verify
an existing release ZIP namelist with ``--archive``.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

from package_runtime import package_entries, verify_package_archive

ROOT_DIRECTORY_PREFIXES = ("configs/", "mysql/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True, help="unpacked package root to validate")
    parser.add_argument("--archive", type=Path, help="optional release ZIP whose namelist must match the same layout")
    parser.add_argument("--show-entries", type=int, default=6, help="number of leading entries to print")
    args = parser.parse_args()

    package_root = args.package_root.resolve()
    entries = package_entries(package_root)
    root_files = sorted(entry for entry in entries if "/" not in entry)
    root_dlls = sorted(entry for entry in root_files if entry.casefold().endswith(".dll"))

    print(f"Package layout valid: {len(entries)} entries relative to {package_root}")
    print("Root files: " + ", ".join(root_files))
    print("Root DLLs: " + ", ".join(root_dlls))
    for prefix in ROOT_DIRECTORY_PREFIXES:
        count = sum(1 for entry in entries if entry.startswith(prefix))
        print(f"{prefix}: {count} entries")
    for entry in entries[: args.show_entries]:
        print(f"  {entry}")

    manifest = "\n".join(entries).encode("utf-8")
    digest = hashlib.sha256(manifest).hexdigest()
    print(f"Manifest SHA-256: {digest}")

    if args.archive is not None:
        archive = args.archive.resolve()
        names = verify_package_archive(archive)
        print(f"Release archive namelist valid: {archive.name} ({len(names)} entries)")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
