use std::cell::{Cell, RefCell};
use std::io;
use std::time::Duration;

use super::redis::RedisConfig;
use super::redis::retry_with_fibonacci;
use redis::{ConnectionAddr, ErrorKind, IntoConnectionInfo, RedisError, RedisResult};

const CAMERA_EVENTS_CHANNEL: &str = "camera.events";

#[test]
fn test_redis_connection_info_uses_host_and_port() {
    let redis_config = RedisConfig {
        host: "redis".to_owned(),
        port: "6379".to_owned(),
        password: None,
        events_channel: CAMERA_EVENTS_CHANNEL.to_owned(),
    };
    let connection_info = redis_config.into_connection_info().unwrap();

    assert_eq!(
        connection_info.addr(),
        &ConnectionAddr::Tcp("redis".to_owned(), 6379)
    );
    assert_eq!(connection_info.redis_settings().password(), None);
}

#[test]
fn test_redis_connection_info_includes_password_when_configured() {
    let redis_config = RedisConfig {
        host: "redis".to_owned(),
        port: "6379".to_owned(),
        password: Some("p@ss:/?#[]!$&'()*+,;=%".to_owned()),
        events_channel: CAMERA_EVENTS_CHANNEL.to_owned(),
    };
    let connection_info = redis_config.into_connection_info().unwrap();

    assert_eq!(
        connection_info.addr(),
        &ConnectionAddr::Tcp("redis".to_owned(), 6379)
    );
    assert_eq!(
        connection_info.redis_settings().password(),
        Some("p@ss:/?#[]!$&'()*+,;=%")
    );
}

#[test]
fn test_retry_with_fibonacci_retries_io_errors_until_success() {
    let attempts = Cell::new(0);
    let delays = RefCell::new(Vec::new());

    let result = retry_with_fibonacci(
        || {
            let attempt = attempts.get();
            attempts.set(attempt + 1);

            if attempt < 3 {
                Err(RedisError::from(io::Error::new(
                    io::ErrorKind::ConnectionRefused,
                    "redis unavailable",
                )))
            } else {
                Ok("connected")
            }
        },
        |delay| delays.borrow_mut().push(delay),
        Duration::from_secs(30),
    );

    assert_eq!(result.unwrap(), "connected");
    assert_eq!(attempts.get(), 4);
    assert_eq!(
        *delays.borrow(),
        vec![
            Duration::from_secs(1),
            Duration::from_secs(1),
            Duration::from_secs(2),
        ]
    );
}

#[test]
fn test_retry_with_fibonacci_does_not_retry_non_io_errors() {
    let attempts = Cell::new(0);
    let delays = RefCell::new(Vec::new());

    let result: RedisResult<()> = retry_with_fibonacci(
        || {
            attempts.set(attempts.get() + 1);
            Err(RedisError::from((
                ErrorKind::InvalidClientConfig,
                "Invalid Redis port",
            )))
        },
        |delay| delays.borrow_mut().push(delay),
        Duration::from_secs(30),
    );

    let err = result.unwrap_err();
    assert_eq!(err.kind(), ErrorKind::InvalidClientConfig);
    assert_eq!(attempts.get(), 1);
    assert!(delays.borrow().is_empty());
}
