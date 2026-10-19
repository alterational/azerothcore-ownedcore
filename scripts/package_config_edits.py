#!/usr/bin/env python3
"""Create active package configs from unchanged templates and apply mapped edits.

Only the generated `.conf` copies are edited. The source `.conf.dist` files are
left byte-for-byte unchanged. A missing target file/key or incompatible value
kind is a non-fatal warning so package preparation can continue.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_EDITS_PATH = ROOT / "config" / "package-config-edits.json"


@dataclass(frozen=True)
class ConfigEdit:
    relative_file: str
    key: str
    value: str


def load_config_edits(path: Path = DEFAULT_CONFIG_EDITS_PATH) -> list[ConfigEdit]:
    """Load and structurally validate the editable package config map."""
    try:
        mapping = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read package config edit map {path}: {exc}") from exc
    if not isinstance(mapping, dict) or mapping.get("schema_version") != 1:
        raise RuntimeError(f"Unsupported package config edit map schema in {path}")
    configs = mapping.get("configs")
    if not isinstance(configs, dict):
        raise RuntimeError(f"Package config edit map {path} must contain a configs object")

    edits: list[ConfigEdit] = []
    seen: set[tuple[str, str]] = set()
    for relative_file, entries in configs.items():
        if not isinstance(relative_file, str) or "\\" in relative_file:
            raise RuntimeError(f"Invalid config path in {path}: {relative_file!r}; use forward slashes")
        relative = PurePosixPath(relative_file)
        valid_target = (
            not relative.is_absolute()
            and ".." not in relative.parts
            and relative.suffix == ".conf"
            and relative_file not in {"", ".", ".."}
            and (
                relative.parts in (("authserver.conf",), ("worldserver.conf",))
                or (len(relative.parts) == 2 and relative.parts[0] == "modules")
            )
        )
        if not valid_target:
            raise RuntimeError(
                f"Invalid package config target {relative_file!r} in {path}; targets must be authserver.conf, "
                "worldserver.conf, or modules/<name>.conf"
            )
        if not isinstance(entries, list):
            raise RuntimeError(f"Config edits for {relative_file} in {path} must be a list")

        for entry in entries:
            if not isinstance(entry, dict):
                raise RuntimeError(f"Invalid config edit for {relative_file} in {path}: {entry!r}")
            key = entry.get("key")
            value = entry.get("value")
            if (
                not isinstance(key, str)
                or not key
                or "\n" in key
                or "\r" in key
                or not isinstance(value, str)
                or "\n" in value
                or "\r" in value
            ):
                raise RuntimeError(f"Config edits require a single-line string key/value: {relative_file}: {entry!r}")
            identity = (relative_file, key)
            if identity in seen:
                raise RuntimeError(f"Duplicate package config edit for {relative_file}, key {key}")
            seen.add(identity)
            edits.append(ConfigEdit(relative_file, key, value))
    return edits


def copy_templates_to_active_configs(etc_dir: Path) -> int:
    """Create every staged `.conf` as a byte-identical sibling of its `.conf.dist`."""
    templates = sorted(etc_dir.rglob("*.conf.dist"))
    if not templates:
        raise RuntimeError(f"No packaged .conf.dist templates found under {etc_dir}")

    copied = 0
    for template in templates:
        active = template.with_suffix("")
        active.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template, active)
        if active.read_bytes() != template.read_bytes():
            raise RuntimeError(f"Generated active config is not byte-identical to its template: {active}")
        copied += 1
    return copied


def _value_and_comment(raw: str) -> tuple[str, str]:
    """Split an assignment value from an inline # comment, respecting quotes."""
    quote: str | None = None
    escaped = False
    for index, character in enumerate(raw):
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote is not None:
            escaped = True
            continue
        if quote is not None:
            if character == quote:
                quote = None
            continue
        if character in {'"', "'"}:
            quote = character
        elif character == "#":
            return raw[:index], raw[index:]
    return raw, ""


