use std::{cell::RefCell, env, error::Error, ffi::OsString, io, rc::Rc, time::Duration};

use super::{
    publish_camera_event,
    redis::{CameraEventType, RedisConfig, configure_redis_conn_with_retry},
};
use camera::camera_metadata::CameraMetadata;
use redis::{Client, Msg};
use testcontainers::{
    ContainerAsync, GenericImage,
    core::{IntoContainerPort, WaitFor},
    runners::AsyncRunner,
};
use tokio::sync::Mutex;

const REDIS_PORT: u16 = 6379;
const REDIS_VERSION: &str = "7.2.4";
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
) -> Result<String, Box<dyn Error>> {
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
    let camera = CameraMetadata {
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

    let payload = receive_message(&mut subscriber, CAMERA_EVENTS_CHANNEL)?;
    assert!(payload.contains(r#""event_type":"connected""#));
    assert!(payload.contains(format!(r#""id":{cam_id}"#).as_str()));
    assert!(payload.contains(r#""name":"default-channel-camera""#));

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
    let camera = CameraMetadata {
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
