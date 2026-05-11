use super::snapshot::{
    CameraMetadata, SnapshotError, SnapshotState, append_camera_metadata, finish_snapshot,
    is_pending_sync_complete, record_snapshot_timeout, remove_camera_metadata,
};
use pipewire as pw;
use std::collections::HashMap;

#[test]
fn snapshot_error_displays_message() {
    let error = SnapshotError::Unavailable("pipewire unavailable".to_string());

    assert_eq!(error.to_string(), "pipewire unavailable");
}

fn node_global_factory(
    id: u32,
    type_: pw::types::ObjectType,
    media_class: Option<&str>,
    nick: Option<&str>,
) -> pw::registry::GlobalObject<pw::properties::PropertiesBox> {
    let props = match (media_class, nick) {
        (Some(media_class), Some(nick)) => Some(pw::properties::properties! {
            *pw::keys::MEDIA_CLASS => media_class,
            *pw::keys::NODE_NICK => nick
        }),
        (Some(media_class), None) => Some(pw::properties::properties! {
            *pw::keys::MEDIA_CLASS => media_class
        }),
        (None, Some(nick)) => Some(pw::properties::properties! {
            *pw::keys::NODE_NICK => nick
        }),
        (None, None) => None,
    };

    pw::registry::GlobalObject {
        id,
        permissions: pw::permissions::PermissionFlags::all(),
        type_,
        version: 0,
        props,
    }
}

#[test]
fn append_camera_metadata_records_only_camera_nodes() {
    let mut cameras = HashMap::new();
    let camera = node_global_factory(
        7,
        pw::types::ObjectType::Node,
        Some("Video/Source"),
        Some("front"),
    );
    let audio = node_global_factory(
        8,
        pw::types::ObjectType::Node,
        Some("Audio/Source"),
        Some("mic"),
    );

    append_camera_metadata(&mut cameras, &camera);
    append_camera_metadata(&mut cameras, &audio);

    assert_eq!(
        cameras.get(&7),
        Some(&CameraMetadata {
            id: 7,
            name: "front".to_string(),
        })
    );
    assert_eq!(cameras.len(), 1);
}

#[test]
fn remove_camera_metadata_drops_camera_by_id() {
    let mut cameras = HashMap::from([(
        7,
        CameraMetadata {
            id: 7,
            name: "front".to_string(),
        },
    )]);

    remove_camera_metadata(&mut cameras, 7);

    assert!(cameras.is_empty());
}

#[test]
fn is_pending_sync_complete_only_for_matching_pending_sync() {
    assert!(!is_pending_sync_complete(
        pw::core::PW_ID_CORE,
        pw::spa::utils::result::AsyncSeq::from_seq(4),
        pw::spa::utils::result::AsyncSeq::from_seq(5),
    ));

    assert!(is_pending_sync_complete(
        pw::core::PW_ID_CORE,
        pw::spa::utils::result::AsyncSeq::from_seq(5),
        pw::spa::utils::result::AsyncSeq::from_seq(5),
    ));
}

#[test]
fn finish_snapshot_returns_recorded_failure() {
    assert_eq!(
        finish_snapshot(
            HashMap::new(),
            Some(SnapshotError::Unavailable("boom".to_string())),
            false,
        ),
        Err(SnapshotError::Unavailable("boom".to_string()))
    );
}

#[test]
fn finish_snapshot_returns_incomplete_when_never_completed() {
    assert_eq!(
        finish_snapshot(HashMap::new(), None, false),
        Err(SnapshotError::Unavailable(
            "PipeWire snapshot did not complete".to_string()
        ))
    );
}

#[test]
fn record_snapshot_timeout_sets_timeout_error_when_snapshot_is_pending() {
    let mut state = SnapshotState::default();

    assert!(record_snapshot_timeout(&mut state));
    assert_eq!(
        state.error,
        Some(SnapshotError::Unavailable(
            "PipeWire snapshot timed out".to_string()
        ))
    );
}

#[test]
fn record_snapshot_timeout_ignores_completed_snapshot() {
    let mut state = SnapshotState {
        done: true,
        ..SnapshotState::default()
    };

    assert!(!record_snapshot_timeout(&mut state));
    assert_eq!(state.error, None);
}

#[test]
fn record_snapshot_timeout_preserves_existing_error() {
    let existing_error_message = "PipeWire core error: boom".to_string();
    let mut state = SnapshotState {
        error: Some(SnapshotError::Unavailable(existing_error_message.clone())),
        ..SnapshotState::default()
    };

    assert!(!record_snapshot_timeout(&mut state));
    assert_eq!(
        state.error,
        Some(SnapshotError::Unavailable(existing_error_message))
    );
}

#[test]
fn finish_snapshot_sorts_cameras_by_id_before_returning() {
    let camera_b = node_global_factory(
        11,
        pw::types::ObjectType::Node,
        Some("Video/Source"),
        Some("rear"),
    );
    let camera_a = node_global_factory(
        7,
        pw::types::ObjectType::Node,
        Some("Video/Source"),
        Some("front"),
    );

    let cameras = finish_snapshot(
        HashMap::from([
            (
                camera_b.id,
                CameraMetadata {
                    id: camera_b.id,
                    name: "rear".to_string(),
                },
            ),
            (
                camera_a.id,
                CameraMetadata {
                    id: camera_a.id,
                    name: "front".to_string(),
                },
            ),
        ]),
        None,
        true,
    )
    .unwrap();
    assert_eq!(cameras[0].id, 7);
    assert_eq!(cameras[1].id, 11);
}

#[test]
fn finish_snapshot_omits_removed_cameras() {
    let mut cameras = HashMap::from([
        (
            7,
            CameraMetadata {
                id: 7,
                name: "front".to_string(),
            },
        ),
        (
            11,
            CameraMetadata {
                id: 11,
                name: "rear".to_string(),
            },
        ),
    ]);

    remove_camera_metadata(&mut cameras, 7);

    let cameras = finish_snapshot(cameras, None, true).unwrap();

    assert_eq!(cameras.len(), 1);
    assert_eq!(cameras[0].id, 11);
}
