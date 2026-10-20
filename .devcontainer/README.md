<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

# Development containers

This repository provides VS Code Dev Containers for the main development areas. Use **Dev Containers: Reopen in Container** and select the relevant configuration.

## Available containers

- `camera`: Rust camera service development. It opens the camera crate with Rust tooling, starts a local PipeWire/WirePlumber runtime, and installs GStreamer plus `grpcurl` for camera debugging.
- `perception`: Python perception service development. It uses the service runtime image, shares the Camera Service PipeWire socket, and starts a GStreamer spoof camera.
- `lib`: Rust/Python SDK development. It opens the SDK workspace and also starts the shared `messaging-service`, `camera-service`, and a GStreamer `camera-spoof-source` for testing SDK camera access.

## Useful SDK checks

From `/workspaces/cairn-sdk/lib` in the `lib` devcontainer, follow the
[SDK build and validation checks](../lib/README.md#building-and-validation).

The camera service is available at `http://127.0.0.1:50051` inside the `lib` devcontainer. PipeWire tools such as `pw-cli` and `pw-link` are installed there for inspecting nodes, ports, and links.

The spoof camera source is launched by `services/camera/scripts/dev-spoof-pipewire-camera.sh` and publishes a `Video/Source` node named `gstreamer-test-source`.
