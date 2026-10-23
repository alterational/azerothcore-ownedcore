# Agent handoff

- **Updated:** 2026-10-20
- **Repository:** `alterational/azerothcore-ownedcore`
- **Integration/base branch:** `rebuild-897a41c`, clean base commit `897a41cf13191bd954c5731bfc3128bf966cdbf2`
- **Session working branch:** `arena/06c5561d-azerothcore-ownedcore`, created from `rebuild-897a41c`
- **Pull-request target:** `rebuild-897a41c`
- **Historical/backup only:** `arena/01a106ef-azerothcore-ownedcore` and PR #1. They are not the active session branch or pull request and must not be merged, closed, or reused in this task.

## Original purpose and OwnedCore reference baseline

The original goal came from the OwnedCore release thread **“AzerothCore WotLK Repack Playerbots Individual Progression 32 other modules”**: <https://www.ownedcore.com/forums/world-of-warcraft/world-of-warcraft-emulator-servers/wow-emu-general-releases/1040387-azerothcore-wotlk-repack-playerbots-individual-progression-32-other-modules.html>.

The build repository began as a separate, initially empty repository—not as a branch of the Playerbots core. The intended work was to reconstruct the selected repack profile from source, rather than copy a binary release: identify the core and module sources, determine the modules/settings that are enabled or disabled, review the default `authserver`/`worldserver` config templates, and compare the resulting runtime package with the supplied binary/config references. Completion of that original comparison by earlier agents has not been verified; do not assume exact parity with the repack.

The original source reference was the Playerbots core at <https://github.com/mod-playerbots/azerothcore-wotlk/tree/Playerbot>. The current authoritative source for this build is the user's fork, `alterational/azerothcore-wotlk.git`, branch `Playerbot`, pinned at `14c435031d2cb31b1af664af9a83c5d6256302b6`. Keep that immutable pin unless the user explicitly authorizes a change.

### MEGA binary/config comparison references

The user supplied these binary release references and October 5 updates:

| Reference profile | Base release | October 5 update |
|---|---|---|
| Without Individual Progression | <https://mega.nz/file/RFYwmAoD#QQuavHJh7XjPMv-HhQpJnQxMVcO_c0tyKVtWEnjvajM> | <https://mega.nz/file/0dADmLZL#njMmwQpipEcUxyALYM0xC7IZuQkZ-Wi9dfjpvI46TWU> |
| With Individual Progression | <https://mega.nz/file/ZMgmADzR#K21c0YnK0CG_eLbYoDMZFHJHbboHzw84bC6sRdWgoTM> | <https://mega.nz/file/tE5ATRTR#CgrY5aupd6RlER_WE1xiW0acY6uO7nai9y6GGYKKAT8> |

The user described these repacks as containing server binaries/configs, module configs, and MySQL setup with automatic database population. Treat them as **comparison references only**: they are not the source of truth for repository pins, and their binaries, databases, SQL, credentials, and game/client data must not be imported into this source build. The repository does not run SQL or migrations automatically; City Life's world SQL remains a manual operation. Do not claim the build reproduces the referenced MySQL/repack behavior unless that has been separately specified and verified.

Individual Progression is a compile-time source-profile choice, not a module that can be reliably switched off merely by changing runtime config after compilation. The current ordinary profile excludes it; add it only on explicit user request. If the user asks for a repack comparison or an artifact and the desired profile is ambiguous, ask whether they mean the with- or without-Individual-Progression variant. Never label an artifact's profile ambiguously.

## Project and build profile

This repository tracks a reproducible build of the user's AzerothCore Playerbots fork and the selected OwnedCore module set. The ordinary build selects the 69 non-Individual-Progression sources, including all 14 modules initially runtime-off. Those runtime-off modules are still materialized and compiled; runtime-off does not mean source-excluded. Individual Progression remains pinned/enabled but is excluded from the default source build and can be included only by explicit opt-in.

The core pin is `alterational/azerothcore-wotlk.git`, branch `Playerbot`, commit `14c435031d2cb31b1af664af9a83c5d6256302b6`. Its committed authserver/worldserver defaults are checked by `scripts/check_core_defaults.py --require-target`.

## User requirements

