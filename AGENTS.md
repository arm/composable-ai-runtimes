<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

# AGENTS

These tool-agnostic instructions apply to any LLM working in this repository.

## Project context

`cairn` provides edge runtime services for camera discovery and streams
(PipeWire), messaging (Redis pub/sub), and perception workflows. Rust and Python
SDK packages under `lib/` expose these services to applications. Cairn targets
Arm Linux devices and is designed to work with [`topo`](https://github.com/arm/topo).

The project is in post-PoC active development. Preserve published APIs,
documented Redis channels and payloads, deployment workflows, and SDK-facing
behavior. Allow iteration where no compatibility surface has been established.

## Repository layout

- `services/media/`: Rust camera discovery, media API, and lifecycle notifications.
- `services/messaging/`: Redis configuration and Rust health API.
- `services/perception/`: Python perception workflow service.
- `lib/crates/`: Rust SDK workspace (`cairn`, `cairn-media`,
  `cairn-notification`, `cairn-perception`) and Python bindings (`cairn-py`).
- `lib/python/cairn/`: Python package and generated type stubs.
- `lib/tests/`: Python SDK tests and their generated protocol fixtures.
- `docs/spec/`: Service and messaging contracts; `docs/testing/`: test strategy
  and hardware validation; `docs/python-api/`: Python API documentation site.
- `.github/workflows/`, `.github/actions/`, and `.github/scripts/`: CI,
  publication workflows, and supporting tooling.
- `.agents/skills/`: Repository-specific agent workflows.

The root `compose.yaml` is the Topo deployment entry point for Media and
Messaging. `services/compose.yaml` combines Media, Messaging, and Perception;
each service also owns a `compose.yaml` in its directory. Check tracked files
when identifying components: local caches and build outputs can leave obsolete
directories in a checkout.

## Decision policy

Ask before making an assumption that could affect compatibility, production
behavior, operations, security, or user expectations. Proceed with small,
reversible implementation choices that do not change behavior. For a
production-facing ambiguity, clarify requirements, compatibility expectations,
operational constraints, or edge cases before implementation.

## Repository contracts and boundaries

- Protobuf files are API contracts. Do not hand-edit generated protobuf
  artifacts. Change the owning `.proto`, regenerate with the owning component's
  generation workflow, and commit generated files only where that area already
  does so.
- Documented Redis channel names and payload formats are compatibility
  surfaces.
- `services/**` owns deployed service behavior.
- For dependency-source supplement hooks and source-report ownership, follow
  the [licensing guide](docs/licensing-guide.md#service-dependency-source-supplements).
- `lib/**` owns reusable Rust and Python SDK behavior. SDK runtime code must
  not acquire service deployment responsibilities; test harnesses may provision
  services for validation.
- `README.md` files provide developer and operator guidance. Keep code comments
  sparse and accurate.

## Engineering gotchas

- Fail fast with actionable logs when a critical dependency is unavailable.
  Make degraded behavior predictable for Redis, PipeWire, and model assets.
- Do not add unobservable background loops; expose health or failure signals.
- Avoid helpers that only rename or partially hide an already clear value. Add
  helpers when they reduce real repetition, clarify ownership, or isolate
  non-obvious behavior.
- Use precise types at module, parser, and test-helper boundaries instead of
  broad `Any` or unstructured dictionaries when the shape is known.
- In handwritten Rust code, prefer explicit imports and re-exports over
  wildcard imports (`use module::*` and `pub use module::*`) so symbol origins
  remain searchable. Reserve wildcard imports for generated code or established
  preludes.
- Apply least privilege to capabilities, devices, and volumes. Never commit
  secrets or environment-specific private endpoints. Justify new privileged
  mappings in Compose comments.

## Task-specific workflows

- For dependency, build-selection, packaging, third-party asset, or publication
  changes, follow [Licensing and SBOM contributor guide](docs/licensing-guide.md).
- For CI workflow or smoke-test changes, use the repository's
  `develop-ci-workflows` skill.
- For a documentation accuracy audit, use `review-docs`.
- Update documentation only when explicitly requested by the user. Use
  `update-docs` for requested branch-wide documentation updates; review, merge,
  handoff, or completion alone does not require documentation updates.

Skills hold the detailed procedures for these tasks; do not duplicate those
procedures in this file.

## Writing conventions

Always use American English spelling and conventions in documentation, code
comments, user-facing copy, and agent responses.

## Validation routing

Run existing tests appropriate to the affected area. Add or modify tests only
when explicitly requested, including for CI workflow changes.

Select the validation path relevant to the change; the blocks below are not one
sequential script. Run commands from the repository root unless a working
directory is given. For Python bindings changes, use the bindings path instead
of repeating the Rust SDK checks.

Repository lint:

```bash
prek validate-config
prek run --all-files --stage pre-push
```

Compose (check the affected entry points):

```bash
docker compose -f compose.yaml config
docker compose -f services/compose.yaml config
docker compose -f services/media/compose.yaml config
```

Messaging:

```bash
docker compose -f services/compose.yaml build messaging-service
docker compose -f services/compose.yaml up -d messaging-service
```

Media service build and standalone startup (the second command runs in the
foreground):

```bash
docker compose -f services/compose.yaml build media-service
docker compose -f services/media/compose.yaml up --build
```

Media Rust checks are a separate path; startup is not a prerequisite:

```bash
cd services/media
cargo fmt --all -- --check
cargo clippy --all-targets --all-features --no-deps
cargo test --all-targets --all-features
```

Perception (choose a marker selection or the full suite):

Integration tests require GStreamer and PyGObject. End-to-end tests require the
packaged service and external dependencies. Unit tests do not require running
native services, but dependency installation can still require native libraries.

```bash
cd services/perception
uv run pytest -m unit
uv run pytest -m integration
uv run pytest -m e2e
uv run pytest
```

Rust SDK:

```bash
cd lib
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --all-features --no-deps
cargo test --workspace --all-targets
```

Python bindings package (when touching `lib/python/**` or `lib/crates/cairn-py/**`):
```bash
cd lib
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --all-features --no-deps
cargo test --workspace --all-targets
uv build --wheel
uv run --package arm-cairn python -m pytest -m "not e2e" tests
```

Python SDK tests require `protoc` and `redis-server`. See `lib/README.md` for
the Perception end-to-end SDK test path and its ARM64 Docker requirement.

Verify relevant observable behavior; lint and startup alone do not establish
correctness. Clean up validation resources without stopping pre-existing user
services.

State explicitly when hardware-dependent or environment-specific validation
could not run and why.

## Change and review expectations

Before editing, read the owning implementation and identify affected contracts,
runtime behavior, generated artifacts, and documentation surfaces. Make
targeted changes and follow nearby code conventions.

After a non-trivial change, review the complete changed surface:

- remove stale names, unnecessary state, duplicated logic, and misleading
  comments;
- confirm setup, branches, assertions, artifacts, and side effects support the
  owning component's responsibility;
- compare nearby implementations and tests for consistent ownership and
  failure handling;
- search for obsolete commands, fields, environment variables, and
  documentation references.

Treat clear in-scope issues found during this review as part of the change
unless fixing them would materially broaden requirements.

For code review, report findings before summaries. Verify language best
practices, repository standards, compatibility impact, and documentation
accuracy. Update this file only when a durable repository convention,
validation entry point, path, or compatibility boundary changes.

Before completion:

- run proportionate validation, including existing tests appropriate to the affected area;
- report relevant documentation and test gaps without making unrequested edits;
- summarize contract and migration impact, or state that there is none;
- summarize runtime impact, residual risks, and untested paths.

## Pull requests

Preserve PR template headings, checklist wording, links, and comments verbatim.
Only change checkbox states and fill designated content sections. Do not append
explanations to checklist items; put relevant explanations in the appropriate
description section.

Keep each PR to at most 500 changed lines, counting additions and deletions
against its base branch. Split changes exceeding 500 lines into multiple
logically cohesive PRs unless the change cannot be logically split.

All checklist items must be completed and checked before a PR is ready for
initial review.

Use `.github/PULL_REQUEST_TEMPLATE.md` and fill every section with concrete
impact and validation details. In `Steps to Validate the Change`, include
concise, change-specific steps a reviewer can use to validate the behavior or
outcome, or state that no manual validation is needed. Do not include CI test
or check commands, runs, results, or status summaries anywhere in PR
descriptions; GitHub checks provide that information.
Use a conventional-commit title such as `docs:`, `test:`, `fix:`, `feat:`, or
`chore:` with a lowercase subject.
