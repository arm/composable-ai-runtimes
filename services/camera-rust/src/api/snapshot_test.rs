use super::snapshot::{SnapshotError, list_camera_metadata};

#[test]
fn snapshot_error_displays_message() {
    let error = SnapshotError::Unavailable("pipewire unavailable".to_string());

    assert_eq!(error.to_string(), "pipewire unavailable");
}

#[test]
fn list_camera_metadata_returns_empty_camera_metadata() {
    let cameras =
        list_camera_metadata().expect("snapshot should return an empty camera metadata list");

    assert!(cameras.is_empty());
}
