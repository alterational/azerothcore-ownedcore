# Build and Codespaces

## What validation does

`.github/workflows/validate.yml` checks manifest/lock consistency, configuration maps, Python syntax, and JSON syntax. It does not fetch sources, compile, start a server, or modify a database.

The Codespaces `postCreateCommand` validates and materializes the pinned core and the 69 default-build module sources, checks the selected checkouts against the lock, applies/checks the two core compatibility patches, applies/checks module configuration defaults, and verifies the pinned core configuration. It does not install system dependencies, compile, start a server, or run SQL. Existing Codespaces do not rerun `postCreateCommand`; update the build-repository checkout and run the preparation commands below, or rebuild the container.

## Core configuration and compatibility

The reviewed authserver/worldserver source defaults are committed in the user's core fork `alterational/azerothcore-wotlk`, branch `Playerbot`, at `14c435031d2cb31b1af664af9a83c5d6256302b6`. Read-only checks confirmed all ten target values in the pinned `.conf.dist` files. Machine-specific paths and database connection settings are not copied.

`python3 scripts/check_core_defaults.py --require-target` is the pre-build gate. The patches under `patches/azerothcore-*-defaults.patch` document defaults already committed to the fork; do not apply them again.

Two Windows compatibility patches are guarded to core SHA `14c435031d2cb31b1af664af9a83c5d6256302b6` and modify only the ignored materialized checkout:

- Ninja/MSVC configuration-path handling in `core/modules/CMakeLists.txt`.
- Cygwin install dispatch in `apps/compiler/includes/functions.sh`, so `cmake --install` runs when the Windows runner reports `Platform: cygwin`.

`scripts/apply_core_compatibility_patches.py` applies and checks these core-only patches. No module-specific compatibility overlays are required: the known module fixes are included in the five user-fork pins listed in [MODULES.md](../MODULES.md).

## Prepare a Linux/Codespaces build

Use the user's Codespace or a comparable Linux machine. The build environment is configured for four CPU cores and 16 GB RAM. From the repository root, prepare the default source set with one command:

```bash
python3 scripts/prepare_build.py
```

Only when Individual Progression is explicitly requested, use `python3 scripts/prepare_build.py --include-module mod-individual-progression` instead. The preparation command validates the project and selected checkout, materializes pinned sources, applies and verifies core/module configuration, and checks the core defaults before any build dependencies or compilation.

The lower-level `--check` modes remain available for a read-only audit when you do not want to change files. They do not need to be run immediately after `--apply`: the apply paths now verify their writes themselves, and the core patch applicator verifies each applied patch.

To build and install after preparation:

```bash
cd core
./acore.sh install-deps
MTHREADS=4 ./acore.sh compiler all
cd ..
```

After installation, apply and verify runtime settings with one command:

```bash
python3 scripts/prepare_build.py --runtime
```

On Windows, add `--config-dir core/env/dist/configs`. This mode applies both reviewed runtime maps and verifies the installed core defaults. Lower-level `--check` modes remain available for a separate read-only audit.

`compiler all` performs a clean, configure, compile, and install using the pinned `acore.sh`. The agent must not create or launch a Codespace for the user. Record actual exit codes and results in [CHECKOUT_REPORT.md](../CHECKOUT_REPORT.md); source materialization and config checks alone are not build evidence.

## Materialized sources and configuration

`materialize.py` shallow-clones the locked core and selected modules. The default selection includes 69 modules (all 14 runtime-off modules included) and omits only `mod-individual-progression`. When switching back to the default profile, it removes an existing optional checkout only if it is a clean Git checkout at the exact locked SHA; modified or unrecognized directories are preserved.

The compatibility-sensitive module fixes are in the locked commits of the user's forks:

| Module | Fork commit | Fix included in source |
|---|---|---|
| BGQueueChecker | `c01d43ea8b69219339eb434c42dd22f34cf11b8c` | Battleground queue hook |
| mod-aoe-loot | `7a921027ff6c58f9b6c905a3d3f4d966dcbc9994` | Packet signature and `::Item` qualification |
| mod-challenge-modes | `a48a4d4ae6082a54647a2524f239a86a8ac16ccb` | `OnPlayerResurrect` signatures |
| mod-dead-means-dead | `47fd15fb0c80e2e7ce36ba0b3188fcd3cb78e853` | `OnPlayerLogin` hook |
| mod-player-bot-level-brackets | `0c9187fa05eecde09c6b89653350d0edf34eced2` | Playerbots persistence config field |

