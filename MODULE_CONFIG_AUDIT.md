# Pinned module master-switch audit

This audit is generated from the 2026-10-04 materialized source checkouts at the commits in `modules.lock.json`. Each listed master key was checked in its pinned `.conf.dist` and referenced by pinned C++ source. Other `Enable`-looking values are subfeatures and are intentionally not flipped. The runtime values are applied from `modules.manifest.json`; the manifest is authoritative for enabled/disabled state.

## How AzerothCore loads the module configuration files

The pinned core builds `CONFIG_FILE_LIST` from each selected module’s `conf/*.conf.dist` in `core/modules/CMakeLists.txt`. `worldserver` passes this list to `ConfigMgr::Configure` in `core/src/server/apps/worldserver/Main.cpp`, calls `LoadModulesConfigs`, and the pinned `ConfigMgr::LoadModulesConfigs` reads each named file from `GetConfigPath()/modules/`. The `acore.sh compiler` install path copies the templates to the configured runtime directory and, when `AC_ENABLE_CONF_COPY_ON_INSTALL` is enabled (default `1`), copies missing `.conf.dist` files to active `.conf` files. Therefore the overlay patches the loaded `.conf` files directly; it is not an unreferenced fragment.

`config/module-switches.json` records the template, active filename, default, key, and a source-code reference for every master switch. `scripts/apply_module_config.py --apply` applies only these key values; `--check` is read-only. The actual generated runtime configs were not created by a full build in this checkout, so application to a real `env/dist/etc/modules` directory remains pending.

## Master switches

`Target` is `1`/`true` for enabled and `0`/`false` for disabled. The `Upstream` column is the pinned template default.

