# AGENTS

The instructions below are tool-agnostic and should be followed by any LLM working in this repo. 

## Project summary

`cairn-sdk` is an early-stage SDK developed by ARM and focused on edge runtime foundations, including camera (PipeWire), messaging (Redis pub/sub), and inference (Concordia gRPC) services. The repo also includes a Rust SDK crate (`lib`) and a Docusaurus docs site (`docs-website`). It is designed to be compatible with [`topo`](https://github.com/Arm-Debug/topo-cli), another ARM tool that simplifies container deployments to edge devices. 

## Project maturity

Proof of concept: prioritise fast learning and working increments, while keeping enough clarity for collaborators.

## Assumption policy

In all cases, avoid assumptions and prefer clarifying questions. The threshold differs by maturity:
- Proof of concept: proceed after minimal clarification; tolerate small ambiguity if it does not change behavior.
- Production: require explicit confirmation on requirements, edge cases, and constraints before implementation.
- In-between: ask when ambiguity could affect user expectations or quality.

This repository currently follows the proof-of-concept threshold by default.

## Repository Engineering Standards

### API and Event Contracts

- Treat protobuf files as the current API contracts for this phase.
- Treat Redis channel names and payload formats as compatibility surface once documented.
- Generated protobuf artefacts (`*_pb2.py`, `*_pb2_grpc.py`, `services/camera/pipewire/gen/*`) are version-controlled in this PoC phase.
- Do not hand-edit generated protobuf artefacts unless generation is broken; edit `.proto`, regenerate, and commit the regenerated files.

### Runtime and Reliability

- Fail fast on critical dependency failures with clear logs.
- Ensure degraded behaviour is predictable when Redis, PipeWire, or model assets are unavailable.
- Avoid hidden background loops without observable health/failure signals.

### Security and Operational Safety

- Apply least privilege for container capabilities, device mounts, and volume mounts.
- Never commit credentials, secrets, or environment-specific private endpoints.
- Any new privileged mapping must be justified in relevant README content and Compose comments.

### Architecture Boundaries

- `services/*` is core SDK behaviour.
- `lib/*` exposes reusable SDK-facing behaviour. It contains Rust SDK crates under `lib/crates/*` and Python package files under `lib/python/*`, with no service deployment logic.
- `docs-website/*` should document existing behaviour, not introduce runtime assumptions, should be updated alongside every new PR/feature to reflect the current behaviour of the SDK for users.

### Code Reviews
During reviews you MUST ensure that:

- AGENTS.md accurately reflects the current changes (paths/functionality) if they have changed.
- docs-website/docs/* are updated to include documentation for any new features/changes
- The changes adhere to best practices of the language being used and the project's coding standards; ensure all changes are justifiable and clean.

## Build and Validation Commands

Run the smallest relevant checks for the files you changed.
For PoC completion, smoke tests are sufficient; prioritise config/build/startup sanity checks over full test suites unless explicitly requested.

Compose checks:
```bash
docker compose -f services/compose.yaml config
docker compose -f services/camera/compose.yaml config
```

Messaging service:
```bash
docker compose -f services/compose.yaml build messaging
docker compose -f services/compose.yaml up -d messaging
```

Camera service:
```bash
docker compose -f services/camera/compose.yaml up --build
```

Concordia service: (TBD)
```bash
docker compose -f services/concordia/compose.yaml build
docker compose -f services/concordia/compose.yaml up --build
```

Concordia proto regeneration (only if `.proto` changed):
```bash
cd services/concordia
./generate_proto.sh
```

PipeWire proto regeneration (only if `.proto` changed):
```bash
cd services/camera/pipewire
make proto
```

PipeWire component build (inside `services/camera/pipewire`):
```bash
make clean && make
```

Rust SDK (when touching `lib/**`):
```bash
cd lib
cargo fmt --all -- --check
cargo clippy --all-targets --all-features --no-deps
```

Python bindings package (when touching `lib/python/**` or `lib/crates/cairn-sdk-pyO3/**`):
```bash
cd lib
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --all-features --no-deps
cd python
maturin build
```

Docs website (when touching `docs-website/**`):
```bash
pnpm --dir docs-website install --frozen-lockfile
pnpm --dir docs-website build
```

If hardware-dependent checks cannot be run, state explicitly what was not validated and why.

## Change Workflow

Before editing:
- Read the relevant files for the area you are changing.
- Identify whether the change affects contract, runtime behaviour, docs, or generated artefacts.

During editing:
- Prefer targeted patches over broad refactors.
- Always reread files before editing to ensure they have not changed.
- Keep comments concise and technical, and only add them when needed to explain non-obvious logic.
- Keep docs and config aligned with behaviour changes.

Before completion:
- Run proportionate smoke validation commands.
- For each feature or contract change, add or update concise development documentation in `docs-website/docs` where appropriate.
- If contracts changed, summarise the impact and any migration expectations.
- Summarise runtime impact (or explicitly state `no runtime behaviour change`).
- Summarise residual risks and untested paths.

## Definition of Done (Early Stage)

A change is done when:
- Relevant Docker builds complete successfully.
- Smoke tests for changed components pass (for example: compose config sanity, startup checks, or compile checks).
- Logs are actionable for startup, lifecycle, and failure states.
- Feature work includes relevant, up-to-date development documentation in `docs-website/docs` where appropriate.
- Docs are updated when behaviour or usage has materially changed.
- Validation evidence and limits are clearly reported.
