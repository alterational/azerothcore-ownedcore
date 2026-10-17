# azerothcore-ownedcore

A reproducible build workspace for the user's AzerothCore Playerbots fork and the OwnedCore module list, with City Life added. The build repository tracks immutable source pins and reviewed config applicators; materialized source and build output stay out of Git.

- **70 modules:** 56 intended enabled and 14 initially disabled. Every entry remains `install: true`; disabled modules are still checked out and compiled.
- [Module inventory and immutable commits](MODULES.md)
- [Configuration policy and application](docs/CONFIGURATION.md)
- [SQL and runtime setup](docs/SQL_SETUP.md)
- [Build, Codespaces, and Windows workflow](docs/BUILD.md)
- [Config audit](MODULE_CONFIG_AUDIT.md) · [checkout/build report](CHECKOUT_REPORT.md)
- [Manifest](modules.manifest.json) · [lockfile](modules.lock.json)

## Source pins

The core is the user's fork `alterational/azerothcore-wotlk`, branch `Playerbot`, pinned at `14c435031d2cb31b1af664af9a83c5d6256302b6`. The user committed the reviewed authserver/worldserver source defaults in the core fork; a read-only check of both `.conf.dist` files at that commit confirmed all ten tracked target values. The previous pin was `f19a18799a35f7c24bdcdc9ea399c601f166259b`. Module locks were refreshed on 2026-10-17 and were preserved during this separate core-pin update. Neither the refreshed module set nor the new core pin has yet been proven by a full build.

Learn Spells uses the approved `azerothcore/mod-learn-spells` repository. Dungeon Clear remains enabled at its upstream `DungeonClear.Enable = 1`; City Life remains enabled at its upstream `CityLife.Enable = 1`.

An explicitly approved module-only pin refresh uses `python3 scripts/refresh_lock.py --modules-only`. It resolves each installed module's current default-branch `HEAD`, preserves the core pin exactly, and aborts rather than writing a partial refresh if a module source cannot be resolved. Refreshed pins are candidates—not compatibility/build proof. The default command without `--modules-only` also refreshes the configured core branch.

## Quick start

```bash
python3 scripts/validate_project.py
python3 scripts/materialize.py
python3 scripts/validate_project.py --check-checkout
python3 scripts/apply_source_patches.py --apply
python3 scripts/apply_source_patches.py --check
python3 scripts/apply_module_config.py --apply --source-templates
python3 scripts/apply_additional_settings.py --apply --source-templates
python3 scripts/apply_module_config.py --check --source-templates
python3 scripts/apply_additional_settings.py --check --source-templates
python3 scripts/check_core_defaults.py
```

The source tree uses about 1.5 GB before build products. The module configuration applicators reproduce the audited master switches and additional settings. `check_core_defaults.py --require-target` checks the ten reviewed authserver/worldserver defaults in the pinned core templates; runtime mode checks installed configs after a build. See [BUILD.md](docs/BUILD.md) for commands. No database is changed by these scripts.

## Safety and current status

- The fast Actions workflow checks manifests, maps, Python syntax, and JSON; it does not prove the sources compile.
- The Windows workflow checks the pinned core defaults before dependency setup or compilation, then builds and checks runtime config. Packaging, artifact upload, and release publication occur only after a successful build. GitHub Releases are published only for `v*` tags after a successful final Windows build.
- No WoW client data, maps, vmaps/mmaps, dumps, passwords, secrets, or active server-specific configs belong in Git or the runtime artifact. The generated `core/` and build output are ignored.
- City Life's SQL is a manual world-database migration. It is not run by this repository; see [SQL_SETUP.md](docs/SQL_SETUP.md).
- No Linux or Windows full build has passed yet. See [`CHECKOUT_REPORT.md`](CHECKOUT_REPORT.md) for observed results and blockers.
