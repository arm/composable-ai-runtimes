# Camera Service

The Camera Service is responsible for management of connected cameras, as well as capturing streams from the cameras and providing them to other services.

This Rust port is currently a stub. The container image uses the Rust `trixie` base image and starts both service binaries.

## Building the Camera Service

The camera service consists of two binaries. One is responsible for handling the gRPC communications and the other is responsible for handling the notifications sending to the event bus. Both are built with `cargo`:

To build the release binaries locally:

```bash
cargo build --release --bins
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
