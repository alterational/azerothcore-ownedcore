# Runtime module and server configuration

`modules.manifest.json` is the module target state: 52 sources enabled and 14 initially disabled. All 66 remain installed in `core/modules`; runtime-off does not omit a source from CMake or the build.

## Audited module maps

`config/module-switches.json` is the reviewed 66-module master-switch map: 48 source-verified switches, two approved upstream-default policies (City Life and Dungeon Clear), and 16 documented modules without an effective module-wide switch. It sets `Dynamic.XP.Rate = 1` for enabled Dynamic XP. See [`MODULE_CONFIG_AUDIT.md`](../MODULE_CONFIG_AUDIT.md) for the full table.

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

## Core worldserver defaults belong in the core fork

The core configuration lives at `src/server/apps/worldserver/worldserver.conf.dist`. Its pinned SHA currently has these upstream values:

| Setting | Current pinned value | Required value | Reason |
|---|---:|---:|---|
| `MapUpdate.Threads` | `1` | `4` | OwnedCore thread recommendation |
| `EnablePlayerSettings` | `0` | `1` | Required by pinned Individual Progression and Challenge Modes READMEs |
| `DBC.EnforceItemAttributes` | `1` | `0` | Required by pinned Individual Progression README |
| `ActivateWeather` | `1` | `0` | Required by pinned Weather Vibe README |

The exact core patch is [`patches/azerothcore-worldserver-defaults.patch`](../patches/azerothcore-worldserver-defaults.patch). It must be applied and committed to `alterational/azerothcore-wotlk` on `Playerbot`. The ignored generated core checkout has not been edited. `config/core-worldserver-defaults.json` records the pending state; `scripts/check_core_defaults.py` verifies the current pin and, after the fork commit and core-SHA update, requires the target values. The Windows workflow uses `--require-target` and will not build/package the stale core pin.

The RDF expansion and Dynamic XP requests preserve pinned defaults; the only module-template value changed beyond master switches is TimeIsTime's speed rate. Do not adjust other upstream defaults.

## How AzerothCore loads module configs

The pinned core builds active module config names from `core/modules/CMakeLists.txt`; `worldserver` passes them to `ConfigMgr::Configure`, and `ConfigMgr::LoadModulesConfigs` reads them from `<CONF_DIR>/modules/`. `acore.sh compiler all` installs the `.conf.dist` files under `env/dist/etc/modules` and copies missing `.conf` runtime files on Linux with the default `AC_ENABLE_CONF_COPY_ON_INSTALL=1`.

After a successful build/install, apply/check runtime configs from the build-repository root:

```bash
python3 scripts/apply_module_config.py --apply
python3 scripts/apply_additional_settings.py --apply
python3 scripts/check_core_defaults.py --runtime --require-target
python3 scripts/apply_module_config.py --check
python3 scripts/apply_additional_settings.py --check
```

The default active directory is `core/env/dist/etc`; pass `--config-dir <path>` when using a custom `CONFDIR`. Runtime applicators patch only their reviewed assignments and preserve unrelated settings. Missing files or changed upstream values fail instead of being silently guessed.

## Decisions and limits

- All 66 module sources are compiled even when their runtime master switch is set to `0`.
- **Dungeon Clear stays enabled** at `DungeonClear.Enable = 1`; its duplicate disabled entry was stale. **City Life stays enabled** at its pinned default `CityLife.Enable = 1`.
- Modules with no master switch are documented instead of receiving invented keys. AHBot seller/buyer toggles stay at their upstream `0` defaults.
- Other prerequisites and setup are described in the pinned module READMEs and [`SQL_SETUP.md`](SQL_SETUP.md). They do not justify changing unspecified config defaults.
- No credentials or server-specific active `.conf` files belong in Git. No database or SQL operation is performed by these scripts.
