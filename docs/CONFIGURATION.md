# Runtime module and server configuration

`modules.manifest.json` is the module target state: 56 sources enabled and 14 initially disabled. All 70 remain installed in `core/modules`; runtime-off does not omit a source from CMake or the build.

## Audited module maps

`config/module-switches.json` is the reviewed 70-module master-switch map: 51 source-verified switches, two approved upstream-default policies (City Life and Dungeon Clear), and 17 documented modules without an effective module-wide switch. It sets `Dynamic.XP.Rate = 1` for enabled Dynamic XP. See [`MODULE_CONFIG_AUDIT.md`](../MODULE_CONFIG_AUDIT.md) for the full table.

`config/additional-module-settings.json` records two additional module settings:

- `RDF.Expansion = 2`: checked against the pinned template and source; this already is the upstream Wrath-of-the-Lich-King default and is not overridden.
- `TimeIsTime.SpeedRate = 15.0`: changes the pinned `1.0` default so one in-game day takes 96 real minutes, as requested from the OwnedCore post.

Apply/check module templates after materializing sources and before compilation:

```bash
python3 scripts/apply_module_config.py --apply --source-templates
python3 scripts/apply_additional_settings.py --apply --source-templates
python3 scripts/apply_module_config.py --check --source-templates
python3 scripts/apply_additional_settings.py --check --source-templates
```

Both applicators use only tracked maps, preserve unrelated defaults, fail closed on unexpected values, and write atomically. City Life remains enabled at `CityLife.Enable = 1`; Dungeon Clear remains enabled at `DungeonClear.Enable = 1`. No SQL is run.

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

After a successful build/install, apply/check runtime configs from the build-repository root:

```bash
python3 scripts/apply_module_config.py --apply
python3 scripts/apply_additional_settings.py --apply
python3 scripts/check_core_defaults.py --runtime --require-target
python3 scripts/apply_module_config.py --check
python3 scripts/apply_additional_settings.py --check
```

On Linux, the default active directory is `core/env/dist/etc`. On Windows, use `--config-dir core/env/dist/configs` to match the pinned core's CMake install layout; the Windows workflow does this explicitly. Pass `--config-dir <path>` for any other nondefault `CONFDIR`. Runtime applicators patch only their reviewed assignments and preserve unrelated settings. Missing files or changed upstream values fail instead of being silently guessed.

## Decisions and limits

- All 70 module sources are compiled even when their runtime master switch is set to `0`.
- **Dungeon Clear stays enabled** at `DungeonClear.Enable = 1`; its duplicate disabled entry was stale. **City Life stays enabled** at its pinned default `CityLife.Enable = 1`.
- Modules with no master switch are documented instead of receiving invented keys. AHBot seller/buyer toggles stay at their upstream `0` defaults.
- Other prerequisites and setup are described in the pinned module READMEs and [`SQL_SETUP.md`](SQL_SETUP.md). They do not justify changing unspecified config defaults.
- No credentials or server-specific active `.conf` files belong in Git. No database or SQL operation is performed by these scripts.
