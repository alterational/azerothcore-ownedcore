#!/usr/bin/env python3
"""Package Windows executables, selected runtime DLLs, and config copies.

The package intentionally excludes game/client data, maps, SQL, database dumps,
and machine-specific active `.conf` files. Public `.conf.dist` templates are copied
byte-for-byte; their `.conf` siblings are generated in the package and edited only
by the reviewed, repository-controlled config map. Failed individual edits warn
but do not fail packaging. Executables and validated runtime dependencies are
placed at the package root; configuration files remain under `etc/`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import zipfile

from module_selection import excluded_module_ids, select_modules
from package_config_edits import DEFAULT_CONFIG_EDITS_PATH, stage_and_edit_configs
from stage_windows_runtime_dlls import is_debug_dll

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "modules.lock.json"
MANIFEST_PATH = ROOT / "modules.manifest.json"

REQUIRED_BINARIES = ("worldserver.exe", "authserver.exe")
REQUIRED_RUNTIME_DLLS = {
    "libmysql.dll",
    "libcrypto-3-x64.dll",
    "libssl-3-x64.dll",
    "legacy.dll",
    "msvcp140.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
}
RUNTIME_INVENTORY = "RUNTIME-DLLS.json"


def copy_config_template(source: Path, destination: Path) -> None:
    """Copy the public pinned template byte-for-byte, preserving every value."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source, destination)
    except OSError as exc:
        raise RuntimeError(f"Cannot copy config template {source} to {destination}: {exc}") from exc


