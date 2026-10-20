// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::cell::{Cell, RefCell};
use std::io;
use std::time::Duration;

use crate::{
    messaging::CairnEvent,
    redis::{CameraEvent, CameraEventType, EventCamera, encode_camera_event},
};

use camera::camera::Camera;
use prost::Message;
use redis::{ConnectionAddr, ErrorKind, IntoConnectionInfo, RedisError, RedisResult};

use super::redis::{RedisConfig, retry_with_fibonacci};

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
fn test_fibonacci_backoff_caps_delay() {
    let attempts = Cell::new(0);
    let delays = RefCell::new(Vec::new());

    let result = retry_with_fibonacci(
        || {
            let attempt = attempts.get();
            attempts.set(attempt + 1);

            if attempt < 6 {
                Err(RedisError::from(io::Error::new(
                    io::ErrorKind::ConnectionRefused,
                    "redis unavailable",
                )))
            } else {
                Ok("connected")
            }
        },
        |delay| delays.borrow_mut().push(delay),
        Duration::from_secs(5),
    );

    assert_eq!(result.unwrap(), "connected");
    assert_eq!(attempts.get(), 7);
    assert_eq!(
        *delays.borrow(),
        vec![
            Duration::from_secs(1),
            Duration::from_secs(1),
            Duration::from_secs(2),
            Duration::from_secs(3),
            Duration::from_secs(5),
            Duration::from_secs(5),
        ]
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

#[test]
fn test_camera_event_payload_from_camera_exposes_object_serial() {
    let camera = Camera {
        node_id: 7,
        object_serial: 42,
        name: "front-camera".to_string(),
    };

    assert_eq!(
        EventCamera::from(&camera),
        EventCamera {
            id: 42,
            name: "front-camera".to_string(),
        }
    );
}

#[test]
fn test_camera_event_type_to_string_returns_event_identifier() {
    assert_eq!(
        CameraEventType::Connected.to_string(),
        "cairn.camera.connected"
    );
    assert_eq!(
        CameraEventType::Disconnected.to_string(),
        "cairn.camera.disconnected"
    );
}

#[test]
fn test_camera_event_encoding_uses_messaging_envelope() {
    let camera = Camera {
        node_id: 7,
        object_serial: 42,
        name: "front-camera".to_string(),
    };

    let encoded_event =
        encode_camera_event(CameraEventType::Connected, &camera, CAMERA_EVENTS_CHANNEL).unwrap();
    let envelope = CairnEvent::decode(encoded_event.as_slice()).unwrap();
    let timestamp = envelope.timestamp.unwrap();
    let payload: CameraEvent = serde_json::from_slice(&envelope.payload).unwrap();

    assert!(timestamp.seconds > 0);
    assert_eq!(envelope.origin, "cairn.camera-service");
    assert_eq!(envelope.event_type, "cairn.camera.connected");
    assert_eq!(envelope.topic, CAMERA_EVENTS_CHANNEL);
    assert_eq!(
        payload,
        CameraEvent {
            event_type: CameraEventType::Connected,
            camera: EventCamera::from(&camera),
        }
    );
}
