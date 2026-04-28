use super::redis::RedisConfig;
use redis::{ConnectionAddr, IntoConnectionInfo};

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
