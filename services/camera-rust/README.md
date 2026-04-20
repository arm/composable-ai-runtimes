# Camera Service

The Camera Service is responsible for management of connected cameras, as well as capturing streams from the cameras and providing them to other services.

## Building the Camera Service

The camera service consists of two binaries. One is responsible for handling the gRPC communications and the other is responsible for handling the notifications sending to the event bus. Both are built with `cargo`:

```bash
cargo build
```
