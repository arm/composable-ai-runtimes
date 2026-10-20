<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

# Perception Service

The Perception Service deploys and runs inference workflows on Cairn camera streams.

## Building and Dependencies

Install [uv](https://docs.astral.sh/uv/getting-started/installation/).

On Debian or Ubuntu, install the native dependencies:

```bash
sudo apt-get update
sudo apt-get install \
  build-essential \
  gir1.2-gst-plugins-base-1.0 \
  gir1.2-gstreamer-1.0 \
  gstreamer1.0-pipewire \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  gstreamer1.0-tools \
  libcairo2-dev \
  libgirepository-2.0-dev \
  pkg-config
```

Run service-specific commands from `services/perception`.

Initialize the project environment:

```bash
uv sync --locked
```

Build the service image:

```bash
docker compose build perception-service
```

This requires an ARM64 Docker host. The build downloads the
[OPK 0.1.1 release](https://github.com/arm/open-perception-kit/releases/tag/v0.1.1)
and verifies its SHA256.

## Running

Logs are written to stderr at `LOG_LEVEL` (`INFO` by default).

From the repository root, run the full service stack with:

```bash
docker compose -f services/compose.yaml up --build
```

### Service

```bash
uv run perception_service
```

| Argument | Default | Description |
| --- | --- | --- |
| `--host` | `0.0.0.0` | gRPC listener host. |
| `--port` | `50053` | gRPC listener port. |
| `--model-path` | Not set | Model package or parent directory; may be repeated. |
| `--model-schema-path` | Not set | Optional OPK JSON schema directory used to validate model packages. |
| `--opk-comm-host` | `127.0.0.1` | Internal `opkcomm` WebSocket host. |
| `--opk-comm-first-port` | `7001` | First port in the internal `opkcomm` WebSocket range. |
| `--redis-url` | `redis://messaging-service:6379/0` | Redis endpoint for event publication. |
| `--redis-queue-size` | `64` | Maximum pending messages per event queue. |
| `--redis-timeout` | `1.0` | Redis connect and socket timeout in seconds. |

Without a model path, the service starts with no registered models. A model
package contains `opchain.json`, `model.json`, and its referenced model files.
OPK packages use string descriptor versions (for example, `"1.0.0"` in
`model.json` and `"1.0.1"` in `opchain.json`) and `opk-*` operation IDs. These
schema versions are independent of the OPK release version.

The package directory name becomes the model ID used by workflow inference
stages. For example:

```bash
uv run perception_service \
  --model-path /absolute/path/to/models \
  --model-path /absolute/path/to/custom-model
```

The container defaults to `--model-path /models`. Empty model directories warn
but allow startup; missing or non-directory paths still fail.

### OPK integration

The [Open Perception Kit (OPK)](https://github.com/arm/open-perception-kit)
integration appends hidden `opkperformance` and `opkcomm` stages after inference. `opkcomm` emits opaque `FrameResults` packets
over WebSocket. The `--opk-comm-host` and `--opk-comm-first-port` arguments
configure a contiguous WebSocket range with one port per active pipeline.

Each result-producing pipeline gets its own `opkcomm` WebSocket port and
advertises a session-specific Redis topic:

```text
cairn.perception.sessions.<session-id>.results
```

Messages use the protobuf `CairnEvent` envelope. Its payload is the original
opaque `FrameResults` packet; Perception does not decode it. Publication uses a
bounded queue, drops the oldest pending result under backpressure, and resumes
with new results after Redis recovers. It does not provide durable replay.

A workflow can request the OPK debug output through `DebugOutput`. Port values
of zero use the defaults: HTTP `9999`, WebSocket signaling `8000`, and control
WebSocket `8001`. A successful deployment returns the resolved ports in
`PerceptionSession.debug_endpoint`. Docker Compose publishes the default ports
on the host's loopback interface. Custom ports require corresponding Compose
port mappings.

### Readiness

Perception exposes `grpc.health.v1.Health/Check` with these service names:

| Service name | Meaning |
| --- | --- |
| `""` | Aggregate API and GStreamer readiness. |
| `cairn.perception.v1.PerceptionService` | gRPC API readiness. |
| `cairn.perception.runtime.gstreamer` | GStreamer runtime and GLib dispatcher readiness. |

Checks start as `NOT_SERVING`; `""` becomes `SERVING` when both components are ready.

## Testing

Run the tests that do not require the packaged service with:

```bash
uv run pytest -m "not e2e"
```

Run the unit or integration test category directly with:

```bash
uv run pytest -m unit
uv run pytest -m integration
```

To reproduce the containerized integration test environment on an ARM64
Docker host, build the production-derived test image and run the integration
suite in it.

```bash
docker compose \
  -f compose.yaml \
  -f tests/integration/compose.yaml \
  build perception-integration-tests
docker compose \
  -f compose.yaml \
  -f tests/integration/compose.yaml \
  run --rm --no-deps perception-integration-tests
```

To run the E2E tests with Docker:

```bash
uv run pytest -m e2e
```
