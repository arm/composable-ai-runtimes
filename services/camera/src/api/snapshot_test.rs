// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use super::snapshot::{
    SnapshotCamera, SnapshotError, SnapshotState, append_camera, camera_lookup_error,
    is_pending_sync_complete,
};
use pipewire as pw;
use std::collections::HashMap;

#[test]
fn snapshot_error_displays_message() {
    let error = SnapshotError::Unavailable("pipewire unavailable".to_string());

    assert_eq!(error.to_string(), "pipewire unavailable");
}

#[test]
fn camera_lookup_error_returns_unavailable_for_bind_failure() {
    let error = camera_lookup_error(52, Some("bind failed".to_string()));

    assert_eq!(
        error,
        SnapshotError::Unavailable(
            "failed to bind camera 52 PipeWire node: bind failed".to_string()
        )
    );
}

#[test]
fn camera_lookup_error_returns_not_found_when_camera_is_absent() {
    let error = camera_lookup_error(52, None);

    assert_eq!(error, SnapshotError::NotFound(52));
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
fn append_camera_records_camera_node() {
    let mut cameras = HashMap::new();
    let camera = node_global_factory(
        7,
        42,
        pw::types::ObjectType::Node,
        Some("Video/Source"),
        Some("front"),
    );

    append_camera(&mut cameras, &camera);

    assert_eq!(
        cameras.get(&7),
        Some(&SnapshotCamera {
            object_serial: 42,
            name: "front".to_string(),
        })
    );
    assert_eq!(cameras.len(), 1);
}

#[test]
fn append_camera_ignores_camera_nodes_without_serial() {
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

    append_camera(&mut cameras, &camera);

    assert!(cameras.is_empty());
}

#[test]
fn append_camera_ignores_camera_nodes_with_invalid_serial() {
    let mut cameras = HashMap::new();
    let camera = node_global_factory(
        7,
        "not-a-number",
        pw::types::ObjectType::Node,
        Some("Video/Source"),
        Some("front"),
    );

    append_camera(&mut cameras, &camera);

    assert!(cameras.is_empty());
}

#[test]
fn append_camera_replaces_existing_camera_for_same_node_id() {
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

    append_camera(&mut cameras, &initial_camera);
    append_camera(&mut cameras, &replacement_camera);

    assert_eq!(cameras.len(), 1);
    assert_eq!(
        cameras.get(&7),
        Some(&SnapshotCamera {
            object_serial: 43,
            name: "front-updated".to_string(),
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
fn take_cameras_returns_empty_vec_for_empty_snapshot() {
    let mut state = SnapshotState::default();

    assert_eq!(state.take_cameras(), vec![]);
}

#[test]
fn take_cameras_consumes_cameras_after_successful_extraction() {
    let mut state = SnapshotState {
        cameras: HashMap::from([(
            7,
            SnapshotCamera {
                object_serial: 42,
                name: "front".to_string(),
            },
        )]),
    };

    assert_eq!(
        state.take_cameras(),
        vec![SnapshotCamera {
            object_serial: 42,
            name: "front".to_string(),
        }]
    );
    assert_eq!(state.take_cameras(), vec![]);
}

#[test]
fn take_cameras_sorts_cameras_by_object_serial_before_returning() {
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

    let mut state = SnapshotState {
        cameras: HashMap::from([
            (
                camera_b.id,
                SnapshotCamera {
                    object_serial: 100,
                    name: "rear".to_string(),
                },
            ),
            (
                camera_a.id,
                SnapshotCamera {
                    object_serial: 50,
                    name: "front".to_string(),
                },
            ),
        ]),
    };

    let cameras = state.take_cameras();
    assert_eq!(cameras[0].object_serial, 50);
    assert_eq!(cameras[1].object_serial, 100);
}
