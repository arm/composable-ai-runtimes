// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::future::Future;
use std::pin::Pin;
use std::time::Duration;

use redis::AsyncCommands;
use redis::aio::MultiplexedConnection;
use redis_test::server::RedisServer;
use tokio::net::TcpListener;
use tokio::sync::mpsc;
use tokio::time::{sleep, timeout};
use tonic::transport::Server;
use tonic::transport::server::TcpIncoming;
use tonic_health::ServingStatus;

use super::service::wait_for_serving;
use super::{Notification, NotificationService, NotificationServiceError, envelope};

const REDIS_STARTUP_TIMEOUT: Duration = Duration::from_secs(5);
const OPERATION_TIMEOUT: Duration = Duration::from_secs(2);

type TestHandlerFuture = Pin<Box<dyn Future<Output = ()> + Send>>;
type TestHandler = Box<dyn Fn(Notification) -> TestHandlerFuture + Send + Sync>;

fn handler_factory() -> (TestHandler, mpsc::Receiver<Notification>) {
    let (sender, receiver) = mpsc::channel(1);
    let handler = Box::new(move |notification: Notification| {
        let sender = sender.clone();
        Box::pin(async move {
            sender
                .send(notification)
                .await
                .expect("test notification receiver should remain open");
        }) as TestHandlerFuture
    });

    (handler, receiver)
}

fn redis_endpoint(server: &RedisServer) -> String {
    let (host, port) = server
        .host_and_port()
        .expect("test Redis server did not use TCP");
    format!("redis://{host}:{port}/0")
}

async fn start_redis_server() -> RedisServer {
    let server = RedisServer::new();
    let readiness_endpoint = redis_endpoint(&server);

    timeout(REDIS_STARTUP_TIMEOUT, async move {
        loop {
            let client = redis::Client::open(readiness_endpoint.clone())
                .expect("test Redis endpoint should be valid");
            if let Ok(mut connection) = client.get_multiplexed_async_connection().await {
                let _: () = redis::cmd("QUIT")
                    .query_async(&mut connection)
                    .await
                    .expect("failed to close test Redis readiness connection");
                break;
            }
            sleep(Duration::from_millis(25)).await;
        }
    })
    .await
    .unwrap_or_else(|_| {
        panic!(
            "test Redis server did not become ready; logs: {}",
            server
                .log_file_contents()
                .unwrap_or_else(|| "<unavailable>".to_string())
        )
    });

    server
}

async fn connected_client_count(connection: &mut MultiplexedConnection) -> usize {
    let clients: String = redis::cmd("CLIENT")
        .arg("LIST")
        .query_async(connection)
        .await
        .expect("failed to inspect test Redis clients");

    clients.lines().count()
}

#[tokio::test]
async fn connect_redis_opens_a_subscriber_connection() {
    let server = start_redis_server().await;
    let endpoint = redis_endpoint(&server);
    let client =
        redis::Client::open(endpoint.clone()).expect("test Redis endpoint should be valid");
    let mut inspection_connection = client
        .get_multiplexed_async_connection()
        .await
        .expect("failed to connect to test Redis for inspection");
    let initial_connection_count = connected_client_count(&mut inspection_connection).await;
    assert_eq!(initial_connection_count, 1, "unexpected test setup clients");

    let result = NotificationService::connect_redis(&endpoint).await;

    let _service = result.expect("failed to construct notification service");
    let connection_count = connected_client_count(&mut inspection_connection).await;
    assert_eq!(
        connection_count, 2,
        "constructor should open one subscriber connection"
    );
}

#[tokio::test]
async fn new_rejects_invalid_grpc_endpoint() {
    let endpoint = "not-a-grpc-endpoint".to_string();

    let result = NotificationService::new(Some(endpoint)).await;

    let error = result
        .err()
        .expect("invalid endpoint should not create a notification service");
    assert!(matches!(error, NotificationServiceError::Connection(_)));
    assert!(
        !error.to_string().is_empty(),
        "invalid endpoint error should include a message"
    );
}

#[tokio::test]
async fn connect_redis_returns_connection_error_when_redis_is_unavailable() {
    let mut server = start_redis_server().await;
    let endpoint = redis_endpoint(&server);
    server.stop();

    let result = timeout(
        OPERATION_TIMEOUT,
        NotificationService::connect_redis(&endpoint),
    )
    .await
    .expect("timed out waiting for constructor to fail");

    let error = result
        .err()
        .expect("unavailable Redis should not create a notification service");
    assert!(matches!(error, NotificationServiceError::Connection(_)));
    assert!(
        !error.to_string().is_empty(),
        "connection error should include a message"
    );
}

