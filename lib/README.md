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
- `inference_service::InferenceService` client for connecting to the Concordia inference service
- Library-owned data types:
  - `camera_service::Camera`
  - `camera_service::Stream`
  - `inference_service::BrickSpec`
  - `inference_service::BrickType`
  - `inference_service::RunBrickInput`
  - `inference_service::RunBrickOutput`
  - `inference_service::Detection`
  - `inference_service::ObjDetectionOutput`
  - `inference_service::AudioOutput`

The protobuf-generated modules are kept internal to each service implementation, and responses are mapped into library types.

## Run the examples

From the `lib` directory:

```bash
cargo run --example list_cameras
cargo run --example list_streams
cargo run --example list_bricks
cargo run --example run_brick_tts
```

By default, camera examples connect to:

```text
http://[::1]:50051
```

By default, inference examples connect to:

```text
http://[::1]:50052
```

Override with `CAIRN_PIPEWIRE_ENDPOINT`:

```bash
CAIRN_PIPEWIRE_ENDPOINT=http://127.0.0.1:50051 cargo run --example list_cameras
CAIRN_PIPEWIRE_ENDPOINT=http://127.0.0.1:50051 cargo run --example list_streams
```

Override with `CAIRN_CONCORDIA_ENDPOINT`:

```bash
CAIRN_CONCORDIA_ENDPOINT=http://127.0.0.1:50052 cargo run --example list_bricks
CAIRN_CONCORDIA_ENDPOINT=http://127.0.0.1:50052 cargo run --example run_brick_tts
```

## Example files

- `examples/list_cameras.rs`
- `examples/list_streams.rs`
- `examples/list_bricks.rs`
- `examples/run_brick_tts.rs`
