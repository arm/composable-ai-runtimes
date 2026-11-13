// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use super::snapshot::{
    SnapshotError, SnapshotState, append_device, camera_lookup_error, is_pending_sync_complete,
};
use crate::device::{Device, DeviceType};
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
fn append_device_records_camera_node() {
    let mut devices = HashMap::new();
    let camera = node_global_factory(
        7,
        42,
        pw::types::ObjectType::Node,
        Some("Video/Source"),
        Some("front"),
    );

    append_device(&mut devices, &camera);

    assert_eq!(
        devices.get(&7),
        Some(&Device {
            node_id: 7,
            object_serial: 42,
            name: "front".to_string(),
            device_type: DeviceType::Camera,
        })
    );
    assert_eq!(devices.len(), 1);
}

#[test]
fn append_device_ignores_camera_nodes_without_serial() {
    let mut devices = HashMap::new();
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

    append_device(&mut devices, &camera);

    assert!(devices.is_empty());
}

#[test]
fn append_device_ignores_camera_nodes_with_invalid_serial() {
    let mut devices = HashMap::new();
    let camera = node_global_factory(
        7,
        "not-a-number",
        pw::types::ObjectType::Node,
        Some("Video/Source"),
        Some("front"),
    );

    append_device(&mut devices, &camera);

    assert!(devices.is_empty());
}

#[test]
fn append_device_replaces_existing_camera_for_same_node_id() {
    let mut devices = HashMap::new();
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

    append_device(&mut devices, &initial_camera);
    append_device(&mut devices, &replacement_camera);

    assert_eq!(devices.len(), 1);
    assert_eq!(
        devices.get(&7),
        Some(&Device {
            node_id: 7,
            object_serial: 43,
            name: "front-updated".to_string(),
            device_type: DeviceType::Camera,
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
fn take_devices_returns_empty_vec_for_empty_snapshot() {
    let mut state = SnapshotState::default();

    assert_eq!(state.take_devices(), vec![]);
}

#[test]
fn take_devices_consumes_devices_after_successful_extraction() {
    let mut state = SnapshotState {
        devices: HashMap::from([(
            7,
            Device {
                node_id: 7,
                object_serial: 42,
                name: "front".to_string(),
                device_type: DeviceType::Camera,
            },
        )]),
    };

    assert_eq!(
        state.take_devices(),
        vec![Device {
            node_id: 7,
            object_serial: 42,
            name: "front".to_string(),
            device_type: DeviceType::Camera,
        }]
    );
    assert_eq!(state.take_devices(), vec![]);
}

#[test]
fn take_devices_sorts_devices_by_object_serial_before_returning() {
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
        devices: HashMap::from([
            (
                camera_b.id,
                Device {
                    node_id: camera_b.id,
                    object_serial: 100,
                    name: "rear".to_string(),
                    device_type: DeviceType::Camera,
                },
            ),
            (
                camera_a.id,
                Device {
                    node_id: camera_a.id,
                    object_serial: 50,
                    name: "front".to_string(),
                    device_type: DeviceType::Camera,
                },
            ),
        ]),
    };

    let devices = state.take_devices();
    assert_eq!(devices[0].object_serial, 50);
    assert_eq!(devices[1].object_serial, 100);
}
