# Runtime module enablement

`modules.manifest.json` is the target state: 52 module sources enabled, 14 initially disabled. All 66 remain installed in `core/modules`; runtime-off does not omit a source from CMake or the build. Upstream `.conf.dist` defaults can differ from the manifest.

## Audited map and load path

`config/module-switches.json` is the reviewed 66-module mapping. It contains 48 source-verified master switches, two approved upstream-default policies (City Life and Dungeon Clear), and 16 documented cases with no effective module-wide switch. Each switch was checked in its pinned `.conf.dist` and referenced by pinned C++ source. Subfeature toggles are deliberately not changed. See [`MODULE_CONFIG_AUDIT.md`](../MODULE_CONFIG_AUDIT.md) for the complete key/default/target/code-reference table.

The pinned core loads module settings from active `.conf` files, not an arbitrary overlay fragment: `core/modules/CMakeLists.txt` constructs `CONFIG_FILE_LIST` from each module’s `conf/*.conf.dist`; `worldserver` passes it to `ConfigMgr::Configure` in `core/src/server/apps/worldserver/Main.cpp`; `ConfigMgr::LoadModulesConfigs` reads the selected names from `<CONF_DIR>/modules/`. The pinned `acore.sh compiler all` install path installs the templates under `env/dist/etc/modules` and, by default (`AC_ENABLE_CONF_COPY_ON_INSTALL=1`), copies missing `.conf.dist` files to active `.conf` files.

## Prepare module defaults before compilation

AzerothCore does not keep all module switches in one `worldserver.conf.dist`. Each module has its own `conf/<name>.conf.dist` under `core/modules/<module-id>/`; the core installs active files under `env/dist/etc/modules/` and loads them from there. After fetching sources and before the first build, run from the repository root:

```bash
python3 scripts/apply_module_config.py --apply --source-templates
python3 scripts/apply_module_config.py --check --source-templates
```

This patches only the audited master assignments in the generated, ignored `core/modules/*/conf/*.conf.dist` source tree. It preserves all other module defaults, is idempotent, and writes atomically. It does not change files in `worldserver.conf.dist`, invented keys, or subfeature switches. City Life and Dungeon Clear remain at their upstream `1` defaults. Re-run after every fresh materialization; the script and reviewed mapping are the reproducible record of the edits.

## Apply after build/install

Fresh installs copy template values into active runtime configs. If active configs already exist, or you want a final verification after install, run from the repository root:

```bash
python3 scripts/apply_module_config.py --apply
python3 scripts/apply_module_config.py --check
```

The default active config directory is `core/env/dist/etc` (with module configs under `modules/`). If the build uses a custom `CONFDIR`, pass it explicitly, for example `python3 scripts/apply_module_config.py --apply --config-dir /srv/azerothcore/etc`. The runtime mode preflights the audited template and active values, patches only mapped master assignments in active `.conf` files, preserves unrelated content, is idempotent, and writes changes atomically. `--check` does not write anything.

If the active `.conf` files are absent, follow the pinned core compiler/install procedure or copy each matching `.conf.dist` to `.conf` in the active `modules/` directory, then run the script. A missing/duplicate setting, unexpected pinned template default, or incorrect City Life/Dungeon Clear value fails closed. The actual `env/dist/etc` runtime files are not present until the core is built/installed; this checkout has not applied changes to a live runtime directory.

## Decisions and limitations

- `BGQueueChecker.Enable`, `BreakingNews.Enable`, and `PvPTitles.Enable` ship at `0` but are set to `1` for intended-enabled modules. Twelve initially-disabled modules ship at `1` and are set to `0`; two more already default to `0`. The exact mapping is in the audit.
- **Dungeon Clear stays enabled** at `DungeonClear.Enable = 1`, with no override. **City Life stays enabled** at `CityLife.Enable = 1`, with no override.
- Modules with no master switch are still compiled; the map records them instead of inventing a key. AHBot’s separate seller/buyer role toggles remain at their upstream `0` defaults. `ReagentBank.Enable` appears in the template but is not read by pinned module C++ and is not treated as an operative master switch.
- Some modules require settings in core `worldserver.conf`, client files, services, or game setup. Those are separate from the module-master overlay and must be reviewed before operating a server: City Life and Playerbots, Individual Progression/Challenge Modes Player Settings, Weather Vibe weather control, Fly Anywhere client/server DBC, and optional Ollama service. See [`SQL_SETUP.md`](SQL_SETUP.md) and the pinned module READMEs.
- No credentials or server-specific `.conf` files belong in Git; the runtime paths are ignored.
