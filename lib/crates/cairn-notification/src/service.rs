// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::future::Future;
use std::panic::AssertUnwindSafe;
use std::pin::Pin;
use std::sync::Arc;

use bytes::Bytes;
use futures_util::{FutureExt, StreamExt};
use prost::Message;
use redis::aio::{PubSubSink, PubSubStream};
use tokio::sync::Mutex;
use tokio::task::JoinHandle;
use tonic::transport::{Channel, Endpoint};
use tonic_health::pb::{
    HealthCheckRequest, health_check_response::ServingStatus, health_client::HealthClient,
};

use crate::messaging::CairnEvent;

const DEFAULT_REDIS_ENDPOINT: &str = "redis://127.0.0.1:6379/0";
const DEFAULT_ENDPOINT: &str = "http://127.0.0.1:50054";

pub(super) async fn wait_for_serving(endpoint: &str) -> Result<Channel, String> {
    let ready_channel = async {
        let channel = Endpoint::from_shared(endpoint.to_owned())
            .map_err(|error| error.to_string())?
            .connect()
            .await
            .map_err(|error| error.to_string())?;
        let mut updates = HealthClient::new(channel.clone())
            .watch(HealthCheckRequest::default())
            .await
            .map_err(|error| error.to_string())?
            .into_inner();
        while let Some(response) = updates.message().await.map_err(|error| error.to_string())? {
            if response.status() == ServingStatus::Serving {
                return Ok(channel);
            }
        }
        Err("health watch ended before SERVING".to_string())
    };
    tokio::time::timeout(std::time::Duration::from_secs(30), ready_channel)
        .await
        .map_err(|_| format!("service at {endpoint} did not report SERVING within 30s"))?
        .map_err(|error| format!("health watch at {endpoint} failed: {error}"))
}

/// A message delivered through a notification subscription.
#[derive(Debug, PartialEq, Eq)]
pub struct Notification {
    /// The Redis channel on which the message was received.
    pub channel: String,
    /// The unmodified message payload.
    pub payload: Bytes,
}
type HandlerFuture = Pin<Box<dyn Future<Output = ()> + Send + 'static>>;
type NotificationHandler = Arc<dyn Fn(Notification) -> HandlerFuture + Send + Sync + 'static>;

/// Identifies a subscription within a notification service.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct NotificationSubscription(u64);

#[derive(Default)]
struct SubscriptionRegistry {
    channels: HashMap<String, HashMap<NotificationSubscription, NotificationHandler>>,
    subscription_channels: HashMap<NotificationSubscription, String>,
}

impl SubscriptionRegistry {
    fn add_subscription(
        &mut self,
        channel: &str,
        subscription_id: NotificationSubscription,
        handler: NotificationHandler,
    ) {
        if let Some(channel_subscriptions) = self.channels.get_mut(channel) {
            channel_subscriptions.insert(subscription_id, handler);
        } else {
            let mut channel_subscriptions = HashMap::new();
            channel_subscriptions.insert(subscription_id, handler);
            self.channels
                .insert(channel.to_owned(), channel_subscriptions);
        }
        self.subscription_channels
            .insert(subscription_id, channel.to_owned());
    }

    fn remove_subscription(&mut self, subscription_id: NotificationSubscription) {
        let channel = self
            .subscription_channels
            .remove(&subscription_id)
            .expect("subscription channel map should contain every registration");
        let channel_subscriptions = self
            .channels
            .get_mut(&channel)
            .expect("subscription channel map should contain every registration");
        channel_subscriptions.remove(&subscription_id);
        if channel_subscriptions.is_empty() {
            self.channels.remove(&channel);
        }
    }
}

/// An error returned by the notification service.
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub enum NotificationServiceError {
    /// The service has already been closed.
    Closed,
    /// The requested subscription ID is not registered.
    SubscriptionNotFound(NotificationSubscription),
    /// The service could not be reached or an active connection failed.
    Connection(String),
}

impl std::fmt::Display for NotificationServiceError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Closed => f.write_str("notification service client is closed"),
            Self::SubscriptionNotFound(subscription_id) => {
                write!(
                    f,
                    "notification subscription not found: {subscription_id:?}"
                )
            }
            Self::Connection(message) => f.write_str(message),
        }
    }
}

