# SDK Test Strategy

- Reference: https://jira.arm.com/browse/DEML-1668
- Authors: Robert Taylor
- Reviewers: Gleb Vinnychenko, Mitch Bailey, Carey Williams, Maurice De Vries

## Purpose

This document defines the proposed test strategy for `cairn-sdk`.

The repository spans reusable library code, containerised services, generated protobuf contracts, and hardware-dependent runtime paths such as PipeWire and camera access. We need a shared strategy that defines the minimum evidence required to merge changes, the additional evidence required to trust `main`, and the validation required before we ship an SDK release.

Without that shared strategy, contributors are left to make local decisions about what to run, which increases the risk of gaps, inconsistent expectations in review, and CI that is either too weak to catch regressions or too slow and unreliable to be useful.

## Scope

This strategy covers:

- pull request validation
- post-merge and scheduled validation for `main`
- release-oriented validation
- hosted CI and target-hardware validation
- protobuf and generated artefacts treated as contract surface.

This strategy is intended to guide repository-wide testing expectations rather than define every workflow file or implementation detail.

This strategy defines the quality bar, validation classes, and expectations for merge readiness, `main` validation, and release readiness. The companion `cairn` test plans should contain the implementation detail that people need to read alongside the CI workflow implementation:

- each `cairn` component should own its component-level test plan.
- cross-component integration and end-to-end scenarios should be owned as repository-level lane definitions.
- those plans and lane definitions should name owners, participating components, routing rules, validation environments, and whether each lane blocks merge, `main` validation, or release.

Use [docs/testing/service-test-plan-template.md](service-test-plan-template.md) when creating or refreshing a component-level service test plan.

## Strategy Summary

The proposed strategy is risk-based, target-aware, and pre-merge by default. Pull-request validation provides the evidence to merge by default, while `main`, scheduled, and release lanes run required checks that do not fit the default merge gate.

For supported runtime behaviour, target hardware is the source of truth. Hosted CI is the fast, deterministic feedback lane for checks that do not need device-specific behaviour. The board-farm lane is the authoritative validation environment for supported end-to-end flows and target-sensitive integration, with documented exceptions where cost, queue time, scarcity, or scope justify moving broader coverage out of the pull-request path.

In practice, this means:

- running the required checks for the risks introduced by each change on every relevant pull request by default, including lint, compile, unit, docs-build, startup, contract, hardware-independent integration, and target-hardware validation for supported target behaviour.
- running supported end-to-end flows and target-sensitive integration on real devices by default.
- using a Raspberry Pi board-farm lane for target-hardware validation. That lane should include camera-attached boards for camera-sensitive flows, be callable from GitHub runners, and cover camera, PipeWire, device access, representative `topo` deployment flows, and other supported target-hardware paths.
- treating protobuf definitions and generated artefacts as contract surface and validating them with regeneration, zero-diff checks, and downstream consumer validation where relevant.
- requiring evidence for the risks a change introduces, rather than relying on one generic test lane for all changes.
- defining separate expectations for merge readiness, `main` readiness, and release readiness.

## Quality Bar

We are not aiming for exhaustive testing of every permutation. We are aiming for enough evidence to make three decisions with confidence:

1. A pull request is safe to merge.
2. The `main` branch remains ready for release.
3. Release candidates can provably work end-to-end on the supported environments and hardware.

Failures in required checks are treated as defects and block release unless they are fixed or waived through the **Waivers and Expected Failures** process below.

That quality bar leads to the following rules:

