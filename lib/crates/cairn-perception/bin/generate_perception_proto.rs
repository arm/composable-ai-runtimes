// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::{env, error::Error, fs, path::Path, process};

const PERCEPTION_PROTO: &str = "cairn/perception/v1/perception.proto";
const OUTPUT_DIR: &str = "src/generated";

fn main() {
    if let Err(error) = generate() {
        eprintln!("failed to generate Perception gRPC bindings: {error}");
        process::exit(1);
    }
}

fn generate() -> Result<(), Box<dyn Error>> {
    let perception_crate_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let proto_dir = perception_crate_dir.join("../../../services/perception/proto");
    let proto_file = proto_dir.join(PERCEPTION_PROTO);
    let output_dir = perception_crate_dir.join(OUTPUT_DIR);
    fs::create_dir_all(&output_dir)?;

    tonic_prost_build::configure()
        .out_dir(&output_dir)
        .compile_protos(&[proto_file], &[proto_dir])?;

    Ok(())
}