impl std::error::Error for NotificationServiceError {}

/// An asynchronous notification service for managing channel subscriptions.
pub struct NotificationService {
    pubsub_sink: Option<PubSubSink>,
    subscriptions: Arc<Mutex<SubscriptionRegistry>>,
    next_subscription_id: u64,
    listener_task: Option<JoinHandle<()>>,
}

impl NotificationService {
    /// Waits for the gRPC endpoint to report readiness, then connects to local Redis.
    /// Uses the default gRPC endpoint when omitted.
    pub async fn new(endpoint: Option<String>) -> Result<Self, NotificationServiceError> {
        let endpoint = endpoint.unwrap_or_else(|| DEFAULT_ENDPOINT.to_string());
        wait_for_serving(&endpoint)
            .await
            .map_err(NotificationServiceError::Connection)?;
        Self::connect_redis(DEFAULT_REDIS_ENDPOINT).await
    }

    pub(super) async fn connect_redis(endpoint: &str) -> Result<Self, NotificationServiceError> {
        let client = redis::Client::open(endpoint)
            .map_err(|err| NotificationServiceError::Connection(err.to_string()))?;
        let (pubsub_sink, pubsub_stream) = client
            .get_async_pubsub()
            .await
            .map_err(|err| NotificationServiceError::Connection(err.to_string()))?
            .split();
        let subscriptions = Arc::new(Mutex::new(SubscriptionRegistry::default()));
        let listener_task = tokio::spawn(listen(pubsub_stream, Arc::clone(&subscriptions)));

        Ok(Self {
            pubsub_sink: Some(pubsub_sink),
            subscriptions,
            next_subscription_id: 0,
            listener_task: Some(listener_task),
        })
    }

    /// Subscribes to a channel and passes its name and payload to the async handler.
    /// The handler must be `Send + Sync + 'static` and return a `Send + 'static` future.
    /// Handlers run serially, so long-running work delays later notifications.
    /// Returns an ID that can be used to remove this subscription.
    ///
    /// This future is not cancellation-safe.
    pub async fn subscribe<H, Fut>(
        &mut self,
        channel: &str,
        handler: H,
    ) -> Result<NotificationSubscription, NotificationServiceError>
    where
        H: Fn(Notification) -> Fut + Send + Sync + 'static,
        Fut: Future<Output = ()> + Send + 'static,
    {
        self.ensure_listener_running()?;
        if self.pubsub_sink.is_none() {
            return Err(NotificationServiceError::Closed);
        }

        let channel = channel.to_string();
        let handler: NotificationHandler =
            Arc::new(move |notification| Box::pin(handler(notification)));
        let subscription_id = NotificationSubscription(self.next_subscription_id);
        self.next_subscription_id = self.next_subscription_id.checked_add(1).ok_or_else(|| {
            NotificationServiceError::Connection(
                "notification subscription ID space exhausted".into(),
            )
        })?;

        let was_empty = {
            let mut subscriptions = self.subscriptions.lock().await;
            let was_empty = subscriptions
                .channels
                .get(&channel)
                .is_none_or(|channel_subscriptions| channel_subscriptions.is_empty());
            subscriptions.add_subscription(&channel, subscription_id, handler);
            was_empty
        };

        if was_empty {
            let subscribe_result = match self.pubsub_sink.as_mut() {
                Some(pubsub_sink) => pubsub_sink
                    .subscribe(channel.as_str())
                    .await
                    .map_err(|err| NotificationServiceError::Connection(err.to_string())),
                None => Err(NotificationServiceError::Closed),
            };

            if let Err(error) = subscribe_result {
                let mut subscriptions = self.subscriptions.lock().await;
                subscriptions.subscription_channels.remove(&subscription_id);
                if let Some(channel_subscriptions) = subscriptions.channels.get_mut(&channel) {
                    channel_subscriptions.remove(&subscription_id);
                    if channel_subscriptions.is_empty() {
                        subscriptions.channels.remove(&channel);
                    }
                }
                return Err(error);
            }
        }

        Ok(subscription_id)
    }

