use std::error::Error;
use std::net::SocketAddr;

use tonic::transport::Server;

use super::config;
use super::service;

pub fn api_listen_addr() -> Result<SocketAddr, Box<dyn Error>> {
    config::api_listen_addr()
}

pub async fn serve(addr: SocketAddr) -> Result<(), tonic::transport::Error> {
    Server::builder()
        .add_service(
            service::pipewire::camera_service_server::CameraServiceServer::new(
                service::CameraApiService::default(),
            ),
        )
        .serve(addr)
        .await
}
