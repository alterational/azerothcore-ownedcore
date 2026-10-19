# OwnedCore config comparison

**Result:** compared the downloaded post-squash build artifact with the repack configs in the `main`-branch ZIP. This audit itself made no project config, source, workflow, or mapping changes; its findings were later used to implement the tracked package-config map and packaging code. The build/reference ZIP files are comparison inputs and are not included in Git.

## Inputs and method

- Build run: [39131427175](https://github.com/alterational/azerothcore-ownedcore/actions/runs/39131427175), success, commit `3855ecb44e700dfa56f079c974320332da55ff03`; artifact `12141476078`.
- Dropbox file: `dropbox/image-1792338424086.zip`, 31,018,055 bytes; SHA-256 `ad311ce0b2e09321b8e11408bc2bab2ed6132124b7565aa76f97933729e8250d`. It contains `azerothcore-ownedcore-windows.zip` (31,148,961 bytes). Both ZIP integrity checks passed.
- Reference: `ownedcore-configs-after-update.zip` from `main` at `bfaf08779abfa9fe7e9ff60a949f00479a37d4a5`, blob `785fbe3d2a36fe98194af78dd7f705ae703b4e43`.
- For the standard build, compared with the archive’s `without-ip` directory. Compared actual artifact `.conf.dist` against both the repack’s active `.conf` and its `.conf.dist`; parsed assignments by exact key name, then separately normalized the Playerbots namespace prefix as a diagnostic.

## Artifact contents and file inventory

The actual build ZIP has 186 entries, including **68 `.conf.dist` templates: 66 module templates and two core templates (`authserver` and `worldserver`)**. It contains **zero active `.conf` files**. Its `README.txt` says the package contains unchanged `*.conf.dist` templates only; `SOURCE-PINS.json` records 69 selected sources and excludes `mod-individual-progression`.

The repack’s `without-ip` tree has 77 module `.conf` files and 77 module `.conf.dist` files. Of the 66 artifact module-template names, 64 have same-name pairs in the reference:

- **45/64** artifact `.conf.dist` files are byte-identical to the repack’s `.conf.dist`.
- **35/64** are byte-identical to the repack’s active `.conf`.
- The artifact has two module templates absent from the repack archive: `mod_playerbots_city_life.conf.dist` and `mod_pvp_zones.conf.dist`.
- The repack has 13 module templates absent from the current default build: `anticheat`, `individual_xp`, `individualprogression`, `mod-bg-item-reward`, `mod-junk-to-gold`, `mod-quest-loot-party`, `mod_acore_subscriptions`, `mod_dungeon_master`, `mod_flightmaster_whistle`, `mod_mythic_plus`, `mod_player_bot_reset`, `mod_tictactoe`, and `mod_weekendbonus` (each appears as both `.conf` and `.conf.dist`). `individualprogression` is intentionally excluded from the default build even though it remains in the repack’s `without-ip` tree.

The two repack variants are not strict supersets of one another: `without-ip` alone has `anticheat`, `mod-bg-item-reward`, `mod_tictactoe`; `with-ip` alone has `npc_beastmaster`, `npc_subclass`.

## Exact common-key value differences: artifact `.conf.dist` vs repack active `.conf`

There are **27 textual value differences over common keys in 22 module files**. The two AHBot `0`/`false` pairs are different text and may be equivalent booleans; they are not counted as proven behavioral differences here.

| Config | Key | Actual build `.conf.dist` | Repack active `.conf` |
|---|---|---:|---:|
| `AutoRevive.conf.dist` | `AutoRevive.Enable` | `1` | `0` |
| `bgqueuechecker.conf.dist` | `BGQueueChecker.Enable` | `1` | `0` |
| `breakingnews.conf.dist` | `BreakingNews.Enable` | `1` | `0` |
| `CFBG.conf.dist` | `CFBG.Enable` | `0` | `1` |
| `challenge_modes.conf.dist` | `ChallengeModes.Enable` | `1` | `0` |
| `dynamicxp.conf.dist` | `Dynamic.XP.Rate` | `1` | `0` |
| `dynamicxp.conf.dist` | `Dynamic.XP.Rate.Announce` | `1` | `0` |
| `mod-time_is_time.conf.dist` | `TimeIsTime.SpeedRate` | `15.0` | `1.0` |
| `mod_achievements.conf.dist` | `Account.Achievements.Announce` | `1` | `0` |
| `mod_achievements.conf.dist` | `Account.Achievements.Enable` | `1` | `0` |
| `mod_ahbot.conf.dist` | `AuctionHouseBot.DEBUG` | `0` | `false` |
| `mod_ahbot.conf.dist` | `AuctionHouseBot.DEBUG_FILTERS` | `0` | `false` |
| `mod_ahbot.conf.dist` | `AuctionHouseBot.EnableSeller` | `0` | `true` |
| `mod_ahbot.conf.dist` | `AuctionHouseBot.ItemsPerCycle` | `200` | `100` |
| `mod_aoe_loot.conf.dist` | `AOELoot.Enable` | `0` | `1` |
| `mod_dead_means_dead.conf.dist` | `DeadMeansDead.RespawnTime.Multiplier.Dungeons` | `1.0` | `0.0` |
| `mod_dead_means_dead.conf.dist` | `DeadMeansDead.RespawnTime.Multiplier.Global` | `0.0` | `1.0` |
| `mod_dead_means_dead.conf.dist` | `DeadMeansDead.RespawnTime.Multiplier.Raids` | `1.0` | `0.0` |
| `mod_dynamic_loot_rates.conf.dist` | `DynamicLootRates.Enable` | `1` | `0` |
| `mod_learnspells.conf.dist` | `LearnSpells.Enable` | `1` | `0` |
| `mod_no_hearthstone_cooldown.conf.dist` | `NoHearthstoneCooldown.Announce` | `1` | `0` |
| `mod_player_bot_level_brackets.conf.dist` | `BotLevelBrackets.CheckFrequency` | `300` | `600` |
| `mod_player_bot_level_brackets.conf.dist` | `BotLevelBrackets.GuildTrackerUpdateFrequency` | `600` | `1200` |
| `mod_pvptitles.conf.dist` | `PvPTitles.Enable` | `1` | `0` |
| `mod_weather_vibe.conf.dist` | `WeatherVibe.Debug` | `1` | `0` |
| `quick_teleport.conf.dist` | `QuickTeleport.enabled` | `true` | `false` |
| `skip_dk_module.conf.dist` | `Skip.Deathknight.Starter.Announce.enable` | `1` | `0` |

This is not just upstream-default drift: the archive has **31 active-vs-template value overrides across 18 files**. The exact list is below so the active repack state can be distinguished from its own `.conf.dist` defaults.

| Repack file | Key | Repack `.conf.dist` | Repack active `.conf` |
|---|---|---:|---:|
| `AutoRevive.conf.dist` | `AutoRevive.Enable` | `1` | `0` |
| `challenge_modes.conf.dist` | `ChallengeModes.Enable` | `1` | `0` |
| `dynamicxp.conf.dist` | `Dynamic.XP.Rate` | `1` | `0` |
| `dynamicxp.conf.dist` | `Dynamic.XP.Rate.Announce` | `1` | `0` |
| `leech.conf.dist` | `Leech.Enable` | `1` | `0` |
| `mod_account_mount.conf.dist` | `Account.Mounts.Enable` | `1` | `0` |
| `mod_achievements.conf.dist` | `Account.Achievements.Announce` | `1` | `0` |
| `mod_achievements.conf.dist` | `Account.Achievements.Enable` | `1` | `0` |
| `mod_ahbot.conf.dist` | `AuctionHouseBot.Alliance.MaxItems` | `15000` | `20000` |
| `mod_ahbot.conf.dist` | `AuctionHouseBot.Buyer.Enabled` | `false` | `true` |
| `mod_ahbot.conf.dist` | `AuctionHouseBot.EnableSeller` | `false` | `true` |
| `mod_ahbot.conf.dist` | `AuctionHouseBot.GUIDs` | `0` | `1` |
| `mod_ahbot.conf.dist` | `AuctionHouseBot.Horde.MaxItems` | `15000` | `20000` |
| `mod_ahbot.conf.dist` | `AuctionHouseBot.ItemsPerCycle` | `150` | `100` |
| `mod_ahbot.conf.dist` | `AuctionHouseBot.ListingExpireTimeInSecondsMin` | `900` | `1800` |
| `mod_ahbot.conf.dist` | `AuctionHouseBot.Neutral.MaxItems` | `15000` | `20000` |
| `mod_dynamic_loot_rates.conf.dist` | `DynamicLootRates.Enable` | `1` | `0` |
| `mod_learnspells.conf.dist` | `LearnSpells.Enable` | `1` | `0` |
| `mod_moneyforkills.conf.dist` | `MFK.Enable` | `1` | `0` |
| `mod_no_hearthstone_cooldown.conf.dist` | `NoHearthstoneCooldown.Announce` | `1` | `0` |
| `mod_no_hearthstone_cooldown.conf.dist` | `NoHearthstoneCooldown.Enable` | `1` | `0` |
| `mod_npc_free_professions.conf.dist` | `NpcFreeProfessions.Enable` | `1` | `0` |
| `mod_ollama_chat.conf.dist` | `OllamaChat.Enable` | `1` | `0` |
| `mod_player_bot_level_brackets.conf.dist` | `BotLevelBrackets.CheckFrequency` | `300` | `600` |
| `mod_player_bot_level_brackets.conf.dist` | `BotLevelBrackets.Enabled` | `1` | `0` |
| `mod_player_bot_level_brackets.conf.dist` | `BotLevelBrackets.GuildTrackerUpdateFrequency` | `600` | `1200` |
| `mod_weather_vibe.conf.dist` | `WeatherVibe.Debug` | `1` | `0` |
| `quick_teleport.conf.dist` | `QuickTeleport.enabled` | `true` | `false` |
| `random_enchants.conf.dist` | `RandomEnchants.Enable` | `1` | `0` |
| `skip_dk_module.conf.dist` | `Skip.Deathknight.Starter.Announce.enable` | `1` | `0` |
| `skip_dk_module.conf.dist` | `Skip.Deathknight.Starter.Enable` | `1` | `0` |

## Playerbots: exact values and key-name normalization

An exact key-string comparison shows 890 artifact-only keys and 887 repack-only keys, largely because the namespaces differ: the artifact uses `Playerbots.*`, while the repack uses `AiPlayerbot.*` and `AIPlayerbot.*`. To compare likely corresponding options, I normalized only that prefix and preserved the rest of each key. Under that diagnostic comparison: 889 common keys, four changed values, five artifact-only keys, and two repack-only keys.

| Normalized setting | Actual artifact key/value | Repack active key/value |
|---|---|---|
| `RandomClassSpecProb.4.0` | `Playerbots.RandomClassSpecProb.4.0 = 40` | `AiPlayerbot.RandomClassSpecProb.4.0 = 45` |
| `RandomClassSpecProb.4.1` | `Playerbots.RandomClassSpecProb.4.1 = 60` | `AiPlayerbot.RandomClassSpecProb.4.1 = 45` |
| `RandomClassSpecProb.4.2` | `Playerbots.RandomClassSpecProb.4.2 = 0` | `AiPlayerbot.RandomClassSpecProb.4.2 = 10` |
| `PvpProhibitedAreaIds` | `Playerbots.PvpProhibitedAreaIds = "976,35,392,2268,4161,4010,4317,4312,3649,3887,3958,3724,4080,3938,3754,3786,3973,4085,4086,4087,4088,251"` | `AiPlayerbot.PvpProhibitedAreaIds = "976,35,392,2268,4161,4010,4317,4312,3649,3887,3958,3724,4080,3938,3754,3786,3973,4085,4086,4087,4088"` |

The five build-only keys after prefix normalization are `Playerbots.AllowBattlegroundCommands`, `Playerbots.RandomBotJoinLfgOutleveledExpansion`, `Playerbots.RandomBotReactStrategies`, `Playerbots.ReactStrategies`, and `Playerbots.RpgStatusProbWeight.DoGather`. The two repack-only keys are `AiPlayerbot.FleeingEnabled` and `AIPlayerbot.GuildFeedback`. Prefix normalization is only a comparison aid; it does not prove the two code versions accept the same key names.

## Other key/schema differences

Exact key comparison across common module filenames gives **966 artifact-only and 1,331 repack-only key names**. The largest contributors are AHBot and Playerbots:

- **AHBot:** 65 keys present only in the artifact template, 444 only in the repack template, and four exact shared keys. The shared values are `AuctionHouseBot.DEBUG` (`0` vs `false`), `DEBUG_FILTERS` (`0` vs `false`), `EnableSeller` (`0` vs `true`), and `ItemsPerCycle` (`200` vs `100`). The remaining key sets are too different for a safe mechanical merge.
- **AOE Loot:** artifact-only `AOELoot.CorpseThreshold`, `AOELoot.Debug`, `AOELoot.MoneyShareDistanceMultiplier`; `AOELoot.Enable` is `0` in the build and `1` in the repack.
- **Dungeon Clear:** artifact-only `DungeonClear.Lab.MaxParties`. Artifact has `DungeonClear.Enable = 1`.
- **Ollama Chat:** artifact-only `OllamaChat.ApiKey`, `ApiKeyHeader`, `Provider`, `RateLimitMaxWaitSeconds`, `RateLimitRetries`, and `VerifyCertificates`. Values are intentionally omitted here.
- **Skip DK:** artifact-only `Skip.Deathknight.Start.WeaponEnchantment`.
- **City Life:** its artifact file is absent from the repack tree; artifact has `CityLife.Enable = 1`.
- **Learn Spells:** the module template is present in the artifact with `LearnSpells.Enable = 1`; the repack active config has `0`. This is a runtime-switch difference, not a source-inclusion difference.

## Core templates

The actual artifact’s core `.conf.dist` compared with the repack’s core `.conf.dist`:

- `authserver.conf.dist`: `Appender.Auth` is `2,5,8,Auth.log,w` in the artifact and `2,5,0,Auth.log,w` in the repack.
- `worldserver.conf.dist`: `Appender.Errors`, `Appender.Playerbots`, and `Appender.Server` use `8` in the artifact and `0` in the repack; `MapUpdate.Threads` is `4` vs `1`; `ActivateWeather` `0` vs `1`; `Die.Command.Mode` `0` vs `1`; `EnablePlayerSettings` `1` vs `0`; `DBC.EnforceItemAttributes` `0` vs `1`.

The repack’s active core `.conf` additionally sets `DataDir`, `LogsDir`, `MySQLExecutable`, `SourceDirectory`, and `TempDir`. Those path-specific active configs are not in the artifact and should not be copied into public `.conf.dist` templates.

## Interpretation

The latest post-squash artifact has the expected structure and does **not** show the pre-squash 30-field sanitizer behavior: its public `DatabaseInfo` defaults are nonempty. The comparison also shows the repack active files contain runtime overrides absent from the shipped `.conf.dist` templates, plus several likely module-version/schema changes. In particular, do not merge AHBot or Playerbots by simple text replacement. No config changes were applied by this comparison itself; the related runtime-package edits are documented in `config/package-config-edits.json`. The ZIP inputs remain local and are not committed.
