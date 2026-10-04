#!/usr/bin/env python3
"""Validate the manifest, immutable source lock, and reviewed config-state mapping."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "modules.manifest.json"
LOCK_PATH = ROOT / "modules.lock.json"
SWITCHES_PATH = ROOT / "config" / "module-switches.json"
ADDITIONAL_SETTINGS_PATH = ROOT / "config" / "additional-module-settings.json"
CORE_DEFAULTS_PATH = ROOT / "config" / "core-worldserver-defaults.json"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_CORE_URL = "https://github.com/alterational/azerothcore-wotlk.git"
EXPECTED_CORE_BRANCH = "Playerbot"
EXPECTED_CORE_SHA = "f19a18799a35f7c24bdcdc9ea399c601f166259b"
PENDING_CORE_SHA = "f19a18799a35f7c24bdcdc9ea399c601f166259b"
EXPECTED_LEARN_SPELLS_URL = "https://github.com/azerothcore/mod-learn-spells.git"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Cannot read valid JSON from {path.relative_to(ROOT)}: {exc}")
    if not isinstance(value, dict):
        fail(f"Expected a JSON object in {path.relative_to(ROOT)}")
    return value


def canonical_url(url: str) -> str:
    return url.removesuffix(".git").rstrip("/").lower()


def git_output(args: list[str]) -> str:
    proc = subprocess.run(args, text=True, capture_output=True)
    if proc.returncode:
        fail(f"Command failed: {' '.join(args)}\n{proc.stderr.strip()}")
    return proc.stdout.strip()


def check_checkout(core_dir: Path, manifest: dict, lock: dict) -> int:
    core_lock = lock["core"]
    actual_core = git_output(["git", "-C", str(core_dir), "rev-parse", "HEAD"])
    if actual_core != core_lock["commit"]:
        fail(f"core HEAD {actual_core} does not match lock {core_lock['commit']}")
    checked = 0
    for module in manifest["modules"]:
        if not module.get("install", True):
            continue
        module_dir = core_dir / "modules" / module["id"]
        if not (module_dir / ".git").exists():
            fail(f"Missing materialized module checkout: {module_dir.relative_to(ROOT)}")
        actual = git_output(["git", "-C", str(module_dir), "rev-parse", "HEAD"])
        expected = lock["modules"][module["id"]]["commit"]
        if actual != expected:
            fail(f"{module['id']} HEAD {actual} does not match lock {expected}")
        checked += 1
    print(f"Checkout pins valid: core and {checked} installed modules match locked HEADs.")
    return checked


def check_config_mapping(manifest: dict, lock: dict) -> tuple[int, int, int]:
    mapping = load_json(SWITCHES_PATH)
    mapped = mapping.get("modules")
    modules = manifest["modules"]
    lock_modules = lock["modules"]
    if not isinstance(mapped, dict):
        fail("config/module-switches.json must contain a modules object")
    ids = {module["id"] for module in modules}
    if set(mapped) != ids:
        fail(f"Config-map IDs differ from manifest (missing={sorted(ids-set(mapped))}; extra={sorted(set(mapped)-ids)})")
    if mapping.get("core_commit") != lock["core"].get("commit"):
        fail("Config mapping was audited against a different core commit")

    counts = {"master_switch": 0, "upstream_default": 0, "no_master_switch": 0}
    by_id = {module["id"]: module for module in modules}
    for module in modules:
        module_id = module["id"]
        entry = mapped[module_id]
        if entry.get("source_commit") != lock_modules[module_id].get("commit"):
            fail(f"{module_id}: config mapping source commit differs from lock")
        if entry.get("manifest_policy") != module.get("config_policy"):
            fail(f"{module_id}: config mapping policy differs from manifest")
        status = entry.get("status")
        if status not in counts:
            fail(f"{module_id}: invalid config mapping status {status!r}")
        counts[status] += 1
        switch = entry.get("switch")
        policy = module.get("config_policy")
        if status == "master_switch":
            if policy != "match_manifest_state" or not isinstance(switch, dict):
                fail(f"{module_id}: invalid master switch mapping")
            for field in ("key", "upstream_default", "enabled_value", "disabled_value", "source_line", "code_reference"):
                if switch.get(field) in (None, ""):
                    fail(f"{module_id}: master switch is missing {field}")
            if not entry.get("source_config") or not entry.get("runtime_config"):
                fail(f"{module_id}: master switch has no source/runtime config path")
            on_value = str(switch["enabled_value"]).strip().lower()
            off_value = str(switch["disabled_value"]).strip().lower()
            if (on_value, off_value) not in {("1", "0"), ("true", "false")}:
                fail(f"{module_id}: master switch must map enabled to 1/true and disabled to 0/false")
            expected = on_value if module["enabled"] else off_value
            if not expected:
                fail(f"{module_id}: missing target switch value")
        elif status == "upstream_default":
            if policy != "leave_upstream_default" or not isinstance(switch, dict):
                fail(f"{module_id}: upstream-default policy not represented in config map")
            if not module.get("enabled") or switch.get("upstream_default") != "1":
                fail(f"{module_id}: approved upstream default must remain enabled with value 1")
            if not entry.get("source_config") or not entry.get("runtime_config"):
                fail(f"{module_id}: upstream-default mapping has no source/runtime config path")
        else:
            if policy != "match_manifest_state" or switch is not None or not entry.get("review_note"):
                fail(f"{module_id}: no-master-switch limitation is not documented")
            if not module["enabled"]:
                fail(f"{module_id}: a manifest-disabled module with no master switch cannot be runtime-disabled")

    expected_upstream = {"mod-playerbots-city-life", "mod-dungeon-clear"}
    actual_upstream = {mid for mid, entry in mapped.items() if entry.get("status") == "upstream_default"}
    if actual_upstream != expected_upstream:
        fail(f"Only City Life and Dungeon Clear may use leave_upstream_default; got {sorted(actual_upstream)}")
    if counts != {"master_switch": 48, "upstream_default": 2, "no_master_switch": 16}:
        fail(f"Unexpected config map classification counts: {counts}")
    if by_id["mod-dungeon-clear"].get("enabled") is not True:
        fail("Dungeon Clear must not be disabled")
    return counts["master_switch"], counts["upstream_default"], counts["no_master_switch"]


def check_additional_settings_mapping(manifest: dict, lock: dict) -> int:
    mapping = load_json(ADDITIONAL_SETTINGS_PATH)
    if mapping.get("core_commit") != lock["core"].get("commit"):
        fail("Additional module settings map was audited against a different core commit")
    entries = mapping.get("settings")
    if not isinstance(entries, list):
        fail("config/additional-module-settings.json must contain a settings list")

    modules = {module["id"]: module for module in manifest["modules"]}
    lock_modules = lock["modules"]
    by_key: dict[tuple[str, str], dict] = {}
    for entry in entries:
        module_id = entry.get("module_id")
        key = entry.get("key")
        if module_id not in modules or not isinstance(key, str):
            fail(f"Invalid additional module settings entry: {entry!r}")
        module = modules[module_id]
        if not module.get("install") or not module.get("enabled"):
            fail(f"{module_id}: additional settings require an installed, enabled module")
        if entry.get("source_commit") != lock_modules[module_id].get("commit"):
            fail(f"{module_id}: additional settings source commit differs from lock")
        for field in ("source_config", "runtime_config", "upstream_default", "target", "evidence"):
            if not isinstance(entry.get(field), str) or not entry[field]:
                fail(f"{module_id}:{key}: missing {field}")
        identity = (module_id, key)
        if identity in by_key:
            fail(f"Duplicate additional module setting {module_id}:{key}")
        by_key[identity] = entry

    expected = {
        ("mod-rdf-expansion", "RDF.Expansion"): ("2", "2"),
        ("mod-TimeIsTime", "TimeIsTime.SpeedRate"): ("1.0", "15.0"),
    }
    if set(by_key) != set(expected):
        fail(f"Unexpected additional module settings keys: {sorted(by_key)}")
    for identity, values in expected.items():
        entry = by_key[identity]
        if (entry.get("upstream_default"), entry.get("target")) != values:
            fail(f"{identity[0]}:{identity[1]} must preserve audited default/target {values}")

    dynamic_xp = load_json(SWITCHES_PATH)["modules"]["mod-dynamic-xp"]["switch"]
    if not isinstance(dynamic_xp, dict) or dynamic_xp.get("key") != "Dynamic.XP.Rate" or dynamic_xp.get("enabled_value") != "1":
        fail("Dynamic XP must remain mapped to Dynamic.XP.Rate = 1 by the module master-switch map")
    return len(entries)


def check_core_defaults_mapping(lock: dict) -> str:
    mapping = load_json(CORE_DEFAULTS_PATH)
    core_commit = lock["core"].get("commit")
    if mapping.get("core_commit") != core_commit:
        fail("Core worldserver defaults map was audited against a different core commit")
    status = mapping.get("status")
    if status not in {"pending_core_fork_commit", "pinned_in_core_fork"}:
        fail(f"Invalid core defaults status: {status!r}")
    if status == "pending_core_fork_commit" and core_commit != PENDING_CORE_SHA:
        fail("The old core SHA cannot remain marked pending after the personal-fork config commit")
    if mapping.get("source_config") != "src/server/apps/worldserver/worldserver.conf.dist":
        fail("Core defaults map points at an unexpected worldserver template")
    patch = ROOT / mapping.get("patch_file", "")
    if not patch.is_file():
        fail("Core defaults patch file is missing")
    entries = mapping.get("settings")
    expected = {
        "MapUpdate.Threads": ("1", "4"),
        "EnablePlayerSettings": ("0", "1"),
        "DBC.EnforceItemAttributes": ("1", "0"),
        "ActivateWeather": ("1", "0"),
    }
    if not isinstance(entries, list) or len(entries) != len(expected):
        fail("Core worldserver defaults map must contain exactly four reviewed settings")
    actual = {entry.get("key"): entry for entry in entries if isinstance(entry, dict)}
    if set(actual) != set(expected):
        fail(f"Unexpected core defaults keys: {sorted(str(key) for key in actual)}")
    for key, values in expected.items():
        entry = actual[key]
        if (entry.get("upstream_default"), entry.get("target")) != values or not entry.get("evidence"):
            fail(f"Core default {key} must retain audited upstream/target values {values} and evidence")
    return status


def check() -> tuple[dict, dict]:
    manifest = load_json(MANIFEST_PATH)
    lock = load_json(LOCK_PATH)
    modules = manifest.get("modules")
    lock_modules = lock.get("modules")
    if not isinstance(modules, list) or not isinstance(lock_modules, dict):
        fail("Manifest 'modules' must be a list and lock 'modules' must be an object")

    ids: list[str] = []
    enabled_count = 0
    disabled_count = 0
    for index, module in enumerate(modules, start=1):
        if not isinstance(module, dict):
            fail(f"Manifest module #{index} is not an object")
        module_id = module.get("id")
        if not isinstance(module_id, str) or not module_id:
            fail(f"Manifest module #{index} has no valid id")
        ids.append(module_id)
        if not isinstance(module.get("enabled"), bool):
            fail(f"{module_id}: 'enabled' must be true or false")
        if module.get("install") is not True:
            fail(f"{module_id}: all 66 requested module sources must remain installable")
        enabled_count += int(module["enabled"])
        disabled_count += int(not module["enabled"])
        clone_url = module.get("clone_url")
        if not isinstance(clone_url, str) or not clone_url:
            fail(f"{module_id}: missing clone_url")
        entry = lock_modules.get(module_id)
        if not isinstance(entry, dict):
            fail(f"{module_id}: missing lock entry")
        if canonical_url(entry.get("url", "")) != canonical_url(clone_url):
            fail(f"{module_id}: lock URL does not match manifest clone_url")
        if not isinstance(entry.get("branch"), str) or not entry["branch"]:
            fail(f"{module_id}: lock entry has no resolved branch")
        commit = entry.get("commit")
        if not entry.get("resolved") or not isinstance(commit, str) or not SHA_RE.fullmatch(commit):
            fail(f"{module_id}: missing a resolved full 40-character commit SHA")

    if len(ids) != len(set(ids)):
        duplicates = sorted({module_id for module_id in ids if ids.count(module_id) > 1})
        fail("Duplicate module IDs: " + ", ".join(duplicates))
    if len(modules) != 66 or enabled_count != 52 or disabled_count != 14:
        fail(f"Expected 66 modules (52 enabled, 14 initially disabled), got {len(modules)} ({enabled_count} enabled, {disabled_count} disabled)")
    if set(ids) != set(lock_modules):
        missing = sorted(set(ids) - set(lock_modules))
        extra = sorted(set(lock_modules) - set(ids))
        fail(f"Manifest/lock IDs differ (missing lock entries: {missing}; extra lock entries: {extra})")

    manifest_core = manifest.get("core", {})
    lock_core = lock.get("core", {})
    if not isinstance(manifest_core, dict) or not isinstance(lock_core, dict):
        fail("Manifest and lock must contain core objects")
    if canonical_url(manifest_core.get("repository", "")) != canonical_url(EXPECTED_CORE_URL):
        fail("Manifest core URL differs from the user-designated Playerbot fork")
    if manifest_core.get("branch") != EXPECTED_CORE_BRANCH:
        fail("Manifest core branch differs from the user-designated Playerbot branch")
    if canonical_url(lock_core.get("url", "")) != canonical_url(EXPECTED_CORE_URL):
        fail("Core lock URL does not match the user-designated repository")
    if lock_core.get("branch") != EXPECTED_CORE_BRANCH or manifest_core.get("branch") != lock_core.get("branch"):
        fail("Core lock branch does not match the manifest branch")
    core_commit = lock_core.get("commit")
    if not lock_core.get("resolved") or core_commit != EXPECTED_CORE_SHA or not SHA_RE.fullmatch(str(core_commit)):
        fail("Core lock SHA differs from the user-designated pinned commit")
    if manifest_core.get("candidate_commit") != core_commit:
        fail("Manifest candidate core commit and lock SHA differ")

    by_id = {module["id"]: module for module in modules}
    for module_id in ("mod-playerbots-city-life", "mod-dungeon-clear"):
        if module_id not in by_id or not by_id[module_id].get("install") or not by_id[module_id].get("enabled"):
            fail(f"{module_id} must remain present, installable, and enabled")
        if by_id[module_id].get("config_policy") != "leave_upstream_default":
            fail(f"{module_id} must retain the approved upstream-default config policy")
    dungeon = by_id["mod-dungeon-clear"]
    if not dungeon.get("source_conflict"):
        fail("Dungeon Clear source-list duplicate/resolution metadata was lost")
    learn = by_id.get("mod-learn-spells")
    if not learn or canonical_url(learn.get("clone_url", "")) != canonical_url(EXPECTED_LEARN_SPELLS_URL):
        fail("Learn Spells must use the user-approved azerothcore/mod-learn-spells replacement")

    master_count, default_count, no_master_count = check_config_mapping(manifest, lock)
    additional_count = check_additional_settings_mapping(manifest, lock)
    core_defaults_status = check_core_defaults_mapping(lock)
    print(
        f"Manifest/lock valid: {len(modules)} modules ({enabled_count} enabled, "
        f"{disabled_count} initially disabled); core {core_commit[:12]} and every module have full pinned commits."
    )
    print(
        f"Config mapping valid: {master_count} verified master switches, {default_count} approved upstream defaults, "
        f"{no_master_count} documented no-master-switch cases."
    )
    print(
        f"Additional settings valid: {additional_count} reviewed module defaults; core worldserver config status={core_defaults_status}."
    )
    return manifest, lock


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-checkout", action="store_true", help="also compare materialized core/module HEADs to the lock")
    parser.add_argument("--core-dir", type=Path, default=ROOT / "core", help="materialized core directory (default: ./core)")
    args = parser.parse_args()
    manifest, lock = check()
    if args.check_checkout:
        check_checkout(args.core_dir, manifest, lock)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
