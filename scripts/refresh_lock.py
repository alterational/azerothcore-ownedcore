#!/usr/bin/env python3
"""Refresh candidate pins from upstream refs (network operation; rewrites lockfile).

This script deliberately has no CLI flags. Running it performs a refresh; it does
not compile/test the resulting set. Use only for an explicitly reviewed pin update.
"""
from __future__ import annotations

import concurrent.futures
import json
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "modules.manifest.json").read_text(encoding="utf-8"))
LOCK_PATH = ROOT / "modules.lock.json"
LOCK = json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def ls_remote(url: str, ref: str = "HEAD") -> tuple[str | None, str | None, str | None]:
    proc = subprocess.run(
        ["git", "ls-remote", "--symref", url, ref],
        text=True,
        capture_output=True,
        timeout=30,
    )
    if proc.returncode:
        return None, None, (proc.stderr.strip() or proc.stdout.strip() or f"git exited {proc.returncode}")
    branch = None
    commit = None
    for line in proc.stdout.splitlines():
        if line.startswith("ref: refs/heads/") and line.endswith("\t" + ref):
            branch = line.split("refs/heads/", 1)[1].split("\t", 1)[0]
        elif line.endswith("\t" + ref):
            commit = line.split("\t", 1)[0]
    return branch, commit, None if commit else "No commit SHA returned"


def resolve_module(module: dict) -> tuple[str, dict]:
    try:
        branch, commit, error = ls_remote(module["clone_url"], "HEAD")
    except Exception as exc:
        branch, commit, error = None, None, str(exc)
    old = LOCK.get("modules", {}).get(module["id"], {})
    if commit:
        return module["id"], {
            "url": module["clone_url"],
            "branch": branch,
            "commit": commit,
            "resolved": True,
            "refresh_ok": True,
        }
    if old.get("commit"):
        kept = dict(old)
        kept["refresh_ok"] = False
        kept["last_refresh_error"] = error
        return module["id"], kept
    return module["id"], {
        "url": module["clone_url"],
        "branch": None,
        "commit": None,
        "resolved": False,
        "refresh_ok": False,
        "last_refresh_error": error,
    }


def main() -> int:
    modules = MANIFEST["modules"]
    refreshed = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for module_id, item in pool.map(resolve_module, modules):
            refreshed[module_id] = item

    core = MANIFEST.get("core", {})
    core_url = core.get("repository")
    core_branch = core.get("branch")
    if core_url and core_branch:
        try:
            _, core_commit, core_error = ls_remote(core_url, f"refs/heads/{core_branch}")
        except Exception as exc:
            core_commit, core_error = None, str(exc)
        old_core = LOCK.get("core", {})
        if core_commit:
            core_entry = {"url": core_url, "branch": core_branch, "commit": core_commit, "resolved": True, "refresh_ok": True}
        elif old_core.get("commit"):
            core_entry = dict(old_core)
            core_entry["refresh_ok"] = False
            core_entry["last_refresh_error"] = core_error
        else:
            core_entry = {"url": core_url, "branch": core_branch, "commit": None, "resolved": False, "refresh_ok": False, "last_refresh_error": core_error}
    else:
        core_entry = LOCK.get("core", {})

    result = {
        "schema_version": 1,
        "resolved_at": date.today().isoformat(),
        "resolution_method": "git ls-remote --symref; commit pins are candidate remote tips, not compile-tested",
        "core": core_entry,
        "modules": refreshed,
    }
    LOCK_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    good = sum(bool(v.get("commit")) for v in refreshed.values())
    bad = [m["name"] for m in modules if not refreshed[m["id"]].get("refresh_ok")]
    print(f"Resolved/refreshed {good}/{len(modules)} module pins.")
    if bad:
        print("Could not refresh these links (previous pins, if present, were kept):")
        for name in bad:
            print(f" - {name}")
    print("Review modules.lock.json, then run a full build/test before merging.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
