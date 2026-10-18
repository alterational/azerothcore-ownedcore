from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from prepare_build import main  # noqa: E402


class PrepareBuildTests(unittest.TestCase):
    def run_main(self, arguments: list[str]):
        with patch.object(sys, "argv", ["prepare_build.py", *arguments]), patch("prepare_build.run_step") as run_step:
            with contextlib.redirect_stdout(io.StringIO()):
                status = main()
        self.assertEqual(status, 0)
        return [call.args for call in run_step.call_args_list]

    def test_default_preparation_runs_each_required_stage(self) -> None:
        calls = self.run_main([])
        self.assertEqual(
            [call[0] for call in calls],
            [
                "Validate manifest, lock, and configuration policy",
                "Materialize pinned core and selected modules",
                "Verify selected checkout pins",
                "Apply and verify core compatibility fixes",
                "Apply and verify module master-switch settings",
                "Apply and verify additional module settings",
                "Require the pinned core server config defaults",
            ],
        )
        self.assertIn("--apply", calls[3][2])
        self.assertNotIn("--check", calls[3][2])

    def test_optional_module_is_forwarded_to_materialize_and_checkout_check(self) -> None:
        calls = self.run_main(["--include-module", "mod-individual-progression"])
        self.assertIn("--include-module", calls[1][2])
        self.assertIn("--include-module", calls[2][2])

    def test_runtime_mode_combines_runtime_maps_and_core_gate(self) -> None:
        calls = self.run_main(["--runtime", "--config-dir", "custom-config"])
        self.assertEqual(len(calls), 3)
        self.assertIn("apply_module_config.py", calls[0][1])
        self.assertIn("apply_additional_settings.py", calls[1][1])
        self.assertIn("--runtime", calls[2][2])
        self.assertIn("--require-target", calls[2][2])


if __name__ == "__main__":
    unittest.main()
