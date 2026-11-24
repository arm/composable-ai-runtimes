// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use super::parameters::{FrameRate, Resolution, StreamFormat};
use super::service::media::media_service_server::MediaService;
use super::service::{
    MediaApiService, MediaServiceProvider, map_snapshot_error, media,
    validate_stream_configuration_request,
};
use super::snapshot::SnapshotError;
use crate::device::{Device, DeviceType};
use tonic::{Code, Request};

#[test]
fn map_snapshot_error_returns_unavailable_status() {
    let status = map_snapshot_error(SnapshotError::Unavailable("pipewire unavailable".into()));

    assert_eq!(status.code(), Code::Unavailable);
    assert_eq!(status.message(), "pipewire unavailable");
}

#[tokio::test]
async fn list_devices_forwards_each_filter_and_returns_empty_results() {
    let camera = MediaServiceProvider {
        list_devices: |filter| {
            assert_eq!(filter, Some(DeviceType::Camera));
            Ok(Vec::new())
        },
        ..Default::default()
    };
    let microphone = MediaServiceProvider {
        list_devices: |filter| {
            assert_eq!(filter, Some(DeviceType::Microphone));
            Ok(Vec::new())
        },
        ..Default::default()
    };
    let speaker = MediaServiceProvider {
        list_devices: |filter| {
            assert_eq!(filter, Some(DeviceType::Speaker));
            Ok(Vec::new())
        },
        ..Default::default()
    };
    for (device_type, provider) in [
        (media::DeviceType::Camera, camera),
        (media::DeviceType::Microphone, microphone),
        (media::DeviceType::Speaker, speaker),
    ] {
        let service = MediaApiService { provider };
        let response = service
            .list_devices(Request::new(media::ListDevicesRequest {
                device_type: Some(device_type.into()),
            }))
            .await
            .expect("listing should succeed");
        assert!(response.into_inner().devices.is_empty());
    }
}

#[test]
fn map_snapshot_error_returns_not_found_status() {
    let status = map_snapshot_error(SnapshotError::NotFound(52));

    assert_eq!(status.code(), Code::NotFound);
    assert_eq!(status.message(), "camera 52 was not found");
}

#[tokio::test]
async fn list_devices_with_empty_request_returns_all_device_identities_and_types() {
    let service = MediaApiService {
        provider: MediaServiceProvider {
            list_devices: |filter| {
                assert_eq!(filter, None);
                Ok([
                    (1, "camera", DeviceType::Camera),
                    (2, "microphone", DeviceType::Microphone),
                    (3, "speaker", DeviceType::Speaker),
                ]
                .into_iter()
                .map(|(node_id, name, device_type)| Device {
                    node_id,
                    object_serial: u64::from(u32::MAX) + u64::from(node_id),
                    name: name.to_string(),
                    device_type,
                })
                .collect())
            },
            ..Default::default()
        },
    };
    let devices = service
        .list_devices(Request::new(media::ListDevicesRequest::default()))
        .await
        .expect("listing should succeed")
        .into_inner()
        .devices;
    let identities = devices
        .into_iter()
        .map(|device| (device.id, device.name, device.device_type))
        .collect::<Vec<_>>();
    assert_eq!(
        identities,
        vec![
            (
                4_294_967_296,
                "camera".to_string(),
                i32::from(media::DeviceType::Camera)
            ),
            (
                4_294_967_297,
                "microphone".to_string(),
                i32::from(media::DeviceType::Microphone)
            ),
            (
                4_294_967_298,
                "speaker".to_string(),
                i32::from(media::DeviceType::Speaker)
            ),
        ]
    );
}

#[test]
fn validate_stream_configuration_request_rejects_zero_camera_id() {
    let request = media::StreamConfigurationRequest {
        camera_id: 0,
        format: None,
    };

    let error = validate_stream_configuration_request(&request).unwrap_err();

    assert_eq!(error.code(), Code::InvalidArgument);
    assert_eq!(error.message(), "camera_id must be greater than zero");
}

#[tokio::test]
async fn list_devices_rejects_unknown_types_before_querying_provider() {
    let service = MediaApiService {
        provider: MediaServiceProvider {
            list_devices: |_| panic!("invalid requests must not query PipeWire"),
            ..Default::default()
        },
    };
    for device_type in [-1, 3] {
        let error = service
            .list_devices(Request::new(media::ListDevicesRequest {
                device_type: Some(device_type),
            }))
            .await
            .expect_err("unknown type should fail");
        assert_eq!(error.code(), Code::InvalidArgument);
        assert_eq!(
            error.message(),
            format!("unknown device_type: {device_type}")
        );
    }
}

#[tokio::test]
async fn list_devices_maps_snapshot_error_to_unavailable() {
    let service = MediaApiService {
        provider: MediaServiceProvider {
            list_devices: |_| Err(SnapshotError::Unavailable("PipeWire disconnected".into())),
            ..Default::default()
        },
    };
    let error = service
        .list_devices(Request::new(media::ListDevicesRequest::default()))
        .await
        .expect_err("provider failure should reach the caller");
    assert_eq!(error.code(), Code::Unavailable);
    assert_eq!(error.message(), "PipeWire disconnected");
}

