// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use super::parameters::{FrameRate, Resolution, StreamFormat};
use super::service::{map_snapshot_error, pipewire, validate_stream_configuration_request};
use super::snapshot::{SnapshotCamera, SnapshotError};
use tonic::Code;

#[test]
fn map_snapshot_error_returns_unavailable_status() {
    let status = map_snapshot_error(SnapshotError::Unavailable("pipewire unavailable".into()));

    assert_eq!(status.code(), Code::Unavailable);
    assert_eq!(status.message(), "pipewire unavailable");
}

#[test]
fn map_snapshot_error_returns_not_found_status() {
    let status = map_snapshot_error(SnapshotError::NotFound(52));

    assert_eq!(status.code(), Code::NotFound);
    assert_eq!(status.message(), "camera 52 was not found");
}

#[test]
fn validate_stream_configuration_request_rejects_zero_camera_id() {
    let request = pipewire::StreamConfigurationRequest {
        camera_id: 0,
        format: None,
    };

    let error = validate_stream_configuration_request(&request).unwrap_err();

    assert_eq!(error.code(), Code::InvalidArgument);
    assert_eq!(error.message(), "camera_id must be greater than zero");
}

#[test]
fn validate_stream_configuration_request_rejects_zero_resolution_dimension() {
    let request = pipewire::StreamConfigurationRequest {
        camera_id: 52,
        format: Some(pipewire::StreamFormat {
            resolution: Some(pipewire::Resolution {
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
    let request = pipewire::StreamConfigurationRequest {
        camera_id: 52,
        format: Some(pipewire::StreamFormat {
            resolution: None,
            pixel_format: String::new(),
            frame_rate: Some(pipewire::FrameRate {
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
    let request = pipewire::StreamConfigurationRequest {
        camera_id: 52,
        format: Some(pipewire::StreamFormat {
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

    let actual = pipewire::StreamFormat::from(format);
    let expected = pipewire::StreamFormat {
        resolution: Some(pipewire::Resolution {
            width: 1920,
            height: 1080,
        }),
        pixel_format: "RGB".to_string(),
        frame_rate: Some(pipewire::FrameRate {
            numerator: 30,
            denominator: 1,
        }),
    };

    assert_eq!(actual, expected);
}

#[test]
fn snapshot_camera_converts_to_grpc_camera() {
    let snapshot = SnapshotCamera {
        object_serial: 7,
        name: "front".to_string(),
    };

    let camera = pipewire::Camera::from(snapshot);

    assert_eq!(camera.id, 7);
    assert_eq!(camera.name, "front");
}
