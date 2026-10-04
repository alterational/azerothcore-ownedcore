# Build and Codespaces

## What the fast CI does

`.github/workflows/validate.yml` runs on pushes and pull requests targeting `main` (and can be dispatched manually). It verifies manifest/lock consistency, the pinned source-state decisions and config-map shape, Python syntax, and JSON syntax. It does **not** fetch sources, compile AzerothCore, start a server, validate a database, require game data, or prove runtime behavior.

On Codespaces creation, the dev container validates metadata, downloads the approximately 1.5 GB pinned core/module source tree, and applies/checks the audited `.conf.dist` switches. It does **not** install system dependencies, compile, start a server, or apply SQL. An already-created Codespace does not rerun `postCreateCommand`; if it was created before this behavior was added, run the preparation commands manually below or rebuild the container.

## Build on demand

Use a Codespace or Linux machine with ample disk, RAM, and CPU. From the repository root:

```bash
python3 scripts/validate_project.py
python3 scripts/materialize.py
python3 scripts/apply_module_config.py --apply --source-templates
python3 scripts/apply_module_config.py --check --source-templates
cd core
./acore.sh install-deps
./acore.sh compiler all
cd ..
python3 scripts/apply_module_config.py --apply
python3 scripts/apply_module_config.py --check
```

The exact `install-deps` and `compiler all` command names were checked against the pinned `acore.sh`; `compiler all` maps to clean, configure, and compile, and the pinned core CI script calls the same command. These commands are **source-verified, not build-verified** in this project until a full successful compile is recorded in `CHECKOUT_REPORT.md`. The available sandbox has limited RAM/CPU; assess resources before compiling. The pinned compiler defaults to `nproc + 2` build jobs; set `MTHREADS=1` in the environment if you intentionally need to reduce parallelism, with the expected longer build time.

Pinned READMEs for AutoBalance, CrossFaction Battleground, and NPC Spectator each cite a minimum AzerothCore revision. Their compatibility with this Playerbots fork's ancestry has not been independently established; preserve the locked SHAs and treat a full compile/runtime review as the compatibility check.

`materialize.py` creates shallow Git checkouts for the locked core and every module with `install: true`, including the 14 initially disabled modules. It does not install dependencies, build, apply the config policy, or apply SQL. Run `apply_module_config.py --apply --source-templates` before the build to set audited switches in the generated modules' `.conf.dist` templates. The pinned core installs active `.conf` files under `core/env/dist/etc/modules`; default `--apply`/`--check` operates on those after install. Pass `--config-dir <path>` if the build uses a custom `CONFDIR`.

The build alone does not apply City Life's manual SQL. Automatic module migrations may run later when a server connects to databases; see [SQL_SETUP.md](SQL_SETUP.md) and review backups/authorization before server startup. Runtime module switch handling is separate; see [CONFIGURATION.md](CONFIGURATION.md).

## Current verification status

The full source checkout was materialized at all locked SHAs and validated, but the full build was not run due to the sandbox's limited resources. No manual compile workflow is present. Do not report a successful build until a real pinned-set compile succeeds. Record the exact command, exit code, and useful output in `CHECKOUT_REPORT.md`. No database credentials or game client data should be added to Actions.
