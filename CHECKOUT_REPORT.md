# Source, configuration, and build status

- **Updated:** 2026-10-21
- **Repository / branch:** `alterational/azerothcore-ownedcore` / `arena/06c5561d-azerothcore-ownedcore` (created from `rebuild-897a41c` at `897a41cf13191bd954c5731bfc3128bf966cdbf2`)
- **PR:** #3 targets `rebuild-897a41c` and stays unmerged until separate approval. Historical PR #1 is untouched.

## Pinned sources and profile

The core is `alterational/azerothcore-wotlk.git`, branch `Playerbot`, commit `14c435031d2cb31b1af664af9a83c5d6256302b6`. The inventory contains 70 locked modules: 55 manifest-enabled, 15 runtime-off. The default build selects 69 module sources and excludes only `mod-individual-progression`.

Five user-maintained forks contain the known module compatibility fixes:

| Module | Branch | Locked commit | Included source fix |
|---|---|---|---|
| BGQueueChecker | `master` | `c01d43ea8b69219339eb434c42dd22f34cf11b8c` | Battleground queue hook |
| mod-aoe-loot | `main` | `7a921027ff6c58f9b6c905a3d3f4d966dcbc9994` | Packet signature and global `Item` qualification |
| mod-challenge-modes | `master` | `a48a4d4ae6082a54647a2524f239a86a8ac16ccb` | `OnPlayerResurrect` signatures |
| mod-dead-means-dead | `main` | `47fd15fb0c80e2e7ce36ba0b3188fcd3cb78e853` | `OnPlayerLogin` hook |
| mod-player-bot-level-brackets | `main` | `0c9187fa05eecde09c6b89653350d0edf34eced2` | `EquipAndSpecPersistence` field name |

There are no module-specific overlay patches or patch runner: the fixes are part of those five source pins. Junk to Gold is pinned to `alterational/mod-junk-to-gold` commit `994797eaf7d010e88d3c27f962518d385f31314b`, which adds the matching config template and renames its PlayerScript callbacks for the pinned core API. That pin builds successfully; the preceding `notepadguyOfficial` commit failed Windows compilation on those callback names.

## Configuration and SQL

The default profile installs 69 `.conf.dist` templates: two core templates and 67 module templates. Only `mod-better-item-reloading` and `mod-dual-tracking` ship no module template at their locked revisions. Packaging keeps every template byte-identical and generates an active `.conf` beside it.

The 15 runtime-off modules remain compiled in the default profile. Seven of them contain SQL files at their locked revisions: `mod-cfbg` (2), `mod-npc-free-professions` (1), `mod-ollama-chat` (9), `mod-player-bot-level-brackets` (1), `mod-random-enchants` (1), `mod-skip-dk-starting-area` (1), and `mod-war-effort` (4). See [docs/SQL_SETUP.md](docs/SQL_SETUP.md) for the SQL path inventory. No SQL or database migration has been run; City Life's world SQL remains manual.

## Windows build and release layout

