#!/usr/bin/env python3
"""Stage the four release DLLs and verify the server import closure.

The package build uses Microsoft's `dumpbin /DEPENDENTS` to analyze both server
executables and their selected DLLs. Only the MySQL client DLL, OpenSSL DLLs, and
OpenSSL's dynamically loaded legacy provider are staged beside the executables.
The VC++ runtime is an external Windows prerequisite and is not bundled.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable

SERVER_BINARIES = ("authserver.exe", "worldserver.exe")
REQUIRED_RUNTIME_DLLS = (
    "libmysql.dll",
    "libcrypto-3-x64.dll",
    "libssl-3-x64.dll",
    "legacy.dll",
)
DEPENDENCY_RE = re.compile(r"^\s*([A-Za-z0-9_.+-]+\.dll)\s*$", re.IGNORECASE)
SYSTEM_API_PREFIXES = ("api-ms-win-", "ext-ms-win-")
VC_RUNTIME_DLL_RE = re.compile(r"^(?:concrt|msvcp|vccorlib|vcruntime|vcomp)\d+.*\.dll$", re.IGNORECASE)
DEBUG_DLL_RE = re.compile(
    r"(?:-debug(?:-|\.)|(?:^|[-_])gd(?:[-_.]|$)|(?:msvcp|vcruntime|concrt|vccorlib|vcomp)\d+d\.dll$)",
    re.IGNORECASE,
)
DependencyReader = Callable[[Path], Iterable[str]]


def is_debug_dll(name: str) -> bool:
    """Reject debug CRT/third-party variants from release packages."""
    return bool(DEBUG_DLL_RE.search(name))


def is_external_vc_runtime_dll(name: str) -> bool:
    """Identify VC++ runtime files supplied by the machine's installed runtime."""
    return bool(VC_RUNTIME_DLL_RE.fullmatch(name))


def parse_dumpbin_dependents(output: str) -> list[str]:
    """Parse DLL names from `dumpbin /DEPENDENTS` output, preserving order."""
    result: list[str] = []
    seen: set[str] = set()
    for line in output.splitlines():
        match = DEPENDENCY_RE.fullmatch(line)
        if not match:
            continue
        name = match.group(1).strip()
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            result.append(name)
    return result


