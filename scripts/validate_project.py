#!/usr/bin/env python3
"""Validate the manifest, immutable source lock, and reviewed config-state mapping."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from module_selection import excluded_module_ids, select_modules
from package_config_edits import load_config_edits

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "modules.manifest.json"
LOCK_PATH = ROOT / "modules.lock.json"
SWITCHES_PATH = ROOT / "config" / "module-switches.json"
ADDITIONAL_SETTINGS_PATH = ROOT / "config" / "additional-module-settings.json"
CORE_DEFAULTS_PATH = ROOT / "config" / "core-worldserver-defaults.json"
CORE_AUTH_DEFAULTS_PATH = ROOT / "config" / "core-authserver-defaults.json"
CORE_COMPATIBILITY_PATCH_PATHS = (
    ROOT / "patches" / "azerothcore-ninja-msvc-config-path.patch",
    ROOT / "patches" / "azerothcore-cygwin-install.patch",
)
CORE_COMPATIBILITY_PATCH_SHA = "14c435031d2cb31b1af664af9a83c5d6256302b6"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_CORE_URL = "https://github.com/alterational/azerothcore-wotlk.git"
EXPECTED_CORE_BRANCH = "Playerbot"
EXPECTED_CORE_SHA = "14c435031d2cb31b1af664af9a83c5d6256302b6"
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


def check_checkout(core_dir: Path, manifest: dict, lock: dict, include_modules: list[str]) -> int:
    core_lock = lock["core"]
    actual_core = git_output(["git", "-C", str(core_dir), "rev-parse", "HEAD"])
    if actual_core != core_lock["commit"]:
        fail(f"core HEAD {actual_core} does not match lock {core_lock['commit']}")

    try:
        selected = select_modules(manifest["modules"], include_modules)
        excluded_ids = excluded_module_ids(manifest["modules"], include_modules)
    except ValueError as exc:
        fail(str(exc))

    modules_root = core_dir / "modules"
    for module_id in excluded_ids:
        excluded_path = modules_root / module_id
        if excluded_path.exists():
            fail(
                f"{module_id}: excluded from this build, but its source directory still exists at {excluded_path}. "
                "Run scripts/materialize.py with the same module selection before compiling."
            )

    checked = 0
    for module in selected:
        module_dir = modules_root / module["id"]
        if not (module_dir / ".git").exists():
            fail(f"Missing materialized module checkout: {module_dir.relative_to(ROOT)}")
        actual = git_output(["git", "-C", str(module_dir), "rev-parse", "HEAD"])
        expected = lock["modules"][module["id"]]["commit"]
        if actual != expected:
            fail(f"{module['id']} HEAD {actual} does not match lock {expected}")
        checked += 1

    selection = f"; excluded source(s): {', '.join(excluded_ids)}" if excluded_ids else ""
    print(f"Checkout pins valid: core and {checked} selected module sources match locked HEADs{selection}.")
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
    if counts != {"master_switch": 52, "upstream_default": 2, "no_master_switch": 16}:
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
        ("mod-TimeIsTime", "TimeIsTime.SpeedRate"): ("1.0", "1.0"),
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
    world = load_json(CORE_DEFAULTS_PATH)
    auth = load_json(CORE_AUTH_DEFAULTS_PATH)
    core_commit = lock["core"].get("commit")
    world_status = world.get("status")
    auth_status = auth.get("status")
    if world_status not in {"pending_core_fork_commit", "pinned_in_core_fork"}:
        fail(f"Invalid worldserver defaults status: {world_status!r}")
    if auth_status != world_status:
        fail("Authserver and worldserver defaults maps must have the same core-fork status")
    if world_status == "pending_core_fork_commit" and core_commit != PENDING_CORE_SHA:
        fail("The old core SHA cannot remain marked pending after the personal-fork config commit")

    expected_maps = [
        (
            world,
            "worldserver",
            "src/server/apps/worldserver/worldserver.conf.dist",
            {
                "MapUpdate.Threads": ("1", "4"),
                "EnablePlayerSettings": ("0", "1"),
                "DBC.EnforceItemAttributes": ("1", "0"),
                "ActivateWeather": ("1", "0"),
                "Appender.Server": ("2,5,0,Server.log,w", "2,5,8,Server.log,w"),
                "Appender.Playerbots": ("2,5,0,Playerbots.log,w", "2,5,8,Playerbots.log,w"),
                "Appender.Errors": ("2,2,0,Errors.log,w", "2,2,8,Errors.log,w"),
                "Die.Command.Mode": ("1", "0"),
                "DungeonFinder.OptionsMask": ("5", "5"),
            },
        ),
        (
            auth,
            "authserver",
            "src/server/apps/authserver/authserver.conf.dist",
            {"Appender.Auth": ("2,5,0,Auth.log,w", "2,5,8,Auth.log,w")},
        ),
    ]
    for mapping, label, source_config, expected in expected_maps:
        if mapping.get("core_commit") != core_commit:
            fail(f"Core {label} defaults map was audited against a different core commit")
        if mapping.get("source_config") != source_config:
            fail(f"Core {label} defaults map points at an unexpected template")
        patch = ROOT / mapping.get("patch_file", "")
        if not patch.is_file():
            fail(f"Core {label} defaults patch file is missing")
        entries = mapping.get("settings")
        if not isinstance(entries, list) or len(entries) != len(expected):
            fail(f"Core {label} defaults map must contain exactly {len(expected)} reviewed settings")
        actual = {entry.get("key"): entry for entry in entries if isinstance(entry, dict)}
        if set(actual) != set(expected):
            fail(f"Unexpected core {label} defaults keys: {sorted(str(key) for key in actual)}")
        for key, values in expected.items():
            entry = actual[key]
            if (entry.get("upstream_default"), entry.get("target")) != values or not entry.get("evidence"):
                fail(f"Core {label} default {key} must retain audited upstream/target values {values} and evidence")
            if key == "DungeonFinder.OptionsMask" and entry.get("patch_base_default") != "7":
                fail("DungeonFinder.OptionsMask must record pre-update Playerbot branch default 7 separately from the pinned core target")
    return world_status


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
            fail(f"{module_id}: all requested module sources must remain installable")
        compile_by_default = module.get("compile_by_default", True)
        if not isinstance(compile_by_default, bool):
            fail(f"{module_id}: compile_by_default must be a boolean when specified")
        if compile_by_default is False and not module.get("optional", False):
            fail(f"{module_id}: only an explicitly optional source may be excluded from the default build")
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
    if len(modules) != 70 or enabled_count != 55 or disabled_count != 15:
        fail(f"Expected 70 modules (55 enabled, 15 initially disabled), got {len(modules)} ({enabled_count} enabled, {disabled_count} disabled)")
    if set(ids) != set(lock_modules):
        missing = sorted(set(ids) - set(lock_modules))
        extra = sorted(set(lock_modules) - set(ids))
        fail(f"Manifest/lock IDs differ (missing lock entries: {missing}; extra lock entries: {extra})")

    default_excluded = {module["id"] for module in modules if module.get("compile_by_default", True) is False}
    if default_excluded != {"mod-individual-progression"}:
        fail(
            "Only mod-individual-progression may be opt-in for the default build; "
            f"found compile_by_default=false for {sorted(default_excluded)}"
        )
    individual_progression = next(module for module in modules if module["id"] == "mod-individual-progression")
    if not individual_progression.get("optional") or not individual_progression.get("enabled"):
        fail("Individual Progression must remain available and enabled when explicitly included")

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
    if core_commit == CORE_COMPATIBILITY_PATCH_SHA:
        for patch_path in CORE_COMPATIBILITY_PATCH_PATHS:
            if not patch_path.is_file():
                fail(f"Tracked Windows core compatibility patch is missing: {patch_path.relative_to(ROOT)}")

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
    if (
        not learn
        or canonical_url(learn.get("clone_url", "")) != canonical_url(EXPECTED_LEARN_SPELLS_URL)
        or learn.get("source_override")
    ):
        fail("Learn Spells must use the approved azerothcore/mod-learn-spells source without a stale override")

    master_count, default_count, no_master_count = check_config_mapping(manifest, lock)
    additional_count = check_additional_settings_mapping(manifest, lock)
    package_edit_count = len(load_config_edits())
    package_overrides = check_package_edit_audit(manifest, lock)
    core_defaults_status = check_core_defaults_mapping(lock)
    default_source_count = len(select_modules(modules))
    print(
        f"Manifest/lock valid: {len(modules)} locked modules ({enabled_count} manifest-enabled, "
        f"{disabled_count} initially runtime-off); default build selects {default_source_count} sources "
        "and leaves Individual Progression opt-in. Core and all module pins are full commits."
    )
    print(
        f"Config mapping valid: {master_count} verified master switches, {default_count} approved upstream defaults, "
        f"{no_master_count} documented no-master-switch cases."
    )
    print(
        f"Additional settings valid: {additional_count} reviewed module defaults; core authserver/worldserver config status={core_defaults_status}."
    )
    override_note = (
        f" (upstream-default overrides: {', '.join(sorted(package_overrides))})" if package_overrides else ""
    )
    print(
        f"Package config edit map valid: {package_edit_count} editable active-config settings{override_note}."
    )
    return manifest, lock


def _canonical(value: str) -> str:
    text = str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text
    if text.casefold() in {"true", "false"}:
        return text.casefold()
    return text


PORTABLE_CORE_KEYS = {
    "authserver.conf": {"LogsDir", "SourceDirectory", "MySQLExecutable", "TempDir"},
    "worldserver.conf": {"DataDir", "LogsDir", "TempDir", "SourceDirectory", "MySQLExecutable"},
}


def check_package_edit_audit(manifest: dict, lock: dict) -> list[str]:
    """Keep the shipped package edits inside the audited configuration policy.

    The package map is what actually reaches a user's `.conf`, so a typo or a
    stale value here silently ships a wrong server configuration. Every module
    master switch must therefore resolve to one of its three audited values, and
    any deviation from modules.manifest.json must be the upstream default, which
    is the only reviewed override form.
    """
    switches = load_json(SWITCHES_PATH)["modules"]
    modules = {module["id"]: module for module in manifest["modules"]}

    by_runtime = {}
    for module_id, entry in switches.items():
        switch = entry.get("switch")
        if switch and entry.get("runtime_config"):
            by_runtime[f"modules/{entry['runtime_config']}"] = (module_id, switch)

    overrides: list[str] = []
    for edit in load_config_edits():
        if edit.relative_file in PORTABLE_CORE_KEYS:
            if edit.key not in PORTABLE_CORE_KEYS[edit.relative_file]:
                fail(f"Unexpected packaged core setting {edit.relative_file}: {edit.key}")
            if not (edit.value.startswith('"') and edit.value.endswith('"')):
                fail(
                    f"{edit.relative_file}: {edit.key} must be a quoted relative path, got {edit.value!r}; "
                    "the packaged core templates declare these as strings"
                )
            continue

        target = by_runtime.get(edit.relative_file)
        if target is None:
            continue
        module_id, switch = target
        if edit.key != switch["key"]:
            continue

        audited = {_canonical(switch["upstream_default"])}
        for field in ("enabled_value", "disabled_value"):
            if switch.get(field) is not None:
                audited.add(_canonical(switch[field]))
        if _canonical(edit.value) not in audited:
            fail(
                f"{edit.relative_file}: {edit.key} ships {edit.value!r}, which is not an audited value "
                f"({', '.join(sorted(audited))})"
            )

        if "enabled_value" in switch and "disabled_value" in switch:
            policy = switch["enabled_value"] if modules[module_id]["enabled"] else switch["disabled_value"]
            if _canonical(edit.value) != _canonical(policy):
                if _canonical(edit.value) != _canonical(switch["upstream_default"]):
                    fail(
                        f"{edit.relative_file}: {edit.key} ships {edit.value!r} but the manifest policy is "
                        f"{policy!r}; a deviation must ship the audited upstream default"
                    )
                overrides.append(f"{module_id}:{edit.key}={edit.value}")
    return overrides


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-checkout", action="store_true", help="also compare materialized core/selected module HEADs to the lock")
    parser.add_argument("--core-dir", type=Path, default=ROOT / "core", help="materialized core directory (default: ./core)")
    parser.add_argument(
        "--include-module",
        action="append",
        default=[],
        metavar="MODULE_ID",
        help="include an optional compile_by_default=false source in checkout validation; may be repeated",
    )
    args = parser.parse_args()
    manifest, lock = check()
    if args.check_checkout:
        check_checkout(args.core_dir, manifest, lock, args.include_module)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
