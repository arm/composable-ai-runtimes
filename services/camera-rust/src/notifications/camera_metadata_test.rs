use super::camera_metadata::CameraMetadata;
use pipewire as pw;

#[test]
fn test_camera_metadata_from_global_object_uses_node_nick() {
    let props = pw::properties::properties! {
        "node.nick" => "front-camera"
    };
    let global = pw::registry::GlobalObject {
        id: 7,
        permissions: pw::permissions::PermissionFlags::all(),
        type_: pw::types::ObjectType::Node,
        version: 0,
        props: Some(props.as_ref()),
    };

    assert_eq!(
        CameraMetadata::from_global_object(&global),
        CameraMetadata {
            id: 7,
            name: "front-camera".to_string(),
        }
    );
}

#[test]
fn test_camera_metadata_from_global_object_defaults_missing_name() {
    let global = pw::registry::GlobalObject {
        id: 9,
        permissions: pw::permissions::PermissionFlags::all(),
        type_: pw::types::ObjectType::Node,
        version: 0,
        props: None,
    };

    assert_eq!(
        CameraMetadata::from_global_object(&global),
        CameraMetadata {
            id: 9,
            name: "unknown".to_string(),
        }
    );
}
