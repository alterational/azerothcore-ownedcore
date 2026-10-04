# SQL and runtime prerequisites

## City Life manual world SQL

At the pinned City Life source, the manual SQL file is:

```text
core/modules/mod-playerbots-city-life/data/sql/manual/world_city_life.sql
```

It targets the **world database** and is in a `manual` directory, so the pinned AzerothCore updater does not discover it automatically. The module README explicitly instructs an import. No target database was supplied or identified, no backup was available, and no SQL has been run.

After identifying the exact world database, taking and verifying a backup, reviewing this pinned SQL against the target schema, and receiving explicit authorization, a password-prompted import is:

```bash
mysql --host=<db-host> --user=<db-user> --password --database=<world_database> < core/modules/mod-playerbots-city-life/data/sql/manual/world_city_life.sql
```

`--password` prompts interactively; do not put a password in the command, shell history, a config committed to Git, or this documentation. This is a procedure only—not authorization to execute it. City Life disables itself and logs an error if its two world tables are missing.

## Playerbot runtime prerequisite

City Life requires the Playerbot core/module and reuses only random bots that are **already online**. It does not create characters, log bots in, or increase the random-bot population. Configure a sufficient online-bot pool in the Playerbots system before expecting the desired city population.

## What the pinned core applies automatically

Compilation does not import SQL. At server startup, the pinned core database updater enumerates module SQL directories whose immediate names match its database names (`auth`, `world`, or `characters`) and recursively reads `.sql` files beneath them. Playerbots also registers a module-owned database updater: with `Playerbots.Updates.EnableDatabases = 1` (upstream default), it creates/opens the configured Playerbots database, populates `data/sql/playerbots/base`, and applies the directories in `updates_include` (including `updates`). These migrations are separate from the manual City Life SQL.

**Important:** the updater enumerates compiled module names and does not gate SQL migrations on a module’s runtime `Enable`/`Enabled` switch. Because this project compiles all installed module sources, automatic SQL for the 14 initially-disabled modules can still be applied on server startup. Review/backup each target database before starting a production server; runtime-off is not equivalent to “no schema changes.” This project never connects to a database.

Pinned module SQL directory scan (paths under `data/sql`; `auth`/`world`/`characters` folders are read by the core updater; Playerbots uses its own updater):

| Module ID | Auto-discovered directories | Nonautomatic/optional SQL directories |
|---|---|---|
| `mod-1v1-arena` | db-world | delete |
| `mod-ah-bot` | db-world | — |
| `mod-challenge-modes` | db-world | — |
| `mod-changeablespawnrates` | db-world | — |
| `mod-playerbots-city-life` | — | manual |
| `mod-dead-means-dead` | db-world | — |
| `mod-emblem-transfer` | db-characters, db-world | — |
| `mod-guildhouse` | db-characters, db-world | — |
| `mod-improved-bank` | db-characters, db-world | — |
| `mod-individual-progression` | world | optional/sql (opt-in) |
| `mod-individual-xp` | db-characters, db-world | — |
| `mod-instance-reset` | db-world | — |
| `mod-low-level-rbg` | db-world | — |
| `mod-morphsummon` | db-characters, db-world | — |
| `mod-npc-beastmaster` | db-characters, db-world | — |
| `mod-npc-buffer` | db-world | — |
| `mod-npc-enchanter` | db-world | — |
| `mod-npc-spectator` | db-world | — |
| `mod-npc-talent-template` | db-characters, db-world | — |
| `mod-playerbots` | characters, playerbots (own updater; base + updates_include), world | playerbots/create (manual sample create/drop; not auto) |
| `mod-queue-list-cache` | db-world | — |
| `mod-racial-trait-swap` | db-world | — |
| `mod-reagent-bank` | db-characters, db-world | — |
| `mod-reward-played-time` | db-characters | — |
| `mod-top-arena` | db-world | — |
| `mod-transmog` | db-auth, db-characters, db-world | updates |
| `mod-war-effort` | db-characters, db-world | — |
| `mod-cfbg` | db-world | — |
| `mod-npc-free-professions` | db-world | — |
| `mod-ollama-chat` | characters | — |
| `mod-player-bot-level-brackets` | characters | — |
| `mod-random-enchants` | db-world | — |
| `mod-skip-dk-starting-area` | db-world | — |

