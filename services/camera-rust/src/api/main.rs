mod config;
#[cfg(test)]
mod config_test;
mod service;
mod snapshot;
#[cfg(test)]
mod snapshot_test;

use std::error::Error;

use config::api_listen_addr;
use service::CameraApiService;
use service::pipewire::camera_service_server::CameraServiceServer;
use tonic::transport::Server;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let addr = api_listen_addr()?;

    eprintln!("starting camera API server on {addr}");

    Server::builder()
        .add_service(CameraServiceServer::new(CameraApiService))
        .serve(addr)
        .await?;

    Ok(())
}
