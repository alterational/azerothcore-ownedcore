from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from stage_windows_runtime_dlls import (  # noqa: E402
    REQUIRED_MYSQL_VERSION,
    REQUIRED_RUNTIME_DLLS,
    SERVER_BINARIES,
    is_boost_dll,
    is_debug_dll,
    is_vc_runtime_dll,
    parse_dumpbin_dependents,
    provider_module_directories,
    stage_runtime_dlls,
    validate_staged_directory,
    write_inventory,
)

DEFAULT_DEPENDENCIES = {
    "authserver.exe": [
        "libmysql.dll",
        "KERNEL32.dll",
        "VCRUNTIME140.dll",
        "VCRUNTIME140_1.dll",
        "MSVCP140.dll",
        "api-ms-win-crt-runtime-l1-1-0.dll",
    ],
    "worldserver.exe": [
        "libmysql.dll",
        "libssl-3-x64.dll",
        "libcrypto-3-x64.dll",
        "WS2_32.dll",
        "KERNEL32.dll",
    ],
    "libmysql.dll": ["libssl-3-x64.dll", "libcrypto-3-x64.dll", "KERNEL32.dll", "SECUR32.dll"],
    "libcrypto-3-x64.dll": ["WS2_32.dll", "CRYPT32.dll", "KERNEL32.dll"],
    "libssl-3-x64.dll": ["libcrypto-3-x64.dll", "KERNEL32.dll"],
    "legacy.dll": ["libcrypto-3-x64.dll"],
}

SYSTEM_DLL_FIXTURES = (
    "kernel32.dll",
    "ws2_32.dll",
    "crypt32.dll",
    "secur32.dll",
    "user32.dll",
)


