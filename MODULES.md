# Module inventory

Extracted from the supplied OwnedCore list with the requested City Life addition. There are **66 unique module repositories**: **52 enabled** and **14 initially disabled**. All 66 have `install: true`; disabled means runtime-off, not omitted from checkout. The source pins are candidate remote tips recorded on 2026-10-04, not compatibility/build proof.

`modules.manifest.json` is the target-state authority; `modules.lock.json` is the immutable branch/commit authority. Each row below shows the exact lock pin.

## Enabled (52)

| Module | ID | Repository | Branch | Locked commit | Notes |
|---|---|---|---|---|---|
| 1v1 Arena | `mod-1v1-arena` | [https://github.com/azerothcore/mod-1v1-arena](https://github.com/azerothcore/mod-1v1-arena) | `master` | `5ef5708d031f3b02283e6e599aa655bd320d904e` | — |
| Account Achievements | `mod-account-achievements` | [https://github.com/azerothcore/mod-account-achievements](https://github.com/azerothcore/mod-account-achievements) | `master` | `bfbe3677635feeef823057964e028e023633115a` | — |
| AHBot | `mod-ah-bot` | [https://github.com/azerothcore/mod-ah-bot](https://github.com/azerothcore/mod-ah-bot) | `master` | `c11d8318cbd8714a9980f9464f78e07d3d48a70a` | — |
| AutoBalance | `mod-autobalance` | [https://github.com/azerothcore/mod-autobalance](https://github.com/azerothcore/mod-autobalance) | `master` | `73d4ad3c379fbfc35c63b5b9b44fba1f7d9e213d` | — |
| AutoRevive | `mod-auto-revive` | [https://github.com/azerothcore/mod-auto-revive](https://github.com/azerothcore/mod-auto-revive) | `master` | `ce5ca7a600dbef0dec48dc6da42d374d08d6b728` | — |
| Better item reloading | `mod-better-item-reloading` | [https://github.com/azerothcore/mod-better-item-reloading](https://github.com/azerothcore/mod-better-item-reloading) | `master` | `24617d0f94d0bc6d24993e4581661af5c7629b5e` | — |
| BG Queue checker | `BGQueueChecker` | [https://github.com/AnchyDev/BGQueueChecker](https://github.com/AnchyDev/BGQueueChecker) | `master` | `0a6b9872f5d4f50286e5152c0debfeb1d6ef73a0` | — |
| Boss Announcer | `mod-boss-announcer` | [https://github.com/azerothcore/mod-boss-announcer](https://github.com/azerothcore/mod-boss-announcer) | `master` | `3af6e83e976a9a143ded51f4e8afeb69863fb5ec` | — |
| Breaking News Override | `mod-breaking-news-override` | [https://github.com/azerothcore/mod-breaking-news-override](https://github.com/azerothcore/mod-breaking-news-override) | `master` | `1016344718b1ace3235b00469f0df65d544371db` | — |
| Challenge Modes | `mod-challenge-modes` | [https://github.com/ZhengPeiRu21/mod-challenge-modes](https://github.com/ZhengPeiRu21/mod-challenge-modes) | `master` | `1930525b9530d329cb9fe0504a3c9b5b40a12261` | — |
| Changeable Spawn Rates | `mod-changeablespawnrates` | [https://github.com/justin-kaufmann/mod-changeablespawnrates](https://github.com/justin-kaufmann/mod-changeablespawnrates) | `main` | `c51cd270034d347e767f0ab4c5498693c41109e3` | — |
| City Life | `mod-playerbots-city-life` | [https://github.com/vrzgames/mod-playerbots-city-life](https://github.com/vrzgames/mod-playerbots-city-life) | `main` | `ce6a05df450f04c4961d09254ad73cf11f1afee2` | User-requested; upstream config default; manual world SQL; no bots spawned |
| Dead Means Dead | `mod-dead-means-dead` | [https://github.com/kjack9/mod-dead-means-dead](https://github.com/kjack9/mod-dead-means-dead) | `main` | `725b14973be28c4acea7d1a892bbe7cfdd2e8a51` | — |
| Desertion Warnings | `mod-desertion-warnings` | [https://github.com/azerothcore/mod-desertion-warnings](https://github.com/azerothcore/mod-desertion-warnings) | `master` | `ed1b7e26869d520b7627c289d461fbc5d040be6a` | — |
| DuelReset | `mod-duel-reset` | [https://github.com/azerothcore/mod-duel-reset](https://github.com/azerothcore/mod-duel-reset) | `master` | `f2c67d4d82b79cefccfc89a4696a428529cf8cfd` | — |
| Dungeon Clear | `mod-dungeon-clear` | [https://github.com/jrad7/mod-dungeon-clear](https://github.com/jrad7/mod-dungeon-clear) | `master` | `60f3d98b83143714041df4120abd45f0e3c3ebd7` | User confirmed enabled; upstream default; duplicate disabled listing stale |
| Dynamic Loot Rates | `mod-dynamic-loot-rates` | [https://github.com/hallgaeuer/mod-dynamic-loot-rates](https://github.com/hallgaeuer/mod-dynamic-loot-rates) | `master` | `41ffb6a7c5bc78d1c062b8237a9a185892514a32` | — |
| Dynamic XP | `mod-dynamic-xp` | [https://github.com/azerothcore/mod-dynamic-xp](https://github.com/azerothcore/mod-dynamic-xp) | `master` | `06d5d370aa7d8d8644ed241f03a986e28195c2f4` | — |
| Emblem Transfer | `mod-emblem-transfer` | [https://github.com/azerothcore/mod-emblem-transfer](https://github.com/azerothcore/mod-emblem-transfer) | `master` | `feb2007a50c77680bd6d15aaaf45e8a185dad7cf` | — |
| Fireworks on Level | `mod-fireworks-on-level` | [https://github.com/azerothcore/mod-fireworks-on-level](https://github.com/azerothcore/mod-fireworks-on-level) | `master` | `e5c58542996e0f1ad3410ebdb7cff9ed9d52e3d6` | — |
| Fly Anywhere | `mod-fly-anywhere` | [https://github.com/abracadaniel22/mod-fly-anywhere](https://github.com/abracadaniel22/mod-fly-anywhere) | `main` | `141b789f9b9c99ebf0c5391df9dafb825f967f9a` | — |
| Guildhouse | `mod-guildhouse` | [https://github.com/azerothcore/mod-guildhouse](https://github.com/azerothcore/mod-guildhouse) | `master` | `0b3cc14e947a859f8a7751a10676107d6316275b` | — |
| Improved Bank | `mod-improved-bank` | [https://github.com/silviu20092/mod-improved-bank](https://github.com/silviu20092/mod-improved-bank) | `master` | `89fc606fe6945f201f15f8a3bbc61d01552ea94c` | — |
| Individual Progression | `mod-individual-progression` | [https://github.com/ZhengPeiRu21/mod-individual-progression](https://github.com/ZhengPeiRu21/mod-individual-progression) | `master` | `60336b349cce2bc209d154bb840f2370f1cc16f2` | Optional module in original list |
| Individual XP | `mod-individual-xp` | [https://github.com/azerothcore/mod-individual-xp](https://github.com/azerothcore/mod-individual-xp) | `master` | `503471f766bc4f21dca0aa05e6a9d3d40718a780` | — |
| Instance Reset | `mod-instance-reset` | [https://github.com/azerothcore/mod-instance-reset](https://github.com/azerothcore/mod-instance-reset) | `master` | `1e2c20770f40f5382348b7649291371f47c86812` | — |
| Junk to Gold | `mod-junk-to-gold` | [https://github.com/noisiver/mod-junk-to-gold](https://github.com/noisiver/mod-junk-to-gold) | `master` | `2134690bb03899e5c9e44d0682e8e6abf0bbbaf2` | — |
| Learn Spells | `mod-learn-spells` | [https://github.com/azerothcore/mod-learn-spells](https://github.com/azerothcore/mod-learn-spells) | `master` | `016b92d520f343d074ffd5d46016a94f4a3a6ebd` | User-approved replacement for unavailable source link |
| Low Level Random Battlegrounds | `mod-low-level-rbg` | [https://github.com/azerothcore/mod-low-level-rbg](https://github.com/azerothcore/mod-low-level-rbg) | `master` | `dcb8989b0635fb6de0477818de2579de1930267f` | — |
| Morph Summon | `mod-morphsummon` | [https://github.com/azerothcore/mod-morphsummon](https://github.com/azerothcore/mod-morphsummon) | `master` | `b1fc9db72b5acbdd30639a131fe84da53c82d8f2` | — |
| Multibot Bridge | `mod-multibot-bridge` | [https://github.com/Wishmaster117/mod-multibot-bridge](https://github.com/Wishmaster117/mod-multibot-bridge) | `main` | `1da05982e478cb00e0b6c87314afe7e0e9653ffb` | — |
| NPC Beastmaster | `mod-npc-beastmaster` | [https://github.com/azerothcore/mod-npc-beastmaster](https://github.com/azerothcore/mod-npc-beastmaster) | `master` | `99dbd9b73f63c39b0773c575bea7a8add8049ccf` | — |
| NPC Buffer | `mod-npc-buffer` | [https://github.com/azerothcore/mod-npc-buffer](https://github.com/azerothcore/mod-npc-buffer) | `master` | `532a6ba80c31b673338fcdb747cb2226bec4887e` | — |
| NPC Enchanter | `mod-npc-enchanter` | [https://github.com/azerothcore/mod-npc-enchanter](https://github.com/azerothcore/mod-npc-enchanter) | `master` | `af32add66eafc0e0eb8775999e76ceed75f18b74` | — |
| NPC Spectator | `mod-npc-spectator` | [https://github.com/Gozzim/mod-npc-spectator](https://github.com/Gozzim/mod-npc-spectator) | `master` | `8c9683a2bd8dcb901cc5338342376b15df9e244b` | — |
| NPC Talent Template | `mod-npc-talent-template` | [https://github.com/azerothcore/mod-npc-talent-template](https://github.com/azerothcore/mod-npc-talent-template) | `master` | `d536079191e6ecabb18273b3e46f7583ad19e355` | — |
| Phased Duels | `mod-phased-duels` | [https://github.com/azerothcore/mod-phased-duels](https://github.com/azerothcore/mod-phased-duels) | `master` | `8f122d9c6fb5fc895a232cbc05b30b72ebc455b2` | — |
| Playerbot Guildhouse | `mod-player-bot-guildhouse` | [https://github.com/DustinHendrickson/mod-player-bot-guildhouse](https://github.com/DustinHendrickson/mod-player-bot-guildhouse) | `main` | `1d4d649982a523b674321f6ca4c23d11e60c1b7b` | — |
| Playerbots | `mod-playerbots` | [https://github.com/liyunfan1223/mod-playerbots](https://github.com/liyunfan1223/mod-playerbots) | `master` | `037c01418b5d01506917a3db9b44fd56ac5f965c` | — |
| PVP Titles | `mod-pvp-titles` | [https://github.com/azerothcore/mod-pvp-titles](https://github.com/azerothcore/mod-pvp-titles) | `master` | `2c7c16a4ff504cb43d60919552581833d7efcb05` | — |
| Queue List Cache NPC | `mod-queue-list-cache` | [https://github.com/azerothcore/mod-queue-list-cache](https://github.com/azerothcore/mod-queue-list-cache) | `main` | `27279f247af0c932962f512d3fc261aefb8dc195` | — |
| Quick Teleport | `mod-quick-teleport` | [https://github.com/azerothcore/mod-quick-teleport](https://github.com/azerothcore/mod-quick-teleport) | `master` | `3a88ac0f294f7ce21441fb3cb3de13f87c9683eb` | — |
| Racial Trait Swap | `mod-racial-trait-swap` | [https://github.com/azerothcore/mod-racial-trait-swap](https://github.com/azerothcore/mod-racial-trait-swap) | `main` | `8ae1e6fab13b4660eed76aca8fce998a18343048` | — |
| RDF Expansion | `mod-rdf-expansion` | [https://github.com/azerothcore/mod-rdf-expansion](https://github.com/azerothcore/mod-rdf-expansion) | `master` | `c7a91c5973cda4529495b52b89375913f98726d6` | — |
| Reagent Bank | `mod-reagent-bank` | [https://github.com/ZhengPeiRu21/mod-reagent-bank](https://github.com/ZhengPeiRu21/mod-reagent-bank) | `master` | `62c265338ceba10fb754394413e6c4c61cedf9de` | — |
| Reward Played Time | `mod-reward-played-time` | [https://github.com/azerothcore/mod-reward-played-time](https://github.com/azerothcore/mod-reward-played-time) | `master` | `0a22f9904878e909287daa9c22deeedc7dc5ff24` | — |
| Solo LFG | `mod-solo-lfg` | [https://github.com/azerothcore/mod-solo-lfg](https://github.com/azerothcore/mod-solo-lfg) | `master` | `3821fe1d108ade8d2b7ad6611e41154e05864c65` | — |
| Time is Time | `mod-TimeIsTime` | [https://github.com/dunjeon/mod-TimeIsTime](https://github.com/dunjeon/mod-TimeIsTime) | `master` | `abfb3a7a031c168c481642604c1389a5d92f4499` | — |
| Top Arena NPC | `mod-top-arena` | [https://github.com/azerothcore/mod-top-arena](https://github.com/azerothcore/mod-top-arena) | `master` | `0cef3e349c93d95ef6fc9f9ffa45772a4f338257` | — |
| Transmog | `mod-transmog` | [https://github.com/azerothcore/mod-transmog](https://github.com/azerothcore/mod-transmog) | `master` | `0d85cbc53d63ce2df8527169ce6ae47f5f6f6ba8` | — |
| Weather Vibe | `mod_weather_vibe` | [https://github.com/hermensbas/mod_weather_vibe](https://github.com/hermensbas/mod_weather_vibe) | `main` | `cb854eb96ef9fa7fa4fd1f6e2d3340fcadb945e8` | — |
| who-logged | `mod-who-logged` | [https://github.com/azerothcore/mod-who-logged](https://github.com/azerothcore/mod-who-logged) | `master` | `3f439d0aa56d3a4782dee1467f1bdcb16b35aa2f` | — |

## Initially disabled (14; still installed)

| Module | ID | Repository | Branch | Locked commit | Target |
|---|---|---|---|---|---|
| Account Mounts | `mod-account-mounts` | [https://github.com/azerothcore/mod-account-mounts](https://github.com/azerothcore/mod-account-mounts) | `master` | `0a3b4c4cc084ebbbb7e7e07f88222a08a70b0dde` | Disabled in runtime config |
| Ahn'Qiraj War Effort | `mod-war-effort` | [https://github.com/azerothcore/mod-war-effort](https://github.com/azerothcore/mod-war-effort) | `master` | `512a2dd97e6589482148ed870dc67e7292a8c5ac` | Disabled in runtime config |
| AOE Loot (Fixed Fork) | `mod-aoe-loot` | [https://github.com/TerraByte-tbwps/mod-aoe-loot](https://github.com/TerraByte-tbwps/mod-aoe-loot) | `main` | `be4f06af8e1b455cc31a227f12e2d0a741c799e0` | Disabled in runtime config |
| Cross Faction Battlegrounds | `mod-cfbg` | [https://github.com/azerothcore/mod-cfbg](https://github.com/azerothcore/mod-cfbg) | `master` | `78771c6d0d9d5fcd80206eaeb9668452adcbf4ee` | Disabled in runtime config |
| Leech | `mod-leech` | [https://github.com/ZhengPeiRu21/mod-leech](https://github.com/ZhengPeiRu21/mod-leech) | `master` | `da779951a82d909fa2202360c015af84c4f8ec41` | Disabled in runtime config |
| Money for Kills | `mod-money-for-kills` | [https://github.com/azerothcore/mod-money-for-kills](https://github.com/azerothcore/mod-money-for-kills) | `master` | `cd365d91bf20f0c9044298e6f85cbf8f4373bf51` | Disabled in runtime config |
| No Heartstone Cooldown | `mod-no-hearthstone-cooldown` | [https://github.com/BytesGalore/mod-no-hearthstone-cooldown](https://github.com/BytesGalore/mod-no-hearthstone-cooldown) | `main` | `832ef5e6d7268876112be65202ee8e60d287a936` | Disabled in runtime config |
| NPC Free Professions | `mod-npc-free-professions` | [https://github.com/azerothcore/mod-npc-free-professions](https://github.com/azerothcore/mod-npc-free-professions) | `master` | `01d8624f9c0789550c0b04b23c54928b054619ce` | Disabled in runtime config |
| Ollama Chat | `mod-ollama-chat` | [https://github.com/DustinHendrickson/mod-ollama-chat](https://github.com/DustinHendrickson/mod-ollama-chat) | `main` | `a9966f3e6b20efb98aab8b56ff9d997d8e1bcc06` | Disabled in runtime config |
| Playerbot Level Brackets | `mod-player-bot-level-brackets` | [https://github.com/DustinHendrickson/mod-player-bot-level-brackets](https://github.com/DustinHendrickson/mod-player-bot-level-brackets) | `main` | `a94f9c6458bf6264164436a53ddd4e5c3ed44fdb` | Disabled in runtime config |
| PVP Zones | `mod-pvp-zones` | [https://github.com/azerothcore/mod-pvp-zones](https://github.com/azerothcore/mod-pvp-zones) | `master` | `14f6eddcec993fa7a7af05b2ccdb069ed20339c9` | Disabled in runtime config |
| Random Enchants | `mod-random-enchants` | [https://github.com/azerothcore/mod-random-enchants](https://github.com/azerothcore/mod-random-enchants) | `master` | `6d49d64918f1e798490d0139038a33194fd294df` | Disabled in runtime config |
| Server Auto Shutdown | `mod-server-auto-shutdown` | [https://github.com/azerothcore/mod-server-auto-shutdown](https://github.com/azerothcore/mod-server-auto-shutdown) | `master` | `625b145109553ed56ec2b2d36d6e7b06fee43520` | Disabled in runtime config |
| Skip Death Knight Starting Area | `mod-skip-dk-starting-area` | [https://github.com/azerothcore/mod-skip-dk-starting-area](https://github.com/azerothcore/mod-skip-dk-starting-area) | `master` | `cd0bac42056cc469399487269acbb96264ff813e` | Disabled in runtime config |

## Source-list resolutions

- **Dungeon Clear:** appeared in both source sections. Per the user decision, it is enabled with upstream `DungeonClear.Enable = 1`; the initially-disabled duplicate is stale.
- **Learn Spells:** uses the user-approved [`azerothcore/mod-learn-spells`](https://github.com/azerothcore/mod-learn-spells) replacement, not the inaccessible `noisiver/mod-learnspells` link.
- **City Life:** enabled addition; its manual world SQL and Playerbots/online-bot requirements are documented in [`docs/SQL_SETUP.md`](docs/SQL_SETUP.md).

Configuration master switches and explicit no-switch cases are in [`MODULE_CONFIG_AUDIT.md`](MODULE_CONFIG_AUDIT.md) and `config/module-switches.json`.
