# cairn-sdk (lib)

`cairn-sdk` is the Rust library crate for talking to Cairn gRPC services.
It reflects the current proof-of-concept (PoC) SDK surface, giving user applications a typed and native feeling integration point with the runtime services.

## Prerequisites

- Rust toolchain (via `rustup`)
- Protocol Buffers compiler (`protoc`) available on `PATH`
- Python 3.12 when building or testing the Python bindings

Quick checks:

```bash
rustc --version
cargo --version
protoc --version
python3 --version
```

Workspace validation from the `lib` directory should explicitly cover both crates:

```bash
cargo check --workspace
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --all-features --no-deps
```

Python binding stub generation from the `lib` directory:

```bash
cargo run -p cairn-sdk-py --bin stub_gen
```

The generated Python stub for the mixed Rust/Python package is written to `python/cairn_sdk/__init__.pyi`.

## Workspace layout

- `crates/cairn-sdk`: Rust SDK crate
- `crates/cairn-sdk-py`: Rust `PyO3` bindings crate
- `python/`: Python package sources and packaging metadata

## Rust SDK

The Rust SDK lives at `crates/cairn-sdk` and is published as the `cairn-sdk-lib` Cargo package. It provides:
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

## Run the Rust examples

From the `lib` directory:

```bash
cargo run -p cairn-sdk-py --example list_cameras
cargo run -p cairn-sdk-lib --example run_brick_tts
```

By default, the camera discovery example connects to this camera service gRPC address:

```text
http://127.0.0.1:50051
```

By default, inference examples connect to:

```text
http://127.0.0.1:50052
```

To point the discovery example at a different camera service gRPC address, set the `CAMERA_SERVICE_ENDPOINT` environment variable:

```bash
CAMERA_SERVICE_ENDPOINT=http://127.0.0.1:50051 cargo run -p cairn-sdk-py --example list_cameras
```

Direct PipeWire capture uses the PipeWire runtime socket rather than the camera service gRPC API.

`CameraOptions::default()` requests `640x480` at `30` FPS with `CapturePixelFormat::Yuy2`. The negotiated frame metadata remains available on `CapturedFrame`, including the final `pixel_format`, `width`, and `height`.

If you need to inspect available nodes manually, use PipeWire tooling against the same runtime dir. The daemon socket will appear at `services/camera/.pipewire-runtime/pipewire-0`:

```bash
XDG_RUNTIME_DIR=../services/camera/.pipewire-runtime pw-cli ls Node
```

Override with `CAIRN_CONCORDIA_ENDPOINT`:

```bash
CAIRN_CONCORDIA_ENDPOINT=http://127.0.0.1:50052 cargo run -p cairn-sdk-lib --example run_brick_tts
```

Both `CameraService::new` and `ConcordiaService::new` accept `Option<String>`. Pass `None` to use the default IPv4 loopback endpoint or `Some(endpoint)` to connect to a custom service address.

## Python bindings

The Python package lives in `python/` and is backed by the `crates/cairn-sdk-py` extension crate.

The bindings currently expose two synchronous clients:
- `CameraService(endpoint=None)` connects to the camera service gRPC endpoint, lists camera metadata, and opens `Camera` handles for frame capture. The default endpoint is `http://127.0.0.1:50051`.
- `ConcordiaService(endpoint=None)` connects to the Concordia inference gRPC endpoint and runs bricks through `run_brick(...)`. The default endpoint is `http://127.0.0.1:50052`.

Opened `Camera` handles use direct PipeWire capture when `get_latest_frame()` is called. `ConcordiaService.run_brick(...)` accepts a Python `dict` payload with exactly one of `text` or `image_bytes` and returns typed output objects. For object detection, `image_bytes` should contain raw packed RGB pixels. If the input comes from `Camera.get_latest_frame()`, pass `frame.pixels.tobytes()` directly when that frame is already RGB.

From the `lib` directory:

```bash
maturin develop
```

Example usage:

```python
from cairn_sdk import ConcordiaService


service = ConcordiaService()
result = service.run_brick(
    "tts",
    "kokoro",
    {"text": "Hello from Cairn SDK"},
)
print(len(result.left_channel), len(result.right_channel))
```

Numeric outputs exposed by the Python bindings use NumPy arrays for channel and bounding-box data.

## Example files

- `crates/cairn-sdk-py/examples/list_cameras.rs`
- `crates/cairn-sdk/examples/run_brick_tts.rs`