def _value_kind(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
        return "string"
    if stripped.casefold() in {"true", "false"}:
        return "boolean"
    if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", stripped):
        return "number"
    return "string"


def _find_assignments(text: str, key: str) -> list[tuple[int, str, str, str, str]]:
    """Return index/prefix/current/comment/newline for active assignments of key."""
    pattern = re.compile(r"^([ \t]*" + re.escape(key) + r"[ \t]*=[ \t]*)(.*?)(\r?\n)?$")
    found: list[tuple[int, str, str, str, str]] = []
    for index, line in enumerate(text.splitlines(keepends=True)):
        if line.lstrip().startswith(("#", ";", "[")):
            continue
        match = pattern.match(line)
        if not match:
            continue
        raw_value, comment = _value_and_comment(match.group(2))
        current = raw_value.strip()
        found.append((index, match.group(1), current, comment, match.group(3) or ""))
    return found


def _warning(relative_file: str, key: str, current: str, new: str) -> str:
    return f"WARNING: couldn't apply config edit for: {relative_file}, key {key} {current} {new}"


def apply_config_edits(etc_dir: Path, edits: list[ConfigEdit]) -> tuple[int, int]:
    """Apply valid edits, printing required non-fatal warnings for skipped edits.

    Returns `(applied_edit_count, warning_count)`.
    """
    working: dict[Path, str] = {}
    changed: set[Path] = set()
    applied = 0
    warning_count = 0

    for edit in edits:
        relative_file = PurePosixPath(edit.relative_file)
        path = etc_dir.joinpath(*relative_file.parts)
        if not path.is_file():
            print(_warning(edit.relative_file, edit.key, "<file-missing>", edit.value))
            warning_count += 1
            continue

        if path not in working:
            try:
                working[path] = path.read_bytes().decode("utf-8")
            except (OSError, UnicodeDecodeError):
                print(_warning(edit.relative_file, edit.key, "<file-unreadable>", edit.value))
                warning_count += 1
                continue

        matches = _find_assignments(working[path], edit.key)
        if not matches:
            print(_warning(edit.relative_file, edit.key, "<key-missing>", edit.value))
            warning_count += 1
            continue
        if len(matches) != 1:
            print(_warning(edit.relative_file, edit.key, "<duplicate-key>", edit.value))
            warning_count += 1
            continue

        index, prefix, current, comment, newline = matches[0]
        if _value_kind(current) != _value_kind(edit.value):
            print(_warning(edit.relative_file, edit.key, current or "<empty>", edit.value))
            warning_count += 1
            continue

        lines = working[path].splitlines(keepends=True)
        replacement = prefix + edit.value
        if comment:
            replacement += " " + comment.lstrip()
        replacement += newline
        if lines[index] != replacement:
            lines[index] = replacement
            working[path] = "".join(lines)
            changed.add(path)
        applied += 1

    for path in sorted(changed):
        path.write_bytes(working[path].encode("utf-8"))
    return applied, warning_count


def stage_and_edit_configs(etc_dir: Path, edits_path: Path = DEFAULT_CONFIG_EDITS_PATH) -> tuple[int, int, int]:
    """Copy all templates, then apply the editable package-only config map."""
    etc_dir = etc_dir.resolve()
    edits = load_config_edits(edits_path)
    copied = copy_templates_to_active_configs(etc_dir)
    applied, warnings = apply_config_edits(etc_dir, edits)
    return copied, applied, warnings


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--etc-dir", type=Path, required=True, help="package etc/ directory containing .conf.dist files")
    parser.add_argument("--config-edits", type=Path, default=DEFAULT_CONFIG_EDITS_PATH, help="editable JSON map")
    args = parser.parse_args()
    copied, applied, warnings = stage_and_edit_configs(args.etc_dir, args.config_edits)
    print(f"Created {copied} active .conf copies; applied {applied} config edits; {warnings} warning(s).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
