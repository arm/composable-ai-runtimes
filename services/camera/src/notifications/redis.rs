use std::{env, error::Error, thread, time::Duration};

use camera::camera_metadata::CameraMetadata;
use redis::{
    Client, Commands, Connection, ConnectionAddr, ConnectionInfo, ErrorKind, IntoConnectionInfo,
    RedisConnectionInfo, RedisError, RedisResult,
};
use serde::Serialize;
use tracing::warn;

const REDIS_HOST_ENV: &str = "PWC_REDIS_HOST";
const REDIS_PORT_ENV: &str = "PWC_REDIS_PORT";
const REDIS_PASSWORD_ENV: &str = "PWC_REDIS_PASSWORD";
const REDIS_CHANNEL_EVENTS_ENV: &str = "PWC_REDIS_CHANNEL_EVENTS";
const DEFAULT_REDIS_HOST: &str = "127.0.0.1";
const DEFAULT_REDIS_PORT: &str = "6379";
const CAMERA_EVENTS_CHANNEL: &str = "camera.events";
const REDIS_RECONNECT_MAX_DELAY: Duration = Duration::from_secs(30);

#[derive(Debug)]
struct FibonacciBackoff {
    current: Duration,
    next: Duration,
    max_delay: Duration,
}

impl FibonacciBackoff {
    fn new(initial_delay: Duration, max_delay: Duration) -> Self {
        Self {
            current: initial_delay,
            next: initial_delay,
            max_delay,
        }
    }

    fn next_delay(&mut self) -> Duration {
        let delay = self.current.min(self.max_delay);
        let next = self.current.saturating_add(self.next);
        self.current = self.next;
        self.next = next;

        delay
    }
}

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

pub fn configure_redis_conn_with_retry(
    redis_config: &RedisConfig,
) -> Result<Connection, Box<dyn Error>> {
    let client = Client::open(redis_config)?;

    Ok(retry_with_fibonacci(
        || client.get_connection(),
        thread::sleep,
        REDIS_RECONNECT_MAX_DELAY,
    )?)
}

pub(crate) fn retry_with_fibonacci<T, Connect, Sleep>(
    mut connect: Connect,
    mut sleep: Sleep,
    max_delay: Duration,
) -> RedisResult<T>
where
    Connect: FnMut() -> RedisResult<T>,
    Sleep: FnMut(Duration),
{
    let mut backoff = FibonacciBackoff::new(Duration::from_secs(1), max_delay);
    loop {
        match connect() {
            Ok(conn) => return Ok(conn),
            Err(err) if err.is_io_error() => {
                let delay = backoff.next_delay();
                warn!(
                    error = %err,
                    retry_delay = ?delay,
                    "failed to connect notifications Redis client; retrying"
                );
                sleep(delay);
            }
            Err(err) => return Err(err),
        }
    }
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
