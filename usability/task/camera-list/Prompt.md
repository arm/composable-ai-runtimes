You are working in the Cairn SDK repository on a Raspberry Pi board-farm runner
with the Cairn camera service available on `127.0.0.1:50051`.

Task:
Create a minimal Rust example at `lib/crates/cairn-sdk/examples/ai_usability_list_cameras.rs` that:
1. Uses the Rust SDK crate API `cairn_sdk::camera_service::CameraService`
2. Connects to the camera service endpoint from `CAMERA_SERVICE_ENDPOINT`, defaulting to `http://127.0.0.1:50051`
3. Calls `list_camera_metadata()`
4. Fails if no cameras are returned
5. Prints one line per discovered camera as `camera: <name>`

Constraints:
- Use Rust
- Use the existing `cairn-sdk-lib` package through its library crate name `cairn_sdk`
- Do not import or use Python `cairn_sdk`
- Do not call `grpcurl`
- Do not use raw gRPC/protobuf clients directly
- The verifier will run `cd lib && CAMERA_SERVICE_ENDPOINT=http://127.0.0.1:50051 cargo run --quiet -p cairn-sdk-lib --example ai_usability_list_cameras`
- Keep the example self-contained
- Do not list the whole repository
- You may inspect `lib/crates/cairn-sdk/examples/list_cameras.rs` and the camera service module if needed
- You must create or update `lib/crates/cairn-sdk/examples/ai_usability_list_cameras.rs` with the `write_file` tool
- Do not change any existing repository files except creating or updating that example
- The example must exit with code 0 on success and non-zero on failure
- The example must print errors to stderr
