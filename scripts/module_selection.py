#!/usr/bin/env python3
"""Select which locked module sources are compiled by a build variant."""
from __future__ import annotations

from collections.abc import Iterable, Sequence


def select_modules(modules: Sequence[dict], include_modules: Iterable[str] = ()) -> list[dict]:
    """Return installable modules selected for this build.

    Modules with ``compile_by_default: false`` stay locked and available, but are
    omitted from the standard source tree unless explicitly included.
    """
    by_id = {module["id"]: module for module in modules}
    requested = set(include_modules)
    unknown = sorted(requested - set(by_id))
    if unknown:
        raise ValueError("Unknown module ID(s) requested for this build: " + ", ".join(unknown))

    not_installable = sorted(module_id for module_id in requested if not by_id[module_id].get("install", True))
    if not_installable:
        raise ValueError("Cannot include module(s) marked install=false: " + ", ".join(not_installable))

    selected = []
    for module in modules:
        if not module.get("install", True):
            continue
        compile_by_default = module.get("compile_by_default", True)
        if not isinstance(compile_by_default, bool):
            raise ValueError(f"{module['id']}: compile_by_default must be a boolean")
        if compile_by_default or module["id"] in requested:
            selected.append(module)
    return selected


def excluded_module_ids(modules: Sequence[dict], include_modules: Iterable[str] = ()) -> list[str]:
    selected_ids = {module["id"] for module in select_modules(modules, include_modules)}
    return [module["id"] for module in modules if module.get("install", True) and module["id"] not in selected_ids]
