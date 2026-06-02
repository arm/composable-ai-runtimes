---
title: cairn_sdk Package
description: Python interface for the Cairn SDK.
sidebar_position: 1
---

Python interface for the Cairn SDK.

Use this package to discover cameras, open a camera, and read frames.

## Submodules

- [notification](./notification/index.md)

## Classes

- [`Camera`](#camera)
- [`CameraMetadata`](#camerametadata)
- [`CameraService`](#cameraservice)
- [`Frame`](#frame)

## Camera

Class that handles reading frames from a camera.

### `get_latest_frame() -> Frame`

Return the latest available frame from the camera.

**Returns**

- `Frame`: The most recent frame captured for this camera.

The returned `Frame` exposes the pixel data and basic image metadata.

## CameraMetadata

Information about a camera returned by `CameraService.list_camera_metadata()`.

**Attributes**

- `id`: Camera identifier used when opening the camera.
- `name`: Human-readable camera name.
- `supported_formats`: supported formats reported by the camera service.

## CameraService

Entry point for discovering cameras and opening a camera connection.

Create `CameraService()`, call `list_camera_metadata()` to inspect available cameras, then pass one of those results to `open()`.

### `list_camera_metadata() -> list[CameraMetadata]`

Return the cameras that are currently available.

**Returns**

- `list[CameraMetadata]`: Camera descriptors that can be passed to `open()`.

### `open(camera: CameraMetadata) -> Camera`

Open a camera using a `CameraMetadata` returned by `CameraService.list_camera_metadata()`.

**Parameters**

- `camera`: The `CameraMetadata` object describing the camera to open the connection to, typically taken from `list_camera_metadata()`.

**Returns**

- `Camera`: An opened camera handle that can be used to read frames.

## Frame

Frame data returned by `Camera.get_latest_frame()`.

**Attributes**

- `pixels`: Frame bytes as a one-dimensional NumPy array of `uint8`.
- `width`: Frame width in pixels.
- `height`: Frame height in pixels.
- `stride`: Number of bytes in each image row.
- `pixel_format`: Pixel format name for the frame data.

### `pixels -> numpy.typing.NDArray[numpy.uint8]`

Frame bytes as a one-dimensional NumPy array of `uint8`.

**Returns**

- `numpy.typing.NDArray[numpy.uint8]`: The raw pixel buffer for the frame.
