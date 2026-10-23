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

Junk to Gold is separately pinned to the user-provided `alterational/mod-junk-to-gold` commit `994797eaf7d010e88d3c27f962518d385f31314b`. The previous candidate failed on two `PlayerScript` callback names; this follow-up renames them to the pinned core API while retaining the matching config and `JunkToGold.Enable` switch. That pin is part of the verified build described below.

The module configuration commands run before compilation only to verify that every pinned module `.conf.dist` still holds its audited upstream default; they never write to a template, because public templates ship verbatim and policy belongs in the active `.conf` files. On Linux, runtime configuration is under `core/env/dist/etc`; on Windows, the pinned core installs templates under `core/env/dist/configs`. Pass `--config-dir <path>` when using a non-default runtime config location.

## Windows build and publication

`.github/workflows/windows-release.yml` runs on pull requests into `main` or `rebuild-897a41c`, manual dispatch, and `v*` tags. It uses `windows-latest`, Ninja/MSVC, `RelWithDebInfo`, `MTHREADS=4`, precompiled headers, and the core-default gate before dependency setup or compilation. Dependencies are pinned explicitly: Boost **1.92.0** prebuilt MSVC 14.3 x64 from `C:\local\boost_1_92_0` (installer SHA-256 verified, `version.hpp` checked for `BOOST_VERSION 109200` / `BOOST_LIB_VERSION "1_92"`), and portable MySQL **8.4.11** from `C:\tools\mysql\current` (dynamic `lib\libmysql.lib` plus `lib\libmysql.dll`; the provisioning marker `.mysql-version`, the `mysql_version.h` version ID `80411`, and the DLL file/product version must all report 8.4.11). The core is configured with explicit `-DMYSQL_ROOT_DIR`, `-DMYSQL_INCLUDE_DIR`, `-DMYSQL_LIBRARY`, and `-DMYSQL_EXECUTABLE` options, and the build `CMakeCache.txt` is verified for `RelWithDebInfo`, the Boost 1.92.0 MSVC 14.3 selection, and those MySQL paths.

Boost 1.92.0 derives its auto-link toolset tag from `_MSC_VER`: anything below `1950` requests `vc143`, while newer images default to a 14.5x compiler that requests `vc145` — a library the MSVC 14.3 binary package does not contain, which fails the link with `LNK1104`. The workflow therefore selects an installed 14.3/14.4-generation MSVC toolset when one is present and always builds with `CL=-DBOOST_ALL_NO_LIB`, so the explicit CMake Boost libraries (verified to be the `-vc143-` set) are authoritative instead of a header-generated pragma. A short compile-and-link probe uses the selected toolset before the full build, so a toolset/auto-link mismatch fails in about a minute instead of after a multi-hour compile. The bash build step must use the `-D` define spelling: MSYS rewrites a leading `/` option into a Windows path before `cl` sees it. Pull-request, push, and tag builds use the 69-source default profile. Manual dispatch has an unchecked `Include Individual Progression` option; when selected, the artifact receives a distinct name and is not eligible for publication as the standard release.

The workflow applies the two guarded core compatibility patches, applies and checks build/runtime module configuration, verifies `authserver.exe` and `worldserver.exe` in the install prefix, checks installed runtime configuration, and uploads the package only after success. `scripts/stage_windows_runtime_dlls.py` then runs `dumpbin /DEPENDENTS` recursively over both executables and stages exactly `libmysql.dll` (from the MySQL `lib` directory), `libcrypto-3-x64.dll`, `libssl-3-x64.dll` (from the OpenSSL `bin` directory), and the OpenSSL `legacy.dll` provider into `core/env/runtime-dlls`; debug, Boost, VC++ runtime, missing, or additional private DLLs fail the step, and the staging inventory is written outside the staging tree. The provider directory is resolved as `lib/ossl-modules`, `ossl-modules`, `bin/ossl-modules`, and finally `bin` itself: the runner image installs OpenSSL with the SLProWeb `copytobin` task, which flattens `legacy.dll` into `bin` and ships no `lib/ossl-modules` directory.

The package is assembled by `scripts/package_runtime.py` with a root-level layout: `authserver.exe`, `worldserver.exe`, exactly those four DLLs, `configs/` (unchanged `.conf.dist` templates plus generated active `.conf` copies, including `configs/modules/`), and the portable MySQL 8.4.11 tree under `mysql/`. There is no `bin/` or `etc/` directory, and no `README.txt`, `SOURCE-PINS.json`, or DLL inventory is written into the package. The MySQL `.mysql-version` provisioning marker and any downloaded archive are excluded. In the config step, each public `.conf.dist` is copied byte-for-byte and gets a sibling `.conf` copy; only the edits in [`config/package-config-edits.json`](../config/package-config-edits.json) are applied to those active copies. That map also sets the core runtime locations (`DataDir`, `LogsDir`, `TempDir`, `SourceDirectory`, `MySQLExecutable`) to paths relative to the package root so the bundled `mysql/` tree is used, while the `.conf.dist` files keep their pinned values. Module `.conf.dist` templates are never edited by any step: the pre-build configuration commands only verify that each pinned template still holds its audited upstream default. The map can target module files as well as `authserver.conf` and `worldserver.conf`. Missing files/keys, duplicate keys, unreadable files, or value-type mismatches emit `WARNING: couldn't apply config edit...` and do not fail compilation or packaging. `CTOOLS_BUILD=none` omits utility executables that are not part of this runtime package.

The build job uploads the unpacked package staging contents (`runtime-package/azerothcore-ownedcore-windows/**`), so the Actions artifact is one ZIP whose root directly holds the release files. A `verify-artifact` job then downloads that artifact and runs `scripts/verify_package_layout.py` against the unpacked root, which fails the run if the upload kept the staging-folder prefix or if any required file is missing. That job reports the entry count, root files, root DLLs, per-directory counts, and a manifest SHA-256 over the sorted entry list, so an artifact can be fingerprinted without downloading it. The tagged Release job downloads that artifact into a clean directory, rebuilds a single `azerothcore-ownedcore-windows.zip` from the package root with `scripts/assemble_release_zip.py`, verifies the namelist (root executables and exactly four DLLs, `configs/`, `mysql/`, no staging-folder prefix, no `bin/`/`etc/`, no nested ZIP), and only then publishes it. A local inspection ZIP may also be written beside the staging tree for debugging; it is never uploaded.

A versioned GitHub Release is published only after a successful no-Individual-Progression tag build; pull-request runs therefore skip that job. Windows run [39590419188](https://github.com/alterational/azerothcore-ownedcore/actions/runs/39590419188) at commit `2b4cca7` passed every other step for the default profile — provisioning gates, clean build directory, `RelWithDebInfo` configuration, full compile/install, CMake verification, config staging, four-DLL staging, packaging, upload, and the artifact check — producing a 440-entry artifact whose manifest SHA-256 is `23cd0f9b…3b36ae52`. No server startup smoke test has been run. See [CHECKOUT_REPORT.md](../CHECKOUT_REPORT.md) for the evidence table and for the failures that shaped each rule above.

## Data and database safety

The package excludes client/game data, maps, vmaps/mmaps, SQL, database dumps, and machine-specific active `.conf` files. It includes public pinned `.conf.dist` templates unchanged and generated active `.conf` copies derived from them; do not put server-specific credentials in the packaging edit map or public templates. Private deployment credentials belong only in ignored, server-specific configs. City Life's world SQL is a manual migration and is never applied by these scripts. Review backups and database authorization before any server startup or updater run.
