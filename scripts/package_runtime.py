#!/usr/bin/env python3
"""Assemble the Windows runtime package with a root-level release layout.

The package root contains exactly the two server executables, exactly the four
validated application DLLs, ``configs/`` with unchanged ``.conf.dist`` templates
plus generated active ``.conf`` copies, and the portable MySQL tree under
``mysql/``. Arbitrary DLLs from the install directory are never copied, and no
``bin/``, ``etc/``, ``README.txt``, ``SOURCE-PINS.json``, inventory, or nested
ZIP is ever created.

When a local archive is requested, every entry name is written relative to the
package root (``authserver.exe``, ``configs/...``, ``mysql/...``), so the same
layout is acceptable both for a manual inspection and for the GitHub artifact.
"""
from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path
import re
import shutil
import sys
import zipfile

from package_config_edits import DEFAULT_CONFIG_EDITS_PATH, stage_and_edit_configs

ROOT = Path(__file__).resolve().parents[1]
SERVER_BINARIES = ("authserver.exe", "worldserver.exe")
ROOT_RUNTIME_DLLS = ("libmysql.dll", "libcrypto-3-x64.dll", "libssl-3-x64.dll", "legacy.dll")
ROOT_DIRECTORIES = ("configs", "mysql")
STAGING_DIRECTORY_NAME = "azerothcore-ownedcore-windows"
ARCHIVE_NAME = "azerothcore-ownedcore-windows.zip"
MYSQL_VERSION_MARKER = ".mysql-version"
EXPECTED_MYSQL_VERSION = "8.4.11"
FORBIDDEN_ROOT_DIRECTORIES = ("bin", "etc")
REQUIRED_ROOT_FILES = (*SERVER_BINARIES, *ROOT_RUNTIME_DLLS)
REQUIRED_CONFIG_FILES = (
    "configs/authserver.conf.dist",
    "configs/authserver.conf",
    "configs/worldserver.conf.dist",
    "configs/worldserver.conf",
)
REQUIRED_MYSQL_FILES = ("mysql/bin/mysqld.exe", "mysql/lib/libmysql.dll")
ABSOLUTE_ENTRY_RE = re.compile(r"^[A-Za-z]:")


