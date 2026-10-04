# Build and Codespaces

## What validation does

`.github/workflows/validate.yml` checks manifest/lock consistency, the module switch map, tracked additional/core-default maps, Python syntax, and JSON syntax. It does not fetch sources, compile, start a server, validate a database, or require client data.

The Codespaces `postCreateCommand` validates and materializes the pinned core plus all 66 modules, validates every checkout against the lock, applies/checks the tracked module switches and additional module settings, then checks the pinned core config state. It does not install system dependencies, compile, start a server, or apply SQL. At the current core SHA, that final check explicitly reports that the four required core defaults are pending in the personal core fork. An already-created Codespace does not rerun `postCreateCommand`; pull the build-repository branch and run the preparation commands below or rebuild the container.

## Required core-fork change before building

The current core SHA still has the original values for `MapUpdate.Threads`, `EnablePlayerSettings`, `DBC.EnforceItemAttributes`, and `ActivateWeather`. The required changes belong in the history of `alterational/azerothcore-wotlk` on `Playerbot`, not as local modifications to the ignored `core/` checkout in this repository.

From the build repository's materialized `core/` checkout, after fetching the current personal `Playerbot` branch:

```bash
cd core
git fetch origin refs/heads/Playerbot:refs/remotes/origin/Playerbot
git switch --track -c Playerbot origin/Playerbot
git apply --check --unidiff-zero ../patches/azerothcore-worldserver-defaults.patch
git apply --unidiff-zero ../patches/azerothcore-worldserver-defaults.patch
grep -n -E '^(MapUpdate\.Threads|EnablePlayerSettings|DBC\.EnforceItemAttributes|ActivateWeather) =' src/server/apps/worldserver/worldserver.conf.dist
git add src/server/apps/worldserver/worldserver.conf.dist
git commit -m "Set OwnedCore worldserver defaults"
git push origin HEAD:Playerbot
git rev-parse HEAD
```

Record the resulting 40-character SHA. Update only these core fields in the build repository: `modules.manifest.json` → `core.candidate_commit`; `modules.lock.json` → `core.commit`; `scripts/validate_project.py` → `EXPECTED_CORE_SHA` (leave `PENDING_CORE_SHA` at the old SHA); `config/module-switches.json` and `config/additional-module-settings.json` → `core_commit`; and `config/core-worldserver-defaults.json` → the new `core_commit` plus status `pinned_in_core_fork`. Update the core SHA in `README.md`, `MODULE_CONFIG_AUDIT.md`, and `CHECKOUT_REPORT.md` too. Do not change any module pin or run `scripts/refresh_lock.py`. Until the new pin and maps are updated, `python3 scripts/check_core_defaults.py --require-target` fails and the Windows workflow stops at its pre-build gate. No dependency setup, compilation, packaging, artifact upload, or release publication may proceed.

> The agent cannot push a commit to `Playerbot` under the session's branch restriction. The zero-context patch is included and was verified with `git apply --check --unidiff-zero` against the current pinned file; the user must apply and commit it to the personal core fork, then provide/update the resulting SHA.

## Linux/Codespaces build

Use the user's Codespace (4 cores, 16 GB RAM) or a comparable Linux machine. From the build-repository root, prepare and verify the exact pinned sources and tracked module defaults:

```bash
python3 scripts/validate_project.py
python3 scripts/materialize.py
python3 scripts/validate_project.py --check-checkout
python3 scripts/apply_module_config.py --apply --source-templates
python3 scripts/apply_additional_settings.py --apply --source-templates
python3 scripts/apply_module_config.py --check --source-templates
python3 scripts/apply_additional_settings.py --check --source-templates
python3 scripts/check_core_defaults.py --require-target
```

After the core-fork commit has been pinned and the last command passes, build with the requested commands:

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

`materialize.py` creates shallow Git checkouts of the locked core and every module with `install: true`, including all 14 initially disabled modules. It does not refresh pins, apply SQL, or prove compatibility. The two module-config commands run before compilation to make the generated `.conf.dist` templates match the tracked policy. Runtime mode operates under `core/env/dist/etc` after install; pass `--config-dir <path>` if using a custom `CONFDIR`.

Some module READMEs cite minimum core revisions. Keep the locked SHAs unchanged and treat the full compile/runtime review as the compatibility check. The build alone does not apply City Life's manual SQL. Read [`SQL_SETUP.md`](SQL_SETUP.md) and review backups and authorization before any server startup/database updater.

## Windows build and publication

`.github/workflows/windows-release.yml` uses the pinned core's Windows dependency/build approach, materializes all lockfile sources, applies the same module config maps, builds with MSVC on `windows-latest`, checks installed runtime configs, and packages Windows server binaries plus sanitized `.conf.dist` templates. The package script blanks database connection strings and password/token/key settings and excludes active `.conf` files, game/client data, maps, SQL, and dumps.

The workflow runs on pull requests, `workflow_dispatch`, and `v*` tags. It runs `python scripts/check_core_defaults.py --require-target` before dependency setup or compilation and stops if the pinned core does not contain all four required defaults. Only after that gate passes does it build, check installed runtime configuration, package the sanitized runtime, and upload an artifact. A GitHub Release is published only for a version tag after that build and package succeed. No artifact or release is claimed until Actions reports it.

The release artifact does not include game/client data, maps, vmaps, mmaps, database dumps, credentials, secrets, or active server-specific configuration. It is not a ready-to-run game server distribution; local database settings and the separately sourced client data are required.
