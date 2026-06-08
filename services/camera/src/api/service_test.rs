use crate::service::{map_snapshot_error, pipewire};
use crate::snapshot::{SnapshotCamera, SnapshotError, SnapshotSupportedFormat};
use ::pipewire::spa::param::format::MediaSubtype;
use ::pipewire::spa::param::video::VideoFormat;
use tonic::Code;

#[test]
fn map_snapshot_error_returns_unavailable_status() {
    let status = map_snapshot_error(SnapshotError::Unavailable("pipewire unavailable".into()));

    assert_eq!(status.code(), Code::Unavailable);
    assert_eq!(status.message(), "pipewire unavailable");
}

#[test]
fn snapshot_camera_converts_to_grpc_camera_with_supported_formats() {
    let snapshot = SnapshotCamera {
        object_serial: 7,
        name: "front".to_string(),
        supported_formats: vec![
            SnapshotSupportedFormat::RawVideo(VideoFormat::RGB),
            SnapshotSupportedFormat::EncodedVideo(MediaSubtype::Mjpg),
        ],
    };

    let camera = pipewire::Camera::from(snapshot);

    assert_eq!(camera.id, 7);
    assert_eq!(camera.name, "front");
    assert_eq!(camera.supported_formats, ["RGB", "Mjpg"]);
}

#[test]
fn snapshot_camera_converts_to_grpc_camera_with_empty_supported_formats() {
    let snapshot = SnapshotCamera {
        object_serial: 7,
        name: "front".to_string(),
        supported_formats: vec![],
    };

    let camera = pipewire::Camera::from(snapshot);

    assert_eq!(camera.id, 7);
    assert_eq!(camera.name, "front");
    assert!(camera.supported_formats.is_empty());
}
