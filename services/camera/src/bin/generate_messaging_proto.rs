// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::{error::Error, fs, path::Path, process};

const MESSAGING_PROTO: &str = "cairn/messaging/v1/messaging.proto";
const OUTPUT_DIR: &str = "src/notifications/generated";
const PROST_OUTPUT_FILE: &str = "cairn.messaging.v1.rs";
const OUTPUT_FILE: &str = "cairn.messaging.v01.rs";
const OUTPUT_PATH: &'static str = "../messaging/proto";

fn main() {
    if let Err(error) = generate() {
        eprintln!("failed to generate Messaging protobuf serialization: {error}");
        process::exit(1);
    }
}

fn generate() -> Result<(), Box<dyn Error>> {
    let camera_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let proto_dir = camera_dir.join(OUTPUT_PATH);
    let proto_file = proto_dir.join(MESSAGING_PROTO);
    let output_dir = camera_dir.join(OUTPUT_DIR);
    fs::create_dir_all(&output_dir)?;

    prost_build::Config::new()
        .out_dir(&output_dir)
        .compile_protos(&[proto_file], &[proto_dir])?;
    fs::rename(
        output_dir.join(PROST_OUTPUT_FILE),
        output_dir.join(OUTPUT_FILE),
    )?;

    Ok(())
}
