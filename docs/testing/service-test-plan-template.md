# Service Test Plan Template

Test Strategy: [docs/testing/test-strategy.md](test-strategy.md)

Use this template when creating or refreshing a `cairn` service test plan. Fill
in the placeholders, delete rows that do not apply, and keep support claims tied
to implemented, documented, and validated behaviour. Bracketed lists are
examples to keep, delete, or replace with service-specific details.

Use these terms consistently:

- **Lane**: a CI, board-farm, scheduled, or release validation path.
- **Required check**: validation that must pass before its merge, `main`, or
  release gate.
- **Documented exception**: why a required check runs after merge, on a
  schedule, or at release.
- **Waiver**: a temporary exception for a failing, skipped, expected-failing, or
  disabled required check. Track it with a `test-waiver` defect.

## Purpose

This plan records `[service name]` compatibility surfaces, support coverage, and
service-owned validation for `[service path]`.

Use it for service-owned checks and support claims. Reference any
repository-level integration, board-farm, deployment, release, or end-to-end lane
that this service can trigger.

## Validation Rules

Use these rules to map service changes and support claims to required
validation. Record service-specific exceptions in Waivers and Expected Failures.

| Rule | Requirement |
| --- | --- |
| Define the service source | Name the owned service path, for example `[service path]/**`. Route those changes through this plan unless another row delegates them. |
| Validate support claims | A support claim is valid only when it appears in the support matrix and has matching required validation. Examples include platforms, devices, deployments, dependencies, clients, protocols, and runtimes. |
| Route validation by risk | Changes require validation when they affect a compatibility surface. Examples include APIs, contracts, Redis events, configuration, container permissions, device access, target runtime behaviour, deployment assets, and docs. |
| Block merge by default | Required checks block merge by default. Moving one to `main`, scheduled, or release validation requires a documented exception and remaining pre-merge protection. |
| Validate target-dependent claims on target hardware | Target-dependent claims must be validated on target hardware unless an exception row says otherwise. Examples include devices, host capabilities, PipeWire, cameras, accelerators, `topo`, and supported target-runtime behaviour. |
| Record persistent validation evidence | Board-farm, `main`, scheduled, and release evidence must name the candidate SHA, environment, workflow run, target, dependency versions, result, and accepted waivers. |
| Skip runtime validation for documentation-only changes only when claims are unchanged | Runtime validation is not required unless docs add, remove, or expand claims about commands, configuration, deployment, validation, runtime behaviour, APIs, or contracts. |
| Track waived validation as defects | Failing, skipped, expected-failing, or disabled required checks are defects until fixed or tracked in the waiver table with a `test-waiver` ticket. |

## Compatibility Surfaces

List service interfaces, hardware dependencies, behaviours, and operational
contracts.

| Surface ID | Surface | Scope / key details | Failure modes |
| --- | --- | --- | --- |
| `[SVC-SRC]` | Service implementation | `[source, binaries, libraries, scripts, packages]` | `[build, logic, lifecycle, configuration regressions]` |
| `[SVC-API]` | API or protocol contract | `[protobuf, HTTP, CLI, SDK-facing behaviour, or "not applicable"]` | `[contract drift, stale artefacts, client breakage]` |
| `[SVC-EVENT]` | Redis channel or event contract | `[channels, environment variables, payload schema, reconnect behaviour, or "not applicable"]` | `[consumers break, events mislead, payloads drift]` |
| `[SVC-CONFIG]` | Runtime configuration | `[environment variables, config files, CLI arguments, defaults]` | `[unsupported defaults, unsafe configuration, unclear failures]` |
| `[SVC-CONTAINER]` | Container and deployment contract | `[Dockerfile, Compose, topo, image, port, health, mount, capability, device, volume, user]` | `[deployment fails, privileges drift, service cannot start]` |
| `[SVC-HARDWARE]` | Hardware and target runtime dependencies | `[required devices, peripherals, host capabilities, drivers, OS image, accelerators, or "not applicable"]` | `[supported hardware path fails, dependency is unavailable, target differs from hosted CI]` |
| `[SVC-OPS]` | Operational behaviour | `[startup logs, dependency failures, retry/reconnect, health, shutdown]` | `[operators cannot diagnose failures, degraded behaviour is unpredictable]` |
| `[SVC-DOCS]` | Documentation surfaces | `[README files, docs-website pages, release notes, API references]` | `[docs overstate support, commands or contracts drift]` |

## Supported Coverage Matrix

Record maintained support claims that need distinct validation, not every
possible environment combination. Use this matrix to expand surface rows such as
`[SVC-HARDWARE]` into specific supported combinations, for example board, OS
image, attached device, driver, or accelerator versions. Keep test mechanics in
Required Validation.

| Coverage target | Environment / variant | Status | Applies to |
| --- | --- | --- | --- |
| `[target, dependency set, protocol, deployment, or client]` | `[board + OS image + device, image + dependencies, model/runtime, or client version]` | `[supported, planned, experimental, unsupported]` | `[PR, main, scheduled, release, or docs only]` |

## Required Validation

