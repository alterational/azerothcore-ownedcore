#!/usr/bin/env python3
"""Stage the four release DLLs beside the Windows server executables.

The release root may contain exactly four application DLLs:

* ``libmysql.dll`` from the gated MySQL 8.4.7 ``lib`` directory,
* ``libcrypto-3-x64.dll`` and ``libssl-3-x64.dll`` from the selected OpenSSL
  ``bin`` directory,
* ``legacy.dll`` from the selected OpenSSL provider-module directory.

Every other dependency must be provided by Windows itself or by the external
Microsoft Visual C++ runtime that a machine installs separately. The
``dumpbin /DEPENDENTS`` import walk is recursive over both executables and the
staged DLLs, so a missing, debug, Boost, or additional private DLL fails the
step instead of silently producing a fifth root DLL.
"""
from __future__ import annotations

import argparse
from collections import deque
from collections.abc import Callable, Collection, Iterable, Sequence
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

SERVER_BINARIES = ("authserver.exe", "worldserver.exe")
REQUIRED_RUNTIME_DLLS = (
    "libmysql.dll",
    "libcrypto-3-x64.dll",
    "libssl-3-x64.dll",
    "legacy.dll",
)
REQUIRED_MYSQL_VERSION = "8.4.7"
SYSTEM_API_PREFIXES = ("api-ms-win-", "ext-ms-win-")
DEPENDENCY_RE = re.compile(r"^\s*([A-Za-z0-9_.+-]+\.dll)\s*$", re.IGNORECASE)
VC_RUNTIME_DLL_RE = re.compile(r"^(?:concrt|msvcp|vccorlib|vcruntime|vcomp)\d+.*\.dll$", re.IGNORECASE)
DEBUG_DLL_RE = re.compile(
    r"(?:-debug(?:-|\.)|(?:^|[-_])gd(?:[-_.]|$)|(?:msvcp|vcruntime|concrt|vccorlib|vcomp)\d+d\.dll$)",
    re.IGNORECASE,
)
DependencyReader = Callable[[Path], Iterable[str]]


def is_debug_dll(name: str) -> bool:
    """Return whether a DLL name is a debug build that must never ship."""
    return bool(DEBUG_DLL_RE.search(name))


def is_vc_runtime_dll(name: str) -> bool:
    """Return whether a DLL belongs to the external VC++ runtime prerequisite."""
    return bool(VC_RUNTIME_DLL_RE.fullmatch(name))


def is_boost_dll(name: str) -> bool:
    """Return whether a DLL is a Boost runtime library."""
    return name.casefold().startswith("boost_")


def parse_dumpbin_dependents(output: str) -> list[str]:
    """Parse DLL names out of ``dumpbin /DEPENDENTS`` output, in file order."""
    names: list[str] = []
    seen: set[str] = set()
    for line in output.splitlines():
        match = DEPENDENCY_RE.fullmatch(line)
        if not match:
            continue
        name = match.group(1).strip()
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            names.append(name)
    return names


def dumpbin_dependencies(binary: Path, dumpbin: str = "dumpbin") -> list[str]:
    """Read the static import table of one PE file with the MSVC toolchain."""
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


def windows_system_dll_names(system_dir: Path) -> set[str]:
    """Index the DLL names that the operating system itself provides."""
    try:
        return {path.name.casefold() for path in system_dir.iterdir() if path.is_file()}
    except OSError:
        return set()


def is_windows_system_dll(name: str, system_dlls: Collection[str]) -> bool:
    """Recognise API-set DLLs and concrete files provided by the operating system."""
    lowered = name.casefold()
    if lowered.startswith(SYSTEM_API_PREFIXES):
        return True
    return lowered in system_dlls


def provider_module_directories(openssl_bin_dir: Path, extra: Sequence[Path] = ()) -> list[Path]:
    """Return the OpenSSL provider-module directories to search for ``legacy.dll``.

    The two locations that the Windows OpenSSL installers use are
    ``<root>/lib/ossl-modules`` and ``<root>/ossl-modules``; a ``bin/ossl-modules``
    layout is also tolerated. The SLProWeb installer runs with its ``copytobin``
    task, which flattens the provider modules (including ``legacy.dll``) into
    ``<root>/bin`` itself, so that directory is searched last. Explicit
    ``--openssl-module-dir`` values come first.
    """
    candidates = [
        *extra,
        openssl_bin_dir.parent / "lib" / "ossl-modules",
        openssl_bin_dir.parent / "ossl-modules",
        openssl_bin_dir / "ossl-modules",
        openssl_bin_dir,
    ]
    seen: set[str] = set()
    ordered: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        key = os.path.normcase(str(resolved))
        if key in seen:
            continue
        seen.add(key)
        ordered.append(resolved)
    return ordered


