# cairn-sdk (lib)

`cairn-sdk` is the Rust library crate for talking to the Concordia inference gRPC service.

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

- `inference_service::InferenceService` client for connecting to the service
- Library-owned data types:
  - `inference_service::BrickSpec`
  - `inference_service::BrickType`
  - `inference_service::RunBrickInput`
  - `inference_service::RunBrickOutput`
  - `inference_service::Detection`
  - `inference_service::ObjDetectionOutput`
  - `inference_service::AudioOutput`

The protobuf-generated module is kept internal to the service implementation, and responses are mapped into library types.

## Inference bricks

Current brick types exposed by the Concordia service:

- `BrickType::Tts` (for example variant `kokoro`)
- `BrickType::ObjectDetection` (for example variant `yolo`)

`run_brick` is intentionally thin and proto-aligned:

- Input:
  - `RunBrickInput::Text { text }`
  - `RunBrickInput::Image { image_bytes }`
- Output:
  - `RunBrickOutput::Audio(AudioOutput)`
  - `RunBrickOutput::Detections(ObjDetectionOutput)`

Example `run_brick` usage for TTS:

```rust
use cairn_sdk_lib::inference_service::{
    BrickSpec, BrickType, InferenceService, RunBrickInput, RunBrickOutput,
};

let mut client = InferenceService::new("http://127.0.0.1:50052".to_string()).await?;
let result = client
    .run_brick(
        BrickSpec {
            brick_type: BrickType::Tts,
            brick_variant: "kokoro".to_string(),
        },
        RunBrickInput::Text {
            text: "Hello from Cairn SDK".to_string(),
        },
    )
    .await?;

if let RunBrickOutput::Audio(audio) = result {
    println!("left={} right={}", audio.left_channel.len(), audio.right_channel.len());
}
```

## Run the examples

From the `lib` directory:

```bash
cargo run --example list_bricks
cargo run --example run_brick_tts
```

By default, examples connect to:

```text
http://[::1]:50052
```

Override with `CAIRN_CONCORDIA_ENDPOINT`:

```bash
CAIRN_CONCORDIA_ENDPOINT=http://127.0.0.1:50052 cargo run --example list_bricks
CAIRN_CONCORDIA_ENDPOINT=http://127.0.0.1:50052 cargo run --example run_brick_tts
```

## Example files

- `examples/list_bricks.rs`
- `examples/run_brick_tts.rs`