| Target | Module ID | Source `.conf.dist` | Master key | Upstream | Target value | Code reference |
|---|---|---|---|---:|---:|---|
| ON | `mod-1v1-arena` | `conf/1v1arena.conf.dist` | `Arena1v1.Enable` | `1` | `1` | `src/cs_1v1arena.cpp:52` |
| ON | `mod-account-achievements` | `conf/mod_achievements.conf.dist` | `Account.Achievements.Enable` | `1` | `1` | `src/mod_achievements.cpp:50` |
| ON | `mod-autobalance` | `conf/AutoBalance.conf.dist` | `AutoBalance.Enable.Global` | `1` | `1` | `src/ABWorldScript.cpp:102` |
| ON | `mod-auto-revive` | `conf/AutoRevive.conf.dist` | `AutoRevive.Enable` | `1` | `1` | `src/AutoRevive.cpp:18` |
| ON | `BGQueueChecker` | `conf/bgqueuechecker.conf.dist` | `BGQueueChecker.Enable` | `0` | `1` | `src/BGQueueChecker.cpp:13` |
| ON | `mod-boss-announcer` | `conf/mod_boss_announcer.conf.dist` | `Boss.Announcer.Enable` | `1` | `1` | `src/mod_boss_announcer.cpp:241` |
| ON | `mod-breaking-news-override` | `conf/breakingnews.conf.dist` | `BreakingNews.Enable` | `0` | `1` | `src/BreakingNews.cpp:146` |
| ON | `mod-challenge-modes` | `conf/challenge_modes.conf.dist` | `ChallengeModes.Enable` | `1` | `1` | `src/ChallengeModes.cpp:263` |
| ON | `mod-changeablespawnrates` | `conf/mod-changeablespawnrates.conf.dist` | `Module.Enable` | `1` | `1` | `src/ChangeableSpawnrates.cpp:213` |
| ON | `mod-dead-means-dead` | `conf/mod_dead_means_dead.conf.dist` | `DeadMeansDead.Enable` | `1` | `1` | `src/DeadMeansDead.cpp:36` |
| ON | `mod-desertion-warnings` | `conf/desertion-warnings.conf.dist` | `DesertionWarnings.Enabled` | `1` | `1` | `src/DesertionWarnings.cpp:32` |
| ON | `mod-dynamic-loot-rates` | `conf/mod_dynamic_loot_rates.conf.dist` | `DynamicLootRates.Enable` | `1` | `1` | `src/mod_dynamic_loot_rates.cpp:26` |
| ON | `mod-dynamic-xp` | `conf/dynamicxp.conf.dist` | `Dynamic.XP.Rate` | `1` | `1` | `src/dynamicxp.cpp:23` |
| ON | `mod-fireworks-on-level` | `conf/mod_customserver.conf.dist` | `CustomServer.FireworkLevels` | `1` | `1` | `src/mod_customserver.cpp:84` |
| ON | `mod-fly-anywhere` | `conf/fly-anywhere.conf.dist` | `FlyAnywhere.Enabled` | `true` | `true` | `src/FlyAnywhereScript.cpp:25` |
| ON | `mod-individual-progression` | `conf/individualProgression.conf.dist` | `IndividualProgression.Enable` | `1` | `1` | `src/IndividualProgression.cpp:1045` |
| ON | `mod-individual-xp` | `conf/individual_xp.conf.dist` | `IndividualXp.Enabled` | `true` | `true` | `src/individual_xp.cpp:45` |
| ON | `mod-instance-reset` | `conf/instance-reset.conf.dist` | `instanceReset.Enable` | `true` | `true` | `src/instance_reset.cpp:239` |
| ON | `mod-learn-spells` | `conf/mod_learnspells.conf.dist` | `LearnSpells.Enable` | `1` | `1` | `src/mod_learnspells.cpp:33` |
| ON | `mod-morphsummon` | `conf/morphsummon.conf.dist` | `MorphSummon.Enabled` | `1` | `1` | `src/morphsummon.cpp:528` |
| ON | `mod-npc-beastmaster` | `conf/mod_npc_beastmaster.conf.dist` | `BeastMaster.Enable` | `1` | `1` | `src/NpcBeastmaster.cpp:337` |
| ON | `mod-npc-buffer` | `conf/npc_buffer.conf.dist` | `Buff.Enable` | `1` | `1` | `src/npc_buffer.cpp:96` |
| ON | `mod-npc-enchanter` | `conf/npc_enchanter.conf.dist` | `Enchanter.Enable` | `1` | `1` | `src/npc_enchanter.cpp:213` |
| ON | `mod-npc-spectator` | `conf/npc_spectator.conf.dist` | `NpcArenaSpectator.Enable` | `1` | `1` | `src/ArenaSpectatorNPC_SC.cpp:66` |
| ON | `mod-phased-duels` | `conf/mod_phased_duels.conf.dist` | `PhasedDuels.Enable` | `1` | `1` | `src/mod_phased_duels.cpp:27` |
| ON | `mod-playerbots` | `conf/playerbots.conf.dist` | `AiPlayerbot.Enabled` | `1` | `1` | `src/PlayerbotAIConfig.cpp:83` |
| ON | `mod-pvp-titles` | `conf/mod_pvptitles.conf.dist` | `PvPTitles.Enable` | `0` | `1` | `src/mod_pvp_titles.cpp:123` |
| ON | `mod-queue-list-cache` | `conf/QueueListCache.conf.dist` | `QLC.Enable` | `1` | `1` | `src/QueueListCache.cpp:24` |
| ON | `mod-quick-teleport` | `conf/quick_teleport.conf.dist` | `QuickTeleport.enabled` | `true` | `true` | `src/QuickTeleport.cpp:38` |
| ON | `mod-reward-played-time` | `conf/reward_system.conf.dist` | `RewardSystemEnable` | `1` | `1` | `src/reward_system.cpp:29` |
| ON | `mod-solo-lfg` | `conf/SoloLfg.conf.dist` | `SoloLFG.Enable` | `1` | `1` | `src/Lfg_Solo.cpp:33` |
| ON | `mod-TimeIsTime` | `conf/mod-time_is_time.conf.dist` | `TimeIsTime.Enable` | `1` | `1` | `src/TimeIsTime.cpp:27` |
| ON | `mod-transmog` | `conf/transmog.conf.dist` | `Transmogrification.Enable` | `1` | `1` | `src/Transmogrification.cpp:1101` |
| ON | `mod_weather_vibe` | `conf/mod_weather_vibe.conf.dist` | `WeatherVibe.Enable` | `1` | `1` | `src/core/mod_wv_core.cpp:55` |
| OFF | `mod-account-mounts` | `conf/mod_account_mount.conf.dist` | `Account.Mounts.Enable` | `1` | `0` | `src/mod_account_mount.cpp:41` |
| OFF | `mod-war-effort` | `conf/mod_aq_war_effort.conf.dist` | `ModWarEffort.Enable` | `0` | `0` | `src/WarEffort.h:286` |
| OFF | `mod-aoe-loot` | `conf/mod_aoe_loot.conf.dist` | `AOELoot.Enable` | `1` | `0` | `src/aoe_loot.cpp:46` |
| OFF | `mod-cfbg` | `conf/CFBG.conf.dist` | `CFBG.Enable` | `1` | `0` | `src/CFBG.cpp:100` |
| OFF | `mod-leech` | `conf/leech.conf.dist` | `Leech.Enable` | `1` | `0` | `src/Leech.cpp:50` |
| OFF | `mod-money-for-kills` | `conf/mod_moneyforkills.conf.dist` | `MFK.Enable` | `1` | `0` | `src/mod_moneyforkills.cpp:96` |
| OFF | `mod-no-hearthstone-cooldown` | `conf/mod_no_hearthstone_cooldown.conf.dist` | `NoHearthstoneCooldown.Enable` | `1` | `0` | `src/NoHearthstoneCooldown.cpp:33` |
| OFF | `mod-npc-free-professions` | `conf/mod_npc_free_professions.conf.dist` | `NpcFreeProfessions.Enable` | `1` | `0` | `src/ProfessionNPC.cpp:32` |
| OFF | `mod-ollama-chat` | `conf/mod_ollama_chat.conf.dist` | `OllamaChat.Enable` | `1` | `0` | `src/mod-ollama-chat_config.cpp:531` |
| OFF | `mod-player-bot-level-brackets` | `conf/mod_player_bot_level_brackets.conf.dist` | `BotLevelBrackets.Enabled` | `1` | `0` | `src/mod-player-bot-level-brackets.cpp:116` |
| OFF | `mod-pvp-zones` | `conf/mod_pvp_zones.conf.dist` | `pvp_zones.Enable` | `1` | `0` | `src/ZoneScript.cpp:61` |
| OFF | `mod-random-enchants` | `conf/random_enchants.conf.dist` | `RandomEnchants.Enable` | `1` | `0` | `src/random_enchants.cpp:6` |
| OFF | `mod-server-auto-shutdown` | `conf/ServerAutoShutdown.conf.dist` | `ServerAutoShutdown.Enabled` | `0` | `0` | `src/ServerAutoShutdown.cpp:87` |
| OFF | `mod-skip-dk-starting-area` | `conf/skip_dk_module.conf.dist` | `Skip.Deathknight.Starter.Enable` | `1` | `0` | `src/SkipDK.cpp:163` |

