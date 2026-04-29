use super::helpers::FibonacciBackoff;
use super::helpers::VIDEO_SOURCE_MEDIA_CLASS;
use super::helpers::is_camera_node;
use pipewire as pw;
use std::time::Duration;

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

#[test]
fn test_fibonacci_backoff_caps_delay() {
    let mut backoff = FibonacciBackoff::new(Duration::from_secs(1), Duration::from_secs(5));
    let delays: Vec<Duration> = (0..8).map(|_| backoff.next_delay()).collect();

    assert_eq!(
        delays,
        vec![
            Duration::from_secs(1),
            Duration::from_secs(1),
            Duration::from_secs(2),
            Duration::from_secs(3),
            Duration::from_secs(5),
            Duration::from_secs(5),
            Duration::from_secs(5),
            Duration::from_secs(5),
        ]
    );
}
