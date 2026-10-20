---
name: develop-ci-workflows
description: Implement or review GitHub Actions workflows, CI scripts, smoke tests, standalone probes, and board-farm validation in Cairn. Use when changing `.github/workflows/**`, CI support scripts, smoke-test entry points, CI provisioning, or hardware-backed validation.
---
<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

# Develop CI Workflows

Keep each workflow focused on the externally meaningful behavior it uniquely
owns.

## Establish ownership

1. State the workflow's responsibility and the failure signal it must provide.
2. Inspect nearby workflows, scripts, and smoke tests before choosing the
   structure.
3. Identify diagnostics, provisioning, validation, and artifacts already owned
   elsewhere.
4. When a shared file triggers the workflow, validate only this workflow's
   owned surface unless it explicitly owns the whole file.

Do not duplicate another workflow's detailed diagnostics or validation unless
there is a documented operational reason.

## Shape smoke tests

- When a smoke test is part of the change, keep its primary entry point focused
  on the externally meaningful behavior being validated.
- Put retry loops, parsing, diagnostics, and artifact writing in helpers when
  those mechanics are not themselves under test.
- Treat expected failures from a standalone probe or CLI as controlled command
  failures with clear stderr and exit codes. Use pytest assertions to validate
  the probe result, returned JSON, and postconditions.
- Keep passing tests quiet. Record optional or non-fatal diagnostics as
  structured output or metadata rather than stderr noise.
- Reuse an established helper only when it owns the same operation and failure
  semantics.

## Provision dependencies

- Keep provisioning and toolchain setup in workflow steps or dedicated build
  jobs unless provisioning is the behavior under test.
- Use `uv` or `uvx` for Python execution and environments, `pytest` for test
  structure, and `prek` for configured lint and pre-push validation.
- Record Python-only test libraries in the Python invocation or dependency
  manifest. Install system dependencies such as GStreamer, PyGObject, Docker,
  or board-farm tooling in the Dockerfile, runner setup, or workflow step that
  provisions them.

## Handle board-farm tests

- Prefer runner selection that matches the validation's hardware and
  environment needs, reserving board-farm capacity for checks that depend on
  its specialized capabilities.
- Use the owning harness's startup, readiness, diagnostics, cleanup, and
  one-off probe helpers.
- Prefer explicit stable configuration for fixed hardware unless discovery or
  hotplug is under test.
- Select fixed cameras through CI variables and stable PipeWire target-object
  identifiers rather than volatile device IDs.

## Review the result

Check that every retained setup step, branch, field, assertion, artifact, and
side effect supports the workflow's stated responsibility. Remove duplicated
failure classification, dependency inventories, setup checks, and diagnostics
owned elsewhere.

Run the smallest relevant checks. Use relevant workflow-run results as
validation evidence when available, and report any validation gaps.
