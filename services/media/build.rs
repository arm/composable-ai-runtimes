// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

fn main() {
    const MIN_PIPEWIRE_VERSION: &str = "1.6.2";
    pkg_config::Config::new()
        .cargo_metadata(false)
        .atleast_version(MIN_PIPEWIRE_VERSION)
        .probe("libpipewire-0.3")
        .unwrap_or_else(|error| {
            panic!(
                "Media requires PipeWire {MIN_PIPEWIRE_VERSION} or newer. \
                 Upgrade the PipeWire development packages or use the container build.\n{error}"
            )
        });

    println!("cargo:rerun-if-changed=proto/media_service.proto");
    println!("cargo:rerun-if-changed=proto/cairn/media/v1/stream_configuration.proto");

    tonic_prost_build::configure()
        .compile_protos(&["proto/media_service.proto"], &["proto"])
        .unwrap_or_else(|error| panic!("failed to compile media API protos: {error:?}"));
}