#[tokio::test]
async fn subscribe_delivers_channel_and_envelope_payload() {
    let server = start_redis_server().await;
    let endpoint = redis_endpoint(&server);
    let channel_name = "rebel.alliance.broadcast";
    let payload = b"Death Star Plans";
    let client =
        redis::Client::open(endpoint.clone()).expect("test Redis endpoint should be valid");
    let mut publisher = client
        .get_multiplexed_async_connection()
        .await
        .expect("failed to connect test Redis publisher");
    let mut service = NotificationService::connect_redis(&endpoint)
        .await
        .expect("failed to connect notification service to test Redis");
    let (handler, mut handler_receiver) = handler_factory();

    service
        .subscribe(channel_name, handler)
        .await
        .expect("failed to subscribe to test Redis channel");
    let _: usize = publisher
        .publish(channel_name, envelope(payload))
        .await
        .expect("failed to publish through test Redis connection");

    let received_notification = timeout(OPERATION_TIMEOUT, handler_receiver.recv())
        .await
        .expect("timed out waiting for subscribed notification")
        .expect("notification handler channel closed unexpectedly");
    assert_eq!(received_notification.channel, channel_name);
    assert_eq!(received_notification.payload, payload.as_slice());
}

#[tokio::test]
async fn handler_panic_does_not_stop_notification_delivery() {
    let server = start_redis_server().await;
    let endpoint = redis_endpoint(&server);
    let panic_channel_name = "rebel.alliance.distress";
    let delivery_channel_name = "rebel.alliance.broadcast";
    let payload = "Death Star Plans";
    let client =
        redis::Client::open(endpoint.clone()).expect("test Redis endpoint should be valid");
    let mut publisher = client
        .get_multiplexed_async_connection()
        .await
        .expect("failed to connect test Redis publisher");
    let mut service = NotificationService::connect_redis(&endpoint)
        .await
        .expect("failed to connect notification service to test Redis");
    let (handler, mut handler_receiver) = handler_factory();
    service
        .subscribe(panic_channel_name, |_notification| async {
            panic!("test handler panic");
        })
        .await
        .expect("failed to subscribe panic handler");
    service
        .subscribe(delivery_channel_name, handler)
        .await
        .expect("failed to subscribe delivery handler");

    let _: usize = publisher
        .publish(panic_channel_name, envelope("Alderaan Coordinates"))
        .await
        .expect("failed to publish notification that panics the handler");
    let _: usize = publisher
        .publish(delivery_channel_name, envelope(payload))
        .await
        .expect("failed to publish notification after handler panic");

    let received_notification = timeout(OPERATION_TIMEOUT, handler_receiver.recv())
        .await
        .expect("timed out waiting for notification after handler panic")
        .expect("notification handler channel closed unexpectedly");
    assert_eq!(received_notification.channel, delivery_channel_name);
    assert_eq!(received_notification.payload, payload.as_bytes());
}

#[tokio::test]
async fn invalid_envelopes_do_not_stop_notification_delivery() {
    let server = start_redis_server().await;
    let endpoint = redis_endpoint(&server);
    let channel_name = "rebel.alliance.broadcast";
    let payload = "Death Star Plans";
    let client =
        redis::Client::open(endpoint.clone()).expect("test Redis endpoint should be valid");
    let mut publisher = client
        .get_multiplexed_async_connection()
        .await
        .expect("failed to connect test Redis publisher");
    let mut service = NotificationService::connect_redis(&endpoint)
        .await
        .expect("failed to connect notification service to test Redis");
    let (handler, mut handler_receiver) = handler_factory();
    service
        .subscribe(channel_name, handler)
        .await
        .expect("failed to subscribe to test Redis channel");

    let _: usize = publisher
        .publish(channel_name, vec![0xff])
        .await
        .expect("failed to publish invalid envelope");
    let _: usize = publisher
        .publish(channel_name, envelope(payload))
        .await
        .expect("failed to publish notification after invalid envelope");

    let received_notification = timeout(OPERATION_TIMEOUT, handler_receiver.recv())
        .await
        .expect("timed out waiting for notification after invalid envelope")
        .expect("notification handler channel closed unexpectedly");
    assert_eq!(received_notification.channel, channel_name);
    assert_eq!(received_notification.payload, payload.as_bytes());
}

