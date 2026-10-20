// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::error::Error;
use std::net::SocketAddr;

use redis::Client;
use tonic::transport::Server;
use tonic_health::ServingStatus;
use tonic_health::pb::health_server::{Health, HealthServer};
use tonic_health::server::HealthReporter;

use super::{config, health};

pub fn api_listen_addr() -> Result<SocketAddr, Box<dyn Error>> {
    config::api_listen_addr()
}

pub(crate) async fn serving_health_service() -> (HealthReporter, HealthServer<impl Health>) {
    let (health_reporter, health_service) = tonic_health::server::health_reporter();
    health_reporter
        .set_service_status("", ServingStatus::NotServing)
        .await;

    (health_reporter, health_service)
}

pub async fn serve(addr: SocketAddr) -> Result<(), Box<dyn Error>> {
    let redis_client = Client::open(config::REDIS_URL)?;
    let (health_reporter, health_service) = serving_health_service().await;
    let server = Server::builder().add_service(health_service).serve(addr);

    tokio::select! {
        result = server => result.map_err(Into::into),
        () = health::monitor_redis_readiness(health_reporter, redis_client) => {
            unreachable!("Redis readiness monitor stopped unexpectedly")
        },
    }
}
