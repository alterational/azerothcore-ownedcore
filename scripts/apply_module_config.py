#!/usr/bin/env python3
"""Apply/check the reviewed module master-switch mapping.

The default mode edits active `env/dist/etc/modules/*.conf` files after install.
Use --source-templates before compilation to patch only audited master keys in
pinned module `conf/*.conf.dist` templates. Both modes preserve unrelated
settings; use --check for read-only validation.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "modules.manifest.json"
LOCK_PATH = ROOT / "modules.lock.json"
SWITCHES_PATH = ROOT / "config" / "module-switches.json"


def fail(message: str) -> None:
    raise RuntimeError(message)


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Cannot read {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"Expected a JSON object in {path}")
    return value


def read_config(path: Path) -> str:
    """Decode without universal-newline conversion so CRLF templates stay intact."""
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        fail(f"Cannot read UTF-8 config {path}: {exc}")


def canonical_value(value: str) -> str:
    return value.strip().strip('"').strip().lower()


def assignment(text: str, key: str, path: Path) -> tuple[int, str, str]:
    """Return (line index, current value, key-prefix) for one active key."""
    pattern = re.compile(r"^(\s*" + re.escape(key) + r"\s*=\s*)(.*?)(\r?\n)?$")
    found: list[tuple[int, str, str]] = []
    for index, line in enumerate(text.splitlines(keepends=True)):
        stripped = line.lstrip()
        if stripped.startswith(("#", ";", "[")):
            continue
        match = pattern.match(line)
        if not match:
            continue
        raw = match.group(2)
        value = raw.split("#", 1)[0].strip().strip('"')
        found.append((index, value, match.group(1)))
    if len(found) != 1:
        fail(f"{path}: expected exactly one active assignment for {key}, found {len(found)}")
    return found[0]


def replace_assignment(text: str, key: str, value: str, path: Path) -> tuple[str, str]:
    lines = text.splitlines(keepends=True)
    index, before, prefix = assignment(text, key, path)
    line = lines[index]
    newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
    body = line[len(prefix):]
    comment_pos = body.find("#")
    comment = body[comment_pos:].rstrip("\r\n") if comment_pos >= 0 else ""
    replacement = prefix + value
    if comment:
        replacement += " " + comment.lstrip()
    replacement += newline
    lines[index] = replacement
    return "".join(lines), before


def verify_project(manifest: dict, lock: dict, mapping: dict) -> None:
    modules = manifest.get("modules", [])
    lock_modules = lock.get("modules", {})
    mapped = mapping.get("modules", {})
    ids = {m["id"] for m in modules}
    if set(mapped) != ids:
        fail(f"Switch map IDs differ from manifest (missing={sorted(ids-set(mapped))}, extra={sorted(set(mapped)-ids)})")
    if mapping.get("core_commit") != lock.get("core", {}).get("commit"):
        fail("Switch map was audited against a different core lock commit")

    for module in modules:
        mid = module["id"]
        entry = mapped[mid]
        if entry.get("source_commit") != lock_modules[mid].get("commit"):
            fail(f"{mid}: switch mapping was audited against a different module commit")
        if entry.get("manifest_policy") != module.get("config_policy"):
            fail(f"{mid}: switch mapping policy does not match manifest")
        policy = module.get("config_policy")
        status = entry.get("status")
        switch = entry.get("switch")
        if policy == "leave_upstream_default":
            if status != "upstream_default" or not isinstance(switch, dict):
                fail(f"{mid}: leave_upstream_default must have one audited upstream-default switch")
            if switch.get("upstream_default") != "1" or not module.get("enabled"):
                fail(f"{mid}: approved default must remain enabled with default value 1")
        elif status == "master_switch":
            if policy != "match_manifest_state" or not isinstance(switch, dict):
                fail(f"{mid}: invalid master-switch policy")
            if not entry.get("source_config") or not entry.get("runtime_config"):
                fail(f"{mid}: master switch has no source/runtime config path")
            enabled_value = str(switch.get("enabled_value", "")).strip().lower()
            disabled_value = str(switch.get("disabled_value", "")).strip().lower()
            if (enabled_value, disabled_value) not in {("1", "0"), ("true", "false")}:
                fail(f"{mid}: master switch must map enabled to 1/true and disabled to 0/false")
            target = enabled_value if module.get("enabled") else disabled_value
            if not target:
                fail(f"{mid}: missing switch value for manifest state")
        elif status == "no_master_switch":
            if policy != "match_manifest_state" or switch is not None or not entry.get("review_note"):
                fail(f"{mid}: no-master-switch limitation is not documented")
        else:
            fail(f"{mid}: unrecognized switch-map status {status!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="patch active runtime module configs to the manifest")
    mode.add_argument("--check", action="store_true", help="read-only check of active runtime config state")
    parser.add_argument("--core-dir", type=Path, default=ROOT / "core", help="pinned core checkout (default: ./core)")
    parser.add_argument("--config-dir", type=Path, default=ROOT / "core" / "env" / "dist" / "etc", help="active AzerothCore config directory")
    parser.add_argument("--source-templates", action="store_true", help="operate on pinned module conf/*.conf.dist files before compilation")
    args = parser.parse_args()

    manifest = read_json(MANIFEST_PATH)
    lock = read_json(LOCK_PATH)
    mapping = read_json(SWITCHES_PATH)
    verify_project(manifest, lock, mapping)

    core_dir = args.core_dir.resolve()
    runtime_modules = args.config_dir.resolve() / "modules"
    template_mode = args.source_templates
    changes: dict[Path, str] = {}
    changed_keys: list[tuple[str, str, str, str]] = []
    switch_count = 0
    default_count = 0
    no_master_count = 0

    for module in manifest["modules"]:
        mid = module["id"]
        entry = mapping["modules"][mid]
        source_rel = entry.get("source_config")
        source_path = core_dir / "modules" / mid / source_rel if source_rel else None
        runtime_name = entry.get("runtime_config")
        runtime_path = runtime_modules / runtime_name if runtime_name else None
        switch = entry.get("switch")
        status = entry["status"]

        if source_path and not source_path.is_file():
            fail(f"{mid}: pinned source config is missing: {source_path}")
        if not template_mode and runtime_path and not runtime_path.is_file():
            fail(
                f"{mid}: active runtime config is missing: {runtime_path}. "
                "Run the pinned core's `./acore.sh compiler all` with its default config-copy behavior, "
                "or copy that module's .conf.dist to the matching .conf in the active modules directory."
            )

        if status == "no_master_switch":
            no_master_count += 1
            continue

        key = switch["key"]
        source_text = changes.get(source_path) if template_mode else None
        if source_text is None:
            source_text = read_config(source_path)
        _, source_value, _ = assignment(source_text, key, source_path)
        upstream = switch["upstream_default"]

        if status == "upstream_default":
            default_count += 1
            if canonical_value(source_value) != canonical_value(upstream):
                fail(f"{mid}: {key} in {source_path} must remain at its pinned upstream default {upstream}; found {source_value}.")
            if not template_mode:
                runtime_text = changes.get(runtime_path)
                if runtime_text is None:
                    runtime_text = read_config(runtime_path)
                _, actual, _ = assignment(runtime_text, key, runtime_path)
                if canonical_value(actual) != canonical_value(upstream):
                    fail(
                        f"{mid}: {key} must remain at its pinned upstream default {upstream}; "
                        f"{runtime_path} currently has {actual}. Restore the upstream value manually; this tool will not override it."
                    )
            continue

        enabled_value = switch["enabled_value"]
        disabled_value = switch["disabled_value"]
        target = enabled_value if module["enabled"] else disabled_value

        if template_mode:
            if args.check and canonical_value(source_value) != canonical_value(target):
                fail(f"{mid}: {key} in {source_path} is {source_value}, expected {target} from manifest enabled={module['enabled']}")
            if canonical_value(source_value) not in {canonical_value(upstream), canonical_value(target)}:
                fail(
                    f"{mid}: {key} in {source_path} is {source_value}; expected the audited upstream default "
                    f"{upstream} or the manifest target {target}. Refusing to overwrite an unreviewed value."
                )
            new_text, before = replace_assignment(source_text, key, target, source_path)
            if canonical_value(before) != canonical_value(target):
                changes[source_path] = new_text
                changed_keys.append((mid, key, before, target))
            else:
                changes.setdefault(source_path, new_text)
        else:
            if canonical_value(source_value) not in {canonical_value(upstream), canonical_value(target)}:
                fail(
                    f"{mid}: source template {source_path} has {key}={source_value}; expected audited default "
                    f"{upstream} or manifest target {target}. Refusing an unreviewed template."
                )
            runtime_text = changes.get(runtime_path)
            if runtime_text is None:
                runtime_text = read_config(runtime_path)
            _, current_value, _ = assignment(runtime_text, key, runtime_path)
            if canonical_value(current_value) not in {canonical_value(upstream), canonical_value(target)}:
                fail(
                    f"{mid}: active {runtime_path} has {key}={current_value}; expected audited default "
                    f"{upstream} or manifest target {target}. Refusing to overwrite an unreviewed runtime value."
                )
            new_text, before = replace_assignment(runtime_text, key, target, runtime_path)
            if canonical_value(before) != canonical_value(target):
                if args.check:
                    fail(f"{mid}: {key} is {before}, expected {target} from manifest enabled={module['enabled']}")
                changes[runtime_path] = new_text
                changed_keys.append((mid, key, before, target))
            else:
                changes.setdefault(runtime_path, new_text)
        switch_count += 1

    if args.check:
        scope = "source .conf.dist templates" if template_mode else "active runtime configs"
        print(
            f"{scope} valid: {switch_count} master switches match the manifest, "
            f"{default_count} upstream defaults are preserved, {no_master_count} modules have no module-wide switch."
        )
        return 0

    # Preflight is complete; replace each changed config atomically.
    for path, content in changes.items():
        original = path.read_bytes()
        try:
            current = original.decode("utf-8")
        except UnicodeDecodeError as exc:
            fail(f"Refusing non-UTF-8 config {path}: {exc}")
        if current == content:
            continue
        mode_bits = stat.S_IMODE(path.stat().st_mode)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as tmp:
            tmp.write(content)
            temporary = Path(tmp.name)
        os.chmod(temporary, mode_bits)
        os.replace(temporary, path)

    for mid, key, before, target in changed_keys:
        print(f"{mid}: {key} {before} -> {target}")
    config_scope = "source .conf.dist templates" if template_mode else "runtime config files"
    print(
        f"Applied manifest state to {len(changes)} {config_scope}; {len(changed_keys)} keys changed. "
        f"{default_count} upstream defaults preserved; {no_master_count} no-master-switch modules documented."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
