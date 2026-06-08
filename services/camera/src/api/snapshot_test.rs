use super::snapshot::{
    SnapshotCamera, SnapshotError, SnapshotPhase, SnapshotState, SnapshotSupportedFormat,
    append_camera_metadata, check_timeout_error, is_pending_sync_complete,
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
    node_id: u32,
    object_serial: impl ToString,
    type_: pw::types::ObjectType,
    media_class: Option<&str>,
    nick: Option<&str>,
) -> pw::registry::GlobalObject<pw::properties::PropertiesBox> {
    let object_serial = object_serial.to_string();
    let props = match (media_class, nick) {
        (Some(media_class), Some(nick)) => Some(pw::properties::properties! {
            *pw::keys::OBJECT_SERIAL => object_serial.as_str(),
            *pw::keys::MEDIA_CLASS => media_class,
            *pw::keys::NODE_NICK => nick
        }),
        (Some(media_class), None) => Some(pw::properties::properties! {
            *pw::keys::OBJECT_SERIAL => object_serial.as_str(),
            *pw::keys::MEDIA_CLASS => media_class
        }),
        (None, Some(nick)) => Some(pw::properties::properties! {
            *pw::keys::OBJECT_SERIAL => object_serial.as_str(),
            *pw::keys::NODE_NICK => nick
        }),
        (None, None) => Some(pw::properties::properties! {
            *pw::keys::OBJECT_SERIAL => object_serial.as_str()
        }),
    };

    pw::registry::GlobalObject {
        id: node_id,
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
        42,
        pw::types::ObjectType::Node,
        Some("Video/Source"),
        Some("front"),
    );

    append_camera_metadata(&mut cameras, &camera);

    assert_eq!(
        cameras.get(&7),
        Some(&SnapshotCamera {
            object_serial: 42,
            name: "front".to_string(),
            supported_formats: vec![],
        })
    );
    assert_eq!(cameras.len(), 1);
}

#[test]
fn append_camera_metadata_ignores_camera_nodes_without_serial() {
    let mut cameras = HashMap::new();
    let camera = pw::registry::GlobalObject {
        id: 7,
        permissions: pw::permissions::PermissionFlags::all(),
        type_: pw::types::ObjectType::Node,
        version: 0,
        props: Some(pw::properties::properties! {
            *pw::keys::MEDIA_CLASS => "Video/Source",
            *pw::keys::NODE_NICK => "front"
        }),
    };

    append_camera_metadata(&mut cameras, &camera);

    assert!(cameras.is_empty());
}

#[test]
fn append_camera_metadata_ignores_camera_nodes_with_invalid_serial() {
    let mut cameras = HashMap::new();
    let camera = node_global_factory(
        7,
        "not-a-number",
        pw::types::ObjectType::Node,
        Some("Video/Source"),
        Some("front"),
    );

    append_camera_metadata(&mut cameras, &camera);

    assert!(cameras.is_empty());
}