- A change must not merge unless all relevant pull-request gates pass.
- Required validation must remain reliable and actionable. Flaky tests and failures that do not help identify what broke are defects and must be fixed, replaced, or removed through the documented waiver process.
- The test strategy, test plans, and CI workflows must remain maintainable. A validation system that contributors cannot understand, update, or troubleshoot is itself a quality risk.
- Pull-request gates are the default place for validation. A test moves to post-merge or scheduled execution only by exception, when we have measured that it materially harms pull-request latency or queue time, depends on scarce hardware or environments, or checks more than the minimum evidence needed before merge.
- When a test is moved out of pre-merge, the change must be made by a pull request to the relevant component test plan, repository-level lane definition, or workflow documentation. That pull request must document the reason, the remaining pre-merge protection for the risk, and the `main` validation or release-validation lane that retains the signal. Use an architecture decision record only when the change alters repository-wide testing policy rather than one test or lane.
- A change that affects camera, PipeWire, device-access, representative `topo` deployment behaviour, or other supported target-hardware behaviour must pass a required board-farm hardware validation lane before merge unless a documented exception moves the relevant check to `main`, scheduled, or release validation.
- The SDK is not considered shippable based on unit and build checks alone. Representative service-to-service flows, contract validation, and hardware-backed validation for supported end-to-end and target-sensitive integration paths are required.
- `topo` deployment validation matters because deployment is part of the product experience. It does not need exhaustive coverage in every lane, but representative deployment flows should run on target hardware by default, with broader matrices handled in `main`, scheduled, or release-oriented lanes by documented exception.
- Manual testing may still supplement automation, but it is not the default control for common regressions that we can detect in CI.

## Waivers and Expected Failures

The default response to a failing required check is to fix the defect. Waiving, disabling, skipping, or marking a test as expected-to-fail is a temporary exception, not a way to keep a broken check passing indefinitely.

Any waiver for a required check must be introduced by a pull request that:

- links to a defect ticket that tracks restoring the check.
- includes the defect ticket identifier in the skip comment, expected-failure marker, disabled-test comment, or workflow annotation.
- scopes the waiver to the smallest practical test, scenario, environment, or lane.
- documents the reason for the waiver, the remaining coverage for the risk, and the affected release scope.
- names an owner and a target condition or date for removing the waiver.
- tags the defect ticket with a `test-waiver` label so open waivers can be listed before release.

Prefer an explicit skip or expected-failure marker for the smallest known failing case over disabling an entire suite. Disabling a whole lane should be reserved for lane or infrastructure failures, and must still document the remaining protection for the affected risk.

Before a release, open `test-waiver` defects must be reviewed. Release cannot proceed unless each waiver is closed by restoring the check or explicitly accepted for a narrower release scope.

## Risk-to-Evidence Mapping

| Risk | Minimum evidence | Execution lane | Blocks |
| --- | --- | --- | --- |
| Basic code regressions in libraries and services | Lint, compile, unit tests, docs build where relevant | Every pull request | Merge |
| Service cannot build, configure, or start | Image builds, `docker compose ... config`, short startup checks | Every pull request | Merge |
| Interface drift in protobuf and generated clients | Regeneration, zero-diff check, downstream consumer build or lint | Every pull request when affected | Merge |
| Hardware-independent integration breaks | Integration tests using real clients, local services, or local Compose where target-device behaviour is not part of the claim | Every pull request | Merge |
| Target-sensitive integration or end-to-end behaviour regresses | Board-farm validation on supported target hardware for the changed path, including camera, PipeWire, device mount, permission, service-to-service behaviour, and other edge-hardware flows | Every affected pull request by default; broader hardware matrices or long-running validation may move post-merge or scheduled by documented exception | Merge by default; `main` validation and release for any checks moved out of pre-merge |
| Broader lifecycle or multi-service regressions | Change-focused Compose, integration, and representative end-to-end scenarios, with target-hardware execution where the scenario represents supported runtime behaviour | Every pull request by default; broader matrices or soak runs may move to `main` or scheduled lanes by documented exception | Merge by default; `main` validation and release when explicitly moved out of pre-merge |
| Deployment regressions | Representative `topo` deployment validation on target hardware or an environment close to target usage | Every affected pull request by default; broader environment matrices may move to release-oriented or scheduled lanes by documented exception | Merge by default; release readiness and `main` validation for any checks moved out of pre-merge |

A pull request is routed to the board-farm hardware lane when it changes camera capture, PipeWire, device access, representative `topo` deployment behaviour, supported end-to-end flows, target-sensitive integration, or other supported target-hardware paths. Those routing rules should be documented in the relevant `cairn` component test plan and enforced in repository workflows, so contributors can tell before review whether the hardware lane is required.

