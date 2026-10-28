<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

# arm-cairn (lib)

Cairn provides Rust and Python client libraries for interacting with
Cairn services. The Rust SDK is organized into crates, and the Python
bindings are published as the `arm-cairn` wheel.

## Prerequisites

- Rust toolchain (via `rustup`)
- Redis server (`redis-server`) available on `PATH` and local port `6379` free
  for notification-service tests
- Python `>=3.13.17,<3.14` when building or testing the Python bindings

## Building and Validation

Workspace validation from the `lib` directory covers all crates:

```bash
cargo check --workspace
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --all-features --no-deps
```

## Testing

From the `lib` directory:

```bash
cargo test --workspace --all-targets
uv run python -m pytest -m "not e2e" tests
```

With an ARM64 Docker host available, deploy the Perception stack and exercise it
through the Python SDK:

```bash
uv run --locked python -m pytest -m e2e tests/test_e2e_perception_workflow.py
```

## Rust SDK

The Rust SDK lives at `crates/cairn` and is published as the `arm-cairn`
Cargo package; its Rust import name is `cairn`. Its supporting client packages
are `arm-cairn-camera`, `arm-cairn-notification`, and `arm-cairn-perception`.
The SDK provides typed clients for the Camera, Notification, and Perception
services. `NotificationService` takes a gRPC health endpoint and connects to
Redis at `127.0.0.1:6379` after the service reports readiness.

Perception result decoding uses the [OPK Rust SDK](https://crates.io/crates/open_perception_kit)
from crates.io. Producer and schema identities must match
the SDK and the OPK release packaged in the Perception service.

## Python Bindings

From the `lib` directory:

```bash
uv sync --locked --no-install-project
uv pip install maturin==1.12.1
uv run --no-sync maturin develop
```

Python binding stub generation from the `lib` directory:

```bash
cargo run -p arm-cairn-py --bin stub_gen
```

The command above generates Python type stubs (`.pyi`) for the SDK's Rust/PyO3
bindings in `python/cairn/`. Regenerate these files after changing the
Python-facing API. The pre-push checks verify that the stubs match the bindings.
