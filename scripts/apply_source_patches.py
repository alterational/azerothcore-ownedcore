#!/usr/bin/env python3
"""Apply/check narrowly scoped compatibility patches to pinned module sources.

Module SHAs remain immutable in modules.lock.json. Each patch is tracked in the
build repository and is accepted only for its audited module commit.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "modules.lock.json"
PATCHES = {
    "BGQueueChecker": ROOT / "patches" / "modules" / "BGQueueChecker-hook-name.patch",
}
PATCHED_MODULE_COMMITS = {
    "BGQueueChecker": "0a6b9872f5d4f50286e5152c0debfeb1d6ef73a0",
}


def git_output(args: list[str]) -> str:
    proc = subprocess.run(args, text=True, capture_output=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}")
    return proc.stdout.strip()


def git_apply_check(module_dir: Path, patch_path: Path, *, reverse: bool = False) -> bool:
    command = ["git", "-C", str(module_dir), "apply", "--check", "--ignore-whitespace", "--unidiff-zero"]
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="Apply each tracked patch when not yet applied")
    mode.add_argument("--check", action="store_true", help="Verify each tracked patch is already applied")
    parser.add_argument("--core-dir", type=Path, default=ROOT / "core", help="Materialized AzerothCore source tree")
    args = parser.parse_args()

    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    lock_modules = lock.get("modules", {})
    for module_id, patch_path in PATCHES.items():
        entry = lock_modules.get(module_id)
        if not isinstance(entry, dict) or not entry.get("commit"):
            raise RuntimeError(f"{module_id}: no immutable commit in modules.lock.json")
        module_dir = args.core_dir / "modules" / module_id
        if not (module_dir / ".git").exists():
            raise RuntimeError(f"{module_id}: module checkout is missing at {module_dir}")
        actual_commit = git_output(["git", "-C", str(module_dir), "rev-parse", "HEAD"])
        if actual_commit != entry["commit"]:
            raise RuntimeError(f"{module_id}: HEAD {actual_commit} does not match locked SHA {entry['commit']}")
        audited_commit = PATCHED_MODULE_COMMITS[module_id]
        if entry["commit"] != audited_commit:
            raise RuntimeError(
                f"{module_id}: patch is audited for {audited_commit}, but the lock records {entry['commit']}; "
                "re-audit the patch instead of changing the pin to hide a build error"
            )
        if not patch_path.is_file():
            raise RuntimeError(f"{module_id}: tracked patch is missing: {patch_path.relative_to(ROOT)}")

        already_applied = git_apply_check(module_dir, patch_path, reverse=True)
        still_applicable = git_apply_check(module_dir, patch_path)
        if already_applied and not still_applicable:
            print(f"{module_id}: tracked source patch verified at {actual_commit[:12]}")
            continue
        if still_applicable and not already_applied:
            if args.check:
                raise RuntimeError(f"{module_id}: tracked source patch is not applied")
            source = module_dir / "src" / "BGQueueChecker.cpp"
            original_source = source.read_bytes()
            git_output(["git", "-C", str(module_dir), "apply", "--ignore-whitespace", "--unidiff-zero", str(patch_path)])
            preserve_crlf(source, original_source)
            if not git_apply_check(module_dir, patch_path, reverse=True):
                raise RuntimeError(f"{module_id}: patch command completed but reverse verification failed")
            print(f"{module_id}: applied tracked source patch at {actual_commit[:12]}")
            continue
        raise RuntimeError(
            f"{module_id}: tracked patch is ambiguous or does not match the locked source "
            f"{actual_commit}; refusing to change the module pin or source"
        )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