    /// Removes one subscription.
    ///
    /// The subscription is removed only when this was the last
    /// subscription registered for the channel.
    ///
    /// This future is not cancellation-safe.
    pub async fn unsubscribe(
        &mut self,
        subscription_id: NotificationSubscription,
    ) -> Result<(), NotificationServiceError> {
        self.ensure_listener_running()?;
        let (channel, should_unsubscribe) = {
            let subscriptions = self.subscriptions.lock().await;
            let Some(channel) = subscriptions
                .subscription_channels
                .get(&subscription_id)
                .cloned()
            else {
                return Err(NotificationServiceError::SubscriptionNotFound(
                    subscription_id,
                ));
            };
            let channel_subscriptions = subscriptions
                .channels
                .get(&channel)
                .expect("subscription channel map should contain every registration");
            let should_unsubscribe = channel_subscriptions.len() == 1;
            (channel, should_unsubscribe)
        };

        if should_unsubscribe {
            self.pubsub_sink
                .as_mut()
                .ok_or(NotificationServiceError::Closed)?
                .unsubscribe(channel)
                .await
                .map_err(|err| NotificationServiceError::Connection(err.to_string()))?;
        }

        self.subscriptions
            .lock()
            .await
            .remove_subscription(subscription_id);

        Ok(())
    }

    /// Closes active connections and stops notification delivery.
    /// Calling this method more than once is safe.
    pub async fn close(&mut self) -> Result<(), NotificationServiceError> {
        self.pubsub_sink.take();
        let mut subscriptions = self.subscriptions.lock().await;
        subscriptions.channels.clear();
        subscriptions.subscription_channels.clear();
        drop(subscriptions);
        match self.listener_task.take() {
            Some(listener_task) => {
                listener_task.abort();
                match listener_task.await {
                    Ok(()) => Ok(()),
                    Err(error) if error.is_cancelled() => Ok(()),
                    Err(error) => Err(NotificationServiceError::Connection(format!(
                        "notification listener task failed: {error}"
                    ))),
                }
            }
            None => Ok(()),
        }
    }

    fn ensure_listener_running(&self) -> Result<(), NotificationServiceError> {
        match &self.listener_task {
            Some(listener_task) if listener_task.is_finished() => {
                Err(NotificationServiceError::Connection(
                    "notification listener terminated".to_string(),
                ))
            }
            Some(_) => Ok(()),
            None => Err(NotificationServiceError::Closed),
        }
    }

    #[cfg(test)]
    pub(super) async fn has_subscription(&self, subscription_id: NotificationSubscription) -> bool {
        self.subscriptions
            .lock()
            .await
            .subscription_channels
            .contains_key(&subscription_id)
    }
}

impl Drop for NotificationService {
    fn drop(&mut self) {
        if let Some(listener_task) = self.listener_task.take() {
            listener_task.abort();
        }
    }
}

async fn listen(mut pubsub_stream: PubSubStream, subscriptions: Arc<Mutex<SubscriptionRegistry>>) {
    while let Some(message) = pubsub_stream.next().await {
        let channel = message.get_channel_name().to_string();
        let encoded_envelope = match message.get_payload::<Bytes>() {
            Ok(payload) => payload,
            Err(error) => {
                tracing::warn!(%error, channel = %channel, "failed to read notification envelope");
                continue;
            }
        };
        let envelope = match CairnEvent::decode(encoded_envelope) {
            Ok(envelope) => envelope,
            Err(error) => {
                tracing::warn!(%error, channel = %channel, "failed to decode notification envelope");
                continue;
            }
        };
        let payload = envelope.payload;

        let channel_subscriptions = {
            let subscriptions = subscriptions.lock().await;
            subscriptions
                .channels
                .get(&channel)
                .map(|channel_subscriptions| {
                    channel_subscriptions.values().cloned().collect::<Vec<_>>()
                })
                .unwrap_or_default()
        };

        for handler in channel_subscriptions {
            let result = AssertUnwindSafe(async {
                handler(Notification {
                    channel: channel.clone(),
                    payload: payload.clone(),
                })
                .await;
            })
            .catch_unwind()
            .await;
            if result.is_err() {
                tracing::error!(channel = %channel, "notification handler failed");
            }
        }
    }

    tracing::error!("notification listener stopped because Redis Pub/Sub stream ended");
}
