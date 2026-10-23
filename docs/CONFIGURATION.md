# Runtime module and server configuration

`modules.manifest.json` records 56 manifest-enabled and 14 initially runtime-off modules across 70 locked sources. The standard build selects 69 source checkouts: all 14 runtime-off modules remain compiled, while the optional `mod-individual-progression` source is omitted until explicitly requested. If Individual Progression is selected, its manifest state remains enabled and its reviewed config value is applied.

## Audited module maps

`config/module-switches.json` is the reviewed 70-module master-switch map: 52 source-verified switches, two approved upstream-default policies (City Life and Dungeon Clear), and 16 documented modules without an effective module-wide switch. It sets `Dynamic.XP.Rate = 1` for enabled Dynamic XP and now includes the authorized Junk to Gold fork's `JunkToGold.Enable = 1`. See [`MODULE_CONFIG_AUDIT.md`](../MODULE_CONFIG_AUDIT.md) for the full table.

`config/additional-module-settings.json` records two additional module settings:

- `RDF.Expansion = 2`: checked against the pinned template and source; this already is the upstream Wrath-of-the-Lich-King default and is not overridden.
- `TimeIsTime.SpeedRate = 1.0`: reviewed and left at the pinned upstream default, so no edit is applied. The OwnedCore post's `15` was rejected during review.

For the normal build, `python3 scripts/prepare_build.py` verifies that every pinned module `.conf.dist` still holds its audited upstream default; it never writes to a template, because public templates ship verbatim. `python3 scripts/prepare_build.py --runtime` then applies both maps to the installed active `.conf` files. The applicators use only tracked maps, preserve unrelated defaults, fail closed on unexpected values, and write atomically. Their `--check` modes remain available for a separate read-only audit; they are not necessary immediately after `--apply`. City Life remains enabled at `CityLife.Enable = 1`. The source/runtime module map retains Dungeon Clear's upstream `DungeonClear.Enable = 1`, but the separate Windows packaging map intentionally changes only the generated active package copy to `0`; its public `.conf.dist` is not modified. No SQL is run.

## Core authserver/worldserver source defaults

The active configs added to build-repository `main` at commit `46c86b8f52445cb2baaff183e77ca2dd62f622b8` were compared with the previous core pin `f19a18799a35f7c24bdcdc9ea399c601f166259b` and the pre-update `Playerbot` tip `8a4e76eac8c4ccebf547113afe7b51d6c3e91641`. The user committed the ten reviewed targets to the core fork; the current pin is `14c435031d2cb31b1af664af9a83c5d6256302b6`. The table's “previous default” column records the before-values:

| Source template | Setting | Previous default (`f19a187`) | Current source default | Reason |
|---|---|---|---|---|
| authserver | `Appender.Auth` | `2,5,0,Auth.log,w` | `2,5,8,Auth.log,w` | Timestamp auth log filenames (flag 8) |
| worldserver | `Appender.Server` | `2,5,0,Server.log,w` | `2,5,8,Server.log,w` | Timestamp server log filenames (flag 8) |
| worldserver | `Appender.Playerbots` | `2,5,0,Playerbots.log,w` | `2,5,8,Playerbots.log,w` | Timestamp Playerbots log filenames (flag 8) |
| worldserver | `Appender.Errors` | `2,2,0,Errors.log,w` | `2,2,8,Errors.log,w` | Timestamp error log filenames (flag 8) |
| worldserver | `MapUpdate.Threads` | `1` | `4` | OwnedCore thread recommendation |
| worldserver | `ActivateWeather` | `1` | `0` | Required by pinned Weather Vibe README |
| worldserver | `Die.Command.Mode` | `1` | `0` | Disable side effects from `.die` |
| worldserver | `DungeonFinder.OptionsMask` | `5` | `5` | Locked core already matches; normalize current Playerbot branch default 7 to retain dungeon finder and seasonal bosses while disabling raid browser |
| worldserver | `EnablePlayerSettings` | `0` | `1` | Required by pinned Individual Progression and Challenge Modes READMEs |
| worldserver | `DBC.EnforceItemAttributes` | `1` | `0` | Required by pinned Individual Progression README |

The config comparison also found path differences for `DataDir`, `LogsDir`, `TempDir`, `SourceDirectory`, and `MySQLExecutable`. These remain environment-specific runtime settings and are deliberately not promoted into shared source defaults. Database connection values were not changed. The two patch files preserve the reviewed source diff; the committed core templates at `14c435031d2cb31b1af664af9a83c5d6256302b6` already contain the targets, so they are not applied again during materialization. The maps record `pinned_in_core_fork`; `scripts/check_core_defaults.py --require-target` verifies both source templates before a build and can also check installed runtime configs.