Junk to Gold is separately pinned to the user-provided `alterational/mod-junk-to-gold` commit `994797eaf7d010e88d3c27f962518d385f31314b`. The previous candidate failed on two `PlayerScript` callback names; this follow-up renames them to the pinned core API while retaining the matching config and `JunkToGold.Enable` switch. Confirm the correction with the full build.

The module configuration commands run before compilation so generated `.conf.dist` templates match tracked policy. On Linux, runtime configuration is under `core/env/dist/etc`; on Windows, the pinned core installs templates under `core/env/dist/configs`. Pass `--config-dir <path>` when using a non-default runtime config location.

## Windows build and publication

`.github/workflows/windows-release.yml` runs on pull requests, manual dispatch, and `v*` tags. It uses `windows-latest`, Ninja, Release mode, `MTHREADS=4`, precompiled headers, and the core-default gate before dependency setup or compilation. Pull-request, push, and tag builds use the 69-source default profile. Manual dispatch has an unchecked `Include Individual Progression` option; when selected, the artifact receives a distinct name and is not eligible for publication as the standard release.

The workflow applies the two guarded core compatibility patches, applies and checks build/runtime module configuration, verifies `authserver.exe` and `worldserver.exe` in the install prefix, checks installed runtime configuration, analyzes/stages runtime DLL dependencies, and uploads the package only after success. In the package step, each public `.conf.dist` is copied byte-for-byte and gets a sibling `.conf` copy; only the edits in [`config/package-config-edits.json`](../config/package-config-edits.json) are applied to those active copies. The map can target module files as well as `authserver.conf` and `worldserver.conf`. Missing files/keys, duplicate keys, unreadable files, or value-type mismatches emit `WARNING: couldn't apply config edit...` and do not fail compilation or packaging. The Windows install puts server executables directly under `core/env/dist` and config templates under `core/env/dist/configs`. The package has no `bin/` directory: `authserver.exe`, `worldserver.exe`, and validated runtime DLLs sit at its root; templates and generated active configs are under `etc/`, with module configs under `etc/modules/`.

The runtime stage uses `dumpbin /DEPENDENTS` recursively on both release executables and their resolved DLLs. It takes `libmysql.dll` from MySQL 8.4.10's `lib/` directory and resolves its actual transitive dependencies from MySQL's `bin/`; OpenSSL's linked DLLs are resolved from the selected OpenSSL install, while `legacy.dll` is seeded explicitly because it is dynamically loaded. The release x64 VC++ runtime DLLs are app-local; any manifest supplied with that redist directory is copied. Boost DLLs and debug variants are excluded. Unresolved non-Windows imports fail the stage instead of producing a potentially incomplete archive. `RUNTIME-DLLS.json` records the resulting inventory. `CTOOLS_BUILD=none` omits utility executables that are not part of this runtime package.

A versioned GitHub Release is published only after a successful no-Individual-Progression tag build. Do not claim a build, artifact, or release as current until its complete Actions workflow succeeds. Historical Windows run `39123849901` successfully built the then-current default profile before the Junk to Gold pin change, but its package step blanked 30 public config values. The local package code now preserves templates, generates active copies, and applies the tracked package edit map; a fresh Windows run must validate the newly pinned Junk to Gold source and corrected package before using or releasing an artifact. See [CHECKOUT_REPORT.md](../CHECKOUT_REPORT.md) for the current verification boundary.

## Data and database safety

The package excludes client/game data, maps, vmaps/mmaps, SQL, database dumps, and machine-specific active `.conf` files. It includes public pinned `.conf.dist` templates unchanged and generated active `.conf` copies derived from them; do not put server-specific credentials in the packaging edit map or public templates. Private deployment credentials belong only in ignored, server-specific configs. City Life's world SQL is a manual migration and is never applied by these scripts. Review backups and database authorization before any server startup or updater run.
