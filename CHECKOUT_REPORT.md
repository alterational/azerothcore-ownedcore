# Source checkout, configuration, SQL, and build report

- **Report date:** 2026-10-04
- **Build repository:** `alterational/azerothcore-ownedcore`, session branch `arena/01a106ef-azerothcore-ownedcore`; PR [#1](https://github.com/alterational/azerothcore-ownedcore/pull/1) targets `main` and remains open/unmerged.
- **Core source:** `https://github.com/alterational/azerothcore-wotlk.git`, branch `Playerbot`, locked SHA `f19a18799a35f7c24bdcdc9ea399c601f166259b`. `git ls-remote` confirmed the branch tip was that SHA. The materialized `core/` origin and `HEAD` were verified to match.
- **Module pins:** unchanged. All 66 manifest modules remain `install: true`: 52 intended enabled, 14 initially disabled.

## Completed and verified

- **Materialization:** `python3 scripts/materialize.py` succeeded against the personal core fork and fetched all 66 modules. `core/` was about 1.5 GB and is ignored by Git. `python3 scripts/validate_project.py --check-checkout` passed: core and all 66 module `HEAD`s matched `modules.lock.json`.
- **Module master switches:** `python3 scripts/apply_module_config.py --apply --source-templates` changed 15 audited values (3 enabled switches `0 -> 1`, 12 disabled switches `1 -> 0`). `--check --source-templates` passed with 48 verified master switches, City Life and Dungeon Clear at their upstream enabled defaults, and 16 documented modules without a module-wide switch. No source pins or SQL changed.
- **Additional module settings:** `python3 scripts/apply_additional_settings.py --apply --source-templates` changed only `TimeIsTime.SpeedRate` from `1.0` to `15.0`. The same checker confirms `RDF.Expansion = 2`; the existing master-switch map confirms enabled Dynamic XP uses `Dynamic.XP.Rate = 1`. Source-template checks passed.
- **Core config audit:** verified the pinned `worldserver.conf.dist` currently has `MapUpdate.Threads = 1`, `EnablePlayerSettings = 0`, `DBC.EnforceItemAttributes = 1`, and `ActivateWeather = 1`. The requested four-value patch is tracked at `patches/azerothcore-worldserver-defaults.patch`; `git -C core apply --check --unidiff-zero ../patches/azerothcore-worldserver-defaults.patch` passed. The patch was **not applied** to the generated checkout.
- **Applicator/package tests:** Python syntax and JSON validation passed. A temporary runtime-config fixture verified the additional-settings runtime apply/check behavior. A temporary package fixture confirmed database/password/API-key values are redacted and active `.conf`, map/client data, and unrelated executables are omitted from the Windows zip.
- **SQL:** no database was supplied and **no SQL was run**. City Life's manual world SQL remains unapplied.

## Pending / not run

- **Personal core-fork commit:** the requested `worldserver.conf.dist` changes must be committed in `alterational/azerothcore-wotlk` on `Playerbot`. This session is restricted to committing/pushing only the build repository's Arena branch, so the core-fork commit was not made. `config/core-worldserver-defaults.json` records `pending_core_fork_commit`; `python3 scripts/check_core_defaults.py` verified the observed pinned defaults and reported the four target values still pending. The core pin must not be advanced until the user pushes that commit and records its new SHA. Then update that SHA in the manifest, lock, validator, config maps, and docs; module SHAs stay unchanged.
- **Codespace build:** the agent has no Codespace shell. Earlier Codespaces API calls returned HTTP 403 (`Resource not accessible by integration`); creation is explicitly prohibited. The user Codespace command `cd core && ./acore.sh install-deps && MTHREADS=4 ./acore.sh compiler all` was **not run**. No Linux build result is claimed.
- **Windows build/release:** `.github/workflows/windows-release.yml` has been added. It can compile the current pin for compatibility testing, but skips packaging/artifact upload until the core-fork commit is pinned. No Windows build, Actions artifact, or GitHub Release has passed or been published yet.
- **Runtime config:** no full build/install was run, so production-style active `env/dist/etc/*.conf` configuration was not available. No live runtime files or secrets were changed.

The exact patch application and Linux/Codespaces build commands are in [`docs/BUILD.md`](docs/BUILD.md). Do not treat source materialization or config-template checks as evidence of a successful compile, runtime test, database migration, or release.
