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
- `docs-website/*` should document existing user-facing behaviour and not introduce runtime assumptions. During feature iteration it may temporarily lag, but before a branch is ready it must be reconciled to the current branch state.

### Documentation Scope and Timing

- `docs-website/**` is user-facing documentation.
- `README.md` files are developer and operator documentation.
- Code comments are developer-facing and should stay sparse; prefer self-explanatory code, but any retained comment must remain accurate.
- Documentation does not need to be updated on every intermediate code change while a branch is still evolving.
- Once implementation on a branch has stabilised, run the documentation reconciliation workflow, preferably via the local `update-docs` skill, against the branch's base branch.
- When the task is to audit documentation accuracy rather than update it, use the local `review-docs` skill.
- Reconcile docs to the branch as a whole. Do not treat documentation as append-only; rewrite or remove stale content so each document tells an accurate current-state story.
- Broader documentation audits should be pedantic about accuracy and call out stale or overstated claims.

### Code Reviews
During reviews you MUST ensure that:

- AGENTS.md accurately reflects the current changes (paths/functionality) if they have changed.
- Documentation affected by the branch is reconciled before approval. If docs were intentionally deferred during implementation, run the documentation reconciliation workflow first.
- Stale documentation is updated, rewritten, or explicitly recommended for removal; do not leave known mismatches in place silently.
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
- Identify which documentation surfaces may need reconciling later: `docs-website/**`, relevant `README.md` files, and any necessary code comments.

During editing:
- Prefer targeted patches over broad refactors.
- Always reread files before editing to ensure they have not changed.
- Keep comments concise and technical, and only add them when needed to explain non-obvious logic.
- It is acceptable for docs to lag temporarily while feature work is still iterating, but avoid making documentation more misleading than necessary.
- Keep track of renamed commands, services, APIs, and workflows that will need documentation reconciliation before the branch is ready.

Before completion:
- Run proportionate smoke validation commands.
- Compare the current branch to its base branch and reconcile affected documentation surfaces to match the branch as it exists now.
- Update user-facing docs in `docs-website/**`, developer/operator guidance in relevant `README.md` files, and any still-necessary code comments.
- Rewrite documents coherently instead of appending isolated notes to the end of stale content.
- Recommend removal or substantial rewrite for documentation that is no longer accurate.
- If contracts changed, summarise the impact and any migration expectations.
- Summarise runtime impact (or explicitly state `no runtime behaviour change`).
- Summarise residual risks and untested paths.

## Definition of Done (Early Stage)

A change is done when:
- Relevant Docker builds complete successfully.
- Smoke tests for changed components pass (for example: compose config sanity, startup checks, or compile checks).
- Logs are actionable for startup, lifecycle, and failure states.
- Documentation affected by the branch has been reconciled against the current branch state, with stale content updated, rewritten, or removed as appropriate.
- User-facing behaviour and usage changes are reflected in `docs-website/**`, and developer-facing changes are reflected in the relevant `README.md` files or necessary code comments.
- Validation evidence and limits are clearly reported.