- **Dependencies:** Boost **1.92.0** prebuilt MSVC 14.3 x64 (installer SHA-256 verified, `version.hpp` checked for `BOOST_VERSION 109200` / `BOOST_LIB_VERSION "1_92"`) and portable MySQL **8.4.11** using the dynamic `lib\libmysql.lib`/`lib\libmysql.dll` pair. Cache key `winbuild-deps-boost-1.92.0-msvc14.3-mysql-8.4.11`, no fallback keys.
- **MySQL gate:** a tree is accepted only when its `.mysql-version` marker, the `mysql_version.h` version ID `80411`, and the `libmysql.dll` file/product version all report 8.4.11, and `libmysql.lib`, `bin\mysql.exe`, `bin\mysqld.exe`, and `include\mysql.h` exist. `mysqlclient.lib` is rejected.
- **Configuration:** `RelWithDebInfo` with explicit `-DBOOST_ROOT` and the four `-DMYSQL_*` options in `core/conf/config.sh`; the written file and the resulting `CMakeCache.txt` are both verified. The build directory must be clean before configuration.
- **DLLs:** exactly `libmysql.dll` (MySQL `lib`), `libcrypto-3-x64.dll`, `libssl-3-x64.dll`, and `legacy.dll` (OpenSSL `bin`), with a recursive `dumpbin /DEPENDENTS` closure check. Debug, Boost, VC++ runtime, extra, and private DLLs fail the step.
- **Package:** root-level `authserver.exe`, `worldserver.exe`, those four DLLs, `configs/` (unchanged `.conf.dist` templates plus generated active `.conf` copies, including `configs/modules/`), and the portable `mysql/` tree. No `bin/`, `etc/`, `README.txt`, `SOURCE-PINS.json`, inventory file, or nested ZIP.
- **Configs:** every packaged `.conf.dist` is byte-identical to its pinned upstream template, because no build or packaging step writes to a template; policy reaches the generated active `.conf` only. The package map also points `DataDir`, `LogsDir`, `TempDir`, `SourceDirectory`, and `MySQLExecutable` at package-relative paths so the bundled `mysql/` tree is used.
- **Publication:** the build job uploads the unpacked staging contents, a `verify-artifact` job re-inspects the uploaded root, and the tag job rebuilds one root-relative ZIP with `zipfile` and verifies the namelist before publishing.

## Verified state

Windows run [39590419188](https://github.com/alterational/azerothcore-ownedcore/actions/runs/39590419188) at commit `2b4cca7` **succeeded end to end** for the default no-Individual-Progression profile: provisioning gates, the clean-build-directory guard, `RelWithDebInfo` configuration, full compile and install of both servers, CMake dependency verification, config staging, four-DLL staging, packaging, artifact upload, and the `verify-artifact` job.

| Evidence | Value |
|---|---|
| Build type | `CMAKE_BUILD_TYPE=RelWithDebInfo` |
| Boost | `BOOST_ROOT=C:/local/boost_1_92_0`; link line uses only `-vc143-` libraries |
| MySQL | `C:/tools/mysql/current` include, `lib/libmysql.lib`, `bin/mysql.exe` |
| Staged DLL sources | `libmysql.dll` from MySQL `lib`; the other three from OpenSSL `bin` |
| Artifact | `azerothcore-ownedcore-windows`, 314,108,255 bytes, 14-day retention |
| Artifact fingerprint | 440 entries, manifest SHA-256 `23cd0f9bdd48deafa009ec7d24d45270cafa6c1496ab3945f8f23a0a3b36ae52` |

Local validation: `scripts/validate_project.py`, `py_compile`, `pyflakes`, 65 unit tests, JSON validation of every tracked map, both workflow YAML files, and `git diff --check` pass. The packaging contract was re-checked against the real pinned templates: 29 templates fetched from the pinned core and module commits, all 39 mapped edits applied with zero warnings, every template byte-identical afterwards, and no installed machine-specific value present in the package.

A later commit in this PR only removes an unused helper and corrects documentation; it does not change build behaviour.

## Why the pipeline looks like this

Each rule below exists because a run failed without it:

- **`-DBOOST_ALL_NO_LIB` with the `-D` spelling:** Boost derives its auto-link tag from `_MSC_VER`, and the runner image ships only a 14.5x toolset, which asks for `vc145` libraries the 14.3 package does not contain. MSYS also rewrites a leading `/D` option into a Windows path.
- **`/MD` Boost probe:** the probe must match the core's runtime library, otherwise it fails for the wrong reason.
- **CMake verification reads the link line, not `Boost_*_LIBRARY_RELEASE` cache keys:** Boost resolves through its config package, so those keys never exist. The MySQL path check ignores internal cache bookkeeping such as `USE_MYSQL_SOURCES`.
- **The provider search includes `bin`:** the image's SLProWeb installer uses `copytobin`, flattening `legacy.dll` into `bin` and shipping no `lib/ossl-modules`.

## Limits

No server startup smoke test has been run, no full Linux/Codespaces build is recorded, and no SQL or live-server test has been performed. A GitHub Release is published only by a `v*` tag build, so pull-request runs correctly skip that job.
