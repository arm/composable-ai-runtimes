// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::error::Error;
use std::net::SocketAddr;

use tonic::transport::Server;
use tonic_health::ServingStatus;
use tonic_health::pb::health_server::{Health, HealthServer};
use tonic_health::server::HealthReporter;

use super::config;
use super::service;

pub fn api_listen_addr() -> Result<SocketAddr, Box<dyn Error>> {
    config::api_listen_addr()
}

pub(crate) async fn serving_health_service() -> (HealthReporter, HealthServer<impl Health>) {
    let (health_reporter, health_service) = tonic_health::server::health_reporter();
    health_reporter
        .set_service_status("", ServingStatus::Serving)
        .await;

    (health_reporter, health_service)
}

pub async fn serve(addr: SocketAddr) -> Result<(), tonic::transport::Error> {
    let (_health_reporter, health_service) = serving_health_service().await;

    Server::builder()
        .add_service(
            service::pipewire::camera_service_server::CameraServiceServer::new(
                service::CameraApiService::default(),
            ),
        )
        .add_service(health_service)
        .serve(addr)
        .await
}
