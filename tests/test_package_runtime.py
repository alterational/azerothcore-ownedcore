from __future__ import annotations

import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from package_config_edits import DEFAULT_CONFIG_EDITS_PATH, load_config_edits, stage_and_edit_configs  # noqa: E402
from package_runtime import (  # noqa: E402
    ROOT_RUNTIME_DLLS,
    copy_config_template,
    create_package_archive,
    validate_package_entries,
    verify_package_archive,
)

SERVER_BINARIES = ("authserver.exe", "worldserver.exe")


class PackageFixture:
    """Build a complete Windows package input tree for one packaging run."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.dist = root / "dist"
        self.dll_dir = root / "runtime-dlls"
        self.mysql_root = root / "mysql"
        self.config_dir = self.dist / "configs"
        self.output = root / "package"
        self.edits_path = root / "config-edits.json"
        self.auth_template = (
            b"# Public pinned source template\n"
            b'WorldDatabaseInfo = "acore;localhost;example;example;3306;"\n'
            b"PublicApiKey = \"documented-example-value\"\n"
            b"AuthServerPort = 3724\n"
        )
        self.world_template = b"MapUpdate.Threads = 4\r\n"
        self.module_template = (
            b'WorldDatabaseInfo = "acore;localhost;example;example;3306;"\n'
            b'PublicApiKey = "documented-example-value"\n'
            b"Demo.Enable = 1\n"
            b"Demo.Flag = true\n"
        )
        self.nested_template = b"SharedOption = 7\n"

        (self.dist / "configs" / "modules").mkdir(parents=True)
        (self.config_dir / "shared").mkdir()
        for binary in SERVER_BINARIES:
            (self.dist / binary).write_bytes(b"test binary")
        # Installed extras that must never reach the package root.
        (self.dist / "worldserver.pdb").write_bytes(b"symbols")
        (self.dist / "zlib1.dll").write_bytes(b"arbitrary dll")
        (self.dist / "map_extractor.exe").write_bytes(b"utility")

        self.dll_dir.mkdir()
        for name in ROOT_RUNTIME_DLLS:
            (self.dll_dir / name).write_bytes(f"{name} bytes".encode())

        (self.mysql_root / "bin").mkdir(parents=True)
        (self.mysql_root / "lib").mkdir()
        (self.mysql_root / "share" / "english").mkdir(parents=True)
        (self.mysql_root / ".mysql-version").write_text("8.4.11\n", encoding="utf-8")
        (self.mysql_root / "mysql-8.4.11-winx64.zip").write_bytes(b"downloaded archive")
        (self.mysql_root / "bin" / "mysqld.exe").write_bytes(b"mysqld")
        (self.mysql_root / "bin" / "mysql.exe").write_bytes(b"mysql client")
        (self.mysql_root / "lib" / "libmysql.dll").write_bytes(b"libmysql 8.4.11")
        (self.mysql_root / "share" / "english" / "errmsg.sys").write_bytes(b"messages")

        (self.config_dir / "authserver.conf.dist").write_bytes(self.auth_template)
        (self.config_dir / "worldserver.conf.dist").write_bytes(self.world_template)
        (self.config_dir / "shared" / "extra.conf.dist").write_bytes(self.nested_template)
        (self.config_dir / "modules" / "sample.conf.dist").write_bytes(self.module_template)
        # Simulate a machine-specific active install config: it must not be used.
        (self.config_dir / "modules" / "sample.conf").write_bytes(b"Demo.Enable = 99\nPRIVATE_MACHINE_VALUE = no\n")

        self.edits_path.write_text(
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

    def arguments(self) -> list[str]:
        return [
            "--dist-dir", str(self.dist),
            "--dll-dir", str(self.dll_dir),
            "--mysql-root", str(self.mysql_root),
            "--config-dir", str(self.config_dir),
            "--config-edits", str(self.edits_path),
            "--output", str(self.output),
        ]

    def run(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "package_runtime.py"), *self.arguments()],
            check=True,
            capture_output=True,
            text=True,
        )

    @property
    def staging(self) -> Path:
        return self.output / "azerothcore-ownedcore-windows"

    @property
    def archive(self) -> Path:
        return self.output / "azerothcore-ownedcore-windows.zip"


class PackageLayoutTests(unittest.TestCase):
    def test_public_template_is_copied_byte_for_byte_without_redaction(self) -> None:
        content = (
            b"# Public pinned source template\r\n"
            b'WorldDatabaseInfo = "acore;localhost;example;example;3306;"\r\n'
            b'PublicApiKey = "documented-example-value"\r\n'
            b'Password = "sample-default"\r\n'
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.conf.dist"
            destination = Path(temporary) / "package" / "configs" / "modules" / "sample.conf.dist"
            source.write_bytes(content)

            copy_config_template(source, destination)

            self.assertEqual(destination.read_bytes(), content)

    def test_package_uses_root_layout_edits_only_active_copies_and_warns_nonfatally(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PackageFixture(Path(temporary))
            result = fixture.run()

            with zipfile.ZipFile(fixture.archive) as package:
                names = package.namelist()
                auth_dist = package.read("configs/authserver.conf.dist")
                auth_active = package.read("configs/authserver.conf")
                world_dist = package.read("configs/worldserver.conf.dist")
                world_active = package.read("configs/worldserver.conf")
                nested_dist = package.read("configs/shared/extra.conf.dist")
                nested_active = package.read("configs/shared/extra.conf")
                packaged_template = package.read("configs/modules/sample.conf.dist")
                packaged_active = package.read("configs/modules/sample.conf")
                mysql_dll = package.read("mysql/lib/libmysql.dll")

            entry_names = set(names)
            # Root files and exactly four root DLLs, with no staging prefix.
            self.assertIn("authserver.exe", entry_names)
            self.assertIn("worldserver.exe", entry_names)
            for name in ROOT_RUNTIME_DLLS:
                self.assertIn(name, entry_names)
                self.assertNotIn(f"bin/{name}", entry_names)
            self.assertFalse(any(name.startswith("azerothcore-ownedcore-windows/") for name in names))
            # Configs keep their templates and gain edited active copies.
            self.assertIn("configs/authserver.conf.dist", entry_names)
            self.assertIn("configs/authserver.conf", entry_names)
            self.assertIn("configs/worldserver.conf.dist", entry_names)
            self.assertIn("configs/worldserver.conf", entry_names)
            self.assertIn("configs/modules/sample.conf.dist", entry_names)
            self.assertIn("configs/modules/sample.conf", entry_names)
            self.assertIn("configs/shared/extra.conf.dist", entry_names)
            self.assertIn("configs/shared/extra.conf", entry_names)
            # Portable MySQL tree without the provisioning marker or downloaded archive.
            self.assertIn("mysql/bin/mysqld.exe", entry_names)
            self.assertIn("mysql/bin/mysql.exe", entry_names)
            self.assertIn("mysql/lib/libmysql.dll", entry_names)
            self.assertIn("mysql/share/english/errmsg.sys", entry_names)
            self.assertNotIn("mysql/.mysql-version", entry_names)
            self.assertFalse(any(name.endswith(".zip") for name in names))
            # No legacy or developer-only layout.
            self.assertFalse(any(name.startswith(("bin/", "etc/")) for name in names))
            for forbidden in ("README.txt", "SOURCE-PINS.json", "RUNTIME-DLLS.json", "worldserver.pdb", "zlib1.dll", "map_extractor.exe"):
                self.assertNotIn(forbidden, entry_names)

            self.assertEqual(auth_dist, fixture.auth_template)
            self.assertEqual(auth_active, fixture.auth_template.replace(b"AuthServerPort = 3724", b"AuthServerPort = 3730"))
            self.assertEqual(world_dist, fixture.world_template)
            self.assertEqual(world_active, fixture.world_template)  # No edit: exact byte-identical copy.
            self.assertEqual(nested_dist, fixture.nested_template)
            self.assertEqual(nested_active, fixture.nested_template)
            self.assertEqual(packaged_template, fixture.module_template)
            self.assertEqual(
                packaged_active,
                fixture.module_template.replace(b"Demo.Enable = 1", b"Demo.Enable = 0"),
            )
            self.assertNotIn(b"PRIVATE_MACHINE_VALUE", packaged_active)
            self.assertNotIn("configs/modules/not-installed.conf", entry_names)
            self.assertEqual(mysql_dll, b"libmysql 8.4.11")

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
            self.assertIn("version marker: 8.4.11", result.stdout)
            self.assertNotIn("redact", result.stdout.lower())

            self.assertEqual(
                sorted(path.name for path in fixture.staging.iterdir()),
                sorted([*SERVER_BINARIES, *ROOT_RUNTIME_DLLS, "configs", "mysql"]),
            )

    def test_repository_edit_map_applies_without_warnings_to_matching_templates(self) -> None:
        """Guard the packaged edit map and the edit engine against drifting apart."""
        edits = load_config_edits()
        self.assertEqual(len(edits), 40)
        by_file: dict[str, list] = {}
        for edit in edits:
            by_file.setdefault(edit.relative_file, []).append(edit)

        def upstream_default(value: str) -> str:
            stripped = value.strip()
            if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
                return stripped
            if stripped.casefold() in {"true", "false"}:
                return "false" if stripped.casefold() == "true" else "true"
            if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", stripped):
                return "2.5" if "." in stripped else "7"
            return stripped

        with tempfile.TemporaryDirectory() as temporary:
            config_dir = Path(temporary) / "configs"
            for relative_file, file_edits in by_file.items():
                target = config_dir / relative_file
                target.parent.mkdir(parents=True, exist_ok=True)
                lines = [f"{edit.key} = {upstream_default(edit.value)}" for edit in file_edits]
                target.with_suffix(target.suffix + ".dist").write_text("\n".join(lines) + "\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()) as output:
                copied, applied, warnings = stage_and_edit_configs(config_dir, DEFAULT_CONFIG_EDITS_PATH)

            self.assertEqual(copied, len(by_file))
            self.assertEqual(applied, 40)
            self.assertEqual(warnings, 0, output.getvalue())
            for edit in edits:
                active = (config_dir / edit.relative_file).read_text(encoding="utf-8")
                self.assertIn(f"{edit.key} = {edit.value}", active)

    def test_shipped_module_switch_values_match_the_reviewed_list(self) -> None:
        """Lock the shipped .conf module state so a stale map cannot regress it."""
        expected = {
            "modules/CFBG.conf": ("CFBG.Enable", "1"),
            "modules/bgqueuechecker.conf": ("BGQueueChecker.Enable", "0"),
            "modules/breakingnews.conf": ("BreakingNews.Enable", "0"),
            "modules/leech.conf": ("Leech.Enable", "0"),
            "modules/mod-time_is_time.conf": ("TimeIsTime.SpeedRate", "1.0"),
            "modules/mod_account_mount.conf": ("Account.Mounts.Enable", "0"),
            "modules/mod_aoe_loot.conf": ("AOELoot.Enable", "1"),
            "modules/mod_dungeon_clear.conf": ("DungeonClear.Enable", "1"),
            "modules/mod_moneyforkills.conf": ("MFK.Enable", "0"),
            "modules/mod_no_hearthstone_cooldown.conf": ("NoHearthstoneCooldown.Enable", "0"),
            "modules/mod_npc_free_professions.conf": ("NpcFreeProfessions.Enable", "0"),
            "modules/mod_player_bot_level_brackets.conf": ("BotLevelBrackets.Enabled", "0"),
            "modules/mod_pvptitles.conf": ("PvPTitles.Enable", "0"),
            "modules/random_enchants.conf": ("RandomEnchants.Enable", "0"),
            "modules/skip_dk_module.conf": ("Skip.Deathknight.Starter.Enable", "0"),
        }
        mapped = {(edit.relative_file, edit.key): edit.value for edit in load_config_edits()}
        for relative_file, (key, value) in expected.items():
            with self.subTest(config=relative_file):
                self.assertEqual(mapped.get((relative_file, key)), value)

    def test_packaged_core_configs_get_portable_runtime_paths(self) -> None:
        expected = {
            "authserver.conf": {
                "LogsDir": '"logs"',
                "SourceDirectory": '"source/azerothCore"',
                "MySQLExecutable": '"mysql/bin/mysql.exe"',
                "TempDir": '"temp"',
            },
            "worldserver.conf": {
                "DataDir": '"data"',
                "LogsDir": '"logs"',
                "TempDir": '"temp"',
                "SourceDirectory": '"source/azerothCore"',
                "MySQLExecutable": '"mysql/bin/mysql.exe"',
            },
        }
        mapped = {}
        for edit in load_config_edits():
            mapped.setdefault(edit.relative_file, {})[edit.key] = edit.value
        for relative_file, settings in expected.items():
            with self.subTest(config=relative_file):
                self.assertEqual(mapped.get(relative_file), settings)

    def test_installed_templates_are_byte_identical_after_packaging(self) -> None:
        """The source .conf.dist tree must never be rewritten by packaging."""
        import hashlib

        with tempfile.TemporaryDirectory() as temporary:
            fixture = PackageFixture(Path(temporary))
            before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture.config_dir.rglob("*.conf.dist")}
            self.assertTrue(before)
            fixture.run()
            after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture.config_dir.rglob("*.conf.dist")}
            self.assertEqual(before, after)

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


class PackageValidationTests(unittest.TestCase):
    def run_failing(self, fixture: PackageFixture) -> str:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "package_runtime.py"), *fixture.arguments()],
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        return completed.stderr

    def test_missing_runtime_dll_fails_packaging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PackageFixture(Path(temporary))
            (fixture.dll_dir / "legacy.dll").unlink()
            self.assertIn("exactly the four release DLLs", self.run_failing(fixture))

    def test_extra_runtime_dll_fails_packaging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PackageFixture(Path(temporary))
            (fixture.dll_dir / "zlib1.dll").write_bytes(b"extra")
            self.assertIn("unexpected zlib1.dll", self.run_failing(fixture))

    def test_inventory_file_in_dll_staging_fails_packaging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PackageFixture(Path(temporary))
            (fixture.dll_dir / "RUNTIME-DLLS.json").write_text("{}", encoding="utf-8")
            self.assertIn("inventory stays outside", self.run_failing(fixture))

    def test_missing_mysqld_fails_packaging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PackageFixture(Path(temporary))
            (fixture.mysql_root / "bin" / "mysqld.exe").unlink()
            self.assertIn("bin/mysqld.exe", self.run_failing(fixture))

    def test_wrong_mysql_marker_fails_packaging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PackageFixture(Path(temporary))
            (fixture.mysql_root / ".mysql-version").write_text("8.4.10\n", encoding="utf-8")
            self.assertIn("requires 8.4.11", self.run_failing(fixture))

    def test_legacy_layout_entries_are_rejected(self) -> None:
        base = ["authserver.exe", "worldserver.exe", *ROOT_RUNTIME_DLLS]
        for entries, expected in (
            ([*base, "bin/authserver.exe", "etc/authserver.conf.dist", "configs/x.conf.dist"], "obsolete 'bin/'+'etc/'"),
            ([*base, "README.txt", "configs/x.conf.dist"], "unexpected files at its root"),
            ([*base, "zlib1.dll", "configs/x.conf.dist"], "exactly four DLLs"),
            ([*base, "nested.zip", "configs/x.conf.dist"], "ZIP inside ZIP"),
        ):
            with self.subTest(expected=expected):
                with self.assertRaises(RuntimeError) as raised:
                    validate_package_entries(entries)
                self.assertIn(expected, str(raised.exception))

    def test_every_template_requires_a_matching_active_copy(self) -> None:
        base = [
            "authserver.exe",
            "worldserver.exe",
            *ROOT_RUNTIME_DLLS,
            "configs/authserver.conf",
            "configs/authserver.conf.dist",
            "configs/worldserver.conf",
            "configs/worldserver.conf.dist",
            "configs/modules/paired.conf",
            "configs/modules/paired.conf.dist",
            "mysql/bin/mysqld.exe",
            "mysql/lib/libmysql.dll",
        ]
        self.assertEqual(validate_package_entries(base), base)

        for extra, expected in (
            (["configs/modules/template-only.conf.dist"], "without a matching active .conf"),
            (["configs/modules/active-only.conf"], "without a matching .conf.dist template"),
        ):
            with self.subTest(expected=expected):
                with self.assertRaises(RuntimeError) as raised:
                    validate_package_entries([*base, *extra])
                self.assertIn(expected, str(raised.exception))

    def test_staging_prefix_is_rejected_inside_an_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "nested.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                for name in ("authserver.exe", "worldserver.exe", *ROOT_RUNTIME_DLLS):
                    bundle.writestr(f"azerothcore-ownedcore-windows/{name}", b"x")
            with self.assertRaises(RuntimeError) as raised:
                verify_package_archive(archive)
            self.assertIn("must be relative to the package root", str(raised.exception))

    def test_create_archive_refuses_to_write_inside_the_staging_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PackageFixture(Path(temporary))
            fixture.run()
            with self.assertRaises(RuntimeError) as raised:
                create_package_archive(fixture.staging, fixture.staging / "inner.zip")
            self.assertIn("outside the staging root", str(raised.exception))


class ReleaseContractTests(unittest.TestCase):
    def test_staging_and_package_agree_on_the_release_root(self) -> None:
        from stage_windows_runtime_dlls import REQUIRED_RUNTIME_DLLS as STAGED_DLLS
        from stage_windows_runtime_dlls import SERVER_BINARIES as STAGED_BINARIES

        self.assertEqual(set(STAGED_DLLS), set(ROOT_RUNTIME_DLLS))
        self.assertEqual(set(STAGED_BINARIES), set(SERVER_BINARIES))


class PackageCommandLineTests(unittest.TestCase):
    def test_package_scripts_render_help_without_formatting_errors(self) -> None:
        for script in ("package_runtime.py", "assemble_release_zip.py", "package_config_edits.py"):
            with self.subTest(script=script):
                completed = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / script), "--help"],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn("usage:", completed.stdout)


class PackageInspectionTests(unittest.TestCase):
    def test_verify_package_layout_accepts_the_packaged_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PackageFixture(Path(temporary))
            fixture.run()
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "verify_package_layout.py"),
                    "--package-root", str(fixture.staging),
                    "--archive", str(fixture.archive),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Package layout valid", completed.stdout)
            self.assertIn("Release archive namelist valid", completed.stdout)
            self.assertIn("Root DLLs: legacy.dll, libcrypto-3-x64.dll, libmysql.dll, libssl-3-x64.dll", completed.stdout)
            self.assertRegex(completed.stdout, r"Manifest SHA-256: [0-9a-f]{64}")
            # The fingerprint must be stable for an unchanged tree.
            repeat = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "verify_package_layout.py"),
                    "--package-root", str(fixture.staging),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            first = next(line for line in completed.stdout.splitlines() if line.startswith("Manifest SHA-256:"))
            second = next(line for line in repeat.stdout.splitlines() if line.startswith("Manifest SHA-256:"))
            self.assertEqual(first, second)

    def test_verify_package_layout_rejects_a_prefixed_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PackageFixture(Path(temporary))
            fixture.run()
            prefixed_root = Path(temporary) / "artifact-root"
            prefixed_root.mkdir()
            fixture.staging.rename(prefixed_root / "azerothcore-ownedcore-windows")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "verify_package_layout.py"),
                    "--package-root", str(prefixed_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertIn("must be relative to the package root", completed.stderr)


class ReleaseArchiveTests(unittest.TestCase):
    def test_release_assembler_writes_one_root_relative_zip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PackageFixture(Path(temporary))
            fixture.run()
            artifact_root = Path(temporary) / "release-assets" / "package-root"
            artifact_root.parent.mkdir(parents=True)
            fixture.staging.rename(artifact_root)
            release_zip = Path(temporary) / "release-assets" / "azerothcore-ownedcore-windows.zip"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "assemble_release_zip.py"),
                    "--package-root", str(artifact_root),
                    "--output", str(release_zip),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            with zipfile.ZipFile(release_zip) as bundle:
                names = bundle.namelist()
            self.assertIn("authserver.exe", names)
            self.assertIn("configs/worldserver.conf.dist", names)
            self.assertIn("mysql/bin/mysqld.exe", names)
            self.assertFalse(any(name.startswith("azerothcore-ownedcore-windows/") for name in names))
            self.assertFalse(any(name.endswith(".zip") for name in names))
            self.assertIn("Created", completed.stdout)

    def test_release_assembler_rejects_a_nested_staging_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PackageFixture(Path(temporary))
            fixture.run()
            artifact_root = Path(temporary) / "package-root"
            artifact_root.mkdir()
            fixture.staging.rename(artifact_root / "azerothcore-ownedcore-windows")
            release_zip = Path(temporary) / "release.zip"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "assemble_release_zip.py"),
                    "--package-root", str(artifact_root),
                    "--output", str(release_zip),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("must be relative to the package root", completed.stderr)
            self.assertFalse(release_zip.exists())


if __name__ == "__main__":
    unittest.main()
