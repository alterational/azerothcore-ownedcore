#!/usr/bin/env python3
"""Apply/check audited compatibility patches for the pinned Windows core build."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "modules.lock.json"
PATCHED_CORE_COMMIT = "14c435031d2cb31b1af664af9a83c5d6256302b6"

NINJA_PATCH_TEXT = (
    'if (CMAKE_CONFIGURATION_TYPES)\n'
    '        set(MSVC_CONFIGURATION_NAME "$<CONFIG>/")\n'
    '      else()\n'
    '        set(MSVC_CONFIGURATION_NAME "")\n'
    '      endif()'
)
PATCH_SPECS = (
    {
        "path": ROOT / "patches" / "azerothcore-ninja-msvc-config-path.patch",
        "source": Path("modules/CMakeLists.txt"),
        "old_markers": ("set(MSVC_CONFIGURATION_NAME $(ConfigurationName)/)",),
        "new_markers": (NINJA_PATCH_TEXT,),
        "label": "Ninja/MSVC config-path",
    },
    {
        "path": ROOT / "patches" / "azerothcore-cygwin-install.patch",
        "source": Path("apps/compiler/includes/functions.sh"),
        "old_markers": ("\n    msys*)\n",),
        "new_markers": ("\n    msys*|cygwin*)\n",),
        "label": "Cygwin Windows install-dispatch",
    },
)


def git_output(args: list[str]) -> str:
    proc = subprocess.run(args, text=True, capture_output=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}")
    return proc.stdout.strip()


def git_apply_check(core_dir: Path, patch_path: Path, *, reverse: bool = False) -> bool:
    command = ["git", "-C", str(core_dir), "apply", "--check", "--ignore-whitespace", "--unidiff-zero"]
    if reverse:
        command.append("--reverse")
    command.append(str(patch_path))
    return subprocess.run(command, text=True, capture_output=True).returncode == 0


def preserve_crlf(source: Path, original: bytes) -> None:
    line_feeds = original.count(b"\n")
    crlf_line_feeds = original.count(b"\r\n")
    if line_feeds and line_feeds == crlf_line_feeds:
        data = source.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        source.write_bytes(data)


def apply_or_check_patch(core_dir: Path, actual_commit: str, spec: dict, *, check_only: bool) -> None:
    patch_path = spec["path"]
    source = core_dir / spec["source"]
    label = spec["label"]
    if not patch_path.is_file():
        raise RuntimeError(f"Tracked core compatibility patch is missing: {patch_path.relative_to(ROOT)}")
    if not source.is_file():
        raise RuntimeError(f"Expected core source for {label} patch is missing: {source}")

    source_text = source.read_text(encoding="utf-8")
    old_markers = spec["old_markers"]
    new_markers = spec["new_markers"]
    already_applied = all(source_text.count(marker) == 1 for marker in new_markers) and all(
        source_text.count(marker) == 0 for marker in old_markers
    )
    applicable = all(source_text.count(marker) == 1 for marker in old_markers) and all(
        source_text.count(marker) == 0 for marker in new_markers
    )
    reverse_check = git_apply_check(core_dir, patch_path, reverse=True)
    forward_check = git_apply_check(core_dir, patch_path)

    if already_applied and reverse_check and not forward_check:
        print(f"Core {label} patch verified at {actual_commit[:12]}")
        return
    if applicable and forward_check and not reverse_check:
        if check_only:
            raise RuntimeError(f"Core {label} patch is not applied")
        original_source = source.read_bytes()
        git_output(["git", "-C", str(core_dir), "apply", "--ignore-whitespace", "--unidiff-zero", str(patch_path)])
        preserve_crlf(source, original_source)
        updated_text = source.read_text(encoding="utf-8")
        if (
            not all(updated_text.count(marker) == 1 for marker in new_markers)
            or any(updated_text.count(marker) for marker in old_markers)
            or not git_apply_check(core_dir, patch_path, reverse=True)
        ):
            raise RuntimeError(f"Patch application completed but the {label} source verification failed")
        print(f"Applied core {label} patch at {actual_commit[:12]}")
        return

    raise RuntimeError(
        f"Core {label} patch is ambiguous or does not match the audited source; "
        "refusing to modify the pin or source."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="Apply the patches unless already applied")
    mode.add_argument("--check", action="store_true", help="Verify that every patch is already applied")
    parser.add_argument("--core-dir", type=Path, default=ROOT / "core", help="Materialized core checkout")
    args = parser.parse_args()

    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    locked_commit = lock.get("core", {}).get("commit")
    if locked_commit != PATCHED_CORE_COMMIT:
        raise RuntimeError(
            f"These compatibility patches are audited for core {PATCHED_CORE_COMMIT}, but the lock records "
            f"{locked_commit!r}; re-audit them instead of changing the core pin to hide a build error."
        )

    core_dir = args.core_dir.resolve()
    if not (core_dir / ".git").exists():
        raise RuntimeError(f"Materialized core Git checkout is missing: {core_dir}")
    actual_commit = git_output(["git", "-C", str(core_dir), "rev-parse", "HEAD"])
    if actual_commit != PATCHED_CORE_COMMIT:
        raise RuntimeError(f"Core HEAD {actual_commit} does not match audited patch SHA {PATCHED_CORE_COMMIT}")

    for spec in PATCH_SPECS:
        apply_or_check_patch(core_dir, actual_commit, spec, check_only=args.check)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