#[tokio::test]
async fn subscribe_delivers_to_each_subscription_on_same_channel() {
    let server = start_redis_server().await;
    let endpoint = redis_endpoint(&server);
    let channel_name = "rebel.alliance.broadcast";
    let payload = "Death Star Plans";
    let client =
        redis::Client::open(endpoint.clone()).expect("test Redis endpoint should be valid");
    let mut publisher = client
        .get_multiplexed_async_connection()
        .await
        .expect("failed to connect test Redis publisher");
    let mut service = NotificationService::connect_redis(&endpoint)
        .await
        .expect("failed to connect notification service to test Redis");
    let (first_handler, mut first_handler_receiver) = handler_factory();
    let (second_handler, mut second_handler_receiver) = handler_factory();
    service
        .subscribe(channel_name, first_handler)
        .await
        .expect("failed to subscribe first handler");
    service
        .subscribe(channel_name, second_handler)
        .await
        .expect("failed to subscribe second handler");
    let _: usize = publisher
        .publish(channel_name, envelope(payload))
        .await
        .expect("failed to publish through test Redis connection");

    let first_notification = timeout(OPERATION_TIMEOUT, first_handler_receiver.recv())
        .await
        .expect("timed out waiting for first handler notification")
        .expect("first handler channel closed unexpectedly");
    assert_eq!(first_notification.channel, channel_name);
    assert_eq!(first_notification.payload, payload.as_bytes());
    let second_notification = timeout(OPERATION_TIMEOUT, second_handler_receiver.recv())
        .await
        .expect("timed out waiting for second handler notification")
        .expect("second handler channel closed unexpectedly");
    assert_eq!(second_notification.channel, channel_name);
    assert_eq!(second_notification.payload, payload.as_bytes());
    assert_eq!(
        first_notification.payload.as_ptr(),
        second_notification.payload.as_ptr(),
        "subscriptions on the same channel should share the payload allocation"
    );
}

#[tokio::test]
async fn unsubscribe_one_subscription_keeps_other_subscription_active() {
    let server = start_redis_server().await;
    let endpoint = redis_endpoint(&server);
    let channel_name = "rebel.alliance.broadcast";
    let payload = "Death Star Plans";
    let client =
        redis::Client::open(endpoint.clone()).expect("test Redis endpoint should be valid");
    let mut publisher = client
        .get_multiplexed_async_connection()
        .await
        .expect("failed to connect test Redis publisher");
    let mut service = NotificationService::connect_redis(&endpoint)
        .await
        .expect("failed to connect notification service to test Redis");
    let (first_handler, _first_handler_receiver) = handler_factory();
    let (second_handler, mut second_handler_receiver) = handler_factory();
    let first_subscription_id = service
        .subscribe(channel_name, first_handler)
        .await
        .expect("failed to subscribe first handler");
    service
        .subscribe(channel_name, second_handler)
        .await
        .expect("failed to subscribe second handler");

    service
        .unsubscribe(first_subscription_id)
        .await
        .expect("failed to unsubscribe first subscription");
    let _: usize = publisher
        .publish(channel_name, envelope(payload))
        .await
        .expect("failed to publish with second handler remaining");

    let second_notification = timeout(OPERATION_TIMEOUT, second_handler_receiver.recv())
        .await
        .expect("timed out waiting for second handler notification")
        .expect("second handler channel closed unexpectedly");
    assert_eq!(second_notification.channel, channel_name);
    assert_eq!(second_notification.payload, payload.as_bytes());
}

#[tokio::test]
async fn subscribe_returns_closed_after_close() {
    let server = start_redis_server().await;
    let mut service = NotificationService::connect_redis(&redis_endpoint(&server))
        .await
        .expect("failed to connect notification service to test Redis");
    service.close().await.expect("failed to close service");
    let (handler, _handler_receiver) = handler_factory();

    let result = service.subscribe("rebel.alliance.broadcast", handler).await;

    assert_eq!(result, Err(NotificationServiceError::Closed));
}

#[tokio::test]
async fn subscribe_maps_redis_disconnect_to_connection_error() {
    let mut server = start_redis_server().await;
    let mut service = NotificationService::connect_redis(&redis_endpoint(&server))
        .await
        .expect("failed to connect notification service to test Redis");
    server.stop();
    let (handler, _handler_receiver) = handler_factory();

    let error = timeout(
        OPERATION_TIMEOUT,
        service.subscribe("rebel.alliance.broadcast", handler),
    )
    .await
    .expect("timed out waiting for subscribe to fail")
    .expect_err("subscribe should fail after Redis disconnects");

    assert!(matches!(error, NotificationServiceError::Connection(_)));
    assert!(
        !error.to_string().is_empty(),
        "connection error should include a message"
    );
}

