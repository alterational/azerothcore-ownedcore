# Source, configuration, and build status

- **Updated:** 2026-10-19
- **Repository / branch:** `alterational/azerothcore-ownedcore` / `arena/01a106ef-azerothcore-ownedcore`
- **PR:** #1 remains open and unmerged.

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

Known module compatibility fixes are part of these five source pins; there are no module-specific overlay patches or patch runner in the repository. Separately, the user explicitly authorized `mod-junk-to-gold` at `notepadguyOfficial/mod-junk-to-gold` commit `50ad84a88a85bfe98cb96f94c277e33fb5da03b9` to provide the matching module config and master switch. This fork's compatibility with the pinned core has not yet been established. Historical Windows run [39123849901](https://github.com/alterational/azerothcore-ownedcore/actions/runs/39123849901) completed the default profile before that pin change, so it does not validate the current source selection.

## Configuration and SQL

Historical run `39123849901` staged 68 `.conf.dist` files: two core templates and 66 module templates. At its pinned revisions, three of the 69 default-profile modules lacked `.conf.dist`: `mod-better-item-reloading`, `mod-dual-tracking`, and `mod-junk-to-gold`. The newly authorized Junk to Gold pin adds a template, so the updated source profile should stage 67 module templates (69 total including core) and leave only Better Item Reloading and Dual Tracking without module templates.

The 14 runtime-off modules remain compiled in the default profile. Seven of them contain SQL files at their locked revisions: `mod-cfbg` (2), `mod-npc-free-professions` (1), `mod-ollama-chat` (9), `mod-player-bot-level-brackets` (1), `mod-random-enchants` (1), `mod-skip-dk-starting-area` (1), and `mod-war-effort` (4). See [docs/SQL_SETUP.md](docs/SQL_SETUP.md) for the SQL path inventory. No SQL or database migration has been run; City Life's world SQL remains manual.

## Windows run and packaging correction

Run `39123849901` completed successfully for its then-current pin set: build/install, runtime-config checks, packaging, and artifact upload all passed. It used the default profile without Individual Progression and predates the newly authorized Junk to Gold pin. The package log reported 116 Windows binaries/DLLs and 68 config templates, but also **redacted 30 public config values**. That was unintended and makes that uploaded artifact unsuitable as the corrected deliverable or as build evidence for the new source pin.

The local package script now copies every public `.conf.dist` byte-for-byte, creates a `.conf` sibling in the same relative directory from those same bytes, and then applies only the editable `config/package-config-edits.json` map to active copies. Missing files/keys, duplicate keys, unreadable configs, and value-type mismatches print the requested `WARNING` and do not fail compilation or archive creation; each warning skips only that one edit and later edits continue. Against the downloaded Windows artifact's 68 templates, an end-to-end local package fixture generated 68 active copies, applied all 39 current edits with zero warnings, and rechecked all `.conf.dist` bytes unchanged. This fixture test is not a Windows Actions run. Run the full Windows workflow after the local changes before treating a new artifact as final.

Local checks for this update: `python3 scripts/validate_project.py`, Python syntax compilation, 12 unit tests (byte-identical copies, package-only edits, Playerbots target values, missing file/key and type-warning behavior, plus preparation orchestration), JSON validation, the downloaded-artifact config smoke test, and `git diff --check` pass. No full Linux/Codespaces build or live-server test is recorded.

The new source pin and packaging changes require a successful full Windows workflow on this branch before claiming compatibility or treating an artifact as final. Do not treat the redacted artifact from run `39123849901` as the final runtime package; check PR #1's latest Actions results for current build status.
