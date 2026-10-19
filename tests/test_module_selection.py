from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from materialize import remove_excluded_checkout  # noqa: E402
from module_selection import excluded_module_ids, select_modules  # noqa: E402


class ModuleSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = json.loads((ROOT / "modules.manifest.json").read_text(encoding="utf-8"))["modules"]

    def test_default_selection_omits_only_individual_progression(self) -> None:
        selected = select_modules(self.modules)
        selected_ids = {module["id"] for module in selected}
        all_ids = {module["id"] for module in self.modules}
        runtime_off_ids = {module["id"] for module in self.modules if not module["enabled"]}
        self.assertEqual(len(selected), 69)
        self.assertEqual(all_ids - selected_ids, {"mod-individual-progression"})
        self.assertTrue(runtime_off_ids.issubset(selected_ids))
        self.assertEqual(excluded_module_ids(self.modules), ["mod-individual-progression"])

    def test_explicit_opt_in_restores_all_locked_sources(self) -> None:
        selected = select_modules(self.modules, ["mod-individual-progression"])
        self.assertEqual(len(selected), 70)
        self.assertIn("mod-individual-progression", {module["id"] for module in selected})
        self.assertEqual(excluded_module_ids(self.modules, ["mod-individual-progression"]), [])

    def test_unknown_module_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown module ID"):
            select_modules(self.modules, ["not-a-locked-module"])

    def make_repo(self, path: Path, origin: str) -> str:
        subprocess.run(["git", "init", "--quiet", str(path)], check=True)
        subprocess.run(["git", "-C", str(path), "config", "user.name", "Build selection test"], check=True)
        subprocess.run(["git", "-C", str(path), "config", "user.email", "build-selection@example.invalid"], check=True)
        (path / "locked.txt").write_text("locked source\n", encoding="utf-8")
        (path / ".gitignore").write_text("scratch/\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(path), "add", "locked.txt", ".gitignore"], check=True)
        subprocess.run(["git", "-C", str(path), "commit", "--quiet", "-m", "locked source"], check=True)
        subprocess.run(["git", "-C", str(path), "remote", "add", "origin", origin], check=True)
        return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()

    def test_variant_switch_removes_only_clean_locked_checkout(self) -> None:
        url = "https://example.invalid/optional-module.git"
        with tempfile.TemporaryDirectory() as temporary:
            checkout = Path(temporary) / "module"
            commit = self.make_repo(checkout, url)
            self.assertTrue(remove_excluded_checkout(url, commit, checkout))
            self.assertFalse(checkout.exists())

    def test_variant_switch_preserves_modified_checkout(self) -> None:
        url = "https://example.invalid/optional-module.git"
        with tempfile.TemporaryDirectory() as temporary:
            checkout = Path(temporary) / "module"
            commit = self.make_repo(checkout, url)
            (checkout / "locked.txt").write_text("local work\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Refusing to delete"):
                remove_excluded_checkout(url, commit, checkout)
            self.assertTrue(checkout.exists())

    def test_variant_switch_preserves_ignored_checkout_files(self) -> None:
        url = "https://example.invalid/optional-module.git"
        with tempfile.TemporaryDirectory() as temporary:
            checkout = Path(temporary) / "module"
            commit = self.make_repo(checkout, url)
            ignored_file = checkout / "scratch" / "local.bin"
            ignored_file.parent.mkdir()
            ignored_file.write_bytes(b"keep me")
            with self.assertRaisesRegex(RuntimeError, "Refusing to delete"):
                remove_excluded_checkout(url, commit, checkout)
            self.assertTrue(ignored_file.is_file())


if __name__ == "__main__":
    unittest.main()
