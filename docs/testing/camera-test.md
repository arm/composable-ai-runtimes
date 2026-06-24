# Camera Test Plan

Test Strategy: [docs/testing/test-strategy.md](test-strategy.md)

## Purpose

This plan records the camera service compatibility surfaces, support coverage,
and service-owned validation for `services/camera`.

Use it for camera-service-owned checks and support claims. Repository-wide gate
policy, release positioning, cross-component integration, and shared
end-to-end validation rules live in [docs/testing/test-strategy.md](test-strategy.md).

## Validation Rules

Use these rules to map camera service changes and support claims to required
validation. Record camera-specific exceptions in Waivers and Expected Failures.

| Rule | Requirement |
| --- | --- |
| Define the service source | `services/camera/**` is the canonical camera service source directory covered by this plan. Route those changes through this plan unless another row delegates them. |
| Validate support claims | A board, operating-system release, camera class, camera model, deployment path, API, Redis event, or runtime behaviour is supported only when it appears in the coverage matrix and has matching required validation. |
| Route validation by risk | Camera changes require validation when they affect one of the compatibility surfaces listed in the Compatibility Surfaces table. |
| Block merge by default | Required checks block merge by default. Moving one to `main`, scheduled, or release validation requires a documented exception and remaining pre-merge protection. |
| Validate target-dependent claims on target hardware | Changes that affect PipeWire, device access, camera discovery, container permissions, hotplug, Topo, or target runtime behaviour require camera-attached board-farm validation before merge unless an exception row says otherwise. |
| Record persistent validation evidence | Board-farm, `main`, scheduled, and release evidence must name the candidate SHA, image or OS identifiers, workflow run, board ID, camera model, dependency versions, result, and accepted waiver IDs. |
| Skip runtime validation for documentation-only changes only when claims are unchanged | Documentation-only changes do not require runtime validation unless they add, remove, or expand support claims about camera behaviour, commands, configuration, deployment, validation, runtime expectations, APIs, or contracts. |
| Track waived validation as defects | Failing, skipped, expected-failing, or disabled required checks are defects until fixed or tracked in the waiver table with a `test-waiver` ticket. |

## Compatibility Surfaces

The camera service must protect the interfaces and runtime behaviours that
users, operators, or other `cairn-sdk` components can depend on.

| Surface ID | Surface | Scope / key details | Failure modes |
| --- | --- | --- | --- |
| `CAM-SRC` | Service implementation | Rust crate under `services/camera`; binaries `api` and `notifications`; library modules, build script, entrypoint scripts, PipeWire/WirePlumber/libcamera config, Dockerfile, Compose, README, and security notes | Build, logic, lifecycle, configuration, logging, dependency, or documentation regressions |
| `CAM-API` | gRPC API and protobuf contract | Package `camera.pipewire.v1`, service `CameraService`, method `list_cameras`, and messages in `services/camera/proto/camera_service.proto`; Rust protobuf bindings are generated during Cargo builds and are not committed | Contract incompatibility, failed binding generation, stale client expectations, or SDK client breakage |
| `CAM-EVENT` | Redis event contract | Default channel `camera.events`, configurable with `PWC_REDIS_CHANNEL_EVENTS`; JSON payload containing `event_type`, `id`, and `name`; Redis connect, publish, and reconnect behaviour | Consumers break, events mislead, payloads drift, failed reconnects hide future events |
| `CAM-CONFIG` | Runtime configuration | `CAMERA_API_LISTEN_ADDR`, `PWC_REDIS_HOST`, `PWC_REDIS_PORT`, `PWC_REDIS_PASSWORD`, `PWC_REDIS_CHANNEL_EVENTS`, and logging with `RUST_LOG`; default API listen address `0.0.0.0:50051`; default Redis endpoint `127.0.0.1:6379` | Unsupported defaults, invalid configuration accepted silently, unclear failures, or exposed services not matching docs |
| `CAM-CONTAINER` | Container and deployment contract | `services/camera/Dockerfile`, `services/camera/compose.yaml`, root-to-`camera-service` entrypoint, host networking, `/dev`, `/run/udev`, shared PipeWire runtime volume, `video` group, `SYS_NICE`, real-time limits, and service extension through `services/compose.yaml` | Deployment fails, privileges drift, PipeWire cannot start, device access breaks, service cannot start |
| `CAM-CAPTURE` | Direct PipeWire capture path | Shared PipeWire runtime socket and permissions exposed by the camera service container; SDK camera handles use this socket for `get_latest_frame()` rather than the camera service gRPC API | SDK clients cannot capture frames, capture format negotiation fails, socket permissions drift, or target capture claims are unproven |
| `CAM-HARDWARE` | Hardware and target runtime dependencies | Raspberry Pi 5 target running the Raspberry Pi OS 64-bit `trixie` board-farm image; PipeWire, WirePlumber, libcamera stack, Redis, and udev-backed hotplug; Raspberry Pi CSI camera and the board-farm Lenovo Performance FHD Webcam USB target listed in the coverage matrix | Supported hardware path fails, host dependency is unavailable, hotplug is missed, target differs from hosted CI |
| `CAM-OPS` | Operational behaviour | API startup, per-request PipeWire snapshot, Redis connection, Redis reconnect after publish failure, child-process lifecycle, clear failure logs, and non-zero exit on broken critical child process | Operators cannot diagnose failures, degraded behaviour is unpredictable, failed dependencies appear healthy |
| `CAM-DOCS` | Documentation surfaces | `services/camera/README.md`, `services/camera/SECURITY.md`, `docs/testing/**`, `docs-website/**`, and release notes that mention camera commands, support, deployment, APIs, Redis events, or validation | Docs overstate support, commands drift, security posture is misrepresented, release scope is unclear |

