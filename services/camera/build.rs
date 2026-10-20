// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

fn main() {
    println!("cargo:rerun-if-changed=proto/camera_service.proto");

    tonic_prost_build::configure()
        .compile_protos(&["proto/camera_service.proto"], &["proto"])
        .unwrap_or_else(|error| panic!("failed to compile camera API protos: {error:?}"));
}
