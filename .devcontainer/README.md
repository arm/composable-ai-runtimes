# Development containers

This repository provides VS Code Dev Containers for the main development areas. Use **Dev Containers: Reopen in Container** and select the relevant configuration.

## Available containers

- `camera`: Rust camera service development. It opens the camera crate with Rust tooling, starts a local PipeWire/WirePlumber runtime, and installs GStreamer plus `grpcurl` for camera debugging.
- `concordia`: Concordia service development. It opens the Python service container and runs `uv sync --active --extra dev` during post-create setup.
- `lib`: Rust/Python SDK development. It opens the SDK workspace and also starts the shared `messaging-service`, `camera-service`, and a GStreamer `camera-spoof-source` so camera SDK examples can be run end to end.

## Useful SDK checks

From the `lib` devcontainer:

```bash
cd /workspaces/cairn-sdk/lib
cargo run -p cairn-sdk-py --example list_cameras
cargo run -p cairn-sdk-py --example get_camera_frame
```

The camera service is available at `http://127.0.0.1:50051` inside the `lib` devcontainer. PipeWire tools such as `pw-cli` and `pw-link` are installed there for inspecting nodes, ports, and links.

The spoof camera source is launched by `services/camera/scripts/dev-spoof-pipewire-camera.sh` and publishes a `Video/Source` node named `gstreamer-test-source`.
