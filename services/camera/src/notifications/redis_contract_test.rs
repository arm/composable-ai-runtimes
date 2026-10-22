// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::{cell::RefCell, env, error::Error, ffi::OsString, io, rc::Rc, time::Duration};

use super::{
    messaging::CairnEvent,
    publish_camera_event,
    redis::{
        CameraEvent, CameraEventType, EventCamera, RedisConfig, configure_redis_conn_with_retry,
    },
};
use camera::camera::Camera;
use prost::Message;
use redis::{Client, Msg};
use testcontainers::{
    ContainerAsync, GenericImage,
    core::{IntoContainerPort, WaitFor},
    runners::AsyncRunner,
};
use tokio::sync::Mutex;

const REDIS_PORT: u16 = 6379;
const REDIS_VERSION: &str = "8.4.7";
const CAMERA_EVENTS_CHANNEL: &str = "camera.events";
const CUSTOM_CAMERA_EVENTS_CHANNEL: &str = "custom.camera.events";
const REDIS_HOST_ENV: &str = "PWC_REDIS_HOST";
const REDIS_PORT_ENV: &str = "PWC_REDIS_PORT";
const REDIS_PASSWORD_ENV: &str = "PWC_REDIS_PASSWORD";
const REDIS_CHANNEL_EVENTS_ENV: &str = "PWC_REDIS_CHANNEL_EVENTS";

static REDIS_CONTRACT_TEST_ENV_LOCK: Mutex<()> = Mutex::const_new(());

struct StartedRedisContainer {
    _container: ContainerAsync<GenericImage>,
    host: String,
    port: u16,
}

async fn start_redis_contract_test_container() -> Result<StartedRedisContainer, Box<dyn Error>> {
    let container = GenericImage::new("redis", REDIS_VERSION)
        .with_exposed_port(REDIS_PORT.tcp())
        .with_wait_for(WaitFor::message_on_stdout("Ready to accept connections"))
        .start()
        .await?;
    let host = container.get_host().await?.to_string();
    let port = container.get_host_port_ipv4(REDIS_PORT.tcp()).await?;

    Ok(StartedRedisContainer {
        _container: container,
        host,
        port,
    })
}

struct EnvVarGuard {
    name: &'static str,
    previous_value: Option<OsString>,
}

impl Drop for EnvVarGuard {
    fn drop(&mut self) {
        unsafe {
            match &self.previous_value {
                Some(value) => env::set_var(self.name, value),
                None => env::remove_var(self.name),
            }
        }
    }
}

fn preserve_env_var(name: &'static str) -> EnvVarGuard {
    EnvVarGuard {
        name,
        previous_value: env::var_os(name),
    }
}

fn set_env_var(name: &'static str, value: &str) -> EnvVarGuard {
    let guard = preserve_env_var(name);

    unsafe {
        env::set_var(name, value);
    }

    guard
}

fn remove_env_var(name: &'static str) -> EnvVarGuard {
    let guard = preserve_env_var(name);

    unsafe {
        env::remove_var(name);
    }

    guard
}

fn subscribe_to_channel(
    redis_config: &RedisConfig,
    channel: &str,
) -> Result<redis::Connection, Box<dyn Error>> {
    let mut connection = Client::open(redis_config)?.get_connection()?;

    redis::cmd("SUBSCRIBE")
        .arg(channel)
        .query::<redis::Value>(&mut connection)?;
    connection.set_read_timeout(Some(Duration::from_secs(2)))?;

    Ok(connection)
}

fn receive_message(
    subscriber: &mut redis::Connection,
    subscription_channel: &str,
) -> Result<Vec<u8>, Box<dyn Error>> {
    let mut pubsub = subscriber.as_pubsub();
    let message: Msg = pubsub.get_message().map_err(|err| {
        io::Error::new(
            io::ErrorKind::TimedOut,
            format!(
                "did not receive Redis message on channel '{subscription_channel}' before timeout: {err}"
            ),
        )
    })?;

    Ok(message.get_payload()?)
}

fn assert_camera_event_envelope(
    payload: &[u8],
    event_type: CameraEventType,
    cam_id: u64,
    name: &str,
    topic: &str,
) -> Result<(), Box<dyn Error>> {
    let envelope = CairnEvent::decode(payload)?;
    let timestamp = envelope
        .timestamp
        .ok_or("event envelope has no timestamp")?;

    assert!(timestamp.seconds > 0, "event envelope timestamp is invalid");
    assert_eq!(envelope.origin, "cairn.camera-service");
    assert_eq!(envelope.event_type, event_type.to_string());
    assert_eq!(envelope.topic, topic);

    let payload: CameraEvent = serde_json::from_slice(&envelope.payload)?;

    assert_eq!(
        payload,
        CameraEvent {
            event_type,
            camera: EventCamera {
                id: cam_id,
                name: name.to_owned(),
            },
        }
    );

    Ok(())
}