## Supported Coverage Matrix

Record maintained support claims that need distinct validation, not every
possible environment combination. Keep test mechanics in Required Validation.

| Coverage target | Environment / variant | Status | Applies to |
| --- | --- | --- | --- |
| Camera service source and hosted checks | `services/camera/**` on hosted CI with Rust, Docker, Compose, and protobuf tooling | Supported | PR and `main` validation |
| gRPC camera listing API | `CameraService.list_cameras` generated from `services/camera/proto/camera_service.proto` | Supported | PR, Rust/Python SDK client validation when the camera contract changes, release |
| Redis camera notifications | Redis endpoint configured by `PWC_REDIS_*`; default `camera.events` channel | Supported | PR for Redis/event changes, board-farm for target hotplug, release |
| Direct PipeWire camera capture | Camera service shared PipeWire runtime socket used by SDK camera handles; frame capture implementation is SDK-owned, but socket availability, permissions, and target PipeWire behaviour are service-owned | Supported | Board-farm validation for service-owned socket or runtime changes that can affect capture; SDK validation for SDK wrapper or frame API changes; release |
| Raspberry Pi CSI camera target | Raspberry Pi 5, Raspberry Pi OS 64-bit `trixie` board-farm image, CSI camera supported by `libcamera` | Supported | Board-farm validation for camera target changes; release |
| USB webcam target | Raspberry Pi 5, Raspberry Pi OS 64-bit `trixie` board-farm image, board-farm-installed Lenovo Performance FHD Webcam (`4XC1D66055`); UVC USB camera expected to expose FHD `1920x1080` MJPEG at 30 FPS and YUY2 video coding | Supported | Board-farm validation for USB webcam target changes; see [USB webcam evidence](camera-usb-webcam-evidence.md) |
| Container runtime | Camera service container with host networking, `/dev`, `/run/udev`, shared PipeWire runtime, `video` group, `SYS_NICE`, and real-time limits from Compose | Supported | PR for container or target runtime changes; board-farm target validation; release |
| Representative Topo deployment | Target-hardware deployment flow that includes the camera service and Redis | Supported | Board-farm validation for Topo, deployment, container privilege, or device mapping changes |
| SDK camera client compatibility | Documented public SDK camera client consuming the camera service contract | Supported | PR for camera API, SDK client, packaging, wrapper behaviour, or release-scope changes; release |

## Required Validation

List validation checks this service requires. Each row says what it covers, what
risk it reduces, when and where it runs, and what it blocks.

The hosted `Camera Smoke` workflow implements the camera-owned Docker and
startup lane as one ordered check: it validates `services/camera/compose.yaml`,
validates the `camera-service` config rendered from `services/compose.yaml`,
builds `camera-service:latest`, and runs the bounded
startup/dependency-failure smoke probes against that same image. The
repository-level `Services Compose Config Check` workflow remains responsible
for non-camera changes to `services/compose.yaml`.

Implementation tickets should define exact proof steps and acceptance criteria
for each required validation lane.