- Work only on the session working branch created from `rebuild-897a41c`. Never push to `rebuild-897a41c`, `main`, or `arena/01a106ef-azerothcore-ownedcore`, never create or rename another branch, and never merge or close PR #1 or the session pull request without separate approval. Do not commit or push unless the user asks.
- Preserve the core pin and all other module pins unless the user supplies a replacement commit.
- Five user-maintained module forks contain the known compatibility fixes:

  | Module | Branch | Commit | Fix included in source |
  |---|---|---|---|
  | BGQueueChecker | `master` | `c01d43ea8b69219339eb434c42dd22f34cf11b8c` | Battleground queue hook |
  | mod-aoe-loot | `main` | `7a921027ff6c58f9b6c905a3d3f4d966dcbc9994` | Packet signature and `::Item` qualification |
  | mod-challenge-modes | `master` | `a48a4d4ae6082a54647a2524f239a86a8ac16ccb` | `OnPlayerResurrect` `bool&` signatures |
  | mod-dead-means-dead | `main` | `47fd15fb0c80e2e7ce36ba0b3188fcd3cb78e853` | `OnPlayerLogin` hook |
  | mod-player-bot-level-brackets | `main` | `0c9187fa05eecde09c6b89653350d0edf34eced2` | `EquipAndSpecPersistence` field spelling |

- Separately, the user supplied `mod-junk-to-gold` at `https://github.com/alterational/mod-junk-to-gold`, commit `994797eaf7d010e88d3c27f962518d385f31314b`, to supply the matching `JunkToGold` config template and rename its callbacks to the pinned core's `PlayerScript` API. The first candidate commit failed Windows compilation on those callback names; the follow-up pin compiles, stages its template, and is part of the verified build below.
- The five known module compatibility fixes are in those fork commits. **There are no module-specific overlay patch files or patch steps.** Do not recreate module patches for these fixes. Do not change any other source pin without explicit authorization.
- Keep the inventory at 70 repositories: 55 enabled, 15 runtime-off. All remain pinned/installable; the default source build selects 69 non-Individual-Progression modules. Individual Progression is the only source opt-in.
- City Life remains enabled. Dungeon Clear remains present/manifest-enabled in the build source set and ships at its upstream default `DungeonClear.Enable = 1` in both the generated active `.conf` and the public `.conf.dist`. Learn Spells must remain `https://github.com/azerothcore/mod-learn-spells`.
- Never run SQL or apply database migrations. City Life's world SQL is manual.
- The user creates and runs their own Codespace; do not create or launch one. Keep Windows builds at `MTHREADS=4` unless measured evidence and the user approve otherwise.
- Do not commit generated `core/`, client/game data, maps, vmaps/mmaps, dumps, secrets, credentials, or machine-specific active configs. Never call an artifact or release final until the full workflow succeeds.
- Public `.conf.dist` templates are part of the deliverable and must be copied byte-for-byte. Do not blank, redact, or rewrite their public defaults (including database or key-looking values). During Windows packaging, create each active `.conf` as a byte-identical sibling first, then apply only `config/package-config-edits.json` to the `.conf` copies. Never include installed machine-specific active configs. Missing files/keys and type mismatches emit the requested WARNING and must not fail compilation or packaging; never invent a missing key.
- The user works from a phone and cannot use Git CLI. Do not delegate repository operations or ask for CLI commands.
- The Windows workflow uses `cancel-in-progress: true`; check for an active run before any push that could cancel it. Do not push documentation-only changes during a long build.
- If checkout history/files look inconsistent, fetch only the session branch, compare tracked blobs, and inspect extras before considering a reset. Never discard unreviewed workspace changes.
- MEGA binaries are comparison references only. Do not import their databases, SQL, or credentials.

## Build compatibility

Two SHA-guarded **core** compatibility patches remain, both restricted to core commit `14c435031d2cb31b1af664af9a83c5d6256302b6`: Ninja/MSVC configuration-path handling and Cygwin install dispatch. They are unrelated to module source fixes and are applied only to the ignored materialized core checkout.

## Windows dependencies and release layout

