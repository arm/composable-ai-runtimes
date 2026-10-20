// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::{error::Error, fs, path::Path, process};

const MESSAGING_PROTO: &str = "cairn/messaging/v1/messaging.proto";
const OUTPUT_DIR: &str = "src/generated";
fn main() {
    if let Err(error) = generate() {
        eprintln!("failed to generate Messaging protobuf bindings: {error}");
        process::exit(1);
    }
}

fn generate() -> Result<(), Box<dyn Error>> {
    let crate_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let proto_dir = crate_dir.join("../../../services/messaging/proto");
    let proto_file = proto_dir.join(MESSAGING_PROTO);
    let output_dir = crate_dir.join(OUTPUT_DIR);
    fs::create_dir_all(&output_dir)?;

    let mut config = prost_build::Config::new();
    config.out_dir(&output_dir);
    config.bytes([".cairn.messaging.v1.CairnEvent.payload"]);
    config.compile_protos(&[proto_file], &[proto_dir])?;

    Ok(())
}