class StagingFixture:
    """Build a fake Windows install tree and dependency map on any platform."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.binary_dir = root / "dist"
        self.mysql_root = root / "mysql"
        self.mysql_lib_dir = self.mysql_root / "lib"
        self.mysql_bin_dir = self.mysql_root / "bin"
        self.openssl_bin_dir = root / "openssl" / "bin"
        self.openssl_module_dir = root / "openssl" / "lib" / "ossl-modules"
        self.fallback_module_dir = root / "openssl" / "ossl-modules"
        self.system_dir = root / "system32"
        self.output_dir = root / "staging"
        self.inventory = root / "staging.json"
        for directory in (
            self.binary_dir,
            self.mysql_lib_dir,
            self.mysql_bin_dir,
            self.openssl_bin_dir,
            self.openssl_module_dir,
            self.system_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        for name in SERVER_BINARIES:
            (self.binary_dir / name).write_bytes(f"{name} binary".encode())
        # The portable MySQL tree ships a second, different libmysql.dll in bin/.
        (self.mysql_lib_dir / "libmysql.dll").write_bytes(b"libmysql-from-lib")
        (self.mysql_bin_dir / "libmysql.dll").write_bytes(b"libmysql-from-bin")
        (self.openssl_bin_dir / "libcrypto-3-x64.dll").write_bytes(b"libcrypto-3-x64")
        (self.openssl_bin_dir / "libssl-3-x64.dll").write_bytes(b"libssl-3-x64")
        (self.openssl_module_dir / "legacy.dll").write_bytes(b"legacy-provider")
        for name in SYSTEM_DLL_FIXTURES:
            (self.system_dir / name).write_bytes(b"system dll")
        self.dependencies = {key: list(value) for key, value in DEFAULT_DEPENDENCIES.items()}

    def reader(self, path: Path) -> list[str]:
        return list(self.dependencies.get(path.name.casefold(), []))

    def stage(self, **overrides) -> dict:
        arguments = {
            "binary_dir": self.binary_dir,
            "mysql_root": self.mysql_root,
            "openssl_bin_dir": self.openssl_bin_dir,
            "output_dir": self.output_dir,
            "system_dir": self.system_dir,
            "dependency_reader": self.reader,
        }
        arguments.update(overrides)
        return stage_runtime_dlls(**arguments)

    def staged_names(self) -> list[str]:
        return sorted(path.name for path in self.output_dir.iterdir())


class StagingSuccessTests(unittest.TestCase):
    def test_exact_four_dlls_are_staged_without_boost_vc_or_system_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = StagingFixture(Path(temporary))
            report = fixture.stage()

            self.assertEqual(fixture.staged_names(), sorted(REQUIRED_RUNTIME_DLLS))
            self.assertEqual(report["root_dlls"], sorted(REQUIRED_RUNTIME_DLLS))
            self.assertEqual(report["mysql_client_version"], REQUIRED_MYSQL_VERSION)
            self.assertIn("VCRUNTIME140.dll", report["external_vc_runtime_imports"])
            self.assertIn("MSVCP140.dll", report["external_vc_runtime_imports"])
            self.assertIn("KERNEL32.dll", report["system_imports_not_packaged"])
            self.assertFalse(any(is_boost_dll(name) for name in fixture.staged_names()))
            self.assertFalse(any(is_vc_runtime_dll(name) for name in fixture.staged_names()))

    def test_libmysql_dll_is_taken_from_mysql_lib_not_mysql_bin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = StagingFixture(Path(temporary))
            report = fixture.stage()

            self.assertEqual((fixture.output_dir / "libmysql.dll").read_bytes(), b"libmysql-from-lib")
            self.assertEqual(
                Path(report["dll_sources"]["libmysql.dll"]),
                (fixture.mysql_lib_dir / "libmysql.dll").resolve(),
            )
            self.assertNotIn("libmysql-from-bin", (fixture.output_dir / "libmysql.dll").read_text())

    def test_legacy_provider_is_found_in_the_fallback_module_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = StagingFixture(Path(temporary))
            (fixture.openssl_module_dir / "legacy.dll").unlink()
            fixture.fallback_module_dir.mkdir(parents=True)
            (fixture.fallback_module_dir / "legacy.dll").write_bytes(b"legacy-from-fallback")

            report = fixture.stage()

            self.assertEqual((fixture.output_dir / "legacy.dll").read_bytes(), b"legacy-from-fallback")
            self.assertIn("legacy.dll", report["root_dlls"])

    def test_explicit_module_directory_takes_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = StagingFixture(Path(temporary))
            (fixture.openssl_module_dir / "legacy.dll").unlink()
            explicit = Path(temporary) / "explicit-ossl-modules"
            explicit.mkdir()
            (explicit / "legacy.dll").write_bytes(b"legacy-explicit")

            fixture.stage(openssl_module_dirs=[explicit])

            self.assertEqual((fixture.output_dir / "legacy.dll").read_bytes(), b"legacy-explicit")

    def test_legacy_provider_is_found_when_flattened_into_the_openssl_bin_directory(self) -> None:
        # The SLProWeb installer runs with its copytobin task, which leaves the
        # provider modules directly in bin/ with no ossl-modules directory.
        with tempfile.TemporaryDirectory() as temporary:
            fixture = StagingFixture(Path(temporary))
            (fixture.openssl_module_dir / "legacy.dll").unlink()
            (fixture.openssl_bin_dir / "legacy.dll").write_bytes(b"legacy-flattened-into-bin")

            report = fixture.stage()

            self.assertEqual(
                (fixture.output_dir / "legacy.dll").read_bytes(), b"legacy-flattened-into-bin"
            )
            self.assertEqual(
                Path(report["dll_sources"]["legacy.dll"]),
                (fixture.openssl_bin_dir / "legacy.dll").resolve(),
            )
            self.assertEqual(fixture.staged_names(), sorted(REQUIRED_RUNTIME_DLLS))

    def test_dedicated_module_directory_wins_over_the_flattened_bin_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = StagingFixture(Path(temporary))
            (fixture.openssl_bin_dir / "legacy.dll").write_bytes(b"legacy-flattened-into-bin")

            fixture.stage()

            self.assertEqual((fixture.output_dir / "legacy.dll").read_bytes(), b"legacy-provider")

    def test_provider_directories_keep_the_documented_search_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bin_dir = root / "openssl" / "bin"
            explicit = root / "explicit"
            directories = provider_module_directories(bin_dir, [explicit])

            self.assertEqual(
                [directory.resolve() for directory in directories],
                [
                    explicit.resolve(),
                    (root / "openssl" / "lib" / "ossl-modules").resolve(),
                    (root / "openssl" / "ossl-modules").resolve(),
                    (bin_dir / "ossl-modules").resolve(),
                    bin_dir.resolve(),
                ],
            )

    def test_inventory_is_written_outside_the_staging_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = StagingFixture(Path(temporary))
            report = fixture.stage()
            written = write_inventory(report, fixture.inventory)

            self.assertEqual(written, fixture.inventory.resolve())
            self.assertEqual(fixture.staged_names(), sorted(REQUIRED_RUNTIME_DLLS))
            inventory = json.loads(fixture.inventory.read_text(encoding="utf-8"))
            self.assertEqual(inventory["mysql_client_version"], "8.4.7")
            self.assertEqual(inventory["schema_version"], 1)


class StagingRejectionTests(unittest.TestCase):
    def assert_stage_fails(self, fixture: StagingFixture, expected: str, **overrides) -> None:
        with self.assertRaises(RuntimeError) as raised:
            fixture.stage(**overrides)
        self.assertIn(expected, str(raised.exception))

    def test_additional_private_dependency_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = StagingFixture(Path(temporary))
            fixture.dependencies["worldserver.exe"].append("acme_core.dll")
            with self.assertRaises(RuntimeError) as raised:
                fixture.stage()
            message = str(raised.exception)
            self.assertIn("acme_core.dll", message)
            self.assertIn("exactly four DLLs", message)
            self.assertFalse(fixture.output_dir.joinpath("acme_core.dll").exists())

    def test_debug_dependency_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = StagingFixture(Path(temporary))
            fixture.dependencies["libmysql.dll"].append("MSVCP140D.dll")
            self.assert_stage_fails(fixture, "debug DLL")

    def test_boost_dependency_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = StagingFixture(Path(temporary))
            fixture.dependencies["libmysql.dll"].append("boost_filesystem-vc143-mt-x64-1_92.dll")
            self.assert_stage_fails(fixture, "Boost DLL")

    def test_missing_openssl_client_dll_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = StagingFixture(Path(temporary))
            (fixture.openssl_bin_dir / "libssl-3-x64.dll").unlink()
            self.assert_stage_fails(fixture, "libssl-3-x64.dll")

    def test_missing_legacy_provider_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = StagingFixture(Path(temporary))
            (fixture.openssl_module_dir / "legacy.dll").unlink()
            self.assert_stage_fails(fixture, "legacy.dll")

    def test_missing_mysql_client_dll_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = StagingFixture(Path(temporary))
            (fixture.mysql_lib_dir / "libmysql.dll").unlink()
            self.assert_stage_fails(fixture, "libmysql.dll")

    def test_missing_server_executable_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = StagingFixture(Path(temporary))
            (fixture.binary_dir / "worldserver.exe").unlink()
            self.assert_stage_fails(fixture, "worldserver.exe")

    def test_wrong_mysql_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = StagingFixture(Path(temporary))
            self.assert_stage_fails(fixture, "MySQL 8.4.9", mysql_version="8.4.9")

    def test_nonempty_staging_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = StagingFixture(Path(temporary))
            fixture.output_dir.mkdir()
            (fixture.output_dir / "stale.dll").write_bytes(b"stale")
            self.assert_stage_fails(fixture, "Refusing to overwrite")


class StagedDirectoryValidationTests(unittest.TestCase):
    def make_directory(self, names) -> tempfile.TemporaryDirectory:
        handle = tempfile.TemporaryDirectory()
        self.addCleanup(handle.cleanup)
        directory = Path(handle.name)
        for name in names:
            (directory / name).write_bytes(b"dll")
        return handle

    def test_exact_four_names_are_accepted_case_insensitively(self) -> None:
        handle = self.make_directory([name.upper() for name in REQUIRED_RUNTIME_DLLS])
        self.assertEqual(len(validate_staged_directory(Path(handle.name))), 4)

    def test_vc_runtime_dll_in_staging_is_rejected(self) -> None:
        handle = self.make_directory([*REQUIRED_RUNTIME_DLLS, "msvcp140.dll"])
        with self.assertRaises(RuntimeError) as raised:
            validate_staged_directory(Path(handle.name))
        self.assertIn("Visual C++ runtime", str(raised.exception))

    def test_extra_dll_in_staging_is_rejected(self) -> None:
        handle = self.make_directory([*REQUIRED_RUNTIME_DLLS, "zlib1.dll"])
        with self.assertRaises(RuntimeError) as raised:
            validate_staged_directory(Path(handle.name))
        self.assertIn("exactly four", str(raised.exception))

    def test_boost_dll_in_staging_is_rejected(self) -> None:
        handle = self.make_directory([*REQUIRED_RUNTIME_DLLS, "boost_json-vc143-mt-x64-1_92.dll"])
        with self.assertRaises(RuntimeError) as raised:
            validate_staged_directory(Path(handle.name))
        self.assertIn("Boost", str(raised.exception))

    def test_debug_dll_in_staging_is_rejected(self) -> None:
        handle = self.make_directory([*REQUIRED_RUNTIME_DLLS, "libmysql-debug.dll"])
        with self.assertRaises(RuntimeError) as raised:
            validate_staged_directory(Path(handle.name))
        self.assertIn("Debug DLLs", str(raised.exception))

    def test_missing_dll_in_staging_is_rejected(self) -> None:
        handle = self.make_directory(REQUIRED_RUNTIME_DLLS[:-1])
        with self.assertRaises(RuntimeError) as raised:
            validate_staged_directory(Path(handle.name))
        self.assertIn("legacy.dll", str(raised.exception))

    def test_non_dll_file_in_staging_is_rejected(self) -> None:
        handle = self.make_directory([*REQUIRED_RUNTIME_DLLS, "RUNTIME-DLLS.json"])
        with self.assertRaises(RuntimeError) as raised:
            validate_staged_directory(Path(handle.name))
        self.assertIn("non-DLL", str(raised.exception))


class CommandLineTests(unittest.TestCase):
    def test_help_renders_without_formatting_errors(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "stage_windows_runtime_dlls.py"), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--mysql-root", completed.stdout)
        self.assertIn("--openssl-bin-dir", completed.stdout)


class NameClassificationTests(unittest.TestCase):
    def test_dumpbin_output_is_parsed(self) -> None:
        output = (
            "Microsoft (R) COFF/PE Dumper Version 14.42.34436.0\n"
            "Copyright (C) Microsoft Corporation.  All rights reserved.\n\n\n"
            "Dump of file worldserver.exe\n\n"
            "File Type: EXECUTABLE IMAGE\n\n"
            "  Image has the following dependencies:\n\n"
            "    KERNEL32.dll\n"
            "    libmysql.dll\n"
            "    MSVCP140.dll\n"
            "    api-ms-win-crt-runtime-l1-1-0.dll\n\n"
            "  Summary\n\n"
            "        1000 .data\n"
        )
        self.assertEqual(
            parse_dumpbin_dependents(output),
            ["KERNEL32.dll", "libmysql.dll", "MSVCP140.dll", "api-ms-win-crt-runtime-l1-1-0.dll"],
        )

    def test_classification_helpers(self) -> None:
        self.assertTrue(is_debug_dll("msvcp140d.dll"))
        self.assertTrue(is_debug_dll("libcrypto-3-x64-gd.dll"))
        self.assertFalse(is_debug_dll("libcrypto-3-x64.dll"))
        self.assertTrue(is_vc_runtime_dll("vcruntime140_1.dll"))
        self.assertTrue(is_vc_runtime_dll("MSVCP140.dll"))
        # Debug variants also belong to the VC++ runtime family, but the debug
        # classification is evaluated first so they are rejected as debug DLLs.
        self.assertTrue(is_debug_dll("msvcp140d.dll"))
        self.assertTrue(is_boost_dll("boost_system-vc143-mt-x64-1_92.dll"))
        self.assertFalse(is_boost_dll("libmysql.dll"))


if __name__ == "__main__":
    unittest.main()
