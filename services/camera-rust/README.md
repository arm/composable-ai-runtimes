# Camera Service

The Camera Service is responsible for management of connected cameras, as well as capturing streams from the cameras and providing them to other services.

This Rust port is still early-stage. The container image uses the Rust `trixie` base image and starts both service binaries.

## Building the Camera Service

The camera service consists of two binaries. One is responsible for handling the API communications and the other is responsible for handling the notifications sending to the event bus. Both are built with `cargo`:

Local prerequisites:

- Rust toolchain with `cargo`
- `protoc` available on `PATH`, or set via `PROTOC`
- For `notifications` only: PipeWire development libraries available via `pkg-config`

To build the API binary locally:

```bash
cargo build --release --bin api
```

The `api` binary compiles `services/camera-rust/proto/camera_service.proto` via `tonic`/`prost` during the Cargo build and starts an API server with a stub response for `list_cameras`.

To run the API server locally:

```bash
cargo run --bin api
```

By default it listens on `0.0.0.0:50051`. Override that with `--listen-addr`:

```bash
cargo run --bin api -- --listen-addr 127.0.0.1:50052
```

Or set `CAMERA_API_LISTEN_ADDR`:

```bash
CAMERA_API_LISTEN_ADDR=127.0.0.1:50052 cargo run --bin api
```

## Building the Container Image

The Docker image is built from the repository root so Docker can copy the Rust crate sources into the build stage:

```bash
docker build -f services/camera-rust/Dockerfile -t camera-service-rust:trixie .
```

The default container entrypoint starts both daemons:

```bash
docker run --rm camera-service-rust:trixie
```

The `notifications` binary currently depends on PipeWire and is only built natively on Linux hosts with the required development libraries available via `pkg-config`.

To build the notifications binary:

```bash
cargo build --bin notifications
```

To build both release binaries on a host with PipeWire development headers installed:

```bash
cargo build --bin api --bin notifications
```

To test it:

```bash
cargo test --bin notifications
```