fn get_redis_client_id(connection: &mut redis::Connection) -> Result<u64, Box<dyn Error>> {
    Ok(redis::cmd("CLIENT").arg("ID").query(connection)?)
}

fn kill_redis_client(redis_config: &RedisConfig, client_id: u64) -> Result<(), Box<dyn Error>> {
    let mut connection = Client::open(redis_config)?.get_connection()?;
    let killed_clients: usize = redis::cmd("CLIENT")
        .arg("KILL")
        .arg("ID")
        .arg(client_id)
        .query(&mut connection)?;

    assert_eq!(
        killed_clients, 1,
        "exactly one Redis client should have been killed"
    );

    Ok(())
}

#[tokio::test]
async fn test_default_channel_from_env_publishes_to_camera_events() -> Result<(), Box<dyn Error>> {
    let redis_container = start_redis_contract_test_container().await?;
    let port = redis_container.port.to_string();

    let redis_config = {
        let _env_lock = REDIS_CONTRACT_TEST_ENV_LOCK.lock().await;
        let _host_env = set_env_var(REDIS_HOST_ENV, redis_container.host.as_str());
        let _port_env = set_env_var(REDIS_PORT_ENV, port.as_str());
        let _password_env = remove_env_var(REDIS_PASSWORD_ENV);
        let _events_channel_env = remove_env_var(REDIS_CHANNEL_EVENTS_ENV);

        RedisConfig::from_env()
    };

    let mut subscriber = subscribe_to_channel(&redis_config, CAMERA_EVENTS_CHANNEL)?;
    let cam_id = 42;
    let camera = Camera {
        node_id: cam_id as u32,
        object_serial: cam_id,
        name: "default-channel-camera".to_owned(),
    };
    let publisher = Rc::new(RefCell::new(configure_redis_conn_with_retry(
        &redis_config,
    )?));

    publish_camera_event(
        &publisher,
        &redis_config,
        CameraEventType::Connected,
        &camera,
        redis_config.events_channel.as_str(),
    );

    receive_message(&mut subscriber, CAMERA_EVENTS_CHANNEL)?;

    Ok(())
}

#[tokio::test]
async fn test_configured_channel_override_publishes_to_configured_channel()
-> Result<(), Box<dyn Error>> {
    let redis_container = start_redis_contract_test_container().await?;
    let port = redis_container.port.to_string();

    let redis_config = {
        let _env_lock = REDIS_CONTRACT_TEST_ENV_LOCK.lock().await;
        let _host_env = set_env_var(REDIS_HOST_ENV, redis_container.host.as_str());
        let _port_env = set_env_var(REDIS_PORT_ENV, port.as_str());
        let _password_env = remove_env_var(REDIS_PASSWORD_ENV);
        let _events_channel_env =
            set_env_var(REDIS_CHANNEL_EVENTS_ENV, CUSTOM_CAMERA_EVENTS_CHANNEL);

        RedisConfig::from_env()
    };

    let mut subscriber = subscribe_to_channel(&redis_config, CUSTOM_CAMERA_EVENTS_CHANNEL)?;
    let cam_id = 84;
    let camera = Camera {
        node_id: cam_id as u32,
        object_serial: cam_id,
        name: "custom-channel-camera".to_owned(),
    };
    let publisher = Rc::new(RefCell::new(configure_redis_conn_with_retry(
        &redis_config,
    )?));

    publish_camera_event(
        &publisher,
        &redis_config,
        CameraEventType::Connected,
        &camera,
        redis_config.events_channel.as_str(),
    );

    receive_message(&mut subscriber, CUSTOM_CAMERA_EVENTS_CHANNEL)?;

    Ok(())
}

#[tokio::test]
async fn test_connected_payload_contains_expected_fields() -> Result<(), Box<dyn Error>> {
    let redis_container = start_redis_contract_test_container().await?;
    let port = redis_container.port.to_string();

    let redis_config = {
        let _env_lock = REDIS_CONTRACT_TEST_ENV_LOCK.lock().await;
        let _host_env = set_env_var(REDIS_HOST_ENV, redis_container.host.as_str());
        let _port_env = set_env_var(REDIS_PORT_ENV, port.as_str());
        let _password_env = remove_env_var(REDIS_PASSWORD_ENV);
        let _events_channel_env = remove_env_var(REDIS_CHANNEL_EVENTS_ENV);

        RedisConfig::from_env()
    };

    let mut subscriber = subscribe_to_channel(&redis_config, CUSTOM_CAMERA_EVENTS_CHANNEL)?;
    let cam_id = 126;
    let camera = Camera {
        node_id: cam_id as u32,
        object_serial: cam_id,
        name: "configured-channel-camera".to_owned(),
    };
    let publisher = Rc::new(RefCell::new(configure_redis_conn_with_retry(
        &redis_config,
    )?));

    publish_camera_event(
        &publisher,
        &redis_config,
        CameraEventType::Connected,
        &camera,
        CUSTOM_CAMERA_EVENTS_CHANNEL,
    );

    let payload = receive_message(&mut subscriber, CUSTOM_CAMERA_EVENTS_CHANNEL)?;
    assert_camera_event_envelope(
        &payload,
        CameraEventType::Connected,
        cam_id,
        "configured-channel-camera",
        CUSTOM_CAMERA_EVENTS_CHANNEL,
    )?;

    Ok(())
}

