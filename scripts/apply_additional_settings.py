#!/usr/bin/env python3
"""Apply/check audited non-master settings in pinned module config files.

Only entries in config/additional-module-settings.json are touched. The source
`.conf.dist` templates are patched before compilation; active runtime configs
can be applied/checked after install. Core worldserver settings deliberately
live in the core fork instead (see config/core-worldserver-defaults.json).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from config_assignments import assignment, atomic_write, canonical_value, read_config, replace_assignment

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "modules.manifest.json"
LOCK_PATH = ROOT / "modules.lock.json"
SETTINGS_PATH = ROOT / "config" / "additional-module-settings.json"


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


def validate_map(manifest: dict, lock: dict, settings: dict) -> None:
    core_commit = lock.get("core", {}).get("commit")
    if settings.get("core_commit") != core_commit:
        fail("Additional module settings map was audited against a different core commit")
    modules = {module["id"]: module for module in manifest.get("modules", [])}
    lock_modules = lock.get("modules", {})
    entries = settings.get("settings")
    if not isinstance(entries, list) or not entries:
        fail("Additional module settings map must contain a nonempty settings list")
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        module_id = entry.get("module_id")
        key = entry.get("key")
        if module_id not in modules or not isinstance(key, str) or not key:
            fail(f"Invalid additional module settings entry: {entry!r}")
        module = modules[module_id]
        lock_entry = lock_modules.get(module_id, {})
        if not module.get("install") or not module.get("enabled"):
            fail(f"{module_id}: additional defaults apply only to installed, enabled modules")
        if entry.get("source_commit") != lock_entry.get("commit"):
            fail(f"{module_id}: additional settings map source commit differs from lock")
        if not entry.get("source_config") or not entry.get("runtime_config"):
            fail(f"{module_id}: source and runtime config paths are required")
        upstream = entry.get("upstream_default")
        target = entry.get("target")
        if not isinstance(upstream, str) or not isinstance(target, str):
            fail(f"{module_id}:{key}: upstream_default and target must be strings")
        identity = (module_id, key)
        if identity in seen:
            fail(f"Duplicate additional settings entry: {module_id}:{key}")
        seen.add(identity)
    expected = {
        ("mod-rdf-expansion", "RDF.Expansion"),
        ("mod-TimeIsTime", "TimeIsTime.SpeedRate"),
    }
    if seen != expected:
        fail(f"Unexpected additional module settings keys: {sorted(seen)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="apply target values")
    mode.add_argument("--check", action="store_true", help="read-only check of target values")
    parser.add_argument("--core-dir", type=Path, default=ROOT / "core", help="pinned core checkout")
    parser.add_argument("--config-dir", type=Path, default=ROOT / "core" / "env" / "dist" / "etc", help="active AzerothCore config directory")
    parser.add_argument("--source-templates", action="store_true", help="operate on module conf/*.conf.dist files before compilation")
    args = parser.parse_args()

    manifest = load_json(MANIFEST_PATH)
    lock = load_json(LOCK_PATH)
    settings = load_json(SETTINGS_PATH)
    validate_map(manifest, lock, settings)

    core_dir = args.core_dir.resolve()
    template_mode = args.source_templates
    runtime_dir = args.config_dir.resolve() / "modules"
    changes: dict[Path, str] = {}
    changed: list[tuple[Path, str, str, str]] = []

    # Preflight every pinned template and, in runtime mode, every active config
    # before writing anything. Unexpected upstream values fail closed.
    for entry in settings["settings"]:
        module_id = entry["module_id"]
        source_path = core_dir / "modules" / module_id / entry["source_config"]
        runtime_path = runtime_dir / entry["runtime_config"]
        if not source_path.is_file():
            fail(f"{module_id}: pinned source config is missing: {source_path}")
        source_text = changes.get(source_path)
        if source_text is None:
            source_text = read_config(source_path)
        _, source_value, _ = assignment(source_text, entry["key"], source_path)
        upstream = entry["upstream_default"]
        target = entry["target"]
        allowed = {canonical_value(upstream), canonical_value(target)}
        if canonical_value(source_value) not in allowed:
            fail(
                f"{module_id}: {entry['key']} in {source_path} is {source_value}; expected audited upstream "
                f"default {upstream} or target {target}. Refusing to overwrite an unreviewed value."
            )

        if template_mode:
            if args.check and canonical_value(source_value) != canonical_value(target):
                fail(f"{module_id}: {entry['key']} in {source_path} is {source_value}, expected {target}")
            new_text, before = replace_assignment(source_text, entry["key"], target, source_path)
            if canonical_value(before) != canonical_value(target):
                changes[source_path] = new_text
                changed.append((source_path, entry["key"], before, target))
            else:
                changes.setdefault(source_path, new_text)
            continue

        if not runtime_path.is_file():
            fail(
                f"{module_id}: active runtime config is missing: {runtime_path}. Build/install first, "
                "or copy the module .conf.dist into the active modules directory."
            )
        runtime_text = changes.get(runtime_path)
        if runtime_text is None:
            runtime_text = read_config(runtime_path)
        _, runtime_value, _ = assignment(runtime_text, entry["key"], runtime_path)
        if canonical_value(runtime_value) not in allowed:
            fail(
                f"{module_id}: active {runtime_path} has {entry['key']}={runtime_value}; expected audited upstream "
                f"default {upstream} or target {target}. Refusing to overwrite an unreviewed value."
            )
        if args.check and canonical_value(runtime_value) != canonical_value(target):
            fail(f"{module_id}: active {entry['key']} in {runtime_path} is {runtime_value}, expected {target}")
        new_text, before = replace_assignment(runtime_text, entry["key"], target, runtime_path)
        if canonical_value(before) != canonical_value(target):
            changes[runtime_path] = new_text
            changed.append((runtime_path, entry["key"], before, target))
        else:
            changes.setdefault(runtime_path, new_text)

    if args.check:
        scope = "source module templates" if template_mode else "active module configs"
        print(f"{scope} valid: {len(settings['settings'])} reviewed non-master settings match the target map.")
        return 0

    for path, content in changes.items():
        atomic_write(path, content)
    for path, key, before, target in changed:
        display_path = path.relative_to(core_dir) if path.is_relative_to(core_dir) else path
        print(f"{display_path}: {key} {before} -> {target}")
    scope = "source module templates" if template_mode else "active module configs"
    print(f"Applied {len(changed)} value changes across {len(changes)} {scope}; settings already at target were preserved.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
