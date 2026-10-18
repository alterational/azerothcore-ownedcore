# Source, configuration, and build status

- **Updated:** 2026-10-18
- **Repository / branch:** `alterational/azerothcore-ownedcore` / `arena/01a106ef-azerothcore-ownedcore`
- **Last published commit:** `8af9eca`; PR #1 remains open and unmerged.

## Pinned sources and profile

The core is `alterational/azerothcore-wotlk.git`, branch `Playerbot`, commit `14c435031d2cb31b1af664af9a83c5d6256302b6`. The inventory contains 70 locked modules: 56 manifest-enabled, 14 runtime-off. The default build selects 69 module sources and excludes only `mod-individual-progression`.

Five user-maintained forks contain the known module compatibility fixes:

| Module | Branch | Locked commit | Included source fix |
|---|---|---|---|
| BGQueueChecker | `master` | `c01d43ea8b69219339eb434c42dd22f34cf11b8c` | Battleground queue hook |
| mod-aoe-loot | `main` | `7a921027ff6c58f9b6c905a3d3f4d966dcbc9994` | Packet signature and global `Item` qualification |
| mod-challenge-modes | `master` | `a48a4d4ae6082a54647a2524f239a86a8ac16ccb` | `OnPlayerResurrect` signatures |
| mod-dead-means-dead | `main` | `47fd15fb0c80e2e7ce36ba0b3188fcd3cb78e853` | `OnPlayerLogin` hook |
| mod-player-bot-level-brackets | `main` | `0c9187fa05eecde09c6b89653350d0edf34eced2` | `EquipAndSpecPersistence` field name |

Known module compatibility fixes are part of these source pins; there are no module-specific overlay patches or patch runner in the repository. The current source set completed a full Windows build in the default no-Individual-Progression profile in run [39123849901](https://github.com/alterational/azerothcore-ownedcore/actions/runs/39123849901).

## Configuration and SQL

The Windows run staged 68 `.conf.dist` files: two core templates and 66 module templates. Of the 69 modules in the default source profile, the three without a module `.conf.dist` are `mod-better-item-reloading`, `mod-dual-tracking`, and `mod-junk-to-gold`.

The 14 runtime-off modules remain compiled in the default profile. Seven of them contain SQL files at their locked revisions: `mod-cfbg` (2), `mod-npc-free-professions` (1), `mod-ollama-chat` (9), `mod-player-bot-level-brackets` (1), `mod-random-enchants` (1), `mod-skip-dk-starting-area` (1), and `mod-war-effort` (4). See [docs/SQL_SETUP.md](docs/SQL_SETUP.md) for the SQL path inventory. No SQL or database migration has been run; City Life's world SQL remains manual.

## Windows run and packaging correction

Run `39123849901` completed successfully: build/install, runtime-config checks, packaging, and artifact upload all passed. It used the current fork pins and the default profile without Individual Progression. The package log reported 116 Windows binaries/DLLs and 68 config templates, but also **redacted 30 public config values**. That was unintended and makes that uploaded artifact unsuitable as the corrected deliverable.

The package script has now been changed locally to copy every public `.conf.dist` template byte-for-byte, with no blanking or rewriting. The workflow label and documentation were corrected, and a regression test confirms database/key-looking public defaults survive the copy unchanged. A fresh Windows run is still required to produce and validate the corrected package. The existing run proves the current source pins compile; it does not validate the post-fix package.

Local checks after the package/command consolidation: `python3 scripts/validate_project.py`, Python syntax compilation, 11 unit tests (including byte-for-byte package and preparation-command regression tests), JSON/pin/profile checks, UTF-8 checks, and `git diff --check` pass. No full Linux/Codespaces build or live-server test is recorded.

The follow-up package correction and handoff/status edits are local and uncommitted. Do not treat the redacted artifact from run `39123849901` as the final runtime package.
