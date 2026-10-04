#!/usr/bin/env python3
"""Shared helpers for safely editing INI-style AzerothCore config templates."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import re
import stat
import tempfile


def canonical_value(value: str) -> str:
    raw = value.strip().strip('"').strip()
    try:
        number = Decimal(raw)
    except InvalidOperation:
        return raw.lower()
    normalized = number.normalize()
    return format(normalized, "f")


def assignment(text: str, key: str, path: Path) -> tuple[int, str, str]:
    """Return (line index, current value, key-prefix) for one active assignment."""
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
        raise RuntimeError(f"{path}: expected exactly one active assignment for {key}, found {len(found)}")
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


def read_config(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"Cannot read UTF-8 config {path}: {exc}") from exc


def atomic_write(path: Path, content: str) -> None:
    original = path.read_bytes()
    try:
        current = original.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"Refusing non-UTF-8 config {path}: {exc}") from exc
    if current == content:
        return
    mode_bits = stat.S_IMODE(path.stat().st_mode)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as tmp:
        tmp.write(content)
        temporary = Path(tmp.name)
    os.chmod(temporary, mode_bits)
    os.replace(temporary, path)
