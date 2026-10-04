#!/usr/bin/env python3
"""Package Windows runtime binaries and sanitized default config templates.

The package intentionally excludes game/client data, maps, SQL, database dumps,
active server-specific `.conf` files, and passwords/secrets. Database connection
and secret-bearing settings in `.conf.dist` files are blanked for distribution.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "modules.lock.json"

# Only server runtimes and shared runtime DLLs are copied from env/dist/bin.
REQUIRED_BINARIES = {"worldserver.exe", "authserver.exe"}
DATABASE_INFO_RE = re.compile(r"^[A-Za-z0-9_.-]*DatabaseInfo$", re.IGNORECASE)
SENSITIVE_KEY_RE = re.compile(
    r"(?:password|passwd|secret|token|api[-_.]?key|access[-_.]?key|private[-_.]?key|client[-_.]?secret)",
    re.IGNORECASE,
)
ASSIGNMENT_RE = re.compile(r"^(\s*[#;]?\s*)([A-Za-z0-9_.-]+)(\s*=\s*)(.*?)(\r?\n)?$")


def sanitize_config(text: str) -> tuple[str, int]:
    lines: list[str] = []
    redacted = 0
    for line in text.splitlines(keepends=True):
        match = ASSIGNMENT_RE.match(line)
        if not match:
            lines.append(line)
            continue
        prefix, key, assignment, _value, newline = match.groups()
        # Never ship connection strings: they contain username/password/database fields.
        if DATABASE_INFO_RE.fullmatch(key):
            lines.append(f'{prefix}{key}{assignment}""{newline or ""}')
            redacted += 1
        elif SENSITIVE_KEY_RE.search(key):
            lines.append(f'{prefix}{key}{assignment}""{newline or ""}')
            redacted += 1
        else:
            lines.append(line)
    return "".join(lines), redacted


def copy_config_template(source: Path, destination: Path) -> int:
    try:
        text = source.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"Cannot read UTF-8 config template {source}: {exc}") from exc
    sanitized, redacted = sanitize_config(text)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(sanitized, encoding="utf-8", newline="")
    return redacted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "core" / "env" / "dist", help="installed AzerothCore runtime tree")
    parser.add_argument("--output", type=Path, default=ROOT / "runtime-package", help="output package directory")
    args = parser.parse_args()

    dist = args.dist_dir.resolve()
    output = args.output.resolve()
    bin_dir = dist / "bin"
    etc_dir = dist / "etc"
    if not bin_dir.is_dir() or not etc_dir.is_dir():
        raise RuntimeError(f"Expected installed runtime directories at {bin_dir} and {etc_dir}")
    missing = sorted(name for name in REQUIRED_BINARIES if not (bin_dir / name).is_file())
    if missing:
        raise RuntimeError("Missing required Windows server binaries: " + ", ".join(missing))
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"Refusing to overwrite nonempty package directory: {output}")
    output.mkdir(parents=True, exist_ok=True)

    package_root = output / "azerothcore-ownedcore-windows"
    binary_output = package_root / "bin"
    binary_output.mkdir(parents=True)
    copied_binaries = 0
    for source in sorted(bin_dir.iterdir()):
        if not source.is_file():
            continue
        suffix = source.suffix.lower()
        if source.name.lower() not in REQUIRED_BINARIES and suffix != ".dll":
            continue
        shutil.copy2(source, binary_output / source.name)
        copied_binaries += 1

    template_sources = sorted(etc_dir.rglob("*.conf.dist"))
    if not template_sources:
        raise RuntimeError(f"No .conf.dist runtime templates found under {etc_dir}")
    copied_configs = 0
    redacted_values = 0
    for source in template_sources:
        relative = source.relative_to(etc_dir)
        # Restrict packaging to the root runtime templates and installed module templates.
        if relative.parts and relative.parts[0] not in {"modules"} and len(relative.parts) != 1:
            continue
        destination = package_root / "etc" / relative
        redacted_values += copy_config_template(source, destination)
        copied_configs += 1

    (package_root / "README.txt").write_text(
        "AzerothCore OwnedCore Windows runtime build.\n"
        "Source pins are recorded in the build repository's modules.lock.json.\n"
        "This package contains server binaries and sanitized *.conf.dist templates only.\n"
        "Database connection strings and secret-bearing settings are blank and must be configured locally.\n"
        "Client/game data, maps, vmaps, mmaps, SQL dumps, and active server configs are not included.\n",
        encoding="utf-8",
        newline="\n",
    )
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    (package_root / "SOURCE-PINS.json").write_text(
        json.dumps({"core": lock["core"], "modules": lock["modules"]}, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    archive = output / "azerothcore-ownedcore-windows.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for source in sorted(package_root.rglob("*")):
            if source.is_file():
                bundle.write(source, source.relative_to(output))

    print(
        f"Packaged {copied_binaries} Windows binaries/DLLs and {copied_configs} sanitized config templates; "
        f"redacted {redacted_values} credential/secret settings. Archive: {archive}"
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
