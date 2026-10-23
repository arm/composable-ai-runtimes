# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

ARG RUST_IMAGE=docker.io/library/rust:1.99.1-alpine3.23@sha256:2a941e16ec6e357ff7112e92336087772584122b6ae4b30eb36cb9adff5b5458

FROM ghcr.io/grpc-ecosystem/grpc-health-probe:v0.4.51@sha256:cc4ff9327e602119103bedef448eec26f8ba02bce5c81107cb3685c360c4a6c0 AS grpc-health-probe

FROM ${RUST_IMAGE} AS messaging-api-build

ARG EXPECTED_RUST_VERSION
RUN if [ -n "$EXPECTED_RUST_VERSION" ]; then \
      actual="$(rustc --version)"; \
      case "$actual" in \
        "rustc $EXPECTED_RUST_VERSION "*) ;; \
        *) echo "Rust compiler mismatch: expected $EXPECTED_RUST_VERSION, found $actual" >&2; exit 1 ;; \
      esac; \
    fi

WORKDIR /src

RUN apk add --no-cache build-base=0.5-r3

COPY Cargo.toml Cargo.lock ./
COPY src ./src

RUN cargo build --locked --release

FROM docker.io/library/redis:8.4.7-alpine@sha256:f9b3b74607c14a568cf0bda340432ca7ffd0682e3a53183412a8236974bdf69e

LABEL org.opencontainers.image.licenses="Apache-2.0"

COPY redis.conf /usr/local/etc/redis/redis.conf
COPY --from=messaging-api-build /src/target/release/api /usr/local/bin/api
COPY --from=grpc-health-probe /ko-app/grpc-health-probe /usr/local/bin/grpc_health_probe
COPY --chmod=755 scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY LICENSE /usr/share/licenses/cairn/LICENSE
COPY THIRD-PARTY-DISCLAIMER.txt /THIRD-PARTY-DISCLAIMER.txt
COPY notices/ /usr/share/licenses/cairn/

HEALTHCHECK --interval=2s --timeout=2s --retries=10 \
  CMD ["grpc_health_probe", "-addr=127.0.0.1:50054"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