| Test / check | Surfaces covered | Mitigates | Required when | Blocks | Run on |
| --- | --- | --- | --- | --- | --- |
| Rust format check | `CAM-SRC` | Formatting drift that makes review and CI inconsistent | Rust source, build script, or Cargo changes under `services/camera/**` | Merge | Hosted CI |
| Rust lint check | `CAM-SRC`, `CAM-CONFIG`, `CAM-OPS` | Static-analysis, API, config, error-handling, and lifecycle regressions | Rust source, Cargo, protobuf, build script, or feature changes under `services/camera/**` | Merge | Hosted CI |
| Rust unit and binary tests | `CAM-SRC`, `CAM-API`, `CAM-EVENT`, `CAM-CONFIG`, `CAM-OPS` | Internal regressions across camera service source, API, event, configuration, and operational behaviour | Rust source, Cargo, protobuf, or build-script changes | Merge | Hosted CI |
| Protobuf generation check | `CAM-API` | Failed protobuf generation or camera service binding compile regressions | Protobuf, Cargo, build script, API, SDK-facing, or public client changes | Merge | Hosted CI |
| SDK client contract and integration checks | `CAM-API`, `CAM-DOCS` | Camera contract, SDK client, packaging, wrapper, or documented public API regressions | Camera protobuf, `CameraService`, SDK client, packaging, wrapper, documented public API, or camera release-scope changes | Merge | Hosted CI |
| Camera service Compose model check | `CAM-CONTAINER`, `CAM-CONFIG` | Compose syntax, model rendering, environment interpolation, and declared container configuration drift | Camera service Compose, Dockerfile, entrypoint, config, dependency, deployment, or operational docs changes | Merge | Hosted CI |
| Repository camera service config check | `CAM-CONTAINER`, `CAM-EVENT`, `CAM-CONFIG` | Repository-level camera and messaging wiring, Redis defaults, service extension, or rendered camera service config regressions | Repository Compose camera service wiring, camera service Compose, messaging wiring, Redis config, or deployment docs changes | Merge | Hosted CI |
| Camera image build | `CAM-SRC`, `CAM-CONTAINER`, `CAM-CONFIG` | Image, package, dependency, build-output, or protobuf-generation failure | Rust sources, Cargo files, protobuf, Dockerfile, entrypoint scripts, configuration files, Compose, or container documentation changes | Merge | Hosted CI |
| Camera startup smoke | `CAM-CONTAINER`, `CAM-CONFIG`, `CAM-OPS` | Startup, dependency, health-signal, logging, process lifecycle, PipeWire wiring, or Redis wiring regressions | Service changes that could affect build output, startup, dependency handling, runtime configuration, logging, process lifecycle, or PipeWire and Redis wiring | Merge | Hosted CI and board-farm |
| Documentation review and link check | `CAM-DOCS` | Broken links, stale commands, inaccurate support claims, release-scope mismatches, or validation-policy mismatches | `services/camera/README.md`, `services/camera/SECURITY.md`, `docs/testing/**`, `docs-website/**`, release note, API reference, or validation-policy changes | Merge | Hosted CI |
| Hardware-independent API integration | `CAM-API`, `CAM-CONFIG`, `CAM-OPS` | Client/server, tonic, stable camera-listing, and API error-mapping regressions without target hardware | API, protobuf, camera snapshot, config, dependency, lifecycle, or SDK-facing changes testable without PipeWire | Merge | Hosted CI |
| Hardware-independent notification integration | `CAM-EVENT`, `CAM-CONFIG`, `CAM-OPS` | Redis channel, payload, publish, reconnect, and future-event regressions without PipeWire | Event producer, payload schema, Redis config, reconnect, or documented event changes testable without target hardware | Merge | Hosted CI |
| Camera-attached board-farm smoke | `CAM-CONTAINER`, `CAM-CAPTURE`, `CAM-HARDWARE`, `CAM-OPS` | Camera discovery, PipeWire runtime, camera access, capture path, startup, and logs | PipeWire discovery, snapshot, service startup, container permissions, capture-sensitive, or target behaviour changes | Merge | Board-farm |
| Board-farm hotplug and reconnect | `CAM-EVENT`, `CAM-HARDWARE`, `CAM-OPS` | Target hotplug, Redis `connected` and `disconnected` events, reconnect logging, and future-event regressions | Redis notification, PipeWire listener, hotplug, reconnect, or target event behaviour changes | Merge | Board-farm |
| Board-farm PipeWire failure | `CAM-API`, `CAM-HARDWARE`, `CAM-OPS` | `list_cameras`, `UNAVAILABLE` error mapping and PipeWire-unavailable failure logging regressions | API request, snapshot, PipeWire dependency, logging, startup, or operational behaviour changes | Merge | Board-farm |
| Entrypoint child-process failure | `CAM-CONTAINER`, `CAM-OPS` | Hidden child-process failures, leaked children, and false-healthy containers | Entrypoint, startup, process lifecycle, child-process launch, or container health changes | Merge for entrypoint, startup, or process lifecycle changes | Hosted CI and board-farm |
| Topo deployment check | `CAM-CONTAINER`, `CAM-CONFIG`, `CAM-EVENT`, `CAM-OPS` | Deployment, startup, Redis wiring, device mapping, permissions, SDK listing, and runtime socket regressions | Topo, deployment assets, container privilege, device mapping, supported deployment docs, or camera release-scope changes | Merge | Board-farm |

## Waivers and Expected Failures

Track waivers, skips, expected failures, disabled tests, or disabled lanes until
removed. Follow [docs/testing/test-strategy.md](test-strategy.md).

| Waiver / expected failure | Scope | Reason | Remaining protection | Owner | Removal condition or target date |
| --- | --- | --- | --- | --- | --- |
| None recorded | Not applicable | No camera-specific waiver is recorded in this plan | Required validation rows still apply | Not assigned | Add a `test-waiver` defect before waiving, skipping, expected-failing, or disabling any required camera check |

## Open Gaps and Follow-Up

This section intentionally avoids maintaining a backlog of immature test lanes
while camera validation is being bootstrapped.

| Gap | Impact | Owner | Target closure |
| --- | --- | --- | --- |
| Informational | Camera testing is still being bootstrapped; immature lanes and future integration-test improvements are tracked through normal planning or waiver/release processes rather than this component plan. | Camera service owner | Add specific rows only when a gap becomes a release-relevant waiver, a supported-claim blocker, or an owned implementation milestone. |