List the validation checks this service requires. For each check, say what it
covers, what risk it reduces, when and where it runs, and what it blocks.

Use path-based triggers in `Required when` when possible. Add behaviour-based
triggers when file paths alone do not describe the risk.

| Test / check | Surfaces covered | Mitigates | Required when | Blocks | Run on |
| --- | --- | --- | --- | --- | --- |
| `[format/lint command]` | `[SVC-SRC, SVC-CONFIG]` | `[style, static analysis, source regressions]` | `[source, build, or dependency changes]` | Merge | Hosted CI |
| `[compile/build command]` | `[SVC-SRC, SVC-CONTAINER]` | `[build, package, or configuration failure]` | `[source, Dockerfile, Compose, dependency, package, or entrypoint changes]` | Merge | Hosted CI |
| `[unit test command]` | `[SVC-SRC, SVC-CONFIG, SVC-OPS]` | `[logic, config, error, retry, or lifecycle regressions]` | `[service source changes]` | Merge | Hosted CI |
| `[docs build or link check]` | `[SVC-DOCS]` | `[documentation, link, command, or support-claim drift]` | `[README, docs-website, release note, API reference, or validation-policy changes]` | Merge | Hosted CI |
| `[compose config + image build command]` | `[SVC-CONTAINER, SVC-CONFIG]` | `[container config, permissions, mounts, or startup ordering]` | `[Dockerfile, Compose, topo, script, entrypoint, config, or dependency changes]` | Merge | Hosted CI |
| `[startup or smoke command]` | `[SVC-CONTAINER, SVC-CONFIG, SVC-OPS]` | `[startup, dependency, or health-signal regressions]` | `[startup, dependency, config, container, or lifecycle changes]` | Merge | Hosted CI |
| `[contract regeneration + zero-diff or build check]` | `[SVC-API]` | `[protobuf drift, stale generated artefacts, client breakage]` | `[proto, generated artefact, public API, or SDK-facing changes]` | Merge | Hosted CI |
| `[downstream consumer build/lint/test]` | `[SVC-API]` | `[generated outputs stop integrating with consumers]` | `[contract, binding, SDK-facing, or public client changes]` | Merge | Hosted CI |
| `[Redis/event payload test command]` | `[SVC-EVENT]` | `[channel, payload, publish, reconnect, or consumer regressions]` | `[event producer, payload schema, Redis config, or documented event changes]` | Merge | Hosted CI |
| `[hardware-independent integration or end-to-end workflow command]` | `[SVC-API, SVC-EVENT, SVC-CONFIG, SVC-OPS]` | `[client/service, local integration, or hardware-independent workflow regressions]` | `[API, event, config, dependency, lifecycle, or supported flow changes testable without target hardware]` | Merge | Hosted CI |
| `[service board-farm or target-runtime smoke command]` | `[SVC-CONTAINER, SVC-OPS, target-specific surfaces]` | `[device access, target runtime, startup, deployment, log, or hardware-sensitive regressions]` | `[device, PipeWire, camera, accelerator, peripheral, host capability, or target behaviour changes]` | Merge by default | Board-farm / target lane |
| `[representative topo deployment check]` | `[SVC-CONTAINER, SVC-CONFIG, SVC-OPS]` | `[deployment, device mapping, service startup, or target environment regressions]` | `[topo, deployment, container privilege, device mapping, or supported deployment changes]` | Merge by default | Board-farm / target lane |
| `[main or scheduled exception lane]` | `[surfaces covered by exception]` | `[broader matrix, long-running, scarce-hardware, soak, recovery, or reliability regressions]` | `[required check moved out of pre-merge by documented exception]` | Main and/or release | `[main, scheduled, or owning lane plan]` |
| `[external lane reference, if applicable]` | `[service surfaces exercised by the external lane]` | `[cross-component regressions this service can trigger]` | `[changes require a repository-level integration, end-to-end, deployment, or release lane]` | `[per owning lane plan]` | `[link/name of owning lane plan]` |
| `[release-candidate validation]` | `[release-scoped service surfaces]` | `[candidate, matrix, contract, target-hardware, or end-to-end regressions]` | `[release includes this service or capability]` | Release | `[release readiness record created from docs/testing/release-readiness-template.md](release-readiness-template.md)` |

## Waivers and Expected Failures

Track waivers, skips, expected failures, disabled tests, or disabled lanes until
removed. Follow [docs/testing/test-strategy.md](test-strategy.md).

| Waiver / expected failure | Scope | Reason | Remaining protection | Owner | Removal condition or target date |
| --- | --- | --- | --- | --- | --- |
| `[test-waiver ticket ID and short title]` | `[test, scenario, environment, lane, or release scope]` | `[why the waiver is needed]` | `[checks that still cover the risk]` | `[person or team]` | `[condition/date]` |

## Open Gaps and Follow-Up

Track known gaps without weakening required evidence.

| Gap | Impact | Owner | Target closure |
| --- | --- | --- | --- |
| `[missing test, lane, environment, support-matrix row, or documentation update]` | `[risk created by the gap]` | `[owner]` | `[condition/date]` |
