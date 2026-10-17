# Build and Codespaces

## What validation does

`.github/workflows/validate.yml` checks manifest/lock consistency, the module switch map, tracked additional/core-default maps, Python syntax, and JSON syntax. It does not fetch sources, compile, start a server, validate a database, or require client data.

The Codespaces `postCreateCommand` validates and materializes the pinned core plus all 70 modules, validates every checkout against the lock, applies/checks the tracked source compatibility patches, applies/checks the tracked module switches and additional module settings, then checks the pinned core config state. It does not install system dependencies, compile, start a server, or apply SQL. At the current core SHA, that final check verifies the committed authserver/worldserver defaults in the personal core fork. An already-created Codespace does not rerun `postCreateCommand`; pull the build-repository branch and run the preparation commands below or rebuild the container.

## Core configuration defaults (committed)

The required authserver/worldserver source-default changes are committed in the user's core fork `alterational/azerothcore-wotlk`, branch `Playerbot`, at `14c435031d2cb31b1af664af9a83c5d6256302b6`. That commit is the core SHA in `modules.lock.json`; read-only checks of both pinned `.conf.dist` templates confirmed all ten target values. The four required compatibility defaults (`MapUpdate.Threads = 4`, `EnablePlayerSettings = 1`, `DBC.EnforceItemAttributes = 0`, and `ActivateWeather = 0`) are present, along with the reviewed logging, `.die`, and Dungeon Finder defaults. Machine-specific path values and database connection settings were not copied.

`python3 scripts/check_core_defaults.py --require-target` is the pre-build gate: it must pass against the pinned source. The patches under `patches/azerothcore-*-defaults.patch` document source defaults already committed to the fork; do not apply them again. A separate Windows Ninja/MSVC compatibility patch fixes the Visual-Studio-only `$(ConfigurationName)` path in `core/modules/CMakeLists.txt`: multi-config generators use `$<CONFIG>/`, while single-config Ninja uses no configuration subdirectory. This prevents Ninja's `bad $-escape` during configure and keeps the copy path aligned with the binary output directory. `scripts/apply_core_compatibility_patches.py` applies it only to the audited core SHA in the ignored materialized checkout. It does not change or mask the core pin.

## Linux/Codespaces build

Use the user's Codespace (4 cores, 16 GB RAM) or a comparable Linux machine. From the build-repository root, prepare and verify the exact pinned sources and tracked module defaults:

```bash
python3 scripts/validate_project.py
python3 scripts/materialize.py
python3 scripts/validate_project.py --check-checkout
python3 scripts/apply_source_patches.py --apply
python3 scripts/apply_source_patches.py --check
python3 scripts/apply_core_compatibility_patches.py --apply
python3 scripts/apply_core_compatibility_patches.py --check
python3 scripts/apply_module_config.py --apply --source-templates
python3 scripts/apply_additional_settings.py --apply --source-templates
python3 scripts/apply_module_config.py --check --source-templates
python3 scripts/apply_additional_settings.py --check --source-templates
python3 scripts/check_core_defaults.py --require-target
```

Once the last pre-build check passes, build with the requested commands:

```bash
cd core
./acore.sh install-deps
MTHREADS=4 ./acore.sh compiler all
cd ..
```

After install, apply and check runtime settings:

```bash
python3 scripts/apply_module_config.py --apply
python3 scripts/apply_additional_settings.py --apply
python3 scripts/check_core_defaults.py --runtime --require-target
python3 scripts/apply_module_config.py --check
python3 scripts/apply_additional_settings.py --check
```

`compiler all` means clean, configure, compile, and install in the pinned `acore.sh`. These exact commands have not yet been run in the user Codespace; Codespaces API access from the agent returned HTTP 403, and the agent must not create or launch one. Record the exact exit codes and results in `CHECKOUT_REPORT.md`; do not claim a build passed until observed.

`materialize.py` creates shallow Git checkouts of the locked core and every module with `install: true`, including all 14 initially disabled modules. It does not refresh pins, apply SQL, or prove compatibility. `apply_source_patches.py` applies five SHA-guarded module fixes: BGQueueChecker (`0a6b9872f5d4f50286e5152c0debfeb1d6ef73a0`) updates the obsolete battleground hook; mod-aoe-loot (`be4f06af8e1b455cc31a227f12e2d0a741c799e0`) matches the const packet API and disambiguates the global `Item` type; mod-challenge-modes (`1930525b9530d329cb9fe0504a3c9b5b40a12261`) uses the pinned core's `bool&` parameter for `PlayerScript::OnPlayerResurrect`; mod-dead-means-dead (`725b14973be28c4acea7d1a892bbe7cfdd2e8a51`) renames `OnLogin` to the pinned core's `OnPlayerLogin` hook; mod-player-bot-level-brackets (`a94f9c6458bf6264164436a53ddd4e5c3ed44fdb`) uses the current `PlayerbotAIConfig::EquipAndSpecPersistence` field name. The script refuses to apply any patch to a different module SHA. The module-config commands run before compilation to make generated `.conf.dist` templates match tracked policy. On Linux, runtime mode operates under `core/env/dist/etc` after install; on Windows, the pinned core's CMake rules install configs under `core/env/dist/configs`. Pass `--config-dir <path>` when using a nondefault runtime config location.

Some module READMEs cite minimum core revisions. Treat the full compile/runtime review as the compatibility check for the exact pinned set; do not auto-refresh pins during that review. The build alone does not apply City Life's manual SQL. Read [`SQL_SETUP.md`](SQL_SETUP.md) and review backups and authorization before any server startup/database updater.

## Windows build and publication

`.github/workflows/windows-release.yml` uses the pinned core's Windows dependency/build approach, materializes all lockfile sources, requires the core-default gate, applies the BGQueueChecker, mod-aoe-loot, mod-challenge-modes, mod-dead-means-dead, and mod-player-bot-level-brackets module patches plus the SHA-guarded Ninja/MSVC CMake path patch, then applies the same module config maps. It maps the materialized core to a short `Z:` drive for the Windows build: Ninja's forced response files cover C/C++ commands but not `rc`, and the full propagated include list had exceeded Windows' `CreateProcess` command-line limit. On Windows the pinned core installs server executables/DLLs directly under `core/env/dist` and config templates under `core/env/dist/configs` (including `configs/modules`); the workflow uses those platform-specific paths for runtime checks and package staging. The release package normalizes these to `bin/` and `etc/` and contains Windows server binaries plus sanitized `.conf.dist` templates. The package script blanks database connection strings and password/token/key settings and excludes active `.conf` files, game/client data, maps, SQL, and dumps.

The workflow runs on pull requests, `workflow_dispatch`, and `v*` tags. It runs `python scripts/check_core_defaults.py --require-target` before dependency setup or compilation and stops unless all ten tracked authserver/worldserver defaults match their requested values in the pinned core. Only after that gate passes does it build, check installed runtime configuration, package the sanitized runtime, and upload an artifact. A GitHub Release is published only for a version tag after that build and package succeed. No artifact or release is claimed until Actions reports it.

The release artifact does not include game/client data, maps, vmaps, mmaps, database dumps, credentials, secrets, or active server-specific configuration. It is not a ready-to-run game server distribution; local database settings and the separately sourced client data are required.
