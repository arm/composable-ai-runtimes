# cairn-sdk (lib)

`cairn-sdk` is the Rust library crate for talking to Cairn gRPC services.
It reflects the current proof-of-concept (PoC) SDK surface, giving user applications a typed and native feeling integration point with the runtime services.

## Prerequisites

- Rust toolchain (via `rustup`)
- Protocol Buffers compiler (`protoc`) available on `PATH`

Quick checks:

```bash
rustc --version
cargo --version
protoc --version
```

## What it provides

- `camera_service::CameraService` client for connecting to the PipeWire camera service
- `camera_service::CameraMetadata` for discovered PipeWire camera nodes
- `camera_service::Camera` for direct PipeWire frame capture
- `concordia_service::ConcordiaService` client for connecting to the Concordia inference service
- Library-owned data types:
  - `camera_service::CameraMetadata`
  - `camera_service::Camera`
  - `camera_service::CameraOptions`
  - `camera_service::CapturedFrame`
  - `camera_service::CapturePixelFormat`
  - `concordia_service::BrickType`
  - `concordia_service::RunBrickOptions`
  - `concordia_service::RunBrickOutput`
  - `concordia_service::Detection`
  - `concordia_service::ObjectDetectionOutput`
  - `concordia_service::AudioOutput`

The protobuf-generated modules are kept internal to each service implementation, and responses are mapped into library types.

## Run the examples

From the `lib` directory:

```bash
cargo run --example list_cameras
cargo run --example run_brick_tts
```

By default, the camera discovery example connects to this camera service gRPC address:

```text
http://[::1]:50051
```

By default, inference examples connect to:

```text
http://[::1]:50052
```

To point the discovery example at a different camera service gRPC address, set the `CAMERA_SERVICE_ENDPOINT` environment variable:

```bash
CAMERA_SERVICE_ENDPOINT=http://127.0.0.1:50051 cargo run --example list_cameras
```

Direct PipeWire capture uses the PipeWire runtime socket rather than the camera service gRPC API.

`CameraOptions::default()` requests `640x480` at `30` FPS with `CapturePixelFormat::Yuy2`. The negotiated frame metadata remains available on `CapturedFrame`, including the final `pixel_format`, `width`, and `height`.

If you need to inspect available nodes manually, use PipeWire tooling against the same runtime dir. The daemon socket will appear at `services/camera/.pipewire-runtime/pipewire-0`:

```bash
XDG_RUNTIME_DIR=../services/camera/.pipewire-runtime pw-cli ls Node
```

Override with `CAIRN_CONCORDIA_ENDPOINT`:

```bash
CAIRN_CONCORDIA_ENDPOINT=http://127.0.0.1:50052 cargo run --example run_brick_tts
```

`ConcordiaService::new` and `ConcordiaService::run_brick` both accept borrowed string slices, so callers can pass either string literals or borrowed `String` values without cloning solely for the API.

## Example files

- `examples/list_cameras.rs`
- `examples/run_brick_tts.rs`
- `crates/cairn-sdk/examples/list_cameras.rs`
- `crates/cairn-sdk/examples/run_brick_tts.rs`
