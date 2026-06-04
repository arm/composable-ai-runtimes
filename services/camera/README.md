# Camera Service

The Camera Service is responsible for management of connected cameras, as well as capturing streams from the cameras and providing them to other services.

This Rust port is still early-stage. The container image is built with a Debian `trixie` multi-stage Dockerfile and starts both service binaries.

For containerised camera development, you can use the `.devcontainer/camera` Dev Container; it includes Rust tooling, PipeWire/WirePlumber, GStreamer camera spoofing support, and `grpcurl`.

## Building the Camera Service

The camera service consists of two binaries. One handles the API communications and the other handles notifications from PipeWire.

Local prerequisites:

- Rust toolchain with `cargo`
- `protoc` available on `PATH`, or set via `PROTOC`
- For `notifications` only: PipeWire development libraries available via `pkg-config`

To build the API binary locally:

```bash
cargo build --release --bin api
```

The `api` binary compiles `services/camera/proto/camera_service.proto` during the Cargo build and serves the `CameraService` gRPC API.

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

The `list_cameras` endpoint queries PipeWire for the currently available cameras and returns their metadata over gRPC. Each request takes a fresh snapshot of the PipeWire registry. If PipeWire is unavailable or the snapshot cannot be completed, the API returns `UNAVAILABLE`.

Runtime logs use `tracing` and default to info-level output. Override the filter with `RUST_LOG` when you need to change the global log level or narrow output to one binary:

```bash
RUST_LOG=info cargo run --bin api
```

Debug logs are not enabled by default. Enable them explicitly when diagnosing startup or request flow:

```bash
RUST_LOG=debug cargo run --bin api
```

Logs are labelled by source, such as `api` or `notifications`. API request logs include request context, and notification logs include structured camera, publish, and Redis reconnect fields.

To build the notifications binary:

```bash
cargo build --bin notifications
```

To run the notifications binary locally with the default Redis settings:

```bash
cargo run --bin notifications
```

To set the global log level while running notifications:

```bash
RUST_LOG=info cargo run --bin notifications
```

To include debug-level PipeWire startup logs while running notifications:

```bash
RUST_LOG=debug cargo run --bin notifications
```

By default it connects to Redis at `127.0.0.1:6379` and publishes camera events to `camera.events`. These Redis environment variables are optional overrides:

- `PWC_REDIS_HOST`
- `PWC_REDIS_PORT`
- `PWC_REDIS_CHANNEL_EVENTS`
- `PWC_REDIS_PASSWORD`

Camera event publishing is best effort. If a publish fails after startup, the notification service logs the failed event and attempts to reconnect to Redis for future events, but it does not retry the failed event.

To run the API tests:

```bash
cargo test --bin api
```

To run the notifications tests:

```bash
cargo test --bin notifications
```

To run both binaries and the library tests:

```bash
cargo test --lib --bins
```

To run only the library tests:

```bash
cargo test --lib
```

## Running with Compose

Use the local Compose file in this directory to build and start the camera service container:

```bash
docker compose up --build
```

The camera Compose smoke check validates Compose configuration only. It does not start the hardware-dependent camera services:

```bash
docker compose -f services/camera/compose.yaml config
```

The default container entrypoint starts both service binaries. The `notifications` binary applies its Redis defaults before connecting, retries Redis connection failures with capped Fibonacci backoff, and also depends on PipeWire. The Compose setup mounts the required host runtime and device paths for that workflow.