def dumpbin_dependencies(binary: Path, dumpbin: str = "dumpbin") -> list[str]:
    """Read static imports from one PE file using the Visual Studio toolchain."""
    try:
        completed = subprocess.run(
            [dumpbin, "/nologo", "/DEPENDENTS", str(binary)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise RuntimeError(f"Cannot run {dumpbin!r} for {binary}: {exc}") from exc
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"{dumpbin} failed for {binary}: {details}")
    return parse_dumpbin_dependents(completed.stdout + "\n" + completed.stderr)


def is_windows_system_dll(name: str, system_dir: Path) -> bool:
    """Recognize OS API-set DLLs and concrete files provided by Windows."""
    lowered = name.casefold()
    if lowered.startswith(SYSTEM_API_PREFIXES):
        return True
    return (system_dir / name).is_file()


def _candidate_index(search_dirs: Iterable[Path]) -> dict[str, Path]:
    """Index release DLL candidates; earlier directories have precedence."""
    candidates: dict[str, Path] = {}
    for directory in search_dirs:
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix.casefold() != ".dll" or is_debug_dll(path.name):
                continue
            candidates.setdefault(path.name.casefold(), path)
    return candidates


def _copy_runtime_file(source: Path, destination: Path, output_dir: Path) -> Path:
    destination_path = output_dir / destination.name
    if destination_path.exists():
        return destination_path
    shutil.copy2(source, destination_path)
    return destination_path


def stage_runtime_dependencies(
    *,
    binary_dir: Path,
    mysql_lib_dir: Path,
    mysql_bin_dir: Path,
    openssl_bin_dir: Path,
    openssl_module_dir: Path | None,
    output_dir: Path,
    system_dir: Path,
    mysql_version: str,
    dependency_reader: DependencyReader = dumpbin_dependencies,
) -> dict:
    """Copy a minimal release DLL set and return the staged inventory.

    The import walk is recursive and fails closed when a non-system, non-VC++
    dependency cannot be resolved or would require a fifth root DLL. The VC++
    runtime is recorded as a machine prerequisite but is never copied. The
    MySQL and OpenSSL DLL candidates are searched only to resolve the four
    approved root DLLs. `legacy.dll` is seeded because OpenSSL loads it by name.
    """
    binary_dir = binary_dir.resolve()
    mysql_lib_dir = mysql_lib_dir.resolve()
    mysql_bin_dir = mysql_bin_dir.resolve()
    openssl_bin_dir = openssl_bin_dir.resolve()
    system_dir = system_dir.resolve()
    output_dir = output_dir.resolve()
    openssl_module_dir = openssl_module_dir.resolve() if openssl_module_dir else None

    missing_binaries = [name for name in SERVER_BINARIES if not (binary_dir / name).is_file()]
    if missing_binaries:
        raise RuntimeError("Missing installed server binaries: " + ", ".join(missing_binaries))
    required_dirs = {
        "MySQL lib directory": mysql_lib_dir,
        "MySQL bin directory": mysql_bin_dir,
        "OpenSSL bin directory": openssl_bin_dir,
    }
    for label, directory in required_dirs.items():
        if not directory.is_dir():
            raise RuntimeError(f"Missing {label}: {directory}")
    if not (mysql_lib_dir / "libmysql.dll").is_file():
        raise RuntimeError(f"MySQL client DLL is missing from its lib directory: {mysql_lib_dir / 'libmysql.dll'}")

    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError(f"Refusing to overwrite nonempty runtime DLL staging directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    search_dirs = [
        output_dir,
        mysql_lib_dir,
        openssl_bin_dir,
        *([openssl_module_dir] if openssl_module_dir else []),
        mysql_bin_dir,
        binary_dir,
    ]
    candidates = _candidate_index(search_dirs)
    staged_paths = {path.name.casefold(): path for path in output_dir.glob("*.dll")}
    staged_names = set(staged_paths)

    # The OpenSSL legacy provider is loaded dynamically by name, not by a PE import.
    for name in REQUIRED_RUNTIME_DLLS:
        if name.casefold() in staged_names:
            continue
        source = candidates.get(name.casefold())
        if source is None:
            raise RuntimeError(f"Required runtime DLL {name} was not found in the selected dependency directories")
        staged_path = _copy_runtime_file(source, Path(name), output_dir)
        staged_names.add(name.casefold())
        staged_paths[name.casefold()] = staged_path

    queue: list[Path] = [binary_dir / name for name in SERVER_BINARIES]
    queue.extend(sorted(output_dir.glob("*.dll")))
    visited: set[str] = set()
    system_imports: set[str] = set()
    external_vc_runtime_imports: set[str] = set()
    while queue:
        binary = queue.pop(0)
        identity = binary.name.casefold()
        if identity in visited:
            continue
        visited.add(identity)
        for dependency in dependency_reader(binary):
            key = dependency.casefold()
            if key in visited:
                continue
            if key in staged_names:
                queue.append(staged_paths[key])
                continue
            if is_debug_dll(dependency):
                raise RuntimeError(f"Release binary unexpectedly imports debug DLL {dependency} (from {binary.name})")
            if is_windows_system_dll(dependency, system_dir):
                system_imports.add(dependency)
                continue
            if is_external_vc_runtime_dll(dependency):
                external_vc_runtime_imports.add(dependency)
                continue
            source = candidates.get(key)
            if source is None:
                raise RuntimeError(
                    f"Unresolved non-system DLL dependency {dependency} imported by {binary.name}; "
                    "refusing to create a potentially incomplete package"
                )
            if key not in {name.casefold() for name in REQUIRED_RUNTIME_DLLS}:
                raise RuntimeError(
                    f"Additional private dependency {dependency} imported by {binary.name} would exceed "
                    "the four-DLL release layout; refusing to add it to the package root"
                )
            target = output_dir / dependency
            if not target.exists():
                shutil.copy2(source, target)
            staged_names.add(key)
            staged_paths[key] = target
            queue.append(target)

    dll_names = sorted(path.name for path in output_dir.iterdir() if path.is_file() and path.suffix.casefold() == ".dll")
    if any(is_debug_dll(name) for name in dll_names):
        raise RuntimeError("Debug DLL unexpectedly staged: " + ", ".join(name for name in dll_names if is_debug_dll(name)))
    report = {
        "schema_version": 1,
        "mysql_client_version": mysql_version,
        "selection": "four root application DLLs; OS and VC++ runtime dependencies are external prerequisites",
        "server_binaries": list(SERVER_BINARIES),
        "dynamic_dependencies": ["legacy.dll"],
        "runtime_dlls": dll_names,
        "external_vc_runtime_imports": sorted(external_vc_runtime_imports, key=str.casefold),
        "system_imports_not_packaged": sorted(system_imports, key=str.casefold),
    }
    (output_dir / "RUNTIME-DLLS.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary-dir", type=Path, required=True, help="installed directory containing authserver.exe and worldserver.exe")
    parser.add_argument("--mysql-lib-dir", type=Path, required=True, help="MySQL 8.0.x lib directory containing libmysql.dll")
    parser.add_argument("--mysql-bin-dir", type=Path, required=True, help="MySQL 8.0.x bin directory with transitive client dependencies")
    parser.add_argument("--openssl-bin-dir", type=Path, required=True, help="selected OpenSSL bin directory")
    parser.add_argument("--openssl-module-dir", type=Path, help="optional OpenSSL provider module directory")
    parser.add_argument("--system-dir", type=Path, help="Windows System32 directory (defaults to %WINDIR%/System32)")
    parser.add_argument("--output-dir", type=Path, required=True, help="empty staging directory for the minimal DLL closure")
    parser.add_argument("--mysql-version", default="8.0.46", help="MySQL client version recorded in the inventory")
    parser.add_argument("--dumpbin", default="dumpbin", help="Visual Studio dumpbin executable")
    args = parser.parse_args()

    system_dir = args.system_dir or Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32"
    report = stage_runtime_dependencies(
        binary_dir=args.binary_dir,
        mysql_lib_dir=args.mysql_lib_dir,
        mysql_bin_dir=args.mysql_bin_dir,
        openssl_bin_dir=args.openssl_bin_dir,
        openssl_module_dir=args.openssl_module_dir,
        output_dir=args.output_dir,
        system_dir=system_dir,
        mysql_version=args.mysql_version,
        dependency_reader=lambda path: dumpbin_dependencies(path, args.dumpbin),
    )
    print(
        f"Staged {len(report['runtime_dlls'])} root DLLs for authserver.exe and worldserver.exe "
        f"(MySQL {args.mysql_version}; VC++ runtime left external; OpenSSL legacy provider included)."
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
