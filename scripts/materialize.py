#!/usr/bin/env python3
"""Materialize AzerothCore and every module at the immutable lockfile SHAs.

By default the complete core plus all manifest entries with install=true are
fetched. Module enabled/disabled runtime state does not affect source checkout.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-dir", type=Path, default=ROOT / "core", help="AzerothCore source directory (default: ./core)")
    parser.add_argument("--skip-core", action="store_true", help="Use an existing core checkout; only place modules under core/modules")
    parser.add_argument("--allow-unresolved", action="store_true", help="Skip repositories without a locked SHA (NOT a complete checkout)")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    core_lock = lock.get("core", {})
    modules = manifest.get("modules", [])
    lock_modules = lock.get("modules", {})
    unresolved = [m["id"] for m in modules if m.get("install", True) and not lock_modules.get(m["id"], {}).get("resolved")]
    if unresolved and not args.allow_unresolved:
        raise RuntimeError(
            "Cannot materialize a complete set; no commit SHA for: " + ", ".join(unresolved)
            + ". Resolve the source URL or explicitly use --allow-unresolved (incomplete checkout)."
        )

    if not args.skip_core:
        if not core_lock.get("resolved") or not core_lock.get("commit"):
            raise RuntimeError("Core repository has no locked commit.")
        checkout_repo(core_lock["url"], core_lock["commit"], args.core_dir)
    elif not (args.core_dir / ".git").exists():
        raise RuntimeError(f"--skip-core specified, but {args.core_dir} is not a git checkout")

    for module in modules:
        if not module.get("install", True):
            continue
        item = lock_modules.get(module["id"], {})
        if not item.get("resolved"):
            print(f"SKIP unresolved: {module['name']} ({module['clone_url']})", file=sys.stderr)
            continue
        destination = args.core_dir / "modules" / module["id"]
        state = "enabled" if module.get("enabled") else "disabled-by-default"
        print(f"[{state}] {module['name']} -> {destination}", flush=True)
        checkout_repo(item["url"], item["commit"], destination)

    print("\nSources materialized at pinned commits. This does not apply module SQL/configuration or prove the set compiles.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
