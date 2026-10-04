#!/usr/bin/env python3
"""Check the pinned core config without editing the core checkout.

While the core fork patch is pending, this confirms the observed upstream
values and reports the outstanding fork change. Once committed, set the map's
status to `pinned_in_core_fork`, update its core commit, and the same checker
requires all target values. `--require-target` is used by Windows build/release
jobs so an artifact cannot be produced from an unupdated core pin.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from config_assignments import assignment, canonical_value, read_config

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "modules.lock.json"
SETTINGS_PATH = ROOT / "config" / "core-worldserver-defaults.json"


def fail(message: str) -> None:
    raise RuntimeError(message)


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Cannot read valid JSON from {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"Expected a JSON object in {path}")
    return value


def validate_settings(settings: dict, core_commit: str) -> None:
    if settings.get("core_commit") != core_commit:
        fail("Core defaults map SHA does not match modules.lock.json; update it only after the fork commit is pinned")
    status = settings.get("status")
    if status not in {"pending_core_fork_commit", "pinned_in_core_fork"}:
        fail(f"Unknown core defaults status: {status!r}")
    entries = settings.get("settings")
    if not isinstance(entries, list):
        fail("Core defaults map must contain a settings list")
    keys = {entry.get("key") for entry in entries if isinstance(entry, dict)}
    expected = {"MapUpdate.Threads", "EnablePlayerSettings", "DBC.EnforceItemAttributes", "ActivateWeather"}
    if keys != expected or len(entries) != len(expected):
        fail(f"Unexpected core defaults keys: {sorted(str(key) for key in keys)}")
    for entry in entries:
        if not isinstance(entry.get("upstream_default"), str) or not isinstance(entry.get("target"), str):
            fail(f"{entry.get('key')}: upstream_default and target must be strings")


def check_file(path: Path, settings: dict, expected_field: str) -> list[tuple[str, str, str]]:
    text = read_config(path)
    actuals: list[tuple[str, str, str]] = []
    for entry in settings["settings"]:
        key = entry["key"]
        expected_value = entry[expected_field]
        _, actual, _ = assignment(text, key, path)
        if canonical_value(actual) != canonical_value(expected_value):
            fail(f"{path}: {key} is {actual}; expected {expected_value} for map status {settings['status']}")
        actuals.append((key, actual, entry["target"]))
    return actuals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-dir", type=Path, default=ROOT / "core", help="pinned core checkout")
    parser.add_argument("--config-dir", type=Path, default=ROOT / "core" / "env" / "dist" / "etc", help="active AzerothCore config directory")
    parser.add_argument("--runtime", action="store_true", help="also check the active worldserver.conf after install")
    parser.add_argument("--require-target", action="store_true", help="fail unless the personal core fork contains the required defaults")
    args = parser.parse_args()

    lock = load_json(LOCK_PATH)
    settings = load_json(SETTINGS_PATH)
    core_commit = lock.get("core", {}).get("commit", "")
    validate_settings(settings, core_commit)
    expected_field = "upstream_default" if settings["status"] == "pending_core_fork_commit" else "target"
    template = args.core_dir.resolve() / settings["source_config"]
    if not template.is_file():
        fail(f"Pinned core worldserver template is missing: {template}")
    actuals = check_file(template, settings, expected_field)

    if args.runtime:
        runtime = args.config_dir.resolve() / "worldserver.conf"
        if not runtime.is_file():
            fail(f"Active runtime worldserver.conf is missing: {runtime}")
        check_file(runtime, settings, expected_field)

    if settings["status"] == "pending_core_fork_commit":
        summary = ", ".join(f"{key}={actual} (target {target})" for key, actual, target in actuals)
        print(f"Core defaults verified at the pinned upstream values; PERSONAL FORK COMMIT PENDING: {summary}")
        if args.require_target:
            fail("Windows build/release is blocked until the four defaults are committed to the personal core fork and its new SHA is pinned.")
    else:
        print(f"Pinned core worldserver defaults valid: {len(actuals)} required settings match the personal fork targets.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
