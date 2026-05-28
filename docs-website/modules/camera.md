---
id: camera
title: Camera Module
sidebar_position: 2
---

*Looking for endpoint contracts and schemas? See the [API Reference](/api).*

:::tip Why this module is useful
You can start using camera input in your application immediately without worrying about device handling, stream lifecycle, fan-out and zero-copy specifics.
:::

:::info Want to have a try?
Check out the [Object Detection tutorial](/tutorials/getting-started/object-detection) for a camera-driven walkthrough.
:::

## About the Camera Module

The Camera Module is responsible for discovering camera devices, managing frame streams, and emitting camera lifecycle events. It abstracts away the complexities of device handling and stream management, providing a stable interface for applications to access camera input.

## Key Capabilities

- [Camera Discovery](#camera-discovery)
- [Zero Copy](#zero-copy)
- [Reconnection and Fallback](#fallback-handling)

### Camera Discovery

The Camera Module takes care of discovering connected camera devices and providing access to their data. It monitors for camera additions and removals, emitting events that your application can subscribe to and provides streaming access to camera frames without needing to manage device nodes, udev interactions, or stream lifecycle directly.

```python
from cairn import CameraService

camera_service = CameraService()
camera_metadata = camera_service.list_camera_metadata()

camera = camera_service.open(camera_metadata[0])
frame = camera.get_latest_frame()
```

### Zero Copy

The Camera Module will enable zero-copy frame streaming using DMA-BUF or shared memory whenever it can, allowing for efficient sharing of camera frames with your application and other modules. This is critical for performance-sensitive applications that need to minimize latency and CPU overhead.

### Fallback Handling

The Camera Module can help you handle camera disconnections and errors gracefully, providing default reconnection and fallback behavior alongside event notifications.
