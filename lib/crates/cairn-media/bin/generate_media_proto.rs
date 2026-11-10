// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::{env, error::Error, fs, path::Path, process};

const MEDIA_PROTO: &str = "media_service.proto";
const OUTPUT_DIR: &str = "src/generated";

fn main() {
    if let Err(error) = generate() {
        eprintln!("failed to generate Media gRPC bindings: {error}");
        process::exit(1);
    }
}

fn generate() -> Result<(), Box<dyn Error>> {
    let media_crate_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let proto_dir = media_crate_dir.join("../../../services/media/proto");
    let proto_file = proto_dir.join(MEDIA_PROTO);
    let output_dir = media_crate_dir.join(OUTPUT_DIR);
    fs::create_dir_all(&output_dir)?;

    tonic_prost_build::configure()
        .out_dir(&output_dir)
        .compile_protos(&[proto_file], &[proto_dir])?;

    Ok(())
}