## Test Categories

The categories below define the terminology used in the quality bar and execution model.

### Unit tests

Unit tests validate a small piece of logic in isolation, usually within a single library, service, app, or binary. They should be fast, deterministic, and not require real services or devices.

Typical examples:

- Rust library logic
- helper functions or translators in service code
- isolated Python logic that does not need a live gRPC service

### Smoke tests

Smoke tests answer the basic question of whether the changed component still configures, builds, starts, and handles basic startup dependencies correctly.

Typical examples:

- `docker compose ... config`
- service image builds
- Docker health checks for containerised services
- short-lived startup checks, including expected dependency and fail-fast behaviour
- package or crate build success

### Contract tests

Contract tests validate compatibility surfaces and schema expectations.

Typical contract surfaces:

- protobuf definitions owned by SDK services
- generated artefacts committed in the repository
- SDK code that depends on generated bindings
- documented Redis channel names and payload shapes once they are formalised

Typical enforcement checks:

- regeneration using the canonical service-owned command
- zero-diff validation for committed generated artefacts
- downstream consumer build, compile, or lint validation

#### Current protobuf contract enforcement

Until we adopt an explicit schema-compatibility tool, protobuf contract validation is defined as reproducible generation plus downstream consumer validation.

On every pull request that changes a protobuf definition or a committed generated protobuf artefact, CI should:

1. Regenerate the affected artefacts using the repository's canonical generation command.
2. If the service commits generated artefacts, fail if regeneration produces a diff relative to the checked-in generated files.
3. Run at least one downstream build, compile, lint, or test check for code that consumes the generated outputs, including consumers that generate bindings only at build time.

For `cairn-sdk`, this means each service that owns protobuf contracts should define and document:

- the canonical regeneration command for its protobuf outputs.
- which generated artefacts are committed and must remain zero-diff in CI.
- at least one downstream consumer build, compile, or lint check that proves the regenerated outputs still integrate correctly.

This rule prevents drift between `.proto` sources and committed generated artefacts without requiring a more mature schema-governance toolchain yet. For consumers that generate bindings only during the build, such as `tonic`-based Rust clients, the downstream consumer build or test step is the enforcement point rather than a zero-diff check.

### Integration tests

Integration tests validate that real components work together across process, container, or network boundaries.

In `cairn-sdk`, the most common integration boundary is often a client library or SDK consumer communicating with a live service, though service-to-service flows are also important where multiple services collaborate.

Typical examples:

- a client library communicating with a live Concordia gRPC service
- generated client bindings exercised against a running service
- service interactions through Redis
- multi-service Compose flows

Integration tests that prove protocol, client, or service wiring without relying on device-specific behaviour can run in hosted CI. Integration tests that make a claim about supported target-device behaviour should run on target hardware by default, because hosted CI cannot prove that the software behaves correctly on the devices we support.

Integration test ownership follows the boundary being tested. A test for one client and one service can be owned by the service or client component plan. A test that spans several `cairn` components should be owned by a repository-level integration lane, with the participating components and blocking status documented in the companion CI test plan.

### End-to-end tests

End-to-end tests validate a representative user or release workflow across deployment, service startup, client interaction, and any required target environment.

Typical examples:

- a representative `topo` deployment followed by a client or SDK workflow against the deployed services
- an SDK consumer exercising a supported service path through the same public API and packaging shape expected by users
- camera-sensitive flows that prove capture, service startup, client access, and output delivery on camera-attached target hardware
- release-candidate validation that combines deployment, service-to-service communication, contract compatibility, and target-hardware behaviour for the supported release scope

End-to-end tests are not expected to exhaustively cover every permutation in every pull request. Supported end-to-end flows should run on target hardware by default because they are evidence about product behaviour on the devices we support. Change-focused, hardware-independent end-to-end checks can still provide fast pre-merge feedback, but they supplement rather than replace target-hardware validation for supported runtime behaviour. Broader environment matrices, long-running flows, and hardware-backed end-to-end runs may run on `main`, on a schedule, or as release gates by documented exception, but their owner, routing rule, and blocking status must be explicit.

