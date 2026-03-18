# Camera Service

The Camera Service is responsible for management of connected cameras, as well as capturing streams from the cameras and providing them to other services. The streaming technology is based on PipeWire.
Within the current Cairn SDK proof of concept (PoC), it serves as the reference implementation for camera discovery and stream handling on supported edge devices.

## Building and Running Camera Service

This service uses WirePlumber as the PipeWire session manager.

The Camera Service is currently designed to run on a Raspberry Pi. The container images are designed to be lightweight to not take up much room.

## Dependencies

### Host Requirements

- Raspberry Pi with camera enabled.
- Docker with Compose v2.
- Access to camera device nodes (e.g. `/dev/video*`, `/dev/media*`, `/dev/v4l-subdev*`).
- DMA-BUF and DRM devices for zero-copy (e.g. `/dev/dma_heap/*`, `/dev/dri/*`).
- Udev data available at `/run/udev` for device discovery.

### Image Dependencies

The daemon image is based on `dtcooper/raspberrypi-os:bookworm` and installs these key components:

- PipeWire and the bundled WirePlumber session manager, built from a pinned upstream commit and installed into the standard system paths.
- Camera stack: `libcamera0.4`, `libcamera-ipa`, `libcamera-v4l2`, `libv4l-0`.
- SPA modules for camera: `libspa-0.2-libcamera`.
- D-Bus and RTKit support for the headless session manager startup path.

The camera service runs WirePlumber with its default configuration (the Raspberry Pi OS package does not expose a profile flag).
It also starts the PipeWire camera monitor (from `services/camera/pipewire`) in the same container so that camera
connect/disconnect and stream link events are visible in logs.

## Build Process

The compose file builds the camera service image locally. Run from the repository root:

```bash
docker compose -f services/camera/compose.yaml up --build
```

# Optional validation client
```bash
docker compose -f services/camera/compose.yaml --profile validation up --build
```

The compose file mounts a minimal set of device nodes for camera and DMA-BUF support. If your camera uses different `/dev/video*`, `/dev/media*`, or `/dev/v4l-subdev*` nodes, update `services/camera/compose.yaml` accordingly.

The compose stack also includes a small client container that connects to the camera service and lists PipeWire nodes every 10 seconds as a lightweight validation step.
It is disabled by default; enable it with `--profile validation`.

The camera service uses RTKit for realtime scheduling inside the container:

- `cap_add: [SYS_NICE]` allows the container to raise thread priority.
- `ulimits: { rtprio: 95, memlock: -1 }` permits realtime priorities and memory locking.

If you want to build just the camera service image:

```bash
docker build -t camera-service:bookworm services/camera
```

You can build and run the Camera Service using `docker compose`:

```bash
docker compose --build
```

Once built, you should be able to see the Camera Service listing the available Video Nodes.
