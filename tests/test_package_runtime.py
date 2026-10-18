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

from package_runtime import copy_config_template  # noqa: E402


class PackageConfigTemplateTests(unittest.TestCase):
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

    def test_archive_contains_the_original_template_unchanged(self) -> None:
        content = (
            b"WorldDatabaseInfo = \"acore;localhost;example;example;3306;\"\n"
            b"PublicApiKey = \"documented-example-value\"\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dist = root / "dist"
            binary_dir = dist / "bin"
            config_dir = dist / "configs"
            output = root / "package"
            binary_dir.mkdir(parents=True)
            (config_dir / "modules").mkdir(parents=True)
            for binary in ("authserver.exe", "worldserver.exe"):
                (binary_dir / binary).write_bytes(b"test binary")
            (config_dir / "authserver.conf.dist").write_bytes(b"AuthServerPort = 3724\n")
            (config_dir / "modules" / "sample.conf.dist").write_bytes(content)

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "package_runtime.py"),
                    "--dist-dir", str(dist),
                    "--binary-dir", str(binary_dir),
                    "--config-dir", str(config_dir),
                    "--output", str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            archive = output / "azerothcore-ownedcore-windows.zip"
            with zipfile.ZipFile(archive) as package:
                packaged_template = package.read(
                    "azerothcore-ownedcore-windows/etc/modules/sample.conf.dist"
                )
                package_readme = package.read("azerothcore-ownedcore-windows/README.txt").decode("utf-8")
                source_pins = json.loads(package.read("azerothcore-ownedcore-windows/SOURCE-PINS.json"))

            self.assertEqual(packaged_template, content)
            self.assertIn("unchanged *.conf.dist templates", package_readme)
            self.assertNotIn("blank", package_readme.lower())
            self.assertNotIn("redact", result.stdout.lower())
            self.assertIn("without Individual Progression", result.stdout)
            self.assertFalse(source_pins["build_selection"]["mod-individual-progression"])


if __name__ == "__main__":
    unittest.main()