#[tokio::test]
async fn unsubscribe_removes_redis_subscription() {
    let server = start_redis_server().await;
    let endpoint = redis_endpoint(&server);
    let channel_name = "rebel.alliance.broadcast";
    let payload = "Death Star Plans";
    let client =
        redis::Client::open(endpoint.clone()).expect("test Redis endpoint should be valid");
    let mut publisher = client
        .get_multiplexed_async_connection()
        .await
        .expect("failed to connect test Redis publisher");
    let mut service = NotificationService::connect_redis(&endpoint)
        .await
        .expect("failed to connect notification service to test Redis");
    let (handler, _handler_receiver) = handler_factory();
    let subscription_id = service
        .subscribe(channel_name, handler)
        .await
        .expect("failed to subscribe to test Redis channel");
    let recipient_count_before: usize = publisher
        .publish(channel_name, envelope(payload))
        .await
        .expect("failed to publish through test Redis connection");

    service
        .unsubscribe(subscription_id)
        .await
        .expect("failed to unsubscribe from test Redis channel");

    let recipient_count_after: usize = publisher
        .publish(channel_name, envelope(payload))
        .await
        .expect("failed to publish through test Redis connection");
    assert_eq!(recipient_count_before, 1);
    assert_eq!(recipient_count_after, 0);
}

#[tokio::test]
async fn unsubscribe_stops_handler_delivery() {
    let server = start_redis_server().await;
    let endpoint = redis_endpoint(&server);
    let channel_name = "rebel.alliance.broadcast";
    let payload = "Death Star Plans";
    let client =
        redis::Client::open(endpoint.clone()).expect("test Redis endpoint should be valid");
    let mut publisher = client
        .get_multiplexed_async_connection()
        .await
        .expect("failed to connect test Redis publisher");
    let mut service = NotificationService::connect_redis(&endpoint)
        .await
        .expect("failed to connect notification service to test Redis");
    let (handler, mut handler_receiver) = handler_factory();
    let subscription_id = service
        .subscribe(channel_name, handler)
        .await
        .expect("failed to subscribe to test Redis channel");

    service
        .unsubscribe(subscription_id)
        .await
        .expect("failed to unsubscribe from test Redis channel");
    let _: usize = publisher
        .publish(channel_name, envelope(payload))
        .await
        .expect("failed to publish through test Redis connection");

    let received_notification = timeout(OPERATION_TIMEOUT, handler_receiver.recv())
        .await
        .expect("timed out waiting for notification handler to close");
    assert_eq!(received_notification, None);
}

#[tokio::test]
async fn unsubscribe_returns_error_for_unknown_subscription() {
    let server = start_redis_server().await;
    let endpoint = redis_endpoint(&server);
    let channel_name = "rebel.alliance.broadcast";
    let mut service = NotificationService::connect_redis(&endpoint)
        .await
        .expect("failed to connect notification service to test Redis");
    let (handler, _handler_receiver) = handler_factory();
    let subscription_id = service
        .subscribe(channel_name, handler)
        .await
        .expect("failed to subscribe to test Redis channel");

    let first_result = service.unsubscribe(subscription_id).await;
    let second_result = service.unsubscribe(subscription_id).await;

    assert_eq!(first_result, Ok(()));
    assert_eq!(
        second_result,
        Err(NotificationServiceError::SubscriptionNotFound(
            subscription_id
        ))
    );
}

#[tokio::test]
async fn unsubscribe_returns_closed_after_close() {
    let server = start_redis_server().await;
    let mut service = NotificationService::connect_redis(&redis_endpoint(&server))
        .await
        .expect("failed to connect notification service to test Redis");
    let (handler, _handler_receiver) = handler_factory();
    let subscription_id = service
        .subscribe("rebel.alliance.broadcast", handler)
        .await
        .expect("failed to subscribe to test Redis channel");
    service.close().await.expect("failed to close service");

    let result = service.unsubscribe(subscription_id).await;

    assert_eq!(result, Err(NotificationServiceError::Closed));
}

#[tokio::test]
async fn unsubscribe_maps_redis_disconnect_to_connection_error() {
    let mut server = start_redis_server().await;
    let mut service = NotificationService::connect_redis(&redis_endpoint(&server))
        .await
        .expect("failed to connect notification service to test Redis");
    let (handler, _handler_receiver) = handler_factory();
    let subscription_id = service
        .subscribe("rebel.alliance.broadcast", handler)
        .await
        .expect("failed to subscribe to test Redis channel");
    server.stop();

    let error = timeout(OPERATION_TIMEOUT, service.unsubscribe(subscription_id))
        .await
        .expect("timed out waiting for unsubscribe to fail")
        .expect_err("unsubscribe should fail after Redis disconnects");

    assert!(matches!(error, NotificationServiceError::Connection(_)));
    assert!(
        !error.to_string().is_empty(),
        "connection error should include a message"
    );
}