def validate_staged_directory(directory: Path) -> list[str]:
    """Require exactly the four approved release DLLs and nothing else."""
    directory = directory.resolve()
    if not directory.is_dir():
        raise RuntimeError(f"Runtime DLL staging directory is missing: {directory}")
    files = sorted(path for path in directory.iterdir() if path.is_file())
    non_dlls = sorted(path.name for path in files if path.suffix.casefold() != ".dll")
    if non_dlls:
        raise RuntimeError(
            "Unexpected non-DLL files in the runtime DLL staging directory: " + ", ".join(non_dlls)
        )
    subdirectories = sorted(path.name for path in directory.iterdir() if path.is_dir())
    if subdirectories:
        raise RuntimeError(
            "Unexpected subdirectories in the runtime DLL staging directory: " + ", ".join(subdirectories)
        )

    dlls = {path.name.casefold(): path.name for path in files}
    debug = sorted(name for key, name in dlls.items() if is_debug_dll(name))
    if debug:
        raise RuntimeError("Debug DLLs must never be staged for a release: " + ", ".join(debug))
    vc_runtime = sorted(name for key, name in dlls.items() if is_vc_runtime_dll(name))
    if vc_runtime:
        raise RuntimeError(
            "The external Visual C++ runtime must not be staged: " + ", ".join(vc_runtime)
        )
    boost = sorted(name for key, name in dlls.items() if is_boost_dll(name))
    if boost:
        raise RuntimeError("Boost libraries are build-time only and must not be staged: " + ", ".join(boost))

    expected = {name.casefold(): name for name in REQUIRED_RUNTIME_DLLS}
    missing = sorted(expected[key] for key in expected if key not in dlls)
    if missing:
        raise RuntimeError("Missing required runtime DLL(s): " + ", ".join(missing))
    extra = sorted(name for key, name in dlls.items() if key not in expected)
    if extra:
        raise RuntimeError(
            "Unexpected runtime DLL(s) in staging; the release root allows exactly four: " + ", ".join(extra)
        )
    return sorted(dlls.values())


def _required_dll_sources(
    mysql_root: Path, openssl_bin_dir: Path, module_dirs: Sequence[Path]
) -> dict[str, Path]:
    """Resolve each approved DLL from its single permitted source location."""
    sources = {
        "libmysql.dll": mysql_root / "lib" / "libmysql.dll",
        "libcrypto-3-x64.dll": openssl_bin_dir / "libcrypto-3-x64.dll",
        "libssl-3-x64.dll": openssl_bin_dir / "libssl-3-x64.dll",
    }
    legacy_candidates = [directory / "legacy.dll" for directory in module_dirs]
    legacy = next((candidate for candidate in legacy_candidates if candidate.is_file()), None)
    if legacy is None:
        searched = ", ".join(str(directory) for directory in module_dirs) or "<none>"
        raise RuntimeError(
            "Required runtime DLL legacy.dll was not found in the OpenSSL provider-module directories; "
            f"searched: {searched}"
        )
    sources["legacy.dll"] = legacy

    missing = [f"{name} ({path})" for name, path in sources.items() if not path.is_file()]
    if missing:
        raise RuntimeError("Required runtime DLL source(s) are missing: " + "; ".join(missing))
    return sources


