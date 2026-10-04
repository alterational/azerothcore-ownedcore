# azerothcore-ownedcore

Azerothcore + Playerbots with the same-ish configuration as on the Ownedcore topic.

A reproducible source workspace for the user-selected AzerothCore Playerbots core and OwnedCore module list, with City Life added. Sources are materialized on demand and kept out of Git; the generated `core/modules` tree is ignored. The current workspace has the pinned sources materialized and module `.conf.dist` defaults configured for compilation.

- **66 unique modules:** 52 enabled and 14 initially disabled. Every module has `install: true`; initially disabled modules are still fetched and built.
- [Module inventory and immutable commits](MODULES.md)
- [Configuration policy and application](docs/CONFIGURATION.md)
- [SQL and runtime setup](docs/SQL_SETUP.md)
- [Build and Codespaces instructions](docs/BUILD.md)
- [Config audit](MODULE_CONFIG_AUDIT.md) · [checkout/build report](CHECKOUT_REPORT.md)
- [Destination repository and status](docs/DESTINATION.md)
- [Manifest](modules.manifest.json) · [lockfile](modules.lock.json)

## Source pins

The core is `mod-playerbots/azerothcore-wotlk`, branch `Playerbot`, commit `f19a18799a35f7c24bdcdc9ea399c601f166259b`. Every module source is pinned to a full commit SHA in `modules.lock.json`; pins are reproducible candidates and have **not** been shown to build together unless a later checkout report explicitly records a successful build.

The approved Learn Spells replacement is `azerothcore/mod-learn-spells`. Dungeon Clear remains enabled with its upstream default (`DungeonClear.Enable = 1`). City Life is enabled with its upstream defaults; its manual world SQL and online Playerbots prerequisite are documented separately.

## Quick start

```bash
python3 scripts/validate_project.py
python3 scripts/materialize.py   # downloads the pinned core and all 66 modules into ./core
python3 scripts/apply_module_config.py --apply --source-templates
```

The source tree uses about 1.5 GB before build products. See [BUILD.md](docs/BUILD.md) for Codespaces and compilation instructions. The quick start applies audited module defaults to generated `.conf.dist` templates before build; active runtime config checks are documented in [CONFIGURATION.md](docs/CONFIGURATION.md). No database is changed by the scripts in this repository.

## Safety and current status

- The Actions workflow checks metadata, Python syntax, and JSON. It does **not** fetch sources, compile, run a server, or apply SQL.
- No WoW client data, maps, database dumps, passwords, or runtime config files belong in Git. `core/` and build output are ignored.
- City Life's SQL is a manual world-database migration, not automatically applied by this repository. Do not run it against a live database without a named target, backup, and explicit authorization.
- The repository has no automated GitHub publication step. Pin refresh is an explicit, reviewed operation and does not prove compatibility.
