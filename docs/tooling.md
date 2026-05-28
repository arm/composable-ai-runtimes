# Tooling

## Use Cases

### Run repository lint checks

Tool: `prek`

`prek` runs repository linting.

### Build and validate the Rust SDK (`lib/`)

Tool: `cargo`  
`cargo` applies when changes touch Rust source, examples, or Rust CI checks. It is appropriate because `cargo` is the intended first-party tool for the Rust ecosystem, with build, dependency resolution, tests, clippy, and rustfmt integrated into one standard workflow.

### Compile and generate protobuf interfaces

Tool: `protoc`  
`protoc` applies when `.proto` contracts change or generated stubs are out of date. It is appropriate because `protoc` is the intended first-party compiler for Protocol Buffers and guarantees both Rust and Python code are generated from exactly the same service contract.

### Manage Python dependencies and environments

Tool: `uv`  
`uv` handles Python dependency resolution and environment synchronization. It is appropriate because it provides fast installs, reproducible dependency sets, and a single workflow for local development and container builds.

### Test Python service behaviour

Tool: `pytest`  
`pytest` handles Concordia test execution, especially gRPC integration checks. It is appropriate because the test suite already uses pytest conventions (assertions, skipping, discovery), so no extra test harness is needed.

### Build and validate the camera service (`services/camera/`)

Tool: `cargo` and `docker compose`
`cargo` handles the Rust camera service binaries, tests, clippy, rustfmt, and gRPC code generation from `services/camera/proto/camera_service.proto`. `docker compose` validates and runs the container workflow that includes PipeWire, WirePlumber, host device mounts, Redis notification settings, and the `camera-service` image.

### Develop and build documentation site (`docs-website/`)

Tool: `pnpm`  
`pnpm` covers install, local docs preview, type checks, and static builds in `docs-website/`. It is appropriate because `pnpm` is fast and space-efficient: it stores package content once in a central content-addressable store and links it into the project, reducing duplicate `node_modules` data.

### Run services locally in containers (`services/*`)

Tool: `docker` + `docker compose`  
`docker` handles image builds, and `docker compose` handles startup of one or more local services together. This is appropriate because it gives repeatable runtime environments and captures service wiring (ports, volumes, device mounts, dependencies) as versioned configuration.

### Automate PR checks and docs deployment

Tool: GitHub Actions  
GitHub Actions handles repository-level validation and docs deployment on PR/push events. It is appropriate because workflows are versioned with the repo, run in clean environments, and enforce the same checks for every contributor.
