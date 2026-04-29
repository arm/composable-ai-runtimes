# Camera Service

The Camera Service is responsible for management of connected cameras, as well as capturing streams from the cameras and providing them to other services.

This Rust port is still early-stage. The container image is built with a Debian `trixie` multi-stage Dockerfile and starts both service binaries.

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

The `api` binary compiles `services/camera-rust/proto/camera_service.proto` during the Cargo build and currently serves a stub `list_cameras` response.

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

To build the notifications binary:

```bash
cargo build --bin notifications
```

To run the notifications binary locally with the default Redis settings:

```bash
cargo run --bin notifications
```

By default it connects to Redis at `127.0.0.1:6379` and publishes camera events to `camera.events`. These Redis environment variables are optional overrides:

- `PWC_REDIS_HOST`
- `PWC_REDIS_PORT`
- `PWC_REDIS_CHANNEL_EVENTS`
- `PWC_REDIS_PASSWORD`

Camera event publishing is best effort. If a publish fails after startup, the notification service logs the failed event and attempts to reconnect to Redis for future events, but it does not retry the failed event.

To run its tests:

```bash
cargo test --lib
```

## Running with Compose

Use the local Compose file in this directory to build and start the camera service container:

```bash
docker compose up --build
```

To validate the Compose configuration without starting the service:

```bash
docker compose config
```

The default container entrypoint starts both service binaries. The `notifications` binary applies its Redis defaults before connecting, retries Redis connection failures with capped Fibonacci backoff, and also depends on PipeWire. The Compose setup mounts the required host runtime and device paths for that workflow.