def stage_runtime_dlls(
    *,
    binary_dir: Path,
    mysql_root: Path,
    openssl_bin_dir: Path,
    output_dir: Path,
    system_dir: Path,
    mysql_version: str = REQUIRED_MYSQL_VERSION,
    openssl_module_dirs: Sequence[Path] = (),
    dependency_reader: DependencyReader = dumpbin_dependencies,
) -> dict:
    """Stage and verify the four-DLL release closure, returning an inventory report."""
    if mysql_version != REQUIRED_MYSQL_VERSION:
        raise RuntimeError(
            f"Refusing to stage DLLs for MySQL {mysql_version}; this profile requires exactly "
            f"MySQL {REQUIRED_MYSQL_VERSION}."
        )

    binary_dir = binary_dir.resolve()
    mysql_root = mysql_root.resolve()
    openssl_bin_dir = openssl_bin_dir.resolve()
    output_dir = output_dir.resolve()
    system_dir = system_dir.resolve()

    missing_binaries = [name for name in SERVER_BINARIES if not (binary_dir / name).is_file()]
    if missing_binaries:
        raise RuntimeError("Missing installed server binaries: " + ", ".join(missing_binaries))
    for label, directory in (
        ("MySQL root", mysql_root),
        ("OpenSSL bin directory", openssl_bin_dir),
        ("Windows system directory", system_dir),
    ):
        if not directory.is_dir():
            raise RuntimeError(f"Missing {label}: {directory}")

    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError(f"Refusing to overwrite nonempty runtime DLL staging directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    module_dirs = provider_module_directories(openssl_bin_dir, openssl_module_dirs)
    sources = _required_dll_sources(mysql_root, openssl_bin_dir, module_dirs)
    for name, source in sources.items():
        shutil.copy2(source, output_dir / name)

    system_dlls = windows_system_dll_names(system_dir)
    staged = {path.name.casefold(): path for path in sorted(output_dir.glob("*.dll"))}
    queue: deque[Path] = deque(binary_dir / name for name in SERVER_BINARIES)
    queue.extend(staged.values())
    visited: set[str] = set()
    system_imports: set[str] = set()
    vc_runtime_imports: set[str] = set()
    while queue:
        binary = queue.popleft()
        identity = binary.name.casefold()
        if identity in visited:
            continue
        visited.add(identity)
        for dependency in dependency_reader(binary):
            name = dependency.strip()
            if not name:
                continue
            key = name.casefold()
            if key == identity:
                continue
            if key in staged:
                if key not in visited:
                    queue.append(staged[key])
                continue
            if is_debug_dll(name):
                raise RuntimeError(
                    f"Release binary {binary.name} imports the debug DLL {name}; debug runtimes are never packaged."
                )
            if is_windows_system_dll(name, system_dlls):
                system_imports.add(name)
                continue
            if is_vc_runtime_dll(name):
                vc_runtime_imports.add(name)
                continue
            if is_boost_dll(name):
                raise RuntimeError(
                    f"{binary.name} imports the Boost DLL {name}; Boost must be linked statically because no "
                    "Boost DLL may appear in the release root."
                )
            raise RuntimeError(
                f"{binary.name} imports the additional private DLL {name}. The release root may contain exactly "
                f"four DLLs ({', '.join(REQUIRED_RUNTIME_DLLS)}); adding {name} would require a fifth root DLL, "
                "so the package is refused."
            )

    staged_names = validate_staged_directory(output_dir)
    report = {
        "schema_version": 1,
        "mysql_client_version": mysql_version,
        "selection": "four root application DLLs; Windows and VC++ runtime imports are external prerequisites",
        "server_binaries": list(SERVER_BINARIES),
        "root_dlls": staged_names,
        "dll_sources": {name: str(path) for name, path in sorted(sources.items())},
        "externally_loaded_dlls": ["legacy.dll"],
        "external_vc_runtime_imports": sorted(vc_runtime_imports, key=str.casefold),
        "system_imports_not_packaged": sorted(system_imports, key=str.casefold),
    }
    return report


def write_inventory(report: dict, inventory_path: Path) -> Path:
    """Write the staging inventory outside the staging tree so it never ships."""
    inventory_path = inventory_path.resolve()
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    return inventory_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary-dir", type=Path, required=True, help="installed directory containing both server executables")
    parser.add_argument("--mysql-root", type=Path, required=True, help="gated MySQL 8.4.7 portable root")
    parser.add_argument("--openssl-bin-dir", type=Path, required=True, help="selected OpenSSL bin directory")
    parser.add_argument("--output-dir", type=Path, required=True, help="initially empty DLL staging directory")
    parser.add_argument("--inventory", type=Path, help="inventory JSON path (default: <output-dir>.json, outside the staging tree)")
    parser.add_argument(
        "--openssl-module-dir",
        type=Path,
        action="append",
        default=[],
        help=(
            "additional OpenSSL provider-module directory to search for legacy.dll "
            "(the default search covers lib/ossl-modules, ossl-modules, bin/ossl-modules, "
            "and bin itself for installers that flatten the modules); may be repeated"
        ),
    )
    parser.add_argument("--mysql-version", default=REQUIRED_MYSQL_VERSION, help="MySQL client version recorded in the inventory")
    parser.add_argument("--system-dir", type=Path, help="Windows system directory (default: %%WINDIR%%/System32)")
    parser.add_argument("--dumpbin", default="dumpbin", help="Visual Studio dumpbin executable")
    args = parser.parse_args()

    system_dir = args.system_dir or Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32"
    inventory_path = args.inventory or args.output_dir.with_suffix(".json")
    report = stage_runtime_dlls(
        binary_dir=args.binary_dir,
        mysql_root=args.mysql_root,
        openssl_bin_dir=args.openssl_bin_dir,
        output_dir=args.output_dir,
        system_dir=system_dir,
        mysql_version=args.mysql_version,
        openssl_module_dirs=args.openssl_module_dir,
        dependency_reader=lambda path: dumpbin_dependencies(path, args.dumpbin),
    )
    written = write_inventory(report, inventory_path)
    print(
        f"Staged exactly {len(report['root_dlls'])} runtime DLLs ({', '.join(report['root_dlls'])}) for "
        f"{len(report['server_binaries'])} server executables from MySQL {report['mysql_client_version']} "
        f"and OpenSSL; the VC++ runtime and Windows DLLs remain external prerequisites."
    )
    print(f"Runtime DLL inventory: {written}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