def copy_config_template(source: Path, destination: Path) -> None:
    """Copy the public pinned template byte-for-byte, preserving every value."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source, destination)
    except OSError as exc:
        raise RuntimeError(f"Cannot copy config template {source} to {destination}: {exc}") from exc


def _normalise_name(name: str) -> str:
    return name.replace("\\", "/").strip("/")


def _casefold_set(names: Iterable[str]) -> set[str]:
    return {name.casefold() for name in names}


def validate_package_entries(entries: Iterable[str], label: str = "package") -> list[str]:
    """Validate a flat list of package-relative entry names, failing closed."""
    normalised: list[str] = []
    for entry in entries:
        name = entry.replace("\\", "/")
        if not name or name.startswith("/") or ABSOLUTE_ENTRY_RE.match(name):
            raise RuntimeError(f"{label} contains an invalid or absolute entry: {entry}")
        if name.casefold().startswith(STAGING_DIRECTORY_NAME.casefold() + "/"):
            raise RuntimeError(
                f"{label} entries must be relative to the package root, but found "
                f"'{STAGING_DIRECTORY_NAME}/...' (the on-disk staging folder must not appear inside the archive)"
            )
        name = name.rstrip("/")
        if name == STAGING_DIRECTORY_NAME:
            raise RuntimeError(
                f"{label} entries must be relative to the package root, but found the staging folder itself"
            )
        normalised.append(name)

    if not normalised:
        raise RuntimeError(f"{label} is empty; nothing would be published")

    root_files = [name for name in normalised if "/" not in name]
    root_directories = {name.split("/", 1)[0] for name in normalised if "/" in name}
    root_file_keys = _casefold_set(root_files)
    root_directory_keys = _casefold_set(root_directories)

    forbidden_directories = sorted(
        directory for directory in root_directories if directory.casefold() in _casefold_set(FORBIDDEN_ROOT_DIRECTORIES)
    )
    if forbidden_directories:
        raise RuntimeError(
            f"{label} uses the obsolete 'bin/'+'etc/' layout: " + ", ".join(forbidden_directories)
        )
    unexpected_directories = sorted(
        directory for directory in root_directories if directory.casefold() not in _casefold_set(ROOT_DIRECTORIES)
    )
    if unexpected_directories:
        raise RuntimeError(
            f"{label} has unexpected directories at its root (only 'configs' and 'mysql' are allowed): "
            + ", ".join(unexpected_directories)
        )

    entry_keys = _casefold_set(normalised)
    nested_archives = sorted(name for name in normalised if name.casefold().endswith(".zip"))
    if nested_archives:
        raise RuntimeError(f"{label} must not contain a ZIP archive (ZIP inside ZIP): " + ", ".join(nested_archives))
    markers = sorted(name for name in normalised if name.rsplit("/", 1)[-1].casefold() == MYSQL_VERSION_MARKER)
    if markers:
        raise RuntimeError(f"{label} must not contain the MySQL provisioning marker: " + ", ".join(markers))

    extra_dlls = sorted(
        name for name in root_files if name.casefold().endswith(".dll") and name.casefold() not in _casefold_set(ROOT_RUNTIME_DLLS)
    )
    if extra_dlls:
        raise RuntimeError(
            "The package root allows exactly four DLLs (" + ", ".join(ROOT_RUNTIME_DLLS) + "); found extra: "
            + ", ".join(extra_dlls)
        )
    unexpected_files = sorted(
        name
        for name in root_files
        if name.casefold() not in _casefold_set(REQUIRED_ROOT_FILES) and not name.casefold().endswith(".dll")
    )
    if unexpected_files:
        raise RuntimeError(
            f"{label} has unexpected files at its root (no README, pin metadata, or inventory is packaged): "
            + ", ".join(unexpected_files)
        )
    missing_files = sorted(name for name in REQUIRED_ROOT_FILES if name.casefold() not in root_file_keys)
    if missing_files:
        raise RuntimeError(f"{label} is missing required root file(s): " + ", ".join(missing_files))
    for directory in ROOT_DIRECTORIES:
        if directory.casefold() not in root_directory_keys:
            raise RuntimeError(f"{label} is missing the required '{directory}/' directory")

    missing_configs = sorted(name for name in REQUIRED_CONFIG_FILES if name.casefold() not in entry_keys)
    if missing_configs:
        raise RuntimeError(f"{label} is missing required config file(s): " + ", ".join(missing_configs))
    module_templates = [
        name
        for name in normalised
        if name.casefold().startswith("configs/modules/") and name.casefold().endswith(".conf.dist")
    ]
    if not module_templates:
        raise RuntimeError(f"{label} contains no module config templates under configs/modules/")

    # Every unchanged template must ship beside an active copy that the edit map
    # was applied to, and no active copy may exist without a template behind it.
    templates = [name for name in normalised if name.casefold().endswith(".conf.dist")]
    active = {name.casefold() for name in normalised if name.casefold().endswith(".conf")}
    unpaired = sorted(name for name in templates if name[:-len(".dist")].casefold() not in active)
    if unpaired:
        raise RuntimeError(
            f"{label} has .conf.dist template(s) without a matching active .conf: " + ", ".join(unpaired)
        )
    orphan_active = sorted(
        name for name in normalised if name.casefold().endswith(".conf") and name.casefold() + ".dist" not in _casefold_set(templates)
    )
    if orphan_active:
        raise RuntimeError(
            f"{label} has active .conf file(s) without a matching .conf.dist template: " + ", ".join(orphan_active)
        )
    missing_mysql = sorted(name for name in REQUIRED_MYSQL_FILES if name.casefold() not in entry_keys)
    if missing_mysql:
        raise RuntimeError(f"{label} is missing required portable MySQL file(s): " + ", ".join(missing_mysql))
    return normalised


def package_entries(root: Path) -> list[str]:
    """Return and validate the sorted package-relative entries of a staging tree."""
    root = root.resolve()
    if not root.is_dir():
        raise RuntimeError(f"Package staging directory is missing: {root}")
    entries: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if not path.is_file():
            raise RuntimeError(f"Package staging tree contains an unsupported entry: {path.relative_to(root).as_posix()}")
        entries.append(path.relative_to(root).as_posix())
    validate_package_entries(entries, f"Package staging tree {root}")
    return entries


def create_package_archive(root: Path, archive: Path) -> list[str]:
    """Write one ZIP whose entries are relative to ``root`` and validate it."""
    root = root.resolve()
    archive = archive.resolve()
    if archive.is_relative_to(root):
        raise RuntimeError(f"The package ZIP must be created outside the staging root: {archive}")
    entries = package_entries(root)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for relative in entries:
            bundle.write(root / relative, relative)
    verify_package_archive(archive)
    return entries


def verify_package_archive(archive: Path) -> list[str]:
    """Verify that an existing ZIP carries exactly the root-level release layout."""
    archive = archive.resolve()
    try:
        with zipfile.ZipFile(archive) as bundle:
            names = [info.filename for info in bundle.infolist() if not info.is_dir()]
    except (OSError, zipfile.BadZipFile) as exc:
        raise RuntimeError(f"Cannot read package archive {archive}: {exc}") from exc
    return validate_package_entries(names, f"Package archive {archive.name}")


def _mysql_version_marker(mysql_root: Path) -> str | None:
    marker = mysql_root / MYSQL_VERSION_MARKER
    if not marker.is_file():
        return None
    value = marker.read_text(encoding="utf-8", errors="replace").strip()
    if value != EXPECTED_MYSQL_VERSION:
        raise RuntimeError(
            f"The portable MySQL tree is marked {value or '<empty>'}, but this package requires "
            f"{EXPECTED_MYSQL_VERSION}: {mysql_root}"
        )
    return value


def _check_required_files(directory: Path, names: Iterable[str], label: str) -> None:
    missing = sorted(name for name in names if not (directory / name).is_file())
    if missing:
        raise RuntimeError(f"Missing required {label}: " + ", ".join(missing))


def _check_runtime_dll_staging(dll_dir: Path) -> list[str]:
    dll_dir = dll_dir.resolve()
    if not dll_dir.is_dir():
        raise RuntimeError(f"Validated runtime DLL staging directory is missing: {dll_dir}")
    files = sorted(path for path in dll_dir.iterdir() if path.is_file())
    subdirectories = sorted(path.name for path in dll_dir.iterdir() if path.is_dir())
    if subdirectories:
        raise RuntimeError(
            "Runtime DLL staging must be a flat directory without subdirectories: " + ", ".join(subdirectories)
        )
    non_dlls = sorted(path.name for path in files if path.suffix.casefold() != ".dll")
    if non_dlls:
        raise RuntimeError(
            "Runtime DLL staging must contain only DLLs (the inventory stays outside the staging tree): "
            + ", ".join(non_dlls)
        )
    names = {path.name.casefold(): path.name for path in files}
    expected = {name.casefold(): name for name in ROOT_RUNTIME_DLLS}
    missing = sorted(expected[key] for key in expected if key not in names)
    extra = sorted(name for key, name in names.items() if key not in expected)
    if missing or extra:
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise RuntimeError(
            "Runtime DLL staging must contain exactly the four release DLLs, no more and no fewer ("
            + "; ".join(details)
            + ")"
        )
    return sorted(names.values())


def _copy_config_templates(config_dir: Path, destination: Path) -> list[Path]:
    templates = sorted(config_dir.rglob("*.conf.dist"))
    if not templates:
        raise RuntimeError(f"No installed .conf.dist templates found under {config_dir}")
    copied: list[Path] = []
    for source in templates:
        relative = source.relative_to(config_dir)
        target = destination / relative
        copy_config_template(source, target)
        copied.append(relative)
    return copied


def _copy_mysql_tree(mysql_root: Path, destination: Path) -> int:
    copied = 0
    for path in sorted(mysql_root.rglob("*")):
        relative = path.relative_to(mysql_root)
        if relative.name == MYSQL_VERSION_MARKER or path.suffix.casefold() == ".zip":
            continue
        if path.is_dir():
            (destination / relative).mkdir(parents=True, exist_ok=True)
            continue
        if not path.is_file():
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied += 1
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "core" / "env" / "dist", help="installed binary directory containing both server executables")
    parser.add_argument("--dll-dir", type=Path, default=ROOT / "core" / "env" / "runtime-dlls", help="validated four-DLL staging directory")
    parser.add_argument("--mysql-root", type=Path, required=True, help="portable MySQL 8.4.11 tree copied under mysql/")
    parser.add_argument("--config-dir", type=Path, help="installed .conf.dist template directory (default: <dist-dir>/configs)")
    parser.add_argument("--output", type=Path, default=ROOT / "runtime-package", help="output directory for the staging tree and optional ZIP")
    parser.add_argument("--config-edits", type=Path, default=DEFAULT_CONFIG_EDITS_PATH, help="JSON map of edits for generated active .conf copies")
    parser.add_argument("--no-archive", action="store_true", help="skip the local inspection ZIP and keep only the staging tree")
    args = parser.parse_args()

    dist = args.dist_dir.resolve()
    dll_dir = args.dll_dir.resolve()
    mysql_root = args.mysql_root.resolve()
    config_dir = (args.config_dir or (dist / "configs")).resolve()
    output = args.output.resolve()

    if not dist.is_dir():
        raise RuntimeError(f"Installed binary directory is missing: {dist}")
    _check_required_files(dist, SERVER_BINARIES, "server executable(s)")
    if not config_dir.is_dir():
        raise RuntimeError(f"Installed config directory is missing: {config_dir}")
    _check_required_files(config_dir, ("authserver.conf.dist", "worldserver.conf.dist"), "config template(s)")
    if not any(config_dir.glob("modules/*.conf.dist")):
        raise RuntimeError(f"No module .conf.dist templates found under {config_dir / 'modules'}")
    if not mysql_root.is_dir():
        raise RuntimeError(f"Portable MySQL tree is missing: {mysql_root}")
    _check_required_files(mysql_root, ("bin/mysqld.exe", "lib/libmysql.dll"), "portable MySQL file(s)")
    mysql_version = _mysql_version_marker(mysql_root)
    staged_dlls = _check_runtime_dll_staging(dll_dir)

    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"Refusing to overwrite nonempty package output directory: {output}")
    output.mkdir(parents=True, exist_ok=True)

    staging = output / STAGING_DIRECTORY_NAME
    staging.mkdir(parents=True)

    for name in SERVER_BINARIES:
        shutil.copy2(dist / name, staging / name)
    for name in staged_dlls:
        source = dll_dir / name
        if not source.is_file():
            raise RuntimeError(f"Cannot stage runtime DLL {name}: {source} is missing")
        shutil.copy2(source, staging / name)

    config_templates = _copy_config_templates(config_dir, staging / "configs")
    active_configs, applied_edits, config_warnings = stage_and_edit_configs(staging / "configs", args.config_edits.resolve())
    mysql_files = _copy_mysql_tree(mysql_root, staging / "mysql")

    entries = package_entries(staging)
    archive: Path | None = None
    if not args.no_archive:
        archive = output / ARCHIVE_NAME
        if archive.exists():
            archive.unlink()
        create_package_archive(staging, archive)

    print(
        f"Packaged {len(SERVER_BINARIES)} executables, {len(staged_dlls)} runtime DLLs ({', '.join(staged_dlls)}), "
        f"{len(config_templates)} unchanged .conf.dist templates, {active_configs} active .conf copies "
        f"({applied_edits} edits applied, {config_warnings} non-fatal warning(s)), and {mysql_files} portable "
        f"MySQL files (version marker: {mysql_version or 'not present'})."
    )
    print(f"Package root: {staging} ({len(entries)} files; entries are relative to this root)")
    print("Root entries: " + ", ".join(sorted({entry.split('/', 1)[0] for entry in entries})))
    if archive is not None:
        print(f"Inspection archive: {archive} (single ZIP, no staging-folder prefix, no nested ZIP)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
