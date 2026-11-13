// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use super::device::{Device, DeviceError, DeviceType};
use pipewire as pw;

#[test]
fn test_device_try_from_global_object_rejects_unsupported_nodes() {
    let valid_props = pw::properties::properties! {
        *pw::keys::OBJECT_SERIAL => "42",
        *pw::keys::MEDIA_CLASS => "Video/Source"
    };
    let mut non_node = node_global_factory(7, Some(valid_props));
    non_node.type_ = pw::types::ObjectType::Link;
    let unsupported_props = pw::properties::properties! {
        *pw::keys::OBJECT_SERIAL => "42",
        *pw::keys::MEDIA_CLASS => "Audio/Source"
    };
    let missing_class_props = pw::properties::properties! { *pw::keys::OBJECT_SERIAL => "42" };

    for global in [
        non_node,
        node_global_factory(7, Some(unsupported_props)),
        node_global_factory(7, Some(missing_class_props)),
        node_global_factory(7, None),
    ] {
        assert_eq!(
            Device::try_from_global_object(&global),
            Err(DeviceError::UnsupportedNode)
        );
    }
}

fn node_global_factory(
    node_id: u32,
    props: Option<pw::properties::PropertiesBox>,
) -> pw::registry::GlobalObject<pw::properties::PropertiesBox> {
    pw::registry::GlobalObject {
        id: node_id,
        permissions: pw::permissions::PermissionFlags::all(),
        type_: pw::types::ObjectType::Node,
        version: 0,
        props,
    }
}

#[test]
fn test_device_try_from_global_object_uses_node_nick() {
    let props = pw::properties::properties! {
        *pw::keys::MEDIA_CLASS => "Video/Source",
        *pw::keys::OBJECT_SERIAL => "42",
        *pw::keys::NODE_NICK => "front-camera"
    };
    let global = node_global_factory(7, Some(props));

    assert_eq!(
        Device::try_from_global_object(&global),
        Ok(Device {
            node_id: 7,
            object_serial: 42,
            name: "front-camera".to_string(),
            device_type: DeviceType::Camera,
        })
    );
}

#[test]
fn test_device_try_from_global_object_falls_back_to_node_description() {
    let props = pw::properties::properties! {
        *pw::keys::MEDIA_CLASS => "Video/Source",
        *pw::keys::OBJECT_SERIAL => "43",
        *pw::keys::NODE_DESCRIPTION => "Front Camera Description"
    };
    let global = node_global_factory(9, Some(props));

    assert_eq!(
        Device::try_from_global_object(&global),
        Ok(Device {
            node_id: 9,
            object_serial: 43,
            name: "Front Camera Description".to_string(),
            device_type: DeviceType::Camera,
        })
    );
}

#[test]
fn test_device_try_from_global_object_falls_back_to_node_name() {
    let props = pw::properties::properties! {
        *pw::keys::MEDIA_CLASS => "Video/Source",
        *pw::keys::OBJECT_SERIAL => "44",
        "node.name" => "front-camera-device"
    };
    let global = node_global_factory(11, Some(props));

    assert_eq!(
        Device::try_from_global_object(&global),
        Ok(Device {
            node_id: 11,
            object_serial: 44,
            name: "front-camera-device".to_string(),
            device_type: DeviceType::Camera,
        })
    );
}

#[test]
fn test_device_try_from_global_object_defaults_missing_name() {
    let props = pw::properties::properties! {
        *pw::keys::MEDIA_CLASS => "Video/Source",
        *pw::keys::OBJECT_SERIAL => "45"
    };
    let global = node_global_factory(13, Some(props));

    assert_eq!(
        Device::try_from_global_object(&global),
        Ok(Device {
            node_id: 13,
            object_serial: 45,
            name: "".to_string(),
            device_type: DeviceType::Camera,
        })
    );
}

#[test]
fn test_device_try_from_global_object_rejects_missing_serial() {
    let props = pw::properties::properties! {
        *pw::keys::MEDIA_CLASS => "Video/Source",
        "node.name" => "front-camera-device"
    };
    let global = node_global_factory(11, Some(props));

    assert_eq!(
        Device::try_from_global_object(&global),
        Err(DeviceError::MissingObjectSerial)
    );
}

#[test]
fn test_device_try_from_global_object_rejects_invalid_serial() {
    let props = pw::properties::properties! {
        *pw::keys::MEDIA_CLASS => "Video/Source",
        *pw::keys::OBJECT_SERIAL => "not-a-number",
        "node.name" => "front-camera-device"
    };
    let global = node_global_factory(11, Some(props));

    assert_eq!(
        Device::try_from_global_object(&global),
        Err(DeviceError::InvalidObjectSerial("not-a-number".to_string()))
    );
}
