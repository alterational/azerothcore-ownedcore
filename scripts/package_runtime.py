#!/usr/bin/env python3
"""Package the Windows release executables, four root DLLs, portable MySQL, and configs.

The package excludes source-pin metadata, developer README/inventory files,
game/client data, maps, SQL, database dumps, and machine-specific active `.conf`
files. Public `.conf.dist` templates are copied byte-for-byte; their `.conf`
siblings are generated in the package and edited only by the reviewed,
repository-controlled config map.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import zipfile

from module_selection import select_modules
from package_config_edits import DEFAULT_CONFIG_EDITS_PATH, stage_and_edit_configs
from stage_windows_runtime_dlls import is_debug_dll, is_external_vc_runtime_dll

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "modules.manifest.json"

REQUIRED_BINARIES = ("worldserver.exe", "authserver.exe")
REQUIRED_RUNTIME_DLLS = {
    "libmysql.dll",
    "libcrypto-3-x64.dll",
    "libssl-3-x64.dll",
    "legacy.dll",
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
    if dll_names != {name.casefold() for name in expected}:
        raise RuntimeError(
            f"Staged DLLs do not match {RUNTIME_INVENTORY}; rerun dependency analysis before packaging"
        )
    unexpected = dll_names - {name.casefold() for name in REQUIRED_RUNTIME_DLLS}
    missing = {name.casefold() for name in REQUIRED_RUNTIME_DLLS} - dll_names
    if unexpected or missing:
        detail = []
        if missing:
            detail.append("missing=" + ",".join(sorted(missing)))
        if unexpected:
            detail.append("unexpected=" + ",".join(sorted(unexpected)))
        raise RuntimeError("Release root must contain exactly the four application DLLs: " + "; ".join(detail))
    return dlls, inventory


def copy_portable_mysql(source: Path, destination: Path) -> int:
    """Copy the portable MySQL distribution under mysql/, excluding build-only markers and forbidden DLLs."""
    source = source.resolve()
    destination = destination.resolve()
    if not source.is_dir():
        raise RuntimeError(f"Missing portable MySQL distribution: {source}")
    required_mysql_files = (source / "bin" / "mysqld.exe", source / "lib" / "libmysql.dll")
    missing = [str(path.relative_to(source)) for path in required_mysql_files if not path.is_file()]
    if missing:
        raise RuntimeError("Portable MySQL distribution is incomplete; missing " + ", ".join(missing))
    if destination.exists():
        raise RuntimeError(f"Refusing to overwrite existing MySQL package directory: {destination}")

    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            path = Path(directory) / name
            if (
                name.casefold() == ".arena-mysql-version"
                or name.casefold().startswith("readme")
                or name.casefold().startswith("vcredist")
            ):
                ignored.add(name)
            elif path.is_file() and path.suffix.casefold() == ".dll":
                if is_debug_dll(name) or is_external_vc_runtime_dll(name) or "boost" in name.casefold():
                    ignored.add(name)
            elif path.is_file() and path.suffix.casefold() == ".manifest" and name.casefold().startswith("microsoft.vc"):
                ignored.add(name)
        return ignored

    shutil.copytree(source, destination, ignore=ignore)
    return sum(1 for path in destination.rglob("*") if path.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "core" / "env" / "dist", help="installed AzerothCore runtime tree")
    parser.add_argument("--binary-dir", type=Path, help="directory containing installed executables (default: <dist-dir>)")
    parser.add_argument("--dll-dir", type=Path, help="validated four-DLL staging directory (default: <dist-dir>/runtime-dlls)")
    parser.add_argument("--mysql-dir", type=Path, required=True, help="portable MySQL distribution root containing bin/ and lib/")
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
        help="include an optional compile_by_default=false module in package variant reporting; may be repeated",
    )
    args = parser.parse_args()

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    try:
        selected_modules = select_modules(manifest["modules"], args.include_module)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc
    selected_ids = [module["id"] for module in selected_modules]
    individual_progression_included = "mod-individual-progression" in selected_ids

    dist = args.dist_dir.resolve()
    output = args.output.resolve()
    binary_dir = (args.binary_dir if args.binary_dir is not None else dist).resolve()
    dll_dir = (args.dll_dir if args.dll_dir is not None else dist / "runtime-dlls").resolve()
    mysql_dir = args.mysql_dir.resolve()
    config_dir = (args.config_dir if args.config_dir is not None else dist / "etc").resolve()
    if not binary_dir.is_dir() or not config_dir.is_dir():
        raise RuntimeError(f"Expected installed binary/config directories at {binary_dir} and {config_dir}")
    missing = sorted(name for name in REQUIRED_BINARIES if not (binary_dir / name).is_file())
    if missing:
        raise RuntimeError("Missing required Windows server binaries: " + ", ".join(missing))
    runtime_dlls, runtime_inventory = validate_runtime_dll_directory(dll_dir)
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"Refusing to overwrite nonempty package directory: {output}")
    output.mkdir(parents=True, exist_ok=True)

    package_root = output / "azerothcore-ownedcore-windows"
    package_root.mkdir(parents=True)
    for name in REQUIRED_BINARIES:
        shutil.copy2(binary_dir / name, package_root / name)
    for source in runtime_dlls:
        shutil.copy2(source, package_root / source.name)
    mysql_file_count = copy_portable_mysql(mysql_dir, package_root / "mysql")

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

    archive = output / "azerothcore-ownedcore-windows.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for source in sorted(package_root.rglob("*")):
            if source.is_file():
                bundle.write(source, source.relative_to(output))

    variant = "with Individual Progression" if individual_progression_included else "without Individual Progression"
    print(
        f"Packaged {len(REQUIRED_BINARIES)} server executables, exactly {len(runtime_dlls)} root DLLs, "
        f"portable MySQL ({mysql_file_count} files), {copied_configs} unchanged .conf.dist templates, "
        f"and {active_configs} active .conf copies; applied {applied_edits} config edits with "
        f"{config_warnings} non-fatal warning(s) ({variant}; MySQL "
        f"{runtime_inventory.get('mysql_client_version', 'unknown')}). Archive: {archive}"
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
