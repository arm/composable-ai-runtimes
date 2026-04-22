ARG RUST_IMAGE=rust:1.93.1-trixie@sha256:ecbe59a8408895edd02d9ef422504b8501dd9fa1526de27a45b73406d734d659

FROM ${RUST_IMAGE} AS camera-service-rust-build

WORKDIR /src

COPY Cargo.toml Cargo.lock ./
COPY src ./src

RUN cargo build --locked --release --bins

FROM ${RUST_IMAGE} AS camera-service-runtime

COPY --from=camera-service-rust-build /src/target/release/grpc /usr/local/bin/grpc
COPY --from=camera-service-rust-build /src/target/release/notifications /usr/local/bin/notifications
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/grpc /usr/local/bin/notifications /usr/local/bin/entrypoint.sh \
  && ldconfig

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
