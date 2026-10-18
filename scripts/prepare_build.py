#!/usr/bin/env python3
"""Prepare the pinned source tree and configuration for a build in one command."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run_step(label: str, script: str, arguments: list[str] | None = None) -> None:
    command = [sys.executable, str(ROOT / "scripts" / script), *(arguments or [])]
    print(f"\n== {label} ==", flush=True)
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode:
        raise RuntimeError(f"{label} failed with exit code {result.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--core-dir",
        type=Path,
        default=ROOT / "core",
        help="materialized core directory (default: ./core)",
    )
    parser.add_argument(
        "--include-module",
        action="append",
        default=[],
        metavar="MODULE_ID",
        help="include an optional compile_by_default=false source; may be repeated",
    )
    parser.add_argument(
        "--runtime",
        action="store_true",
        help="apply and verify reviewed runtime settings after build/install instead of preparing sources",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=ROOT / "core" / "env" / "dist" / "etc",
        help="active runtime config directory used with --runtime (default: core/env/dist/etc)",
    )
    args = parser.parse_args()

    core_dir = args.core_dir.resolve()
    core_argument = ["--core-dir", str(core_dir)]
    if args.runtime:
        if args.include_module:
            parser.error("--include-module applies only while preparing a source build")
        runtime_arguments = ["--config-dir", str(args.config_dir.resolve())]
        run_step(
            "Apply and verify runtime module settings",
            "apply_module_config.py",
            [*core_argument, *runtime_arguments, "--apply"],
        )
        run_step(
            "Apply and verify additional runtime settings",
            "apply_additional_settings.py",
            [*core_argument, *runtime_arguments, "--apply"],
        )
        run_step(
            "Verify installed core runtime defaults",
            "check_core_defaults.py",
            [*core_argument, *runtime_arguments, "--runtime", "--require-target"],
        )
        print("\nInstalled runtime configuration is ready. No SQL was run.")
        return 0

    module_arguments = [item for module_id in args.include_module for item in ("--include-module", module_id)]

    run_step("Validate manifest, lock, and configuration policy", "validate_project.py")
    run_step("Materialize pinned core and selected modules", "materialize.py", [*core_argument, *module_arguments])
    run_step(
        "Verify selected checkout pins",
        "validate_project.py",
        ["--check-checkout", *core_argument, *module_arguments],
    )
    run_step("Apply and verify core compatibility fixes", "apply_core_compatibility_patches.py", [*core_argument, "--apply"])
    run_step(
        "Apply and verify module master-switch settings",
        "apply_module_config.py",
        [*core_argument, "--apply", "--source-templates"],
    )
    run_step(
        "Apply and verify additional module settings",
        "apply_additional_settings.py",
        [*core_argument, "--apply", "--source-templates"],
    )
    run_step(
        "Require the pinned core server config defaults",
        "check_core_defaults.py",
        [*core_argument, "--require-target"],
    )
    print("\nPinned build sources and configuration are ready. No compilation or SQL was run.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
