use std::{env, error::Error};

use crate::camera_metadata::CameraMetadata;
use redis::{
    Client, Commands, Connection, ConnectionAddr, ConnectionInfo, ErrorKind, IntoConnectionInfo,
    RedisConnectionInfo, RedisError, RedisResult,
};
use serde::Serialize;

const REDIS_HOST_ENV: &str = "PWC_REDIS_HOST";
const REDIS_PORT_ENV: &str = "PWC_REDIS_PORT";
const REDIS_PASSWORD_ENV: &str = "PWC_REDIS_PASSWORD";
const REDIS_CHANNEL_EVENTS_ENV: &str = "PWC_REDIS_CHANNEL_EVENTS";
const DEFAULT_REDIS_HOST: &str = "127.0.0.1";
const DEFAULT_REDIS_PORT: &str = "6379";
const CAMERA_EVENTS_CHANNEL: &str = "camera.events";

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum CameraEventType {
    Connected,
    Disconnected,
}

#[derive(Debug, Serialize)]
struct CameraEvent<'a> {
    event_type: CameraEventType,
    #[serde(flatten)]
    camera: &'a CameraMetadata,
}

#[derive(Debug, Eq, PartialEq)]
pub struct RedisConfig {
    pub host: String,
    pub port: String,
    pub password: Option<String>,
    pub events_channel: String,
}

impl RedisConfig {
    pub fn from_env() -> Self {
        Self {
            host: env_or_default(REDIS_HOST_ENV, DEFAULT_REDIS_HOST),
            port: env_or_default(REDIS_PORT_ENV, DEFAULT_REDIS_PORT),
            password: env::var(REDIS_PASSWORD_ENV)
                .ok()
                .filter(|value| !value.is_empty()),
            events_channel: env_or_default(REDIS_CHANNEL_EVENTS_ENV, CAMERA_EVENTS_CHANNEL),
        }
    }
}

fn env_or_default(var_name: &str, default: &str) -> String {
    env::var(var_name)
        .ok()
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| default.to_owned())
}

impl IntoConnectionInfo for &RedisConfig {
    fn into_connection_info(self) -> RedisResult<ConnectionInfo> {
        let redis_port = self.port.parse::<u16>().map_err(|_| {
            RedisError::from((ErrorKind::InvalidClientConfig, "Invalid Redis port"))
        })?;
        let redis_addr = ConnectionAddr::Tcp(self.host.clone(), redis_port);
        let mut redis_settings = RedisConnectionInfo::default();

        if let Some(password) = &self.password {
            redis_settings = redis_settings.set_password(password);
        }

        Ok(redis_addr
            .into_connection_info()?
            .set_redis_settings(redis_settings))
    }
}

pub fn configure_redis_conn(redis_config: &RedisConfig) -> Result<Connection, Box<dyn Error>> {
    let client = Client::open(redis_config)?;

    Ok(client.get_connection()?)
}

pub fn send_camera_event(
    redis_conn: &mut Connection,
    event_type: CameraEventType,
    camera: &CameraMetadata,
    events_channel: &str,
) -> Result<(), Box<dyn Error>> {
    let payload = serde_json::to_string(&CameraEvent { event_type, camera })?;
    let _: usize = redis_conn.publish(events_channel, payload)?;

    Ok(())
}
