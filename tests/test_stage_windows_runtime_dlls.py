from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from stage_windows_runtime_dlls import parse_dumpbin_dependents, stage_runtime_dependencies  # noqa: E402


class WindowsRuntimeDllStagingTests(unittest.TestCase):
    def test_dumpbin_dependency_parser_keeps_unique_dll_imports(self) -> None:
        output = """
Microsoft (R) COFF/PE Dumper Version

Image has the following dependencies:

    KERNEL32.dll
    libmysql.dll
    LIBMYSQL.DLL
    MSVCP140.dll

Summary
"""
        self.assertEqual(
            parse_dumpbin_dependents(output),
            ["KERNEL32.dll", "libmysql.dll", "MSVCP140.dll"],
        )

    def test_stages_recursive_mysql_openssl_and_vc_runtime_import_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary_dir = root / "installed"
            mysql_lib = root / "mysql" / "lib"
            mysql_bin = root / "mysql" / "bin"
            openssl_bin = root / "openssl" / "bin"
            openssl_modules = root / "openssl" / "lib" / "ossl-modules"
            vc_redist = root / "vc" / "x64" / "Microsoft.VC143.CRT"
            system_dir = root / "windows" / "System32"
            output_dir = root / "staged"
            for directory in (binary_dir, mysql_lib, mysql_bin, openssl_bin, openssl_modules, vc_redist, system_dir):
                directory.mkdir(parents=True)
            for binary in ("authserver.exe", "worldserver.exe"):
                (binary_dir / binary).write_bytes(binary.encode())
            # Ensure libmysql.dll comes from lib/, even if a same-named file exists in bin/.
            (mysql_lib / "libmysql.dll").write_bytes(b"mysql client from lib")
            (mysql_bin / "libmysql.dll").write_bytes(b"incorrect duplicate from bin")
            (mysql_bin / "libprotobuf.dll").write_bytes(b"protobuf")
            (mysql_bin / "libabsl.dll").write_bytes(b"abseil")
            (mysql_bin / "libprotobuf-debug.dll").write_bytes(b"debug protobuf")
            (mysql_bin / "boost_atomic-vc143-mt-x64-1_87.dll").write_bytes(b"boost release")
            (mysql_bin / "boost_atomic-vc143-mt-gd-x64-1_87.dll").write_bytes(b"boost debug")
            (openssl_bin / "libssl-3-x64.dll").write_bytes(b"openssl ssl")
            (openssl_bin / "libcrypto-3-x64.dll").write_bytes(b"openssl crypto")
            (openssl_modules / "legacy.dll").write_bytes(b"openssl legacy provider")
            for name in ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
                (vc_redist / name).write_bytes(name.encode())
            (vc_redist / "MSVCP140D.dll").write_bytes(b"debug CRT")
            (vc_redist / "Microsoft.VC143.CRT.manifest").write_text("<assembly />\n", encoding="utf-8")
            (system_dir / "KERNEL32.dll").write_bytes(b"Windows system library")

            imports = {
                "authserver.exe": ["KERNEL32.dll", "libmysql.dll", "libcrypto-3-x64.dll", "MSVCP140.dll"],
                "worldserver.exe": ["KERNEL32.dll", "libssl-3-x64.dll", "VCRUNTIME140_1.dll"],
                "libmysql.dll": ["libssl-3-x64.dll", "libcrypto-3-x64.dll", "libprotobuf.dll"],
                "libprotobuf.dll": ["libabsl.dll", "KERNEL32.dll"],
                "libabsl.dll": ["KERNEL32.dll"],
                "libssl-3-x64.dll": ["libcrypto-3-x64.dll"],
                "libcrypto-3-x64.dll": ["KERNEL32.dll"],
                "legacy.dll": ["libcrypto-3-x64.dll"],
                "msvcp140.dll": ["vcruntime140.dll", "KERNEL32.dll"],
                "vcruntime140.dll": ["KERNEL32.dll"],
                "vcruntime140_1.dll": ["vcruntime140.dll", "KERNEL32.dll"],
            }

            report = stage_runtime_dependencies(
                binary_dir=binary_dir,
                mysql_lib_dir=mysql_lib,
                mysql_bin_dir=mysql_bin,
                openssl_bin_dir=openssl_bin,
                openssl_module_dir=openssl_modules,
                vc_redist_dir=vc_redist,
                output_dir=output_dir,
                system_dir=system_dir,
                mysql_version="8.4.10",
                dependency_reader=lambda path: imports.get(path.name.casefold(), []),
            )

            staged_names = {path.name.casefold() for path in output_dir.glob("*.dll")}
            self.assertEqual((output_dir / "libmysql.dll").read_bytes(), b"mysql client from lib")
            for expected in (
                "libmysql.dll",
                "libssl-3-x64.dll",
                "libcrypto-3-x64.dll",
                "legacy.dll",
                "libprotobuf.dll",
                "libabsl.dll",
                "msvcp140.dll",
                "vcruntime140.dll",
                "vcruntime140_1.dll",
            ):
                self.assertIn(expected, staged_names)
            self.assertFalse(any("boost" in name for name in staged_names))
            self.assertFalse(any("debug" in name or name.endswith("140d.dll") for name in staged_names))
            self.assertTrue((output_dir / "Microsoft.VC143.CRT.manifest").is_file())
            self.assertTrue((output_dir / "RUNTIME-DLLS.json").is_file())
            self.assertEqual(report["mysql_client_version"], "8.4.10")
            self.assertIn("legacy.dll", report["dynamic_dependencies"])
            self.assertEqual(report["vc_runtime_manifests"], ["Microsoft.VC143.CRT.manifest"])
            self.assertEqual(json.loads((output_dir / "RUNTIME-DLLS.json").read_text())["runtime_dlls"], report["runtime_dlls"])
            self.assertIn("KERNEL32.dll", report["system_imports_not_packaged"])

    def test_fails_closed_for_unresolved_non_system_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary_dir = root / "installed"
            mysql_lib = root / "mysql" / "lib"
            mysql_bin = root / "mysql" / "bin"
            openssl_bin = root / "openssl" / "bin"
            vc_redist = root / "vc"
            system_dir = root / "System32"
            output_dir = root / "staged"
            for directory in (binary_dir, mysql_lib, mysql_bin, openssl_bin, vc_redist, system_dir):
                directory.mkdir(parents=True)
            for name in ("authserver.exe", "worldserver.exe"):
                (binary_dir / name).write_bytes(b"exe")
            for name in ("libmysql.dll",):
                (mysql_lib / name).write_bytes(b"mysql")
            for name in ("libssl-3-x64.dll", "libcrypto-3-x64.dll"):
                (openssl_bin / name).write_bytes(b"openssl")
            (openssl_bin / "legacy.dll").write_bytes(b"legacy")
            for name in ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
                (vc_redist / name).write_bytes(b"runtime")
            (vc_redist / "Microsoft.VC143.CRT.manifest").write_text("<assembly />", encoding="utf-8")

            def dependencies(path: Path) -> list[str]:
                if path.name == "authserver.exe":
                    return ["missing-private-runtime.dll"]
                return []

            with self.assertRaisesRegex(RuntimeError, "Unresolved non-system DLL dependency missing-private-runtime.dll"):
                stage_runtime_dependencies(
                    binary_dir=binary_dir,
                    mysql_lib_dir=mysql_lib,
                    mysql_bin_dir=mysql_bin,
                    openssl_bin_dir=openssl_bin,
                    openssl_module_dir=None,
                    vc_redist_dir=vc_redist,
                    output_dir=output_dir,
                    system_dir=system_dir,
                    mysql_version="8.4.10",
                    dependency_reader=dependencies,
                )


if __name__ == "__main__":
    unittest.main()
