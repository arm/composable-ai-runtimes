use std::error::Error;

use camera::api;
use camera::logging;
use tracing::info;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    logging::init();

    let addr = api::api_listen_addr()?;

    info!(%addr, "starting camera API server");

    api::serve(addr).await?;

    Ok(())
}