#[tokio::test]
async fn unsubscribe_retains_subscription_when_redis_unsubscribe_fails() {
    let mut server = start_redis_server().await;
    let mut service = NotificationService::connect_redis(&redis_endpoint(&server))
        .await
        .expect("failed to connect notification service to test Redis");
    let (handler, _handler_receiver) = handler_factory();
    let subscription_id = service
        .subscribe("rebel.alliance.broadcast", handler)
        .await
        .expect("failed to subscribe to test Redis channel");
    server.stop();

    let unsubscribe_error = timeout(OPERATION_TIMEOUT, service.unsubscribe(subscription_id))
        .await
        .expect("timed out waiting for unsubscribe to fail")
        .expect_err("unsubscribe should fail after Redis disconnects");

    assert!(matches!(
        unsubscribe_error,
        NotificationServiceError::Connection(_)
    ));
    assert!(
        service.has_subscription(subscription_id).await,
        "failed unsubscribe should retain its subscription"
    );

    let retry_error = service
        .unsubscribe(subscription_id)
        .await
        .expect_err("retrying unsubscribe should not lose the subscription ID");

    assert!(matches!(
        retry_error,
        NotificationServiceError::Connection(_)
    ));
}

#[tokio::test]
async fn close_is_idempotent() {
    let server = start_redis_server().await;
    let endpoint = redis_endpoint(&server);
    let mut service = NotificationService::connect_redis(&endpoint)
        .await
        .expect("failed to connect notification service to test Redis");

    let first_result = service.close().await;
    let second_result = service.close().await;

    assert_eq!(first_result, Ok(()));
    assert_eq!(second_result, Ok(()));
}

#[tokio::test]
async fn close_succeeds_after_listener_terminates() {
    let mut server = start_redis_server().await;
    let mut service = NotificationService::connect_redis(&redis_endpoint(&server))
        .await
        .expect("failed to connect notification service to test Redis");
    server.stop();

    timeout(OPERATION_TIMEOUT, async {
        loop {
            match service
                .subscribe("rebel.alliance.broadcast", |_| async {})
                .await
            {
                Err(NotificationServiceError::Connection(message))
                    if message == "notification listener terminated" =>
                {
                    break;
                }
                _ => sleep(Duration::from_millis(25)).await,
            }
        }
    })
    .await
    .expect("timed out waiting for notification listener to terminate");

    let result = service.close().await;

    assert_eq!(result, Ok(()));
}

async fn start_health_server(
    address: &str,
    status: ServingStatus,
) -> (
    String,
    tonic_health::server::HealthReporter,
    tokio::task::JoinHandle<()>,
) {
    let incoming = TcpIncoming::from(TcpListener::bind(address).await.unwrap());
    let endpoint = format!("http://{}", incoming.local_addr().unwrap());
    let (reporter, health_service) = tonic_health::server::health_reporter();
    reporter.set_service_status("", status).await;
    let server = tokio::spawn(async move {
        Server::builder()
            .add_service(health_service)
            .serve_with_incoming(incoming)
            .await
            .expect("test health server failed");
    });

    (endpoint, reporter, server)
}

#[tokio::test]
async fn waits_for_serving() {
    let (health_endpoint, reporter, server) =
        start_health_server("127.0.0.1:0", ServingStatus::NotServing).await;
    let readiness = wait_for_serving(&health_endpoint);
    tokio::pin!(readiness);
    assert!(
        timeout(Duration::from_millis(100), &mut readiness)
            .await
            .is_err(),
        "readiness must stay pending while health is NOT_SERVING"
    );

    reporter
        .set_service_status("", ServingStatus::Serving)
        .await;
    timeout(Duration::from_secs(2), readiness)
        .await
        .expect("readiness did not complete after SERVING")
        .expect("readiness failed after SERVING");

    server.abort();
    let _ = server.await;
}

#[tokio::test]
async fn accepts_already_serving() {
    let (health_endpoint, _reporter, server) =
        start_health_server("127.0.0.1:0", ServingStatus::Serving).await;
    timeout(Duration::from_secs(2), wait_for_serving(&health_endpoint))
        .await
        .expect("already-serving health did not complete readiness")
        .expect("readiness failed for an already-serving service");

    server.abort();
    let _ = server.await;
}
