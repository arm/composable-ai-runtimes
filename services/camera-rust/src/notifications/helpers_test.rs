use crate::helpers::VIDEO_SOURCE_MEDIA_CLASS;
use crate::helpers::is_camera_node;
use pipewire as pw;

fn node_global_factory(
    id: u32,
    type_: pw::types::ObjectType,
    media_class: Option<&str>,
) -> pw::registry::GlobalObject<pw::properties::PropertiesBox> {
    let props = media_class.map(|media_class| {
        pw::properties::properties! {
            *pw::keys::MEDIA_CLASS => media_class
        }
    });

    pw::registry::GlobalObject {
        id,
        permissions: pw::permissions::PermissionFlags::all(),
        type_,
        version: 0,
        props,
    }
}

#[test]
fn test_is_camera_node_detects_video_source_nodes() {
    let global = node_global_factory(
        10,
        pw::types::ObjectType::Node,
        Some(VIDEO_SOURCE_MEDIA_CLASS),
    );

    assert!(is_camera_node(&global));
}

#[test]
fn test_is_camera_node_rejects_non_camera_media_class() {
    let global = node_global_factory(42, pw::types::ObjectType::Node, Some("Audio/Source"));

    assert!(!is_camera_node(&global));
}

#[test]
fn test_is_camera_node_rejects_non_node_globals() {
    let global = node_global_factory(
        24,
        pw::types::ObjectType::Link,
        Some(VIDEO_SOURCE_MEDIA_CLASS),
    );

    assert!(!is_camera_node(&global));
}

#[test]
fn test_is_camera_node_rejects_missing_media_class() {
    let global = node_global_factory(11, pw::types::ObjectType::Node, None);

    assert!(!is_camera_node(&global));
}
