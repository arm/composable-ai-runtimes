# PipeWire Camera Service

## Requirements

- PipeWire development libraries installed (libpipewire-0.3)
- `pkg-config`
- For gRPC server: `grpc++`, `protobuf`
- For proto generation: `protoc` and `grpc_cpp_plugin`

## Quick start (build + run)

```sh
make
./server
```

## Proto layout

The protobuf contracts are split by responsibility:

- `pipewire_types.proto`: shared `Camera` and `Stream` messages
- `pipewire_service.proto`: public gRPC service contract
- `pipewire_events.proto`: event schema used with Redis

Generate the protobuf artefacts locally with:

```sh
make proto
```

## gRPC server runtime arguments

The gRPC server in `src/server.cc` accepts positional arguments:

- `argv[1]`: bind address (default `0.0.0.0`)
- `argv[2]`: port (default `50051`)

Examples:

```sh
# defaults to 0.0.0.0:50051
./server

# binds to 127.0.0.1:6000
./server 127.0.0.1 6000
```
