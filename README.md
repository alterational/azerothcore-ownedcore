# AzerothCore OwnedCore Build

A reproducible source-build workspace for the user's AzerothCore Playerbots fork and the module set assembled from the OwnedCore reference project. Source revisions and configuration policy are tracked in this repository; materialized sources and build output are kept out of Git.

## Build profile

- **Core:** `alterational/azerothcore-wotlk`, branch `Playerbot`, commit `14c435031d2cb31b1af664af9a83c5d6256302b6`.
- **Modules:** 70 immutable source pins; 56 are enabled and 14 are initially runtime-off. The default build selects 69 module sources (55 enabled plus all 14 runtime-off modules).
- **Individual Progression:** pinned and enabled for explicit use, but excluded from the default source build. Add it only when requested.
- **Compatibility:** previously identified module API fixes are included in the selected user-fork commits. No module-specific source overlays are needed.

See [MODULES.md](MODULES.md) for the inventory and [modules.lock.json](modules.lock.json) for every exact revision.

## Prepare a pinned checkout

Requires Python 3.11 and Git. From the repository root, prepare the standard build with one command:

```bash
python3 scripts/prepare_build.py
```

Only when Individual Progression is explicitly requested, use this instead:

```bash
python3 scripts/prepare_build.py --include-module mod-individual-progression
```

The preparation command validates and materializes the pinned sources, applies and verifies the tracked settings, and checks core defaults. It does not compile the server or run SQL. For build commands and Windows workflow details, see [docs/BUILD.md](docs/BUILD.md).

## Configuration and operations

- [Configuration policy](docs/CONFIGURATION.md)
- [Module configuration audit](MODULE_CONFIG_AUDIT.md)
- [SQL and runtime setup](docs/SQL_SETUP.md)
- [Build and Codespaces guide](docs/BUILD.md)
- [Source/build verification status](CHECKOUT_REPORT.md)

Learn Spells uses the approved [azerothcore/mod-learn-spells](https://github.com/azerothcore/mod-learn-spells) repository. City Life remains enabled. Dungeon Clear stays in the selected source build, while the packaging-only config map sets `DungeonClear.Enable = 0` in its generated active `.conf`; its public `.conf.dist` remains unchanged. Build preparation and packaging never execute SQL, but AzerothCore may apply compiled-module migrations at server startup; review [docs/SQL_SETUP.md](docs/SQL_SETUP.md) first. City Life's world SQL remains manual.

## CI and safety

The Windows workflow verifies the pinned core defaults before building, uses four build threads, checks installed runtime configuration, and packages only after the build succeeds. It pins Boost **1.92.0** (prebuilt MSVC 14.3 x64, SHA-256-verified installer) and portable MySQL **8.4.11** with the dynamic `libmysql.lib`, builds with `RelWithDebInfo`, and verifies the generated `core/conf/config.sh` and the CMake dependency cache before packaging. Individual Progression is excluded from pull-request, push, and tag builds; manual workflow dispatch can opt it in. A versioned release is restricted to a successful no-Individual-Progression tag build.

The published archive is a single ZIP whose root directly contains `authserver.exe`, `worldserver.exe`, exactly the four runtime DLLs (`libmysql.dll`, `libcrypto-3-x64.dll`, `libssl-3-x64.dll`, `legacy.dll`), `configs/` with `configs/modules/`, and the portable `mysql/` tree. There is no `bin/`, no `etc/`, no developer metadata, and no ZIP inside the ZIP.

Historical Windows run [39123849901](https://github.com/alterational/azerothcore-ownedcore/actions/runs/39123849901) completed the then-current default no-Individual-Progression build, including runtime-config checks and artifact upload; it predates the Junk to Gold config pin. The first build with that module's repack-matching source, [39157828752](https://github.com/alterational/azerothcore-ownedcore/actions/runs/39157828752), failed on two `PlayerScript` callback names. The user-provided follow-up source pin renames those callbacks to the pinned core API; a fresh Windows run is required to verify it. The older packaging step also blanked 30 public config values, so its artifact is not the corrected deliverable. The local package code preserves each `.conf.dist` byte-for-byte, creates a sibling `.conf`, and applies only the tracked packaging edits. No Linux/Codespaces full build is recorded; see [CHECKOUT_REPORT.md](CHECKOUT_REPORT.md).

The runtime package includes unchanged public `.conf.dist` templates and active `.conf` copies generated from them under `configs/`. `config/package-config-edits.json` controls edits to module, authserver, and worldserver copies; missing files/keys or incompatible value types produce non-fatal warnings. `scripts/stage_windows_runtime_dlls.py` proves the DLL closure with `dumpbin`, and `scripts/package_runtime.py` refuses any layout other than the root-level release layout described above. Installed machine-specific active configs are not copied. Do not add private credentials/secrets, client/game data, maps, vmaps/mmaps, or database dumps to Git or the package. Generated `core/` and build output are ignored. Review [docs/SQL_SETUP.md](docs/SQL_SETUP.md) before a server startup; City Life's world-database SQL remains a manual operation.
