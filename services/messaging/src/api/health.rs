// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use redis::Client;
use tonic_health::ServingStatus;
use tonic_health::server::HealthReporter;
use tracing::{info, warn};

use super::config;

async fn ping_redis(client: &Client) -> redis::RedisResult<bool> {
    let mut connection = client.get_multiplexed_async_connection().await?;
    let response: String = redis::cmd("PING").query_async(&mut connection).await?;

    Ok(response == "PONG")
}

pub(super) async fn monitor_redis_readiness(health_reporter: HealthReporter, redis_client: Client) {
    let mut interval = tokio::time::interval(config::READINESS_CHECK_INTERVAL);
    interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
    let mut previous_status = None;

    loop {
        interval.tick().await;

        let status = match tokio::time::timeout(
            config::READINESS_TIMEOUT,
            ping_redis(&redis_client),
        )
        .await
        {
            Ok(Ok(true)) => ServingStatus::Serving,
            _ => ServingStatus::NotServing,
        };

        if previous_status != Some(status) {
            match status {
                ServingStatus::Serving => info!("Redis is up."),
                ServingStatus::NotServing => warn!("Redis is down."),
                _ => unreachable!("Redis check returned an unexpected status: {:?}", status),
            }

            health_reporter.set_service_status("", status).await;
            previous_status = Some(status);
        }
    }
}
