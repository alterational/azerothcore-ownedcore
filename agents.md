# Agent handoff

- **Updated:** 2026-10-19
- **Repository:** `alterational/azerothcore-ownedcore`
- **Session branch for the target handoff:** `arena/01a106ef-azerothcore-ownedcore`
- **PR:** #1 is open and must not be merged or closed without the user's instruction.

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

- Work only on `arena/01a106ef-azerothcore-ownedcore`. Never push to `main`, create another branch, or merge/close PR #1. Do not commit or push unless the user asks.
- Preserve the core pin and all other module pins unless the user supplies a replacement commit.
- Five user-maintained module forks contain the known compatibility fixes:

  | Module | Branch | Commit | Fix included in source |
  |---|---|---|---|
  | BGQueueChecker | `master` | `c01d43ea8b69219339eb434c42dd22f34cf11b8c` | Battleground queue hook |
  | mod-aoe-loot | `main` | `7a921027ff6c58f9b6c905a3d3f4d966dcbc9994` | Packet signature and `::Item` qualification |
  | mod-challenge-modes | `master` | `a48a4d4ae6082a54647a2524f239a86a8ac16ccb` | `OnPlayerResurrect` `bool&` signatures |
  | mod-dead-means-dead | `main` | `47fd15fb0c80e2e7ce36ba0b3188fcd3cb78e853` | `OnPlayerLogin` hook |
  | mod-player-bot-level-brackets | `main` | `0c9187fa05eecde09c6b89653350d0edf34eced2` | `EquipAndSpecPersistence` field spelling |

- Separately, the user explicitly authorized `mod-junk-to-gold` at `https://github.com/notepadguyOfficial/mod-junk-to-gold`, commit `50ad84a88a85bfe98cb96f94c277e33fb5da03b9`, to supply the matching `JunkToGold` config template. This is not one of the five source-compatibility fixes above; its compatibility with the pinned core is pending the new Windows build.
- The five known module compatibility fixes are in those fork commits. **There are no module-specific overlay patch files or patch steps.** Do not recreate module patches for these fixes. Do not change any other source pin without explicit authorization.
- Keep the inventory at 70 repositories: 56 enabled, 14 runtime-off. All remain pinned/installable; the default source build selects 69 non-Individual-Progression modules. Individual Progression is the only source opt-in.
- City Life remains enabled. Dungeon Clear remains present/manifest-enabled in the build source set, but the user's 2026-10-19 package request deliberately sets `DungeonClear.Enable = 0` only in the generated active package `.conf`; its public `.conf.dist` remains unchanged. Learn Spells must remain `https://github.com/azerothcore/mod-learn-spells`.
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

## Verification status

- Historical Windows run `39099758327` completed build, runtime-config checks, packaging, and artifact upload using the older module SHAs plus temporary compatibility overlays (now removed), with Individual Progression included. That artifact is interim, not validation of the current pins or default profile.
- Historical Windows run `39123849901` completed successfully for the then-current default no-Individual-Progression PR profile, including build, runtime-config checks, packaging, and artifact upload. It predates the newly authorized Junk to Gold pin, and the old packaging code blanked 30 public config values; that artifact does not validate the new source and is not the corrected deliverable.
- The local Windows packaging code preserves public `.conf.dist` templates byte-for-byte, creates matching `.conf` siblings in the same relative directories, and applies `config/package-config-edits.json` only to active copies. Against the downloaded 68-template Windows artifact, it generated 68 `.conf` copies, applied all 39 mapped settings with zero warnings, set the existing numeric AHBot keys, and rechecked every `.conf.dist` as byte-identical. This is an end-to-end local package fixture, not a post-change Windows build; run Actions before treating a new artifact as final.
- Local validation after this packaging update passed: `python3 scripts/validate_project.py`, Python syntax compilation, 12 unit tests (including template-copy, active-edit, Playerbots target, missing-key/file and type-warning behavior), JSON/pin/profile consistency, actual-artifact config smoke test, and `git diff --check`.
- No full Linux/Codespaces build is recorded. No SQL, database migration, or live server test has been run.
- PR #1 remains open. Recheck Actions before relying on this snapshot, and update this section after post-fix tests or a new run.

## Key files

- `modules.manifest.json`, `modules.lock.json`: module inventory and exact source pins.
- `config/module-switches.json`, `config/additional-module-settings.json`: reviewed source/runtime configuration policy; `config/package-config-edits.json` controls package-only active `.conf` edits.
- `scripts/prepare_build.py`: one-command source preparation or post-install runtime configuration.
- `scripts/validate_project.py`: manifest, lock, configuration-map, and source-selection checks.
- `scripts/package_config_edits.py`, `scripts/package_runtime.py`: duplicate unchanged templates into package `.conf` copies, apply only mapped edits, and report non-fatal edit warnings.
- `scripts/apply_core_compatibility_patches.py`: the two guarded core-only build fixes.
- `MODULES.md`, `docs/BUILD.md`, `docs/SQL_SETUP.md`, `CHECKOUT_REPORT.md`: inventory and operating guidance.
