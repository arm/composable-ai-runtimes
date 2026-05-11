use super::camera_metadata::CameraMetadata;
use pipewire as pw;

fn node_global_factory(
    id: u32,
    props: Option<pw::properties::PropertiesBox>,
) -> pw::registry::GlobalObject<pw::properties::PropertiesBox> {
    pw::registry::GlobalObject {
        id,
        permissions: pw::permissions::PermissionFlags::all(),
        type_: pw::types::ObjectType::Node,
        version: 0,
        props,
    }
}

#[test]
fn test_camera_metadata_from_global_object_uses_node_nick() {
    let props = pw::properties::properties! {
        "node.nick" => "front-camera"
    };
    let global = node_global_factory(7, Some(props));

    assert_eq!(
        CameraMetadata::from_global_object(&global),
        CameraMetadata {
            id: 7,
            name: "front-camera".to_string(),
        }
    );
}

#[test]
fn test_camera_metadata_from_global_object_falls_back_to_node_description() {
    let props = pw::properties::properties! {
        "node.description" => "Front Camera Description"
    };
    let global = node_global_factory(9, Some(props));

    assert_eq!(
        CameraMetadata::from_global_object(&global),
        CameraMetadata {
            id: 9,
            name: "Front Camera Description".to_string(),
        }
    );
}

#[test]
fn test_camera_metadata_from_global_object_falls_back_to_node_name() {
    let props = pw::properties::properties! {
        "node.name" => "front-camera-device"
    };
    let global = node_global_factory(11, Some(props));

    assert_eq!(
        CameraMetadata::from_global_object(&global),
        CameraMetadata {
            id: 11,
            name: "front-camera-device".to_string(),
        }
    );
}

#[test]
fn test_camera_metadata_from_global_object_defaults_missing_name() {
    let global = node_global_factory(13, None);

    assert_eq!(
        CameraMetadata::from_global_object(&global),
        CameraMetadata {
            id: 13,
            name: "".to_string(),
        }
    );
}
