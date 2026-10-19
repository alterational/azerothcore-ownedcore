from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from package_config_edits import load_config_edits  # noqa: E402
from package_runtime import copy_config_template, validate_runtime_dll_directory  # noqa: E402

RUNTIME_DLLS = [
    "libmysql.dll",
    "libcrypto-3-x64.dll",
    "libssl-3-x64.dll",
    "legacy.dll",
]


def make_runtime_dll_fixture(directory: Path, extra_dlls: tuple[str, ...] = ()) -> None:
    directory.mkdir(parents=True)
    names = RUNTIME_DLLS + list(extra_dlls)
    for name in names:
        (directory / name).write_bytes(("fixture: " + name).encode())
    (directory / "RUNTIME-DLLS.json").write_text(
        json.dumps({
            "schema_version": 1,
            "mysql_client_version": "8.0.46",
            "runtime_dlls": names,
            "external_vc_runtime_imports": ["MSVCP140.dll", "VCRUNTIME140.dll"],
        }, indent=2) + "\n",
        encoding="utf-8",
    )


class PackageConfigTemplateTests(unittest.TestCase):
    def test_playerbots_package_targets_match_requested_values(self) -> None:
        values = {
            edit.key: edit.value
            for edit in load_config_edits()
            if edit.relative_file == "modules/playerbots.conf"
        }
        self.assertEqual(
            values,
            {
                "Playerbots.RandomClassSpecProb.4.0": "45",
                "Playerbots.RandomClassSpecProb.4.1": "45",
                "Playerbots.RandomClassSpecProb.4.2": "10",
                "Playerbots.PvpProhibitedAreaIds": '"976,35,392,2268,4161,4010,4317,4312,3649,3887,3958,3724,4080,3938,3754,3786,3973,4085,4086,4087,4088"',
            },
        )

    def test_public_template_is_copied_byte_for_byte_without_redaction(self) -> None:
        content = (
            b"# Public pinned source template\r\n"
            b"WorldDatabaseInfo = \"acore;localhost;example;example;3306;\"\r\n"
            b"PublicApiKey = \"documented-example-value\"\r\n"
            b"Password = \"sample-default\"\r\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.conf.dist"
            destination = Path(temporary) / "package" / "etc" / "modules" / "sample.conf.dist"
            source.write_bytes(content)

            copy_config_template(source, destination)

            self.assertEqual(destination.read_bytes(), content)

    def test_package_rejects_debug_or_boost_dlls_in_dependency_stage(self) -> None:
        for forbidden in ("boost_atomic-vc143-mt-x64-1_87.dll", "libprotobuf-debug.dll", "MSVCP140D.dll"):
            with self.subTest(forbidden=forbidden), tempfile.TemporaryDirectory() as temporary:
                dll_dir = Path(temporary) / "runtime-dlls"
                make_runtime_dll_fixture(dll_dir, (forbidden,))
                with self.assertRaisesRegex(RuntimeError, "Boost DLLs|Debug DLLs"):
                    validate_runtime_dll_directory(dll_dir)

    def test_package_rejects_extra_release_vc_runtime_dlls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            dll_dir = Path(temporary) / "runtime-dlls"
            make_runtime_dll_fixture(dll_dir, ("vcruntime140.dll",))
            with self.assertRaisesRegex(RuntimeError, "exactly the four application DLLs"):
                validate_runtime_dll_directory(dll_dir)

    def test_package_clones_templates_edits_only_active_copies_and_places_runtime_at_root(self) -> None:
        module_template = (
            b"WorldDatabaseInfo = \"acore;localhost;example;example;3306;\"\n"
            b"PublicApiKey = \"documented-example-value\"\n"
            b"Demo.Enable = 1\n"
            b"Demo.Flag = true\n"
        )
        auth_template = b"AuthServerPort = 3724\n"
        world_template = b"MapUpdate.Threads = 4\r\n"
        nested_template = b"SharedOption = 7\n"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dist = root / "dist"
            binary_dir = dist
            config_dir = dist / "configs"
            dll_dir = root / "runtime-dlls"
            mysql_dir = root / "mysql-portable"
            output = root / "package"
            dist.mkdir(parents=True)
            (config_dir / "modules").mkdir(parents=True)
            (config_dir / "shared").mkdir(parents=True)
            for binary in ("authserver.exe", "worldserver.exe"):
                (binary_dir / binary).write_bytes(b"test binary")
            # An unrelated DLL in the install directory must not be swept into the package.
            (binary_dir / "stale-unrelated.dll").write_bytes(b"not a runtime dependency")
            make_runtime_dll_fixture(dll_dir)
            (mysql_dir / "bin").mkdir(parents=True)
            (mysql_dir / "lib").mkdir(parents=True)
            (mysql_dir / "share" / "charsets").mkdir(parents=True)
            (mysql_dir / "bin" / "mysqld.exe").write_bytes(b"portable MySQL server")
            (mysql_dir / "bin" / "mysql.exe").write_bytes(b"portable MySQL client")
            (mysql_dir / "lib" / "libmysql.dll").write_bytes(b"portable MySQL client library")
            (mysql_dir / "share" / "charsets" / "Index.xml").write_text("<charsets />", encoding="utf-8")
            (mysql_dir / "bin" / "boost_atomic-vc143-mt-x64.dll").write_bytes(b"must be filtered")
            (mysql_dir / "bin" / "libprotobuf-debug.dll").write_bytes(b"must be filtered")
            (mysql_dir / "bin" / "vcruntime140.dll").write_bytes(b"VC runtime is external")
            (mysql_dir / "bin" / "vcredist_x64.exe").write_bytes(b"installer is not requested")
            (mysql_dir / ".arena-mysql-version").write_text("8.0.46", encoding="utf-8")
            (mysql_dir / "README.txt").write_text("No release README", encoding="utf-8")
            (config_dir / "authserver.conf.dist").write_bytes(auth_template)
            (config_dir / "worldserver.conf.dist").write_bytes(world_template)
            (config_dir / "shared" / "extra.conf.dist").write_bytes(nested_template)
            (config_dir / "modules" / "sample.conf.dist").write_bytes(module_template)
            # Simulate a machine-specific active install config: the package must not use it.
            (config_dir / "modules" / "sample.conf").write_bytes(b"Demo.Enable = 99\nPRIVATE_MACHINE_VALUE = no\n")

            edits_path = root / "config-edits.json"
            edits_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "configs": {
                            "authserver.conf": [{"key": "AuthServerPort", "value": "3730"}],
                            "worldserver.conf": [],
                            "modules/sample.conf": [
                                {"key": "Demo.Flag", "value": "1"},
                                {"key": "Demo.Enable", "value": "0"},
                                {"key": "Missing.Key", "value": "1"},
                            ],
                            "modules/not-installed.conf": [{"key": "Gone", "value": "false"}],
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "package_runtime.py"),
                    "--dist-dir", str(dist),
                    "--binary-dir", str(binary_dir),
                    "--dll-dir", str(dll_dir),
                    "--mysql-dir", str(mysql_dir),
                    "--config-dir", str(config_dir),
                    "--config-edits", str(edits_path),
                    "--output", str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            archive = output / "azerothcore-ownedcore-windows.zip"
            with zipfile.ZipFile(archive) as package:
                auth_dist = package.read("azerothcore-ownedcore-windows/etc/authserver.conf.dist")
                auth_active = package.read("azerothcore-ownedcore-windows/etc/authserver.conf")
                world_dist = package.read("azerothcore-ownedcore-windows/etc/worldserver.conf.dist")
                world_active = package.read("azerothcore-ownedcore-windows/etc/worldserver.conf")
                nested_dist = package.read("azerothcore-ownedcore-windows/etc/shared/extra.conf.dist")
                nested_active = package.read("azerothcore-ownedcore-windows/etc/shared/extra.conf")
                packaged_template = package.read(
                    "azerothcore-ownedcore-windows/etc/modules/sample.conf.dist"
                )
                packaged_active = package.read(
                    "azerothcore-ownedcore-windows/etc/modules/sample.conf"
                )
                names = set(package.namelist())

            self.assertEqual(auth_dist, auth_template)
            self.assertEqual(auth_active, b"AuthServerPort = 3730\n")
            self.assertEqual(world_dist, world_template)
            self.assertEqual(world_active, world_template)  # No edit: exact byte-identical copy.
            self.assertEqual(nested_dist, nested_template)
            self.assertEqual(nested_active, nested_template)  # Nested templates are also duplicated.
            self.assertEqual(packaged_template, module_template)
            self.assertEqual(
                packaged_active,
                module_template.replace(b"Demo.Enable = 1", b"Demo.Enable = 0"),
            )  # The boolean-to-number edit is warned about and left unchanged.
            self.assertNotIn(b"PRIVATE_MACHINE_VALUE", packaged_active)
            self.assertNotIn("azerothcore-ownedcore-windows/etc/modules/not-installed.conf", names)
            self.assertIn("azerothcore-ownedcore-windows/authserver.exe", names)
            self.assertIn("azerothcore-ownedcore-windows/worldserver.exe", names)
            for name in RUNTIME_DLLS:
                self.assertIn(f"azerothcore-ownedcore-windows/{name}", names)
            root_dlls = {
                name.rsplit("/", 1)[-1]
                for name in names
                if name.startswith("azerothcore-ownedcore-windows/")
                and name.count("/") == 1
                and name.casefold().endswith(".dll")
            }
            self.assertEqual(root_dlls, set(RUNTIME_DLLS))
            root_files = {
                Path(name).name
                for name in names
                if name.startswith("azerothcore-ownedcore-windows/") and name.count("/") == 1
            }
            self.assertEqual(root_files, {"authserver.exe", "worldserver.exe", *RUNTIME_DLLS})
            self.assertIn("azerothcore-ownedcore-windows/mysql/bin/mysqld.exe", names)
            self.assertIn("azerothcore-ownedcore-windows/mysql/bin/mysql.exe", names)
            self.assertIn("azerothcore-ownedcore-windows/mysql/lib/libmysql.dll", names)
            self.assertIn("azerothcore-ownedcore-windows/mysql/share/charsets/Index.xml", names)
            self.assertNotIn("azerothcore-ownedcore-windows/mysql/bin/boost_atomic-vc143-mt-x64.dll", names)
            self.assertNotIn("azerothcore-ownedcore-windows/mysql/bin/libprotobuf-debug.dll", names)
            self.assertNotIn("azerothcore-ownedcore-windows/mysql/bin/vcruntime140.dll", names)
            self.assertNotIn("azerothcore-ownedcore-windows/mysql/bin/vcredist_x64.exe", names)
            self.assertNotIn("azerothcore-ownedcore-windows/mysql/.arena-mysql-version", names)
            self.assertFalse(any(Path(name).name.casefold().startswith("readme") for name in names))
            self.assertNotIn("azerothcore-ownedcore-windows/SOURCE-PINS.json", names)
            self.assertNotIn("azerothcore-ownedcore-windows/RUNTIME-DLLS.json", names)
            self.assertFalse(any(name.startswith("azerothcore-ownedcore-windows/bin/") for name in names))
            self.assertNotIn("azerothcore-ownedcore-windows/stale-unrelated.dll", names)
            self.assertIn("without Individual Progression", result.stdout)
            self.assertIn("MySQL 8.0.46", result.stdout)
            self.assertIn(
                "WARNING: couldn't apply config edit for: modules/sample.conf, key Demo.Flag true 1",
                result.stdout,
            )
            self.assertIn(
                "WARNING: couldn't apply config edit for: modules/sample.conf, key Missing.Key <key-missing> 1",
                result.stdout,
            )
            self.assertIn(
                "WARNING: couldn't apply config edit for: modules/not-installed.conf, key Gone <file-missing> false",
                result.stdout,
            )
            self.assertIn("3 non-fatal warning(s)", result.stdout)
            self.assertNotIn("redact", result.stdout.lower())
            self.assertIn("portable MySQL", result.stdout)
            self.assertIn("exactly 4 root DLLs", result.stdout)


if __name__ == "__main__":
    unittest.main()
