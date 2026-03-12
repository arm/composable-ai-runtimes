# Messaging Redis Docker Image

This directory contains a Redis Docker image using a custom `redis.conf` tuned for pub/sub workloads.
It underpins the messaging path used in the current Cairn SDK proof of concept (PoC), where lightweight pub/sub integration is enough to exercise cross-module communication.

## Prerequisites

- Docker installed and running.

## Build

From this directory:

```sh
docker build -t redis-pubsub:local .
```

## Run

```sh
docker run -d -p 6379:6379 --name redis-pubsub redis-pubsub:local
```

## Docs

- Default port (6379): https://github.com/redis/docker-library-redis/blob/6dabc615e3296bea231564400fa89e4b8b1312ee/alpine/Dockerfile#L153
- Config docs:
  - https://raw.githubusercontent.com/redis/redis/8.4/redis.conf
  - https://redis.io/docs/latest/operate/oss_and_stack/management/config/
