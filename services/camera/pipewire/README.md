# PipeWire Camera Monitor (Scaffold)

## Requirements

- PipeWire development libraries installed (libpipewire-0.3)
- `pkg-config`

## Quick start (build + run):

```sh
make
./server
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
