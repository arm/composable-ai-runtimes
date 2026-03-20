# User Image

This directory contains a multi-stage container build for running the Cairn Python bindings against the container's native PipeWire stack.

## Why this exists

The Python bindings must be built inside a Linux environment that already has the target PipeWire development packages installed. Building the wheel with:

```bash
maturin build --release --auditwheel skip
```

avoids bundling a separate `libpipewire` into the wheel, so the installed extension links against the runtime image's system `libpipewire` and `libspa` libraries.

The Rust SDK build also depends on protobuf source files outside `lib/`, so the Docker build copies:

- `lib/`
- `services/concordia/src/inference/proto/`
- `services/camera/pipewire/proto/`

into the builder stage.

## Build & Deploy

Run from the repository root:

```bash
docker compose -f user-application/compose.yaml build
docker compose -f user-application/compose.yaml push
```
