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

The daemon image is based on the first-party `debian:trixie` image.
It uses the Raspberry Pi package archive for the camera stack and builds PipeWire from source so the runtime image stays aligned with the Raspberry Pi `libcamera` packages.

- PipeWire runtime and SPA camera modules.
- Raspberry Pi camera stack: `libcamera0.7`, `libcamera-v4l2`, `libpisp1`.
- WirePlumber and the supporting runtime libraries needed for the headless startup path.

The camera service runs WirePlumber with the configuration in `services/camera/config/wireplumber`.
It also starts the PipeWire camera monitor (from `services/camera/pipewire`) in the same container so that camera
connect/disconnect and stream link events are visible in logs.

## Build Process

The compose file builds the camera service image locally. Run from the repository root:

```bash
docker compose -f services/camera/compose.yaml up --build
```

The camera container uses network_mode: host to ensure reliable hotplug detection. PipeWire depends on udev events, which are not consistently delivered inside the container under the default network configuration.

The compose file mounts a minimal set of device nodes for camera and DMA-BUF support. If your camera uses different `/dev/video*`, `/dev/media*`, or `/dev/v4l-subdev*` nodes, update `services/camera/compose.yaml` accordingly.

The compose service starts with a root-only permission entrypoint so it can repair ownership on the mounted `XDG_RUNTIME_DIR` path (`/run/pipewire` by default), then immediately drops back to the non-privileged `camera-service` user before starting PipeWire, WirePlumber, and the camera monitor.

The camera service uses RTKit for realtime scheduling inside the container:

- `cap_add: [SYS_NICE]` allows the container to raise thread priority.
- `ulimits: { rtprio: 95, memlock: -1 }` permits realtime priorities and memory locking.

If you want to build just the camera service image:

```bash
docker build -t camera-service:trixie services/camera
```

You can build and run the Camera Service using `docker compose`:

```bash
docker compose --build
```

Once built, you should be able to see the Camera Service listing the available Video Nodes.