#[tokio::test]
async fn test_disconnected_payload_contains_expected_fields() -> Result<(), Box<dyn Error>> {
    let redis_container = start_redis_contract_test_container().await?;
    let port = redis_container.port.to_string();

    let redis_config = {
        let _env_lock = REDIS_CONTRACT_TEST_ENV_LOCK.lock().await;
        let _host_env = set_env_var(REDIS_HOST_ENV, redis_container.host.as_str());
        let _port_env = set_env_var(REDIS_PORT_ENV, port.as_str());
        let _password_env = remove_env_var(REDIS_PASSWORD_ENV);
        let _events_channel_env = remove_env_var(REDIS_CHANNEL_EVENTS_ENV);

        RedisConfig::from_env()
    };

    let mut subscriber = subscribe_to_channel(&redis_config, CUSTOM_CAMERA_EVENTS_CHANNEL)?;
    let cam_id = 126;
    let camera = Camera {
        node_id: cam_id as u32,
        object_serial: cam_id,
        name: "configured-channel-camera".to_owned(),
    };
    let publisher = Rc::new(RefCell::new(configure_redis_conn_with_retry(
        &redis_config,
    )?));

    publish_camera_event(
        &publisher,
        &redis_config,
        CameraEventType::Disconnected,
        &camera,
        CUSTOM_CAMERA_EVENTS_CHANNEL,
    );

    let payload = receive_message(&mut subscriber, CUSTOM_CAMERA_EVENTS_CHANNEL)?;
    assert_camera_event_envelope(
        &payload,
        CameraEventType::Disconnected,
        cam_id,
        "configured-channel-camera",
        CUSTOM_CAMERA_EVENTS_CHANNEL,
    )?;

    Ok(())
}

#[tokio::test]
async fn test_publish_failure_reconnects_and_replaces_redis_connection()
-> Result<(), Box<dyn Error>> {
    let redis_container = start_redis_contract_test_container().await?;
    let port = redis_container.port.to_string();

    let redis_config = {
        let _env_lock = REDIS_CONTRACT_TEST_ENV_LOCK.lock().await;
        let _host_env = set_env_var(REDIS_HOST_ENV, redis_container.host.as_str());
        let _port_env = set_env_var(REDIS_PORT_ENV, port.as_str());
        let _password_env = remove_env_var(REDIS_PASSWORD_ENV);
        let _events_channel_env = remove_env_var(REDIS_CHANNEL_EVENTS_ENV);

        RedisConfig::from_env()
    };

    let mut subscriber = subscribe_to_channel(&redis_config, CAMERA_EVENTS_CHANNEL)?;
    let cam_id = 126;
    let camera = Camera {
        node_id: cam_id as u32,
        object_serial: cam_id,
        name: "reconnected-camera".to_owned(),
    };
    let publisher = Rc::new(RefCell::new(configure_redis_conn_with_retry(
        &redis_config,
    )?));
    let original_client_id = {
        let mut connection = publisher.borrow_mut();
        get_redis_client_id(&mut connection)?
    };

    kill_redis_client(&redis_config, original_client_id)?;

    publish_camera_event(
        &publisher,
        &redis_config,
        CameraEventType::Connected,
        &camera,
        redis_config.events_channel.as_str(),
    );

    let reconnected_client_id = {
        let mut connection = publisher.borrow_mut();
        get_redis_client_id(&mut connection)?
    };
    assert_ne!(
        original_client_id, reconnected_client_id,
        "a new Redis connection should have been established after the original connection was killed"
    );

    publish_camera_event(
        &publisher,
        &redis_config,
        CameraEventType::Disconnected,
        &camera,
        redis_config.events_channel.as_str(),
    );

    let payload = receive_message(&mut subscriber, CAMERA_EVENTS_CHANNEL)?;
    assert_camera_event_envelope(
        &payload,
        CameraEventType::Disconnected,
        cam_id,
        "reconnected-camera",
        CAMERA_EVENTS_CHANNEL,
    )?;

    Ok(())
}