### Target-hardware validation

Target-hardware validation covers supported runtime paths where real device behaviour is part of the product claim, including paths that require real devices or host capabilities not available on standard hosted runners.

Typical examples:

- PipeWire camera capture
- device mounts and permissions
- end-to-end flows that depend on edge hardware
- `topo` deployment validation against realistic device conditions

The validation environment and routing expectations for these checks are defined below.

## Validation Environments

Validation runs across two complementary environments:

- **Hosted CI**: the fast feedback environment for every pull request. It runs checks that do not require target devices or host capabilities unavailable on standard hosted runners, including lint, compile, unit, documentation, smoke, contract, hardware-independent integration, and hardware-independent end-to-end checks.
- **Board-farm hardware lane**: a Raspberry Pi-backed environment for supported target behaviour. It is the authoritative validation environment for supported end-to-end flows and target-sensitive integration, and it is required pre-merge for routed changes that affect camera capture, PipeWire, device access, representative `topo` deployment behaviour, or other supported target-hardware behaviour unless a documented exception applies.

The supported platform and hardware matrix should be recorded in the relevant component test plans, repository-level lane definitions, or release criteria. Adding support for a new operating system image, device class, or runtime should include a matching update to the board-farm or release-validation matrix before that platform is treated as supported.

## Execution Model

### Pull Request Validation

Every relevant pull request starts in hosted CI and runs:

- unit tests
- smoke tests, including build and short startup checks
- documentation build
- contract tests, including protobuf regeneration, zero-diff checks on committed generated artefacts, and downstream consumer validation for affected protobuf outputs
- hardware-independent integration tests
- hardware-independent representative end-to-end checks where relevant

Pull requests routed to the board-farm hardware lane must also pass the required target-hardware checks before merge. Routing applies to supported end-to-end flows, target-sensitive integration, and changed target-hardware behaviour. Validation starts in the pull-request gate unless there is a documented exception.

### `main` and Scheduled Validation

This lane is for documented exceptions from pull-request validation: required checks that are too broad, costly, or environment-constrained for the default merge gate.

When a test moves to `main` or scheduled execution, the lane remains a required `main` validation or release check where designated. These lanes are not optional diagnostics.

### Board-Farm Hardware Validation

The board-farm hardware lane runs target-hardware validation for supported end-to-end flows and target-sensitive integration, including camera, PipeWire, `topo`, device access, and other supported hardware-dependent paths.

For routed changes, this lane is pre-merge and change-focused. It proves the hardware path touched by the pull request still works on target hardware using checks such as:

- camera discovery
- short capture or startup validation
- PipeWire attachment
- device-access validation
- one representative `topo` deployment smoke

Broader hardware matrices, disconnect and reconnect behaviour, restart and recovery scenarios, longer soak runs, or fuller end-to-end deployment flows may run after merge or on a schedule only when their cost or scope justifies moving them out of the default pull-request path.

## Readiness Criteria

### Merge readiness

A pull request is ready to merge when:

- all relevant pre-merge CI gates pass, including hosted CI gates, contract checks, and the required board-farm hardware lane for any changed supported end-to-end flow, target-sensitive integration path, or target-hardware behaviour.
- any changed protobuf surface passes regeneration and downstream consumer validation.
- any changed service that should start in CI demonstrates that it can start with its expected dependencies and fail clearly when critical dependencies are missing.
- any camera-sensitive change passes the camera-attached board-farm lane before merge.
- if any check has been moved out of pre-merge by exception, the remaining merge gate for that risk is documented and still passes.
- broader post-merge or scheduled runs may add confidence, but they do not replace required pre-merge evidence unless that exception has been explicitly documented in the repository.

### `main` Readiness

The `main` branch is considered ready for release when:

