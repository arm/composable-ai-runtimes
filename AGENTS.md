# AGENTS

The instructions below are tool-agnostic and should be followed by any LLM working in this repo.

## Project summary

`cairn-sdk` is an SDK developed by ARM and focused on edge runtime foundations, including camera (PipeWire), messaging (Redis pub/sub), and inference (Concordia gRPC) services. The repo also includes a Rust SDK crate (`lib`) and a Docusaurus docs site (`docs-website`). It is designed to be compatible with [`topo`](https://github.com/Arm-Debug/topo-cli), another ARM tool that simplifies container deployments to edge devices.

## Project maturity

Post-PoC active development: prioritise dependable, documented increments that preserve compatibility for published APIs, documented Redis channels, deployment workflows, and SDK-facing behaviour. Keep room for iteration, but treat user-facing contracts and operational guidance as compatibility surfaces once documented.

## Assumption policy

Prefer clarifying questions over risky assumptions. This repository currently follows the in-between threshold by default: ask when ambiguity could affect user expectations, compatibility, operations, or quality; proceed on small internal implementation choices that do not change behaviour.

For production-bound changes, require explicit confirmation on requirements, edge cases, compatibility expectations, and operational constraints before implementation.

## Repository Engineering Standards

### API and Event Contracts

- Treat protobuf files as the current API contracts.
- Treat Redis channel names and payload formats as compatibility surface once documented.
- Follow the existing policy for generated protobuf artefacts in the area you touch: committed generated files stay committed unless the project explicitly changes that policy, while build-generated artefacts stay out of version control.
- Do not hand-edit generated protobuf artefacts unless generation is broken; edit `.proto`, regenerate using the owning service's workflow, and commit regenerated files only where that is the established policy.

### Runtime and Reliability

- Fail fast on critical dependency failures with clear logs.
- Ensure degraded behaviour is predictable when Redis, PipeWire, or model assets are unavailable.
- Avoid hidden background loops without observable health/failure signals.

### Implementation Hygiene

- Avoid helper wrappers that only rename, reshape, or partially hide an already clear value. Add helpers when they reduce real repetition, clarify ownership, or isolate non-obvious behaviour.
- Use precise types at module boundaries, parser boundaries, and test helper boundaries. Avoid broad `Any` or unstructured `dict` annotations when the expected shape is known and can be represented with a dataclass, `TypedDict`, protocol, or narrower built-in type.

### CI Workflow Ownership

- When adding or changing CI workflows, keep each workflow focused on its stated responsibility.
- Avoid duplicating diagnostics or validation already owned by another workflow unless the duplication is intentional and documented.
- Before preserving extra logging or checks, ask whether this workflow should be the source of truth for that failure mode. If another workflow owns it, prefer a clear failure signal here and let the owning workflow provide detailed diagnostics.
- When a workflow is triggered by a shared file, keep validation scoped to the workflow's owned surface unless the workflow explicitly owns the whole shared file. Prefer targeted checks over broad shared-file checks when they preserve the required signal.
- When adding or changing smoke tests, first identify the workflow's owned validation surface and compare against nearby smoke tests before implementation.
- Keep smoke tests focused on behaviour the workflow uniquely validates. Avoid duplicating diagnostics, artifacts, dependency inventories, setup checks, or failure classifications owned by another workflow unless there is a clear operational reason.
- Reuse local helper patterns where they fit, but do not copy another smoke test's structure or assertions without confirming it owns the same validation surface.
- Keep provisioning and toolchain setup in workflow setup steps or dedicated build jobs unless provisioning itself is the behaviour under test.

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
- Documentation does not need to be updated on every intermediate code change while a branch is still evolving, but it must be reconciled before the branch is considered ready.
- Run full documentation reconciliation when the user asks to prepare the branch for review, merge, handoff, or completion; when responding to review feedback about documentation; or when documented behaviour, commands, APIs, or workflows changed.
- When the task is to audit documentation accuracy rather than update it, use the repository's documentation review workflow when one is available.
- Reconcile docs to the branch as a whole. Do not treat documentation as append-only; rewrite or remove stale content so each document tells an accurate current-state story.
- Broader documentation audits should be pedantic about accuracy and call out stale or overstated claims.

### Code Reviews
During reviews you MUST ensure that:

- AGENTS.md accurately reflects the current changes (paths/functionality) if they have changed.
- Documentation affected by the branch is reconciled before approval. If docs were intentionally deferred during implementation, run the documentation reconciliation workflow first.
- Stale documentation is updated, rewritten, or explicitly recommended for removal; do not leave known mismatches in place silently.
- The changes adhere to best practices of the language being used and the project's coding standards; ensure all changes are justifiable and clean.

## Build and Validation Commands

Run the smallest relevant checks for the files you changed. Broaden validation for contract, runtime, service, packaging, or documentation-site changes; smoke tests alone are only sufficient when they cover the changed behaviour. The commands below are the current common entry points; prefer the owning area's current documented command if a service, package, or workflow moves.

Repository lint workspace:
```bash
prek validate-config
prek run --all-files --stage pre-push
```

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
docker compose -f services/compose.yaml build camera-service
docker compose -f services/camera/compose.yaml up --build
```

Camera service proto, binary, and contract checks (when touching `services/camera/**`):
```bash
cd services/camera
cargo fmt --all -- --check
cargo clippy --all-targets --all-features --no-deps
cargo test --lib --bins --tests
```

Concordia service:
```bash
docker compose -f services/concordia/compose.yaml build
docker compose -f services/concordia/compose.yaml up --build
```

Concordia proto regeneration (only if `.proto` changed):
```bash
cd services/concordia
./generate_proto.sh
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
- Run proportionate validation commands.
- After targeted fixes, reread the touched function, workflow block, or document section as a whole and look for duplicated cleanup, logging, assertion, validation, or failure-handling paths.
- Compare the current branch to its base branch and reconcile affected documentation surfaces to match the branch as it exists now.
- Update user-facing docs in `docs-website/**`, developer/operator guidance in relevant `README.md` files, and any still-necessary code comments.
- Rewrite documents coherently instead of appending isolated notes to the end of stale content.
- Recommend removal or substantial rewrite for documentation that is no longer accurate.
- If contracts changed, summarise the impact and any migration expectations.
- Summarise runtime impact (or explicitly state `no runtime behaviour change`).
- Summarise residual risks and untested paths.

### Pull Requests

- Use the repository PR template and fill in each section with concrete impact and validation details.
- Choose a PR title that satisfies the repository title validation check. For this repo, use a conventional-commit style prefix such as `docs:`, `test:`, `fix:`, `feat:`, or `chore:`, and keep the subject lowercase.

## Definition of Done

A change is done when:
- The smallest relevant validation for changed areas passes; service changes include relevant Docker build, compose config, startup, or compile checks.
- Smoke tests for changed components pass when they are the proportionate validation path, and broader tests run when behaviour, compatibility, or packaging risk warrants them.
- Runtime changes have actionable logs for startup, lifecycle, and failure states.
- Documentation affected by the branch has been reconciled against the current branch state, with stale content updated, rewritten, or removed as appropriate.
- User-facing behaviour and usage changes are reflected in `docs-website/**`, and developer-facing changes are reflected in the relevant `README.md` files or necessary code comments.
- Validation evidence and limits are clearly reported.
