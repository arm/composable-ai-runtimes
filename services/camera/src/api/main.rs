mod config;
#[cfg(test)]
mod config_test;
mod service;
#[cfg(test)]
mod service_test;
mod snapshot;
#[cfg(test)]
mod snapshot_test;

use std::error::Error;

use camera::logging;
use config::api_listen_addr;
use service::CameraApiService;
use service::pipewire::camera_service_server::CameraServiceServer;
use tonic::transport::Server;
use tracing::info;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    logging::init();

    let addr = api_listen_addr()?;

    info!(%addr, "starting camera API server");

    Server::builder()
        .add_service(CameraServiceServer::new(CameraApiService))
        .serve(addr)
        .await?;

    Ok(())
}