def validate_runtime_dll_directory(dll_dir: Path) -> tuple[list[Path], dict]:
    """Validate the dependency stage inventory and reject debug/Boost DLLs."""
    if not dll_dir.is_dir():
        raise RuntimeError(f"Missing staged Windows runtime DLL directory: {dll_dir}")
    dlls = sorted(
        (path for path in dll_dir.iterdir() if path.is_file() and path.suffix.casefold() == ".dll"),
        key=lambda path: path.name.casefold(),
    )
    dll_names = {path.name.casefold() for path in dlls}
    missing = sorted(name for name in REQUIRED_RUNTIME_DLLS if name.casefold() not in dll_names)
    if missing:
        raise RuntimeError("Missing required Windows runtime DLLs: " + ", ".join(missing))
    debug_dlls = [path.name for path in dlls if is_debug_dll(path.name)]
    boost_dlls = [path.name for path in dlls if "boost" in path.name.casefold()]
    if debug_dlls:
        raise RuntimeError("Debug DLLs are not permitted in the release package: " + ", ".join(debug_dlls))
    if boost_dlls:
        raise RuntimeError("Boost DLLs are not required by the release executables and must not be packaged: " + ", ".join(boost_dlls))

    inventory_path = dll_dir / RUNTIME_INVENTORY
    if not inventory_path.is_file():
        raise RuntimeError(f"Missing dependency-analysis inventory: {inventory_path}")
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read dependency-analysis inventory {inventory_path}: {exc}") from exc
    if not isinstance(inventory, dict) or inventory.get("schema_version") != 1:
        raise RuntimeError(f"Unsupported dependency-analysis inventory schema in {inventory_path}")
    expected = inventory.get("runtime_dlls")
    if not isinstance(expected, list) or not all(isinstance(name, str) for name in expected):
        raise RuntimeError(f"Invalid runtime_dlls list in {inventory_path}")
    if {name.casefold() for name in expected} != dll_names:
        raise RuntimeError(
            f"Staged DLLs do not match {RUNTIME_INVENTORY}; rerun dependency analysis before packaging"
        )
    runtime_manifests = sorted(
        (path for path in dll_dir.iterdir() if path.is_file() and path.suffix.casefold() == ".manifest"),
        key=lambda path: path.name.casefold(),
    )
    expected_manifests = inventory.get("vc_runtime_manifests", [])
    if not isinstance(expected_manifests, list) or not all(isinstance(name, str) for name in expected_manifests):
        raise RuntimeError(f"Invalid vc_runtime_manifests list in {inventory_path}")
    if {name.casefold() for name in expected_manifests} != {path.name.casefold() for path in runtime_manifests}:
        raise RuntimeError(
            f"Staged VC++ manifests do not match {RUNTIME_INVENTORY}; rerun dependency analysis before packaging"
        )
    return dlls, inventory, runtime_manifests


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "core" / "env" / "dist", help="installed AzerothCore runtime tree")
    parser.add_argument("--binary-dir", type=Path, help="directory containing installed executables (default: <dist-dir>)")
    parser.add_argument("--dll-dir", type=Path, help="validated minimal runtime DLL staging directory (default: <dist-dir>/runtime-dlls)")
    parser.add_argument("--config-dir", type=Path, help="directory containing installed .conf.dist templates (default: <dist-dir>/etc)")
    parser.add_argument("--output", type=Path, default=ROOT / "runtime-package", help="output package directory")
    parser.add_argument(
        "--config-edits",
        type=Path,
        default=DEFAULT_CONFIG_EDITS_PATH,
        help="JSON map of edits for generated active .conf copies",
    )
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
    binary_dir = (args.binary_dir if args.binary_dir is not None else dist).resolve()
    dll_dir = (args.dll_dir if args.dll_dir is not None else dist / "runtime-dlls").resolve()
    config_dir = (args.config_dir if args.config_dir is not None else dist / "etc").resolve()
    if not binary_dir.is_dir() or not config_dir.is_dir():
        raise RuntimeError(f"Expected installed binary/config directories at {binary_dir} and {config_dir}")
    missing = sorted(name for name in REQUIRED_BINARIES if not (binary_dir / name).is_file())
    if missing:
        raise RuntimeError("Missing required Windows server binaries: " + ", ".join(missing))
    runtime_dlls, runtime_inventory, runtime_manifests = validate_runtime_dll_directory(dll_dir)
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"Refusing to overwrite nonempty package directory: {output}")
    output.mkdir(parents=True, exist_ok=True)

    package_root = output / "azerothcore-ownedcore-windows"
    package_root.mkdir(parents=True)
    for name in REQUIRED_BINARIES:
        shutil.copy2(binary_dir / name, package_root / name)
    for source in runtime_dlls:
        shutil.copy2(source, package_root / source.name)
    for manifest_file in runtime_manifests:
        shutil.copy2(manifest_file, package_root / manifest_file.name)
    shutil.copy2(dll_dir / RUNTIME_INVENTORY, package_root / RUNTIME_INVENTORY)

    template_sources = sorted(config_dir.rglob("*.conf.dist"))
    if not template_sources:
        raise RuntimeError(f"No .conf.dist runtime templates found under {config_dir}")
    copied_configs = 0
    for source in template_sources:
        relative = source.relative_to(config_dir)
        destination = package_root / "etc" / relative
        copy_config_template(source, destination)
        copied_configs += 1

    active_configs, applied_edits, config_warnings = stage_and_edit_configs(
        package_root / "etc", args.config_edits.resolve()
    )

    (package_root / "README.txt").write_text(
        "AzerothCore OwnedCore Windows runtime build.\n"
        "authserver.exe, worldserver.exe, and the selected runtime DLLs are at the package root (there is no bin/ directory).\n"
        "RUNTIME-DLLS.json records the dependency-analysis inventory; Boost and debug DLLs are not packaged.\n"
        "Any Visual C++ runtime manifests supplied with the selected release DLLs are included.\n"
        "Configuration templates and generated active copies are under etc/; module configs are under etc/modules/.\n"
        "Public *.conf.dist templates are unchanged. Only edits listed in the build repository's config/package-config-edits.json are applied to generated active copies; installed machine-specific configs are not copied.\n"
        "Unapplied edits caused by a missing file/key or a value-type mismatch are reported as non-fatal warnings.\n"
        "Individual Progression source is "
        + ("included by explicit request.\n" if individual_progression_included else "omitted from the default build.\n")
        + "Review the supplied configs and set deployment-specific values before first startup.\n"
        "Client/game data, maps, vmaps, mmaps, SQL dumps, and machine-specific active server configs are not included.\n",
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
        f"Packaged {len(REQUIRED_BINARIES)} server executables, {len(runtime_dlls)} selected runtime DLLs, "
        f"{copied_configs} unchanged .conf.dist templates, and {active_configs} active .conf copies; "
        f"applied {applied_edits} config edits with {config_warnings} non-fatal warning(s) "
        f"({variant}; MySQL {runtime_inventory.get('mysql_client_version', 'unknown')}). Archive: {archive}"
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