- all required post-merge and scheduled validation runs on `main` are passing.
- a failing required validation run on `main` is a defect and must be assigned and fixed, not ignored.
- the team can identify whether the key supported workflows are currently healthy or degraded, including service startup, cross-service integration, representative `topo` deployment, and hardware-backed end-to-end, camera, or PipeWire paths where relevant.

`main` readiness is the continuous baseline for release. It means there are no known blocking failures in supported workflows on the latest shared branch, but it does not replace release-candidate validation for a specific version, environment matrix, or release scope.

### Release readiness

Release readiness is a candidate-specific decision. `main` readiness is required, but it is not sufficient on its own.

A release candidate is ready to ship only when:

- the candidate commit comes from a `main` branch that is ready for release.
- all release-candidate validation required for the release scope is green.
- the supported environment and hardware matrix for the release scope has passed.
- there are no known blocking regressions in the supported release scope.
- any open `test-waiver` defects have been reviewed under **Waivers and Expected Failures** and either closed or explicitly accepted for the release scope.

## Approaches Not Taken

### Move broader validation out of the pull-request path before measuring cost

This would assume in advance that slower integration, deployment, or hardware checks are too expensive to keep pre-merge. It was rejected because it weakens confidence in pull requests before we have data and makes `main` the first place we find regressions that could have been caught and attributed to a single pull request.

Expected downsides:

- regressions discovered only after merge
- weaker attribution when several pull requests land before the failure appears
- lower confidence that a green pull request is actually safe to merge

### Rely mostly on manual testing

This would reduce short-term CI effort, but it was rejected because the repository already includes multiple contract and runtime surfaces where regressions are easy to introduce and expensive to debug later.

Expected downsides:

- inconsistent validation expectations
- more regressions escaping into shared branches
- less confidence in interface behaviour and basic service startup health

## Assumptions and Constraints

Assumptions:

- hosted CI runners are available for standard build, lint, docs, and non-hardware service validation.
- hardware-backed validation is available via a board-farm lane backed by Raspberry Pis, including camera-attached boards for camera-sensitive validation, accessible to GitHub runners for board-level paths. This environment is more operationally complex than standard hosted CI and requires active management to maintain reliability.
- protobuf definitions and generated artefacts continue to be treated as active compatibility surface.
- release scope will be defined tightly enough that representative end-to-end and hardware-backed validation is feasible before shipping.

Constraints:

- PipeWire and camera validation require environment capabilities not present on standard hosted runners. Enforcing those gates depends on maintaining board-farm routing and camera-attached Raspberry Pis.
- some integration and hardware checks may become too costly to keep in the default pull-request path and may therefore need a documented exception into post-merge or scheduled lanes once measured data justifies it.
- the repository spans multiple languages and packaging systems, so validation cost is not uniform across components.
- CI complexity needs to remain proportionate to the project's maturity while still enforcing a release-oriented quality bar.

## Trade-offs

Positive outcomes:

- Creates a clearer shared standard for what "tested enough" means for different kinds of changes.
- Makes the quality bars for merge, `main` validation, and release explicit.
- Keeps validation close to the change by default, which should improve attribution and reduce regressions first discovered after merge.
- Gives contract and startup validation higher priority, which should catch a large class of likely regressions early.
- Makes hardware-gated and deployment validation visible while still allowing documented exceptions for truly costly or broad validation.

Trade-offs and limitations:

- Some contributors may see longer feedback cycles for changes that now keep broader validation pre-merge until cost justifies demotion.
- Some important runtime paths sit outside hosted CI and require routed board-farm hardware validation.
- Broader integration confidence may still arrive later than PR feedback when a check has been explicitly moved to post-merge or scheduled execution.
- Additional CI design work will still be needed to translate this strategy into concrete workflows, routing rules, and release criteria.

Security and operational impact:

- Hardware-dependent validation may require privileged containers, device mounts, or host integration on the Raspberry Pi, which should remain isolated from the standard hosted CI lane.
- Keeping board-farm hardware checks operationally separate from hosted CI reduces the risk of privileged or environment-sensitive validation while still allowing automation in CI.

## References and Further Reading

- https://jira.arm.com/browse/DEML-1668
