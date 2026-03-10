---
name: topo
description: Test the deployment of this repository against `topo` CLI tool.
---

This skill tests deployment of the current repository with the `topo` CLI.

## Default behaviour

Prefer a fast, low-overhead path:
1. Load `./.agents/skills/topo/.topocache` if it exists and values are valid (referenced as `.topocache` throughout).
2. If cached values exist, ask the user whether to use cached values or input new ones.
3. Run only the minimum command sequence needed for validation.

## Binary and target resolution

1. Resolve `topo` binary in this order:
   - `TOPO_BIN` from `.topocache`
   - `topo` on `PATH`
   - Ask the user for the binary location
2. Prefer asking the user over filesystem searching.
3. If `topo` cannot be found from cache, `PATH`, or a user-provided location, tell the user they can install from `https://github.com/Arm-Debug/topo-cli.git` and offer to install it.
4. Resolve target in this order:
   - `TOPO_TARGET` from `.topocache`
   - If `.topocache` does not exist (or cached target is not being used), inspect `~/.ssh/config` and ask the user which host alias or `localhost` should be used
5. Do not validate SSH connectivity by default; assume SSH config is correct.

## Execution flow

1. Create a temporary directory for test deployment.
2. Run `topo clone` from the chosen source.
3. Run `topo deploy --target {target}`.
4. Run `docker --context {target} ps`.
5. If requested, inspect logs for specific services.

## Clone from current directory

When running this skill in this repository, treat the current directory as the repo root and clone from `./` by default.

1. Ensure current directory is the repo root (it should contain `services/`).
2. Use this clone command:
   - `TMP_DIR="$(mktemp -d /tmp/topo-XXXXXX)"`
   - `"${TOPO_BIN:-topo}" clone "$TMP_DIR/my-demo" "${TOPO_CLONE_SOURCE:-dir:./}"`
3. Confirm clone success by checking `"$TMP_DIR/my-demo/compose.yaml"` exists.
4. If not running from repo root, use an explicit source path instead (for example `dir:/absolute/path/to/repo/`).

Use this command budget by default:
- `topo clone ...`
- `topo deploy --target ...`
- `docker --context ... ps`
- Optional: `docker --context ... logs <service>`

## Arguments and help usage

1. Do not pre-scan compose files for `x-topo`/template arguments.
2. Only inspect arguments when `topo clone` fails and reports missing required values.
3. If unsure at any point, use `topo --help` (or relevant subcommand `--help`) to check command usage.

## Failure policy

1. Stop at the first blocking failure.
2. Report the exact error and the smallest next action to unblock.
3. Do not apply fixes unless the user explicitly asks.

## Cache file

Use `./.agents/skills/topo/.topocache` as `KEY=VALUE` lines.
Required keys:
- `TOPO_BIN`
- `TOPO_TARGET`
Optional keys:
- `TOPO_CLONE_SOURCE`