#[tokio::test]
async fn list_devices_maps_snapshot_panic_to_unavailable() {
    let service = MediaApiService {
        provider: MediaServiceProvider {
            list_devices: |_| panic!("snapshot task panicked"),
            ..Default::default()
        },
    };
    let error = service
        .list_devices(Request::new(media::ListDevicesRequest::default()))
        .await
        .expect_err("task failure should reach the caller");
    assert_eq!(error.code(), Code::Unavailable);
    assert!(error.message().starts_with("device listing task failed:"));
}

#[tokio::test]
async fn list_cameras_returns_camera_identities() {
    let service = MediaApiService {
        provider: MediaServiceProvider {
            list_devices: |filter| {
                assert_eq!(filter, Some(DeviceType::Camera));
                Ok(vec![
                    Device {
                        node_id: 7,
                        object_serial: 4_294_967_303,
                        name: "front-door".to_string(),
                        device_type: DeviceType::Camera,
                    },
                    Device {
                        node_id: 8,
                        object_serial: 4_294_967_304,
                        name: "loading-bay".to_string(),
                        device_type: DeviceType::Camera,
                    },
                ])
            },
            ..Default::default()
        },
    };

    let cameras = service
        .list_cameras(Request::new(media::ListRequest {}))
        .await
        .expect("listing should succeed")
        .into_inner()
        .cameras;

    assert_eq!(
        cameras
            .into_iter()
            .map(|camera| (camera.id, camera.name))
            .collect::<Vec<_>>(),
        vec![
            (4_294_967_303, "front-door".to_string()),
            (4_294_967_304, "loading-bay".to_string()),
        ]
    );
}

#[tokio::test]
async fn list_cameras_maps_snapshot_error_to_unavailable() {
    let service = MediaApiService {
        provider: MediaServiceProvider {
            list_devices: |_| Err(SnapshotError::Unavailable("PipeWire disconnected".into())),
            ..Default::default()
        },
    };

    let error = service
        .list_cameras(Request::new(media::ListRequest {}))
        .await
        .expect_err("provider failure should reach the caller");

    assert_eq!(error.code(), Code::Unavailable);
    assert_eq!(error.message(), "PipeWire disconnected");
}

#[tokio::test]
async fn list_cameras_maps_blocking_task_panic_to_unavailable() {
    let service = MediaApiService {
        provider: MediaServiceProvider {
            list_devices: |_| panic!("snapshot task panicked"),
            ..Default::default()
        },
    };

    let error = service
        .list_cameras(Request::new(media::ListRequest {}))
        .await
        .expect_err("task failure should reach the caller");

    assert_eq!(error.code(), Code::Unavailable);
    assert!(error.message().starts_with("camera listing task failed:"));
}

#[test]
fn validate_stream_configuration_request_rejects_zero_resolution_dimension() {
    let request = media::StreamConfigurationRequest {
        camera_id: 52,
        format: Some(media::StreamFormat {
            resolution: Some(media::Resolution {
                width: 0,
                height: 1080,
            }),
            pixel_format: String::new(),
            frame_rate: None,
        }),
    };

    let error = validate_stream_configuration_request(&request).unwrap_err();

    assert_eq!(error.code(), Code::InvalidArgument);
    assert_eq!(
        error.message(),
        "resolution width and height must be greater than zero"
    );
}

#[test]
fn validate_stream_configuration_request_rejects_zero_frame_rate_value() {
    let request = media::StreamConfigurationRequest {
        camera_id: 52,
        format: Some(media::StreamFormat {
            resolution: None,
            pixel_format: String::new(),
            frame_rate: Some(media::FrameRate {
                numerator: 30,
                denominator: 0,
            }),
        }),
    };

    let error = validate_stream_configuration_request(&request).unwrap_err();

    assert_eq!(error.code(), Code::InvalidArgument);
    assert_eq!(
        error.message(),
        "frame rate numerator and denominator must be greater than zero"
    );
}

#[test]
fn validate_stream_configuration_request_rejects_invalid_pixel_format() {
    let request = media::StreamConfigurationRequest {
        camera_id: 52,
        format: Some(media::StreamFormat {
            resolution: None,
            pixel_format: "RGB 24".to_string(),
            frame_rate: None,
        }),
    };

    let error = validate_stream_configuration_request(&request).unwrap_err();

    assert_eq!(error.code(), Code::InvalidArgument);
    assert_eq!(error.message(), "pixel_format contains invalid characters");
}

#[test]
fn stream_format_converts_to_grpc_stream_format() {
    let format = StreamFormat {
        resolution: Resolution {
            width: 1920,
            height: 1080,
        },
        pixel_format: "RGB".to_string(),
        frame_rate: FrameRate {
            numerator: 30,
            denominator: 1,
        },
    };

    let actual = media::StreamFormat::from(format);
    let expected = media::StreamFormat {
        resolution: Some(media::Resolution {
            width: 1920,
            height: 1080,
        }),
        pixel_format: "RGB".to_string(),
        frame_rate: Some(media::FrameRate {
            numerator: 30,
            denominator: 1,
        }),
    };

    assert_eq!(actual, expected);
}

#[test]
fn device_converts_to_grpc_camera() {
    let snapshot = Device {
        node_id: 11,
        object_serial: 7,
        name: "front".to_string(),
        device_type: DeviceType::Camera,
    };

    let camera = media::Camera::from(snapshot);

    assert_eq!(camera.id, 7);
    assert_eq!(camera.name, "front");
}