The table is a path classification from the locked source checkouts, not a record of SQL execution. In particular, `mod-ollama-chat` includes a file named `2025_11_01_personality_manual_only.sql` under its auto-discovered `data/sql/characters/base` directory; the filename does not exclude it from that loader. Its `2026_08_29_memory_relationships.sql` requirement is likewise in the auto-discovered character base tree.

### Nonautomatic SQL that needs separate review

- **City Life:** `data/sql/manual/world_city_life.sql` — manual world import described above.
- **Individual Progression (enabled):** 22 optional patches under `core/modules/mod-individual-progression/optional/sql/world/`. The module README marks these as optional; they are outside `data/sql/world` and are not applied by the updater. Do not choose or apply them without an explicit gameplay decision and database review.
- **Transmog (enabled):** `core/modules/mod-transmog/data/sql/updates/world/2026_05_09_transmog_set_disclaimer.sql` is in a nonstandard `data/sql/updates/world` tree rather than the pinned updater’s immediate `db-world`/`world` layout. The other `db-auth`, `db-characters`, and `db-world` directories are automatically discovered. Treat this one file as not automatically discovered; inspect the module’s instructions and decide/import separately only with backup and authorization.
- **1v1 Arena (enabled):** `data/sql/delete/1v1_delete.sql` is a deletion/removal script, not an installation migration. It is not discovered by the normal updater and must not be run for setup.
- **Playerbots:** `data/sql/playerbots/create/create_mysql.sql` and the `drop_mysql*.sql` examples are not automatically applied. The pinned module updater can create its configured DB and populate/update it when enabled; the sample create script hard-codes an `acore` user and broad grants, and drop scripts are destructive. Do not run them blindly.

Older module READMEs sometimes say to use the historical `db_assembler.sh` or import SQL manually. For this pinned core, files under the documented standard module update directories are discovered by the worldserver DB updater; the nonstandard paths above are called out separately.

## Other setup/runtime requirements in pinned module instructions

- **Individual Progression and Challenge Modes:** their READMEs require `EnablePlayerSettings = 1` in `worldserver.conf`; Individual Progression also requests `DBC.EnforceItemAttributes = 0`. The pinned core currently defaults these to `0` and `1`, respectively; the required changes are in `patches/azerothcore-worldserver-defaults.patch` and remain pending a commit in the personal core fork. They are not part of the module master-switch overlay.
- **Weather Vibe (enabled):** its README requires `ActivateWeather = 0` in `worldserver.conf`; the pinned core currently defaults it to `1`. This change is also pending in the personal core fork. Review the interaction with any other weather module/server policy before starting a server.
- **Fly Anywhere (enabled):** requires server and client `AreaTable.dbc` changes. The module README says the build/install step should install the server DBC (keep its backup); if not, copy the module’s `data/patch/server` file into the server data DBC directory. The client needs the module’s `data/patch/client/Patch-o.mpq` in the WoW 3.3.5a client `Data` folder and cache removal. Client files/data are not stored in this repository.
- **Playerbots:** the module uses `PlayerbotsDatabaseInfo` (upstream sample default `acore_playerbots`) and `Playerbots.Updates.EnableDatabases = 1`. The database updater can create and migrate this module-owned database at runtime; its connection credentials belong only in ignored, server-specific runtime config.
- **MultiBot Bridge:** its optional in-game UI depends on the companion MultiBot-Chatless client addon; the addon is not included here.
- **NPC placement:** the pinned 1v1 Arena and Top Arena READMEs show GM commands `.npc add 999991` and `.npc add 55333`; Guildhouse shows `.npc add 500030`. These are optional in-game setup steps after the relevant automatic migrations, not SQL imports performed by this project.
- **Playerbot Guildhouse integration:** requires the Playerbots module and Guildhouse module to be present/loaded; both are target-enabled here.
- **AHBot:** `EnableSeller` and `EnableBuyer` default off and require deliberate account/database/economy configuration. They are not enabled by this overlay.
- **Ollama Chat (initially disabled):** if deliberately enabled later, it requires an Ollama service/model and additional dependency/setup review. It remains runtime-off in this project.

No SQL has been applied to any database, and no database credentials are stored in this repository.
