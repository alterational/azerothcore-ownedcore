#!/usr/bin/env python3
"""Package Windows runtime binaries and the selected pinned config templates unchanged.

The package intentionally excludes game/client data, maps, SQL, database dumps,
and active server-specific `.conf` files. Public `.conf.dist` templates are copied
byte-for-byte; no config values are redacted or rewritten.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import zipfile

from module_selection import excluded_module_ids, select_modules

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "modules.lock.json"
MANIFEST_PATH = ROOT / "modules.manifest.json"

# Only required server runtimes and shared runtime DLLs are copied from the selected binary directory.
REQUIRED_BINARIES = {"worldserver.exe", "authserver.exe"}


def copy_config_template(source: Path, destination: Path) -> None:
    """Copy the public pinned template byte-for-byte, preserving every value."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source, destination)
    except OSError as exc:
        raise RuntimeError(f"Cannot copy config template {source} to {destination}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "core" / "env" / "dist", help="installed AzerothCore runtime tree")
    parser.add_argument("--binary-dir", type=Path, help="directory containing installed executables/DLLs (default: <dist-dir>/bin)")
    parser.add_argument("--config-dir", type=Path, help="directory containing installed .conf.dist templates (default: <dist-dir>/etc)")
    parser.add_argument("--output", type=Path, default=ROOT / "runtime-package", help="output package directory")
    parser.add_argument(
        "--include-module",
        action="append",
        default=[],
        metavar="MODULE_ID",
        help="include an optional compile_by_default=false source in package pin metadata; may be repeated",
    )
    args = parser.parse_args()

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    try:
        selected_modules = select_modules(manifest["modules"], args.include_module)
        excluded_ids = excluded_module_ids(manifest["modules"], args.include_module)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc
    selected_ids = [module["id"] for module in selected_modules]
    individual_progression_included = "mod-individual-progression" in selected_ids

    dist = args.dist_dir.resolve()
    output = args.output.resolve()
    bin_dir = (args.binary_dir if args.binary_dir is not None else dist / "bin").resolve()
    config_dir = (args.config_dir if args.config_dir is not None else dist / "etc").resolve()
    if not bin_dir.is_dir() or not config_dir.is_dir():
        raise RuntimeError(f"Expected installed binary/config directories at {bin_dir} and {config_dir}")
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

    template_sources = sorted(config_dir.rglob("*.conf.dist"))
    if not template_sources:
        raise RuntimeError(f"No .conf.dist runtime templates found under {config_dir}")
    copied_configs = 0
    for source in template_sources:
        relative = source.relative_to(config_dir)
        # Restrict packaging to the root runtime templates and installed module templates.
        if relative.parts and relative.parts[0] not in {"modules"} and len(relative.parts) != 1:
            continue
        destination = package_root / "etc" / relative
        copy_config_template(source, destination)
        copied_configs += 1

    (package_root / "README.txt").write_text(
        "AzerothCore OwnedCore Windows runtime build.\n"
        "Source pins are recorded in the build repository's modules.lock.json.\n"
        "This package contains server binaries and unchanged *.conf.dist templates only.\n"
        "Individual Progression source is "
        + ("included by explicit request.\n" if individual_progression_included else "omitted from the default build.\n")
        + "Review the supplied config templates and set deployment-specific values before first startup.\n"
        "Client/game data, maps, vmaps, mmaps, SQL dumps, and active server configs are not included.\n",
        encoding="utf-8",
        newline="\n",
    )
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    build_pins = {
        "core": lock["core"],
        "modules": {module_id: lock["modules"][module_id] for module_id in selected_ids},
        "excluded_modules": excluded_ids,
        "build_selection": {"mod-individual-progression": individual_progression_included},
    }
    (package_root / "SOURCE-PINS.json").write_text(
        json.dumps(build_pins, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    archive = output / "azerothcore-ownedcore-windows.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for source in sorted(package_root.rglob("*")):
            if source.is_file():
                bundle.write(source, source.relative_to(output))

    variant = "with Individual Progression" if individual_progression_included else "without Individual Progression"
    print(
        f"Packaged {copied_binaries} Windows binaries/DLLs and {copied_configs} unchanged config templates "
        f"({variant}). Archive: {archive}"
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