## Explicit upstream-default policies

| Module ID | Source config | Key | Pinned default | Policy |
|---|---|---|---:|---|
| `mod-playerbots-city-life` | `conf/mod_playerbots_city_life.conf.dist` | `CityLife.Enable` | `1` | Preserve; no override |
| `mod-dungeon-clear` | `conf/mod_dungeon_clear.conf.dist` | `DungeonClear.Enable` | `1` | Preserve; no override |

Dungeon Clear is enabled at `DungeonClear.Enable = 1`; its duplicate disabled source-list row is stale. City Life is enabled at `CityLife.Enable = 1`. The configuration applicator verifies both runtime values and refuses to change them.

## Modules with no effective module-wide switch

These modules are still present/compiled. No key is invented or flipped; their master-state limitation or module-specific behavior is recorded below. Some have subordinate tuning options that remain at upstream defaults.

| Target | Module ID | Config template | Finding |
|---|---|---|---|
| ON | `mod-ah-bot` | `conf/mod_ahbot.conf.dist` | No module-wide enable switch. AuctionHouseBot.EnableSeller and .EnableBuyer are separate operational roles and both default to 0; leave them unchanged until seller/buyer accounts, SQL, and economy behavior are deliberately configured. |
| ON | `mod-better-item-reloading` | — | No module .conf.dist or module-wide runtime switch was found; its source hooks are active when the module is compiled. |
| ON | `mod-duel-reset` | `conf/duelreset.conf.dist` | The config contains cooldown, health/mana, and zone/area behavior settings but no module-wide switch. |
| ON | `mod-emblem-transfer` | `conf/emblem_transfer.conf.dist` | The config contains transfer amount, penalty, and per-emblem options but no module-wide switch. |
| ON | `mod-guildhouse` | `conf/mod_guildhouse.conf.dist` | The config contains guildhouse service prices/ranks but no module-wide switch. |
| ON | `mod-improved-bank` | `conf/mod_improved_bank.conf.dist` | The config contains bank feature settings but no module-wide switch. |
| ON | `mod-junk-to-gold` | — | No module .conf.dist or module-wide runtime switch was found; its source hooks are active when compiled. |
| ON | `mod-low-level-rbg` | `conf/low_level_rbg.conf.dist` | The config sets queue level bounds only; no module-wide enable switch was found. |
| ON | `mod-multibot-bridge` | `conf/MultiBotBridge.conf.dist` | The only config setting toggles console logging; it is not a module enable switch. |
| ON | `mod-npc-talent-template` | `conf/npc_talent_template.conf.dist` | Config switches control individual gossip actions (reset talents, glyphs, and gear); no module-wide switch exists. |
| ON | `mod-player-bot-guildhouse` | `conf/mod_player_bot_guildhouse.conf.dist` | Config settings tune behavior; no module-wide enable switch was found. |
| ON | `mod-racial-trait-swap` | `conf/RacialTraitSwap.conf.dist` | The config exposes login announcement and cost settings only; no module-wide enable switch was found. |
| ON | `mod-rdf-expansion` | `conf/mod-rdf-expansion.conf.dist` | The config selects the RDF expansion behavior; it has no module-wide enable switch. |
| ON | `mod-reagent-bank` | `conf/reagent_bank.conf.dist` | The pinned .conf.dist contains ReagentBank.Enable=1, but the pinned C++ sources do not read this key; it is not an effective runtime master switch. The module hooks are compiled in. |
| ON | `mod-top-arena` | `conf/modarenatop.conf.dist` | The config only controls a Hello World startup message; no module-wide enable switch was found. |
| ON | `mod-who-logged` | `conf/who-logged.conf.dist` | The config has separate login/logout announcement toggles; no module-wide switch exists. The upstream login-announce default remains unchanged. |

## Upstream differences handled intentionally

- Enabled but upstream-off defaults are set on: `BGQueueChecker.Enable` (`0` → `1`), `BreakingNews.Enable` (`0` → `1`), and `PvPTitles.Enable` (`0` → `1`).
- Disabled but upstream-on defaults are set off for 12 modules: Account Mounts, AOE Loot, Cross Faction Battlegrounds, Leech, Money for Kills, No Hearthstone Cooldown, NPC Free Professions, Ollama Chat, Playerbot Level Brackets, PVP Zones, Random Enchants, and Skip Death Knight Starting Area.
- Ahn’Qiraj War Effort and Server Auto Shutdown already default off (`0`), so their master values are kept at `0`.
- The AHBot seller and buyer options are separate operational roles, both default to `0`; the overlay leaves them off because turning on auction behavior needs an explicit server/economy configuration.
- City Life and Dungeon Clear remain at their pinned enabled upstream defaults.
- All non-master settings (including AutoBalance submodes, NPC feature flags, city hubs, announcer options, Playerbots population settings, and DB values) are left untouched.