- **Boost 1.92.0**, prebuilt **MSVC 14.3 x64**, selected explicitly: installer `boost_1_92_0-msvc-14.3-64.exe` from `https://archives.boost.io/release/1.92.0/binaries/`, SHA-256 `90db7bdf26ad34a670fcf5b43c95c5253252098de01402cd758df8e801c383b3`, installed to `C:\local\boost_1_92_0` with libraries in `lib64-msvc-14.3`. `version.hpp` must report `BOOST_VERSION 109200` / `BOOST_LIB_VERSION "1_92"`. Boost is compile/link-only; **no Boost DLL is packaged**.
- **MySQL 8.4.11**, dynamic: `C:\tools\mysql\current` with the marker `.mysql-version`, `include\mysql.h`, `include\mysql_version.h` (version ID `80411`), `lib\libmysql.lib`, `lib\libmysql.dll`, `bin\mysql.exe`, and `bin\mysqld.exe`. Never `lib\mysqlclient.lib`, and never MySQL 8.4.9, 8.4.10, 8.0.46, or a 26.x release. The dependency cache uses the single exact key `winbuild-deps-boost-1.92.0-msvc14.3-mysql-8.4.11` with no broad restore keys.
- **MSVC toolset:** the Boost 1.92.0 auto-link tag comes from `_MSC_VER` (`<1950` asks for `vc143`, which is what the prebuilt package ships). The workflow selects an installed `14.3.x` toolset, else `14.4.x`, and always builds with `CL=-DBOOST_ALL_NO_LIB` (the `-D` spelling, because MSYS rewrites a leading `/D` into a path) so the explicit CMake Boost libraries are linked instead of a header-generated `vc145` pragma. The CMake cache check requires the `-vc143-` library set and rejects `-vc144-`/`-vc145-`.
- Build type **`RelWithDebInfo`**, `MTHREADS=4`, Ninja/MSVC, and the short `Z:` build path. The core is configured with explicit `-DBOOST_ROOT`, `-DMYSQL_ROOT_DIR`, `-DMYSQL_INCLUDE_DIR`, `-DMYSQL_LIBRARY`, and `-DMYSQL_EXECUTABLE`; the generated `core/conf/config.sh` and the build `CMakeCache.txt` are verified before an artifact is accepted.
- Release root (both the Actions artifact ZIP and a tagged Release ZIP): `authserver.exe`, `worldserver.exe`, and exactly `libmysql.dll`, `libcrypto-3-x64.dll`, `libssl-3-x64.dll`, `legacy.dll`, plus `configs/` (including `configs/modules/`) and the portable `mysql/` tree. No `bin/`, no `etc/`, no `README.txt`, no `SOURCE-PINS.json`, no DLL inventory, no nested ZIP, and no `azerothcore-ownedcore-windows/` prefix inside the archive. The provider search covers `lib/ossl-modules`, `ossl-modules`, `bin/ossl-modules`, then `bin` itself, because the runner image's SLProWeb installer uses `copytobin` and flattens `legacy.dll` into `bin`.
- `scripts/stage_windows_runtime_dlls.py` stages exactly those four DLLs and verifies the recursive `dumpbin /DEPENDENTS` closure; `scripts/package_runtime.py` builds the root layout; `scripts/assemble_release_zip.py` creates and verifies the single release ZIP in the tag job. The build job uploads the unpacked staging contents, never an inner ZIP.

## Verification status

- **Verified end to end:** Windows run [39590419188](https://github.com/alterational/azerothcore-ownedcore/actions/runs/39590419188) at commit `2b4cca7` succeeded for the default profile — provisioning gates, clean build directory, `RelWithDebInfo` configuration, full compile/install, CMake dependency verification (`-vc143-` Boost set, pinned MySQL paths), config staging, four-DLL staging, packaging, artifact upload, and the `verify-artifact` job. Artifact `azerothcore-ownedcore-windows`, 314,108,255 bytes, 440 entries, manifest SHA-256 `23cd0f9bdd48deafa009ec7d24d45270cafa6c1496ab3945f8f23a0a3b36ae52`, 14-day retention.
- Local validation: `scripts/validate_project.py`, `py_compile`, `pyflakes`, 65 unit tests, JSON validation, both workflow YAML files, and `git diff --check`. The packaging contract was additionally re-checked against the real pinned templates (29 templates, 39/39 edits, zero warnings, templates byte-identical).
- **Not verified:** no server startup smoke test, no full Linux/Codespaces build, and no SQL, migration, or live-server test. A GitHub Release requires a `v*` tag build, so pull-request runs skip that job by design.
- Superseded runs are not evidence for the current tree; only the run above matches the shipped pipeline.

## Key files

- `modules.manifest.json`, `modules.lock.json`: module inventory and exact source pins.
- `config/module-switches.json`, `config/additional-module-settings.json`: reviewed source/runtime configuration policy; `config/package-config-edits.json` controls package-only active `.conf` edits.
- `scripts/prepare_build.py`: one-command source preparation or post-install runtime configuration.
- `scripts/validate_project.py`: manifest, lock, configuration-map, and source-selection checks.
- `scripts/package_config_edits.py`, `scripts/package_runtime.py`: duplicate unchanged templates into package `configs/` `.conf` copies, apply only mapped edits, report non-fatal edit warnings, and assemble the root-level release layout.
- `scripts/stage_windows_runtime_dlls.py`, `scripts/assemble_release_zip.py`, `scripts/verify_package_layout.py`: deterministic four-DLL staging with a recursive `dumpbin` closure check, artifact-root layout verification, and the single-ZIP release assembly/verification step.
- `scripts/apply_core_compatibility_patches.py`: the two guarded core-only build fixes.
- `MODULES.md`, `docs/BUILD.md`, `docs/SQL_SETUP.md`, `CHECKOUT_REPORT.md`: inventory and operating guidance.
