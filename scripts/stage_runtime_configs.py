#!/usr/bin/env python3
"""Stage fresh runtime config files from the materialized, patched source tree.

CMake's Windows install layout has varied across generator/runner combinations.
The source templates have already passed the locked-SHA and compatibility/config
checks before compilation, so stage those exact templates into the canonical
Windows runtime layout instead of guessing where CMake installed them.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys


def stage_configs(core_dir: Path, dist_dir: Path) -> tuple[int, int]:
    core_dir = core_dir.resolve()
    dist_dir = dist_dir.resolve()
    root_sources = [
        core_dir / "src/server/apps/authserver/authserver.conf.dist",
        core_dir / "src/server/apps/worldserver/worldserver.conf.dist",
    ]
    missing = [path for path in root_sources if not path.is_file()]
    if missing:
        raise RuntimeError("Required core config templates are missing: " + ", ".join(map(str, missing)))

    module_sources = sorted((core_dir / "modules").glob("*/conf/*.conf.dist"))
    if not module_sources:
        raise RuntimeError(f"No module .conf.dist templates found under {core_dir / 'modules'}")

    # CMake installs module templates into one flat configs/modules directory;
    # reject collisions rather than silently selecting one source.
    by_name: dict[str, Path] = {}
    for source in module_sources:
        previous = by_name.get(source.name.casefold())
        if previous is not None:
            raise RuntimeError(f"Duplicate module config template name {source.name}: {previous} and {source}")
        by_name[source.name.casefold()] = source

    config_dir = dist_dir / "configs"
    module_dir = config_dir / "modules"
    config_dir.mkdir(parents=True, exist_ok=True)
    module_dir.mkdir(parents=True, exist_ok=True)

    # Record any templates already present under the Windows dist tree before
    # staging. This helps diagnose layout differences without assuming where
    # CMake placed them.
    existing = sorted(dist_dir.rglob("*.conf.dist"))
    if existing:
        print(f"Found {len(existing)} existing .conf.dist files under {dist_dir} before staging:")
        for path in existing:
            print(f"  {path.relative_to(dist_dir)}")
    else:
        print(f"No .conf.dist files found under {dist_dir} before staging; using checked source templates.")

    for source in root_sources:
        destination = config_dir / source.name
        shutil.copy2(source, destination)
        active = destination.with_suffix("")
        if not active.exists():
            shutil.copy2(source, active)

    for source in module_sources:
        destination = module_dir / source.name
        shutil.copy2(source, destination)
        active = destination.with_suffix("")
        if not active.exists():
            shutil.copy2(source, active)

    return len(root_sources), len(module_sources)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-dir", type=Path, default=Path("core"), help="materialized core source directory")
    parser.add_argument("--dist-dir", type=Path, default=Path("core/env/dist"), help="Windows runtime install directory")
    args = parser.parse_args()
    root_count, module_count = stage_configs(args.core_dir, args.dist_dir)
    print(
        f"Staged {root_count} core and {module_count} module config templates into "
        f"{args.dist_dir.resolve() / 'configs'} and created missing active .conf files."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
