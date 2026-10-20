<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

# Messaging Service

The Messaging Service provides Redis-based publish and subscribe messaging for
Cairn services and applications.

Its container image runs Redis and a companion Rust gRPC server that exposes the
standard Health API on port `50054`. The API reports `SERVING` when Redis is ready
and `NOT_SERVING` otherwise.

## Building and Dependencies

The service consists of Redis and the `api` binary. The binary serves the
standard `grpc.health.v1.Health` API and is built into the container image.

Dependencies:

- Rust toolchain with `cargo`
- Redis available on `PATH` when running or testing readiness locally

Run all commands from `services/messaging`.

To build the API binary locally:

```bash
cargo build --bin api
```

## Running

Logs are written to stderr, and `RUST_LOG` controls the tracing filter.

### API

Start Redis with the service configuration:

```bash
redis-server redis.conf
```

In another terminal, start the API:

```bash
cargo run --bin api
```

The API listens on `0.0.0.0:50054` and checks Redis at `redis://127.0.0.1:6379/0`.
Override the gRPC bind address with `--listen-addr HOST:PORT` or
`CAIRN_MESSAGING_API_LISTEN_ADDR`; the flag takes precedence.

### Container

Build and start the service:

```bash
docker compose up --build
```

## Testing

To run the Messaging Service tests:

```bash
cargo test --all-targets --all-features
```
