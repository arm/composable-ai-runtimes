// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::error::Error;

use messaging::api;
use messaging::logging;
use tracing::info;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    logging::init();

    let addr = api::api_listen_addr()?;

    info!(%addr, "starting Messaging API server");

    api::serve(addr).await?;

    Ok(())
}
