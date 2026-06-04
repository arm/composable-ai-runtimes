use super::snapshot::{
    SnapshotCamera, SnapshotError, SnapshotPhase, SnapshotState, SnapshotSupportedFormat,
    append_camera_metadata, is_pending_sync_complete,
};
use pipewire as pw;
use pw::spa::param::format::MediaSubtype;
use pw::spa::param::video::VideoFormat;
use std::collections::HashMap;

#[test]
fn snapshot_error_displays_message() {
    let error = SnapshotError::Unavailable("pipewire unavailable".to_string());

    assert_eq!(error.to_string(), "pipewire unavailable");
}

#[test]
fn snapshot_supported_format_displays_pipewire_format_name() {
    assert_eq!(
        SnapshotSupportedFormat::RawVideo(VideoFormat::RGB).to_string(),
        "RGB"
    );
    assert_eq!(
        SnapshotSupportedFormat::EncodedVideo(MediaSubtype::Mjpg).to_string(),
        "Mjpg"
    );
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

fn async_seq_factory(seq: i32) -> pw::spa::utils::result::AsyncSeq {
    pw::spa::utils::result::AsyncSeq::from_seq(seq)
}

fn non_core_pipewire_id_factory() -> u32 {
    pw::core::PW_ID_CORE + 1
}

#[test]
fn append_camera_metadata_records_camera_node() {
    let mut cameras = HashMap::new();
    let camera = node_global_factory(
        7,
        pw::types::ObjectType::Node,
        Some("Video/Source"),
        Some("front"),
    );

    append_camera_metadata(&mut cameras, &camera);

    assert_eq!(
        cameras.get(&7),
        Some(&SnapshotCamera {
            id: 7,
            name: "front".to_string(),
            supported_formats: vec![],
        })
    );
    assert_eq!(cameras.len(), 1);
}

#[test]
fn is_pending_sync_complete_only_for_matching_pending_sync() {
    assert!(!is_pending_sync_complete(
        pw::core::PW_ID_CORE,
        async_seq_factory(4),
        async_seq_factory(5),
    ));

    assert!(is_pending_sync_complete(
        pw::core::PW_ID_CORE,
        async_seq_factory(5),
        async_seq_factory(5),
    ));
}

#[test]
fn is_pending_sync_complete_rejects_matching_sequence_from_non_core_id() {
    assert!(!is_pending_sync_complete(
        non_core_pipewire_id_factory(),
        async_seq_factory(5),
        async_seq_factory(5),
    ));
}

#[test]
fn take_result_returns_recorded_failure() {
    let mut state = SnapshotState::default();
    state.error = Some(SnapshotError::Unavailable("boom".to_string()));

    assert_eq!(
        state.take_result(),
        Err(SnapshotError::Unavailable("boom".to_string()))
    );
}

#[test]
fn take_result_returns_incomplete_when_never_completed() {
    let mut state = SnapshotState::default();

    assert_eq!(
        state.take_result(),
        Err(SnapshotError::Unavailable(
            "PipeWire snapshot did not complete".to_string()
        ))
    );
}

#[test]
fn is_pending_without_error_returns_true_when_snapshot_is_pending() {
    let state = SnapshotState::default();

    assert!(state.is_pending_without_error());
    assert_eq!(state.error, None);
}

#[test]
fn is_pending_without_error_returns_false_for_completed_snapshot() {
    let mut state = SnapshotState::default();
    state.phase = SnapshotPhase::Complete;

    assert!(!state.is_pending_without_error());
    assert_eq!(state.error, None);
}

#[test]
fn is_pending_without_error_returns_false_for_existing_error() {
    let existing_error_message = "PipeWire core error: boom".to_string();
    let mut state = SnapshotState::default();
    state.error = Some(SnapshotError::Unavailable(existing_error_message.clone()));

    assert!(!state.is_pending_without_error());
    assert_eq!(
        state.error,
        Some(SnapshotError::Unavailable(existing_error_message))
    );
}

#[test]
fn take_result_sorts_cameras_by_id_before_returning() {
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

    let mut state = SnapshotState::default();
    state.phase = SnapshotPhase::Complete;
    state.cameras = HashMap::from([
        (
            camera_b.id,
            SnapshotCamera {
                id: camera_b.id,
                name: "rear".to_string(),
                supported_formats: vec![],
            },
        ),
        (
            camera_a.id,
            SnapshotCamera {
                id: camera_a.id,
                name: "front".to_string(),
                supported_formats: vec![],
            },
        ),
    ]);

    let cameras = state.take_result().unwrap();
    assert_eq!(cameras[0].id, 7);
    assert_eq!(cameras[1].id, 11);
}

#[test]
fn take_result_omits_removed_cameras() {
    let mut cameras = HashMap::from([
        (
            7,
            SnapshotCamera {
                id: 7,
                name: "front".to_string(),
                supported_formats: vec![],
            },
        ),
        (
            11,
            SnapshotCamera {
                id: 11,
                name: "rear".to_string(),
                supported_formats: vec![],
            },
        ),
    ]);

    cameras.remove(&7);

    let mut state = SnapshotState::default();
    state.phase = SnapshotPhase::Complete;
    state.cameras = cameras;

    let cameras = state.take_result().unwrap();

    assert_eq!(cameras.len(), 1);
    assert_eq!(cameras[0].id, 11);
}
