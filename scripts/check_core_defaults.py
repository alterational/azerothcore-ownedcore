#!/usr/bin/env python3
"""Check the pinned core config without editing the core checkout.

The maps distinguish pending core-fork changes from defaults already committed
in the personal fork. Pending mode verifies observed base values and reports the
outstanding targets; pinned mode requires every target in both server templates.
`--require-target` is used before Windows dependency setup and compilation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from config_assignments import assignment, canonical_value, read_config

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "modules.lock.json"
WORLD_SETTINGS_PATH = ROOT / "config" / "core-worldserver-defaults.json"
AUTH_SETTINGS_PATH = ROOT / "config" / "core-authserver-defaults.json"
WORLD_EXPECTED = {
    "MapUpdate.Threads": ("1", "4"),
    "EnablePlayerSettings": ("0", "1"),
    "DBC.EnforceItemAttributes": ("1", "0"),
    "ActivateWeather": ("1", "0"),
    "Appender.Server": ("2,5,0,Server.log,w", "2,5,8,Server.log,w"),
    "Appender.Playerbots": ("2,5,0,Playerbots.log,w", "2,5,8,Playerbots.log,w"),
    "Appender.Errors": ("2,2,0,Errors.log,w", "2,2,8,Errors.log,w"),
    "Die.Command.Mode": ("1", "0"),
    "DungeonFinder.OptionsMask": ("5", "5"),
}
AUTH_EXPECTED = {
    "Appender.Auth": ("2,5,0,Auth.log,w", "2,5,8,Auth.log,w"),
}
WORLD_PATCH_BASE_DEFAULTS = {"DungeonFinder.OptionsMask": "7"}


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


def validate_settings(
    settings: dict,
    core_commit: str,
    expected: dict[str, tuple[str, str]],
    expected_source: str,
    label: str,
) -> None:
    if settings.get("core_commit") != core_commit:
        fail(f"{label} defaults map SHA does not match modules.lock.json; update it only after the fork commit is pinned")
    status = settings.get("status")
    if status not in {"pending_core_fork_commit", "pinned_in_core_fork"}:
        fail(f"Unknown {label} defaults status: {status!r}")
    if settings.get("source_config") != expected_source:
        fail(f"{label} defaults map points at an unexpected source template")
    patch = ROOT / str(settings.get("patch_file", ""))
    if not patch.is_file():
        fail(f"{label} defaults patch file is missing: {patch}")
    entries = settings.get("settings")
    if not isinstance(entries, list):
        fail(f"{label} defaults map must contain a settings list")
    actual = {entry.get("key"): entry for entry in entries if isinstance(entry, dict)}
    if set(actual) != set(expected) or len(entries) != len(expected):
        fail(f"Unexpected {label} defaults keys: {sorted(str(key) for key in actual)}")
    for key, values in expected.items():
        entry = actual[key]
        if (entry.get("upstream_default"), entry.get("target")) != values or not entry.get("evidence"):
            fail(f"{label} default {key} must retain audited upstream/target values {values} and evidence")
        if key in WORLD_PATCH_BASE_DEFAULTS and entry.get("patch_base_default") != WORLD_PATCH_BASE_DEFAULTS[key]:
            fail(f"{label} default {key} must record pre-update Playerbot branch base {WORLD_PATCH_BASE_DEFAULTS[key]}")


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
    world_settings = load_json(WORLD_SETTINGS_PATH)
    auth_settings = load_json(AUTH_SETTINGS_PATH)
    core_commit = lock.get("core", {}).get("commit", "")
    validate_settings(
        world_settings,
        core_commit,
        WORLD_EXPECTED,
        "src/server/apps/worldserver/worldserver.conf.dist",
        "worldserver",
    )
    validate_settings(
        auth_settings,
        core_commit,
        AUTH_EXPECTED,
        "src/server/apps/authserver/authserver.conf.dist",
        "authserver",
    )
    if world_settings["status"] != auth_settings["status"]:
        fail("Authserver and worldserver defaults maps must have the same core-fork status")
    status = world_settings["status"]
    expected_field = "upstream_default" if status == "pending_core_fork_commit" else "target"

    world_template = args.core_dir.resolve() / world_settings["source_config"]
    auth_template = args.core_dir.resolve() / auth_settings["source_config"]
    if not world_template.is_file():
        fail(f"Pinned core worldserver template is missing: {world_template}")
    if not auth_template.is_file():
        fail(f"Pinned core authserver template is missing: {auth_template}")
    world_actuals = check_file(world_template, world_settings, expected_field)
    auth_actuals = check_file(auth_template, auth_settings, expected_field)

    if args.runtime:
        world_runtime = args.config_dir.resolve() / "worldserver.conf"
        auth_runtime = args.config_dir.resolve() / "authserver.conf"
        if not world_runtime.is_file():
            fail(f"Active runtime worldserver.conf is missing: {world_runtime}")
        if not auth_runtime.is_file():
            fail(f"Active runtime authserver.conf is missing: {auth_runtime}")
        check_file(world_runtime, world_settings, expected_field)
        check_file(auth_runtime, auth_settings, expected_field)

    actuals = [("worldserver", *item) for item in world_actuals] + [("authserver", *item) for item in auth_actuals]
    if status == "pending_core_fork_commit":
        summary = ", ".join(f"{config}.{key}={actual} (target {target})" for config, key, actual, target in actuals)
        print(f"Core server config defaults verified at the pinned upstream values; PERSONAL FORK COMMIT PENDING: {summary}")
        if args.require_target:
            fail("Windows build/release is blocked until the tracked authserver/worldserver defaults are committed to the personal core fork and its new SHA is pinned.")
    else:
        print(f"Pinned core authserver/worldserver defaults valid: {len(actuals)} required settings match the personal fork targets.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
