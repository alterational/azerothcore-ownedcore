#!/usr/bin/env python3
"""Apply/check the audited Windows+CMake compatibility patch for the pinned core."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "modules.lock.json"
PATCH_PATH = ROOT / "patches" / "azerothcore-ninja-msvc-config-path.patch"
PATCHED_CORE_COMMIT = "14c435031d2cb31b1af664af9a83c5d6256302b6"
PATCHED_SOURCE = Path("modules/CMakeLists.txt")
OLD_ASSIGNMENT = "set(MSVC_CONFIGURATION_NAME $(ConfigurationName)/)"
NEW_ASSIGNMENT = (
    'if (CMAKE_CONFIGURATION_TYPES)\n'
    '        set(MSVC_CONFIGURATION_NAME "$<CONFIG>/")\n'
    '      else()\n'
    '        set(MSVC_CONFIGURATION_NAME "")\n'
    '      endif()'
)


def git_output(args: list[str]) -> str:
    proc = subprocess.run(args, text=True, capture_output=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}")
    return proc.stdout.strip()


def git_apply_check(core_dir: Path, *, reverse: bool = False) -> bool:
    command = ["git", "-C", str(core_dir), "apply", "--check", "--ignore-whitespace", "--unidiff-zero"]
    if reverse:
        command.append("--reverse")
    command.append(str(PATCH_PATH))
    return subprocess.run(command, text=True, capture_output=True).returncode == 0


def preserve_crlf(source: Path, original: bytes) -> None:
    line_feeds = original.count(b"\n")
    crlf_line_feeds = original.count(b"\r\n")
    if line_feeds and line_feeds == crlf_line_feeds:
        data = source.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        source.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="Apply the patch unless already applied")
    mode.add_argument("--check", action="store_true", help="Verify that the patch is already applied")
    parser.add_argument("--core-dir", type=Path, default=ROOT / "core", help="Materialized core checkout")
    args = parser.parse_args()

    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    locked_commit = lock.get("core", {}).get("commit")
    if locked_commit != PATCHED_CORE_COMMIT:
        raise RuntimeError(
            f"This compatibility patch is audited for core {PATCHED_CORE_COMMIT}, but the lock records "
            f"{locked_commit!r}; re-audit it instead of changing the core pin to hide the Ninja error."
        )

    core_dir = args.core_dir.resolve()
    if not (core_dir / ".git").exists():
        raise RuntimeError(f"Materialized core Git checkout is missing: {core_dir}")
    actual_commit = git_output(["git", "-C", str(core_dir), "rev-parse", "HEAD"])
    if actual_commit != PATCHED_CORE_COMMIT:
        raise RuntimeError(f"Core HEAD {actual_commit} does not match audited patch SHA {PATCHED_CORE_COMMIT}")
    if not PATCH_PATH.is_file():
        raise RuntimeError(f"Tracked core compatibility patch is missing: {PATCH_PATH.relative_to(ROOT)}")

    source = core_dir / PATCHED_SOURCE
    if not source.is_file():
        raise RuntimeError(f"Expected core CMake file is missing: {source}")
    source_text = source.read_text(encoding="utf-8")
    already_applied = NEW_ASSIGNMENT in source_text and OLD_ASSIGNMENT not in source_text
    applicable = OLD_ASSIGNMENT in source_text and NEW_ASSIGNMENT not in source_text
    reverse_check = git_apply_check(core_dir, reverse=True)
    forward_check = git_apply_check(core_dir)

    if already_applied and reverse_check and not forward_check:
        print(f"Core Ninja/MSVC config-path patch verified at {actual_commit[:12]}")
        return 0
    if applicable and forward_check and not reverse_check:
        if args.check:
            raise RuntimeError("Core Ninja/MSVC config-path patch is not applied")
        original_source = source.read_bytes()
        git_output(["git", "-C", str(core_dir), "apply", "--ignore-whitespace", "--unidiff-zero", str(PATCH_PATH)])
        preserve_crlf(source, original_source)
        updated_text = source.read_text(encoding="utf-8")
        if NEW_ASSIGNMENT not in updated_text or OLD_ASSIGNMENT in updated_text or not git_apply_check(core_dir, reverse=True):
            raise RuntimeError("Patch application completed but the CMake source verification failed")
        print(f"Applied core Ninja/MSVC config-path patch at {actual_commit[:12]}")
        return 0

    raise RuntimeError(
        "Core Ninja/MSVC config-path patch is ambiguous or does not match the audited source; "
        "refusing to modify the pin or source."
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
