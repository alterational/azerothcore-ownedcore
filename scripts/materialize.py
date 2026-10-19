#!/usr/bin/env python3
"""Materialize AzerothCore and the selected modules at immutable lockfile SHAs.

By default, compile_by_default=false module sources are excluded. Use
--include-module <id> to opt an optional source into a specific build.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from module_selection import excluded_module_ids, select_modules

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "modules.manifest.json"
LOCK_PATH = ROOT / "modules.lock.json"


def run(args: list[str], *, cwd: Path | None = None) -> str:
    proc = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode:
        msg = proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}"
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{msg}")
    return proc.stdout.strip()


def canonical_url(url: str) -> str:
    return url.removesuffix(".git").rstrip("/").lower()


def checkout_repo(url: str, commit: str, destination: Path) -> None:
    """Fetch just the locked commit, avoiding a full clone of long histories."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not (destination / ".git").exists():
            if any(destination.iterdir()):
                raise RuntimeError(f"Refusing to overwrite non-git path: {destination}")
            run(["git", "init", "--quiet", str(destination)])
            run(["git", "-C", str(destination), "remote", "add", "origin", url])
        actual_url = run(["git", "-C", str(destination), "config", "--get", "remote.origin.url"])
        if canonical_url(actual_url) != canonical_url(url):
            raise RuntimeError(f"{destination} has origin {actual_url}, expected {url}")
    else:
        destination.mkdir(parents=True, exist_ok=True)
        run(["git", "init", "--quiet", str(destination)])
        run(["git", "-C", str(destination), "remote", "add", "origin", url])

    have_commit = subprocess.run(
        ["git", "-C", str(destination), "cat-file", "-e", f"{commit}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0
    if not have_commit:
        run(["git", "-C", str(destination), "fetch", "--depth=1", "origin", commit])
    run(["git", "-C", str(destination), "checkout", "--detach", commit])
    actual_commit = run(["git", "-C", str(destination), "rev-parse", "HEAD"])
    if actual_commit != commit:
        raise RuntimeError(f"Checked out {actual_commit}, expected locked commit {commit} in {destination}")


def remove_excluded_checkout(url: str, commit: str, destination: Path) -> bool:
    """Remove a stale optional checkout only when it exactly matches the clean lock pin."""
    if destination.is_symlink():
        raise RuntimeError(f"Refusing to remove symlink used as an excluded module checkout: {destination}")
    if not destination.exists():
        return False
    if not (destination / ".git").exists():
        raise RuntimeError(f"Refusing to remove non-Git path for excluded optional module: {destination}")

    actual_url = run(["git", "-C", str(destination), "config", "--get", "remote.origin.url"])
    actual_commit = run(["git", "-C", str(destination), "rev-parse", "HEAD"])
    changes = run(
        ["git", "-C", str(destination), "status", "--porcelain", "--untracked-files=all", "--ignored"]
    )
    if canonical_url(actual_url) != canonical_url(url) or actual_commit != commit or changes:
        raise RuntimeError(
            f"Excluded optional module checkout is not the clean locked source: {destination}. "
            "Refusing to delete it; inspect or preserve local changes before switching variants."
        )
    shutil.rmtree(destination)
    print(f"Removed clean, locked checkout for excluded optional module: {destination}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-dir", type=Path, default=ROOT / "core", help="AzerothCore source directory (default: ./core)")
    parser.add_argument("--skip-core", action="store_true", help="Use an existing core checkout; only place modules under core/modules")
    parser.add_argument("--allow-unresolved", action="store_true", help="Skip repositories without a locked SHA (NOT a complete checkout)")
    parser.add_argument(
        "--include-module",
        action="append",
        default=[],
        metavar="MODULE_ID",
        help="include an optional compile_by_default=false source; may be repeated",
    )
    args = parser.parse_args()

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    core_lock = lock.get("core", {})
    all_modules = manifest.get("modules", [])
    modules = select_modules(all_modules, args.include_module)
    excluded_ids = excluded_module_ids(all_modules, args.include_module)
    lock_modules = lock.get("modules", {})
    unresolved = [m["id"] for m in modules if not lock_modules.get(m["id"], {}).get("resolved")]
    if unresolved and not args.allow_unresolved:
        raise RuntimeError(
            "Cannot materialize the selected build; no commit SHA for: " + ", ".join(unresolved)
            + ". Resolve the source URL or explicitly use --allow-unresolved (incomplete checkout)."
        )

    if not args.skip_core:
        if not core_lock.get("resolved") or not core_lock.get("commit"):
            raise RuntimeError("Core repository has no locked commit.")
        checkout_repo(core_lock["url"], core_lock["commit"], args.core_dir)
    elif not (args.core_dir / ".git").exists():
        raise RuntimeError(f"--skip-core specified, but {args.core_dir} is not a git checkout")

    modules_dir = args.core_dir / "modules"
    selected_ids = {module["id"] for module in modules}
    for module in all_modules:
        module_id = module["id"]
        if not module.get("install", True) or module_id in selected_ids:
            continue
        item = lock_modules.get(module_id, {})
        destination = modules_dir / module_id
        if item.get("resolved") and item.get("commit"):
            remove_excluded_checkout(item["url"], item["commit"], destination)

    for module in modules:
        item = lock_modules.get(module["id"], {})
        if not item.get("resolved"):
            print(f"SKIP unresolved: {module['name']} ({module['clone_url']})", file=sys.stderr)
            continue
        destination = modules_dir / module["id"]
        state = "enabled" if module.get("enabled") else "disabled-by-default"
        print(f"[{state}] {module['name']} -> {destination}", flush=True)
        checkout_repo(item["url"], item["commit"], destination)

    print(f"\nSelected {len(modules)} module sources at pinned commits.")
    if excluded_ids:
        print("Excluded source(s): " + ", ".join(excluded_ids))
    print("This does not apply module SQL or prove the selected set compiles.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