The RDF expansion and Dynamic XP requests preserve pinned defaults; the only module-template value changed beyond master switches is TimeIsTime's speed rate. Do not adjust other upstream defaults.

## How AzerothCore loads module configs

The pinned core builds active module config names from `core/modules/CMakeLists.txt`; `worldserver` passes them to `ConfigMgr::Configure`, and `ConfigMgr::LoadModulesConfigs` reads them from `<CONF_DIR>/modules/`. On Linux, `acore.sh compiler all` installs the `.conf.dist` files under `env/dist/etc/modules` and copies missing `.conf` runtime files with the default `AC_ENABLE_CONF_COPY_ON_INSTALL=1`. On Windows, the pinned core's CMake install rules put server executables directly under `env/dist` and config templates under `env/dist/configs/modules`; use that platform-specific path when checking installed runtime configs.

## Active configs in the Windows package

`scripts/package_runtime.py` copies each installed public `.conf.dist` into the package's `configs/` directory unchanged, then creates a sibling `.conf` from the same bytes. It applies package-only changes afterward, leaving the `.conf.dist` untouched. The single editable map is [`config/package-config-edits.json`](../config/package-config-edits.json), whose paths are relative to package `configs/`; add entries there for `authserver.conf`, `worldserver.conf`, or a `modules/<filename>.conf` target. The package root itself holds only `authserver.exe`, `worldserver.exe`, the four staged runtime DLLs, `configs/`, and the portable `mysql/` tree; the old `bin/` + `etc/` layout is gone.

A missing target file or key, duplicate key, unreadable file, or incompatible value type produces a line in this form:

```text
WARNING: couldn't apply config edit for: modules/mod_ahbot.conf, key AuctionHouseBot.EnableSeller 0 true
```

The edit is skipped without inserting a new key or coercing a boolean to a number (or the reverse). Warnings are non-fatal: they do not fail compilation or stop archive creation. This packaging map is intentionally separate from source-template/runtime module policy; for example, it can override the active package copy without changing the checked source defaults.

The package map also rewrites the core runtime locations so the package is self-contained: `authserver.conf` gets `LogsDir`, `SourceDirectory`, `MySQLExecutable`, and `TempDir`, and `worldserver.conf` gets those plus `DataDir`, all as quoted paths relative to the package root (`"logs"`, `"data"`, `"temp"`, `"source/azerothCore"`, `"mysql/bin/mysql.exe"`), where the portable `mysql/` tree actually ships. The `.conf.dist` files keep their pinned upstream values for those keys.

Module master-switch entries in this map are the reviewed shipped state. Where a shipped value differs from `modules.manifest.json`, the value must be the audited upstream default; `scripts/validate_project.py` rejects anything else and prints every such override (currently CFBG, BGQueueChecker, Breaking News, AOE Loot, and PvP Titles). Entries whose value already matches upstream are harmless no-ops that document the intended state.

After a successful build/install, apply and verify all build-repository runtime settings from the repository root with one command:

```bash
python3 scripts/prepare_build.py --runtime
```

On Linux, the default active directory is `core/env/dist/etc`. On Windows, use `python scripts/prepare_build.py --runtime --config-dir core/env/dist/configs` to match the pinned core's CMake install layout; the Windows workflow does this explicitly. Pass `--config-dir <path>` for any other nondefault `CONFDIR`. The `--runtime` mode applies both reviewed settings maps and checks core defaults. For a read-only audit instead, invoke the lower-level applicators with `--check`.

## Decisions and limits

- All 14 initially runtime-off module sources remain in the standard build and are compiled even with their master switches set to `0`. Individual Progression is separate: it is not checked out/compiled in the standard build, and its source is included only on explicit opt-in. A config switch alone never substitutes for omitting or adding the source.
- City Life stays enabled at its pinned default `CityLife.Enable = 1`. Dungeon Clear remains included, manifest-enabled, and enabled at its upstream default `DungeonClear.Enable = 1` in both the generated active `.conf` and the `.conf.dist`.
- Modules with no master switch are documented instead of receiving invented keys. The package map edits only the existing numeric AHBot keys `AuctionHouseBot.EnableSeller = 1` and `AuctionHouseBot.ItemsPerCycle = 100`; it does not invent optional capacity/buyer/GUID/expiry keys absent from the pinned template.
- Other prerequisites and setup are described in the pinned module READMEs and [`SQL_SETUP.md`](SQL_SETUP.md). They do not justify changing unspecified config defaults.
- No credentials or server-specific active `.conf` files belong in Git. No database or SQL operation is performed by these scripts.
