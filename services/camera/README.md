<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

# Camera Service

The Camera Service discovers connected cameras and their stream formats, making
them available.

## Building and Dependencies

The camera service consists of two binaries. One handles the API communications and the other handles notifications from PipeWire.

Dependencies:

- Rust toolchain with `cargo`
- `protoc` available on `PATH`, or set via `PROTOC`
- PipeWire libraries available via `pkg-config`

Run all commands from `services/camera`.

To build the API binary locally:

```bash
cargo build --bin api
```

To build the notifications binary:

```bash
cargo build --bin notifications
```

## Running

Logs are labeled by source, such as `api` or `notifications`, and `RUST_LOG` controls the tracing filter. API request logs include request context, and notification logs include structured camera, publish, and Redis reconnect fields.

### API

To run the API server locally:

```bash
cargo run --bin api
```

By default it listens on `0.0.0.0:50051`. Override that with `--listen-addr`:

```bash
cargo run --bin api -- --listen-addr 127.0.0.1:50052
```

Or set `CAIRN_CAMERA_API_LISTEN_ADDR`:

```bash
CAIRN_CAMERA_API_LISTEN_ADDR=127.0.0.1:50052 cargo run --bin api
```

The `ListCameras` endpoint returns only camera IDs and names from a fresh PipeWire
registry snapshot. It does not query format parameters. If PipeWire is unavailable
or the snapshot cannot be completed, the API returns `UNAVAILABLE`.

The `supported_formats` camera metadata field has been removed. Use
`get_stream_configurations` with a camera ID to discover resolution, pixel-format,
and frame-rate combinations, optionally filtered by the requested format. Format
collection failures are reported by this endpoint, independently of camera listing.

The API supports standard gRPC health checks. The default health check reports
`SERVING` when the API is accepting requests; it does not check PipeWire or
camera availability.

### Notifications

To run the notifications binary locally with the default Redis settings:

```bash
cargo run --bin notifications
```

By default it connects to Redis at `127.0.0.1:6379` and publishes camera events to `camera.events`. These Redis environment variables are optional overrides:

- `PWC_REDIS_HOST`
- `PWC_REDIS_PORT`
- `PWC_REDIS_CHANNEL_EVENTS`
- `PWC_REDIS_PASSWORD`

Camera event publishing is best effort: failed events are logged but not retried.

### Container

Build and start the camera service container:

```bash
docker compose up --build
```

## Testing

To run the binaries, library tests, and any integration tests:

```bash
cargo test --lib --bins --tests
```
