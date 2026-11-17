// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use super::device::DeviceType;
use super::helpers::{is_device_type, should_include_device};
use pipewire as pw;

fn node_global_factory(
    node_id: u32,
    type_: pw::types::ObjectType,
    media_class: Option<&str>,
) -> pw::registry::GlobalObject<pw::properties::PropertiesBox> {
    let props = media_class.map(|media_class| {
        pw::properties::properties! {
            *pw::keys::MEDIA_CLASS => media_class
        }
    });

    pw::registry::GlobalObject {
        id: node_id,
        permissions: pw::permissions::PermissionFlags::all(),
        type_,
        version: 0,
        props,
    }
}

#[test]
fn should_include_device_selects_only_requested_type() {
    for requested in [
        DeviceType::Camera,
        DeviceType::Microphone,
        DeviceType::Speaker,
    ] {
        for (media_class, actual) in [
            ("Video/Source", DeviceType::Camera),
            ("Audio/Source", DeviceType::Microphone),
            ("Audio/Sink", DeviceType::Speaker),
        ] {
            let global = node_global_factory(10, pw::types::ObjectType::Node, Some(media_class));
            assert_eq!(
                should_include_device(&global, Some(requested)),
                actual == requested,
                "media class: {media_class}, filter: {requested:?}"
            );
        }
    }
}

#[test]
fn should_include_device_without_type_accepts_all_supported_types() {
    for media_class in ["Video/Source", "Audio/Source", "Audio/Sink"] {
        let global = node_global_factory(10, pw::types::ObjectType::Node, Some(media_class));
        assert!(
            should_include_device(&global, None),
            "media class: {media_class}"
        );
    }
}

#[test]
fn should_include_device_without_type_rejects_unsupported_globals() {
    for (object_type, media_class) in [
        (pw::types::ObjectType::Node, Some("Stream/Output/Video")),
        (pw::types::ObjectType::Node, None),
        (pw::types::ObjectType::Link, Some("Video/Source")),
        (pw::types::ObjectType::Link, Some("Audio/Source")),
        (pw::types::ObjectType::Link, Some("Audio/Sink")),
    ] {
        let global = node_global_factory(10, object_type, media_class);
        assert!(
            !should_include_device(&global, None),
            "media class: {media_class:?}"
        );
    }
}

#[test]
fn is_device_type_matches_requested_media_class() {
    for (media_class, device_type, expected) in [
        ("Video/Source", DeviceType::Camera, true),
        ("Audio/Source", DeviceType::Camera, false),
        ("Audio/Source", DeviceType::Microphone, true),
        ("Video/Source", DeviceType::Microphone, false),
    ] {
        let global = node_global_factory(10, pw::types::ObjectType::Node, Some(media_class));
        assert_eq!(
            is_device_type(&global, &device_type),
            expected,
            "media class: {media_class}, device type: {device_type:?}"
        );
    }
}

#[test]
fn is_device_type_requires_node_object() {
    let global = node_global_factory(24, pw::types::ObjectType::Link, Some("Video/Source"));

    assert!(!is_device_type(&global, &DeviceType::Camera));
}

#[test]
fn is_device_type_requires_media_class_property() {
    for (case, props) in [
        ("no properties", None),
        (
            "no media class",
            Some(pw::properties::properties! {
                *pw::keys::NODE_NAME => "camera"
            }),
        ),
    ] {
        let mut global = node_global_factory(11, pw::types::ObjectType::Node, None);
        global.props = props;
        assert!(!is_device_type(&global, &DeviceType::Camera), "{case}");
    }
}