#[test]
fn append_camera_metadata_replaces_existing_camera_for_same_node_id() {
    let mut cameras = HashMap::new();
    let initial_camera = node_global_factory(
        7,
        42,
        pw::types::ObjectType::Node,
        Some("Video/Source"),
        Some("front"),
    );
    let replacement_camera = node_global_factory(
        7,
        43,
        pw::types::ObjectType::Node,
        Some("Video/Source"),
        Some("front-updated"),
    );

    append_camera_metadata(&mut cameras, &initial_camera);
    append_camera_metadata(&mut cameras, &replacement_camera);

    assert_eq!(cameras.len(), 1);
    assert_eq!(
        cameras.get(&7),
        Some(&SnapshotCamera {
            object_serial: 43,
            name: "front-updated".to_string(),
            supported_formats: vec![],
        })
    );
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
fn take_result_returns_recorded_failure_when_cameras_were_collected() {
    let mut state = SnapshotState::default();
    state.error = Some(SnapshotError::Unavailable("boom".to_string()));
    state.cameras = HashMap::from([(
        7,
        SnapshotCamera {
            object_serial: 42,
            name: "front".to_string(),
            supported_formats: vec![],
        },
    )]);

    assert_eq!(
        state.take_result(),
        Err(SnapshotError::Unavailable("boom".to_string()))
    );
}

#[test]
fn take_result_returns_incomplete_without_returning_collected_cameras() {
    let mut state = SnapshotState::default();
    state.cameras = HashMap::from([(
        7,
        SnapshotCamera {
            object_serial: 42,
            name: "front".to_string(),
            supported_formats: vec![],
        },
    )]);

    assert_eq!(
        state.take_result(),
        Err(SnapshotError::Unavailable(
            "PipeWire snapshot did not complete".to_string()
        ))
    );
}

#[test]
fn take_result_returns_empty_vec_for_completed_empty_snapshot() {
    let mut state = SnapshotState::default();
    state.phase = SnapshotPhase::Complete;

    assert_eq!(state.take_result(), Ok(vec![]));
}

#[test]
fn take_result_consumes_cameras_after_successful_extraction() {
    let mut state = SnapshotState::default();
    state.phase = SnapshotPhase::Complete;
    state.cameras = HashMap::from([(
        7,
        SnapshotCamera {
            object_serial: 42,
            name: "front".to_string(),
            supported_formats: vec![],
        },
    )]);

    assert_eq!(
        state.take_result(),
        Ok(vec![SnapshotCamera {
            object_serial: 42,
            name: "front".to_string(),
            supported_formats: vec![],
        }])
    );
    assert_eq!(state.take_result(), Ok(vec![]));
}

#[test]
fn take_result_returns_timeout_after_timeout_error_is_recorded() {
    let mut state = SnapshotState::default();
    state.error = check_timeout_error(&state);

    assert_eq!(
        state.take_result(),
        Err(SnapshotError::Unavailable(
            "PipeWire snapshot timed out".to_string()
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
fn check_timeout_error_returns_timeout_for_pending_snapshot() {
    let state = SnapshotState::default();

    assert_eq!(
        check_timeout_error(&state),
        Some(SnapshotError::Unavailable(
            "PipeWire snapshot timed out".to_string()
        ))
    );
}

#[test]
fn check_timeout_error_returns_none_for_completed_snapshot() {
    let mut state = SnapshotState::default();
    state.phase = SnapshotPhase::Complete;

    assert_eq!(check_timeout_error(&state), None);
}

#[test]
fn check_timeout_error_returns_none_for_existing_error() {
    let mut state = SnapshotState::default();
    state.error = Some(SnapshotError::Unavailable(
        "PipeWire core error: boom".to_string(),
    ));

    assert_eq!(check_timeout_error(&state), None);
}

#[test]
fn take_result_sorts_cameras_by_object_serial_before_returning() {
    let camera_b = node_global_factory(
        11,
        100,
        pw::types::ObjectType::Node,
        Some("Video/Source"),
        Some("rear"),
    );
    let camera_a = node_global_factory(
        7,
        50,
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
                object_serial: 100,
                name: "rear".to_string(),
                supported_formats: vec![],
            },
        ),
        (
            camera_a.id,
            SnapshotCamera {
                object_serial: 50,
                name: "front".to_string(),
                supported_formats: vec![],
            },
        ),
    ]);

    let cameras = state.take_result().unwrap();
    assert_eq!(cameras[0].object_serial, 50);
    assert_eq!(cameras[1].object_serial, 100);
}

#[test]
fn take_result_omits_removed_cameras() {
    let mut cameras = HashMap::from([
        (
            7,
            SnapshotCamera {
                object_serial: 42,
                name: "front".to_string(),
                supported_formats: vec![],
            },
        ),
        (
            11,
            SnapshotCamera {
                object_serial: 84,
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
    assert_eq!(cameras[0].object_serial, 84);
}
