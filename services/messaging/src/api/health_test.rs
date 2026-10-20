// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::time::Duration;

use redis::ConnectionAddr;
use redis_test::server::RedisServer;
use tokio::net::TcpListener;
use tokio::sync::oneshot;
use tokio::task::JoinHandle;
use tokio::time::{sleep, timeout};
use tokio_stream::wrappers::TcpListenerStream;
use tonic::transport::{Channel, Server};
use tonic_health::pb::HealthCheckRequest;
use tonic_health::pb::health_check_response::ServingStatus;
use tonic_health::pb::health_client::HealthClient;

use super::{health, server::serving_health_service};

const STATUS_TIMEOUT: Duration = Duration::from_secs(10);

struct RunningServer {
    health_client: HealthClient<Channel>,
    redis_address: ConnectionAddr,
    redis_server: RedisServer,
    shutdown: oneshot::Sender<()>,
    task: JoinHandle<Result<(), tonic::transport::Error>>,
}

impl RunningServer {
    async fn wait_for_status(&mut self, expected: ServingStatus) {
        timeout(STATUS_TIMEOUT, async {
            loop {
                let response = self
                    .health_client
                    .check(HealthCheckRequest::default())
                    .await;
                if response
                    .map(|response| response.into_inner().status)
                    .is_ok_and(|status| status == expected as i32)
                {
                    return;
                }
                sleep(Duration::from_millis(25)).await;
            }
        })
        .await
        .unwrap_or_else(|_| panic!("health status should reach {expected:?}"));
    }

    fn stop_redis(&mut self) {
        self.redis_server.stop();
    }

    fn restart_redis(&mut self) {
        self.redis_server =
            RedisServer::new_with_addr_and_modules(self.redis_address.clone(), &[], false);
    }

    async fn shutdown(self) {
        self.shutdown
            .send(())
            .expect("health server should still be running");
        self.task
            .await
            .expect("health server task should not panic")
            .expect("health server should shut down cleanly");
    }
}

async fn start_server() -> RunningServer {
    let redis_server = RedisServer::new();
    let redis_address = redis_server.client_addr().clone();
    let redis_client = redis::Client::open(redis_server.connection_info())
        .expect("test Redis endpoint should be valid");
    let listener = TcpListener::bind("127.0.0.1:0")
        .await
        .expect("health server should bind");
    let address = listener
        .local_addr()
        .expect("health server should have an address");
    let (shutdown, shutdown_rx) = oneshot::channel();
    let (health_reporter, health_service) = serving_health_service().await;
    let task = tokio::spawn(async move {
        let server = Server::builder()
            .add_service(health_service)
            .serve_with_incoming_shutdown(TcpListenerStream::new(listener), async {
                let _ = shutdown_rx.await;
            });

        tokio::select! {
            result = server => result,
            () = health::monitor_redis_readiness(health_reporter, redis_client) => unreachable!(),
        }
    });
    let channel = Channel::from_shared(format!("http://{address}"))
        .expect("health endpoint should be valid")
        .connect()
        .await
        .expect("health client should connect");

    RunningServer {
        health_client: HealthClient::new(channel),
        redis_address,
        redis_server,
        shutdown,
        task,
    }
}

#[tokio::test]
async fn health_check_tracks_redis_readiness() {
    let mut server = start_server().await;

    server.wait_for_status(ServingStatus::Serving).await;

    server.stop_redis();
    server.wait_for_status(ServingStatus::NotServing).await;

    server.restart_redis();
    server.wait_for_status(ServingStatus::Serving).await;

    server.shutdown().await;
}
