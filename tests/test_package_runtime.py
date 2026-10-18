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
    "msvcp140.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
]


def make_runtime_dll_fixture(directory: Path, extra_dlls: tuple[str, ...] = ()) -> None:
    directory.mkdir(parents=True)
    names = RUNTIME_DLLS + list(extra_dlls)
    for name in names:
        (directory / name).write_bytes(("fixture: " + name).encode())
    (directory / "Microsoft.VC143.CRT.manifest").write_text("<assembly />\n", encoding="utf-8")
    (directory / "RUNTIME-DLLS.json").write_text(
        json.dumps({"schema_version": 1, "mysql_client_version": "8.4.10", "runtime_dlls": names}, indent=2) + "\n",
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
            output = root / "package"
            dist.mkdir(parents=True)
            (config_dir / "modules").mkdir(parents=True)
            (config_dir / "shared").mkdir(parents=True)
            for binary in ("authserver.exe", "worldserver.exe"):
                (binary_dir / binary).write_bytes(b"test binary")
            # An unrelated DLL in the install directory must not be swept into the package.
            (binary_dir / "stale-unrelated.dll").write_bytes(b"not a runtime dependency")
            make_runtime_dll_fixture(dll_dir)
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
                package_readme = package.read("azerothcore-ownedcore-windows/README.txt").decode("utf-8")
                source_pins = json.loads(package.read("azerothcore-ownedcore-windows/SOURCE-PINS.json"))
                runtime_inventory = json.loads(package.read("azerothcore-ownedcore-windows/RUNTIME-DLLS.json"))
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
            self.assertIn("azerothcore-ownedcore-windows/Microsoft.VC143.CRT.manifest", names)
            self.assertNotIn("azerothcore-ownedcore-windows/stale-unrelated.dll", names)
            self.assertFalse(any("/bin/" in name for name in names))
            self.assertEqual(runtime_inventory["mysql_client_version"], "8.4.10")
            self.assertIn("there is no bin/ directory", package_readme)
            self.assertIn("unchanged", package_readme)
            self.assertIn("active copies", package_readme)
            self.assertNotIn("blank", package_readme.lower())
            self.assertIn("without Individual Progression", result.stdout)
            self.assertIn("MySQL 8.4.10", result.stdout)
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
            self.assertFalse(source_pins["build_selection"]["mod-individual-progression"])


if __name__ == "__main__":
    unittest.main()
