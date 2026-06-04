use super::camera_metadata::{CameraMetadata, CameraMetadataError};
use pipewire as pw;

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
fn test_camera_metadata_try_from_global_object_uses_node_nick() {
    let props = pw::properties::properties! {
        *pw::keys::OBJECT_SERIAL => "42",
        "node.nick" => "front-camera"
    };
    let global = node_global_factory(7, Some(props));

    assert_eq!(
        CameraMetadata::try_from_global_object(&global),
        Ok(CameraMetadata {
            node_id: 7,
            object_serial: 42,
            name: "front-camera".to_string(),
        })
    );
}

#[test]
fn test_camera_metadata_try_from_global_object_falls_back_to_node_description() {
    let props = pw::properties::properties! {
        *pw::keys::OBJECT_SERIAL => "43",
        "node.description" => "Front Camera Description"
    };
    let global = node_global_factory(9, Some(props));

    assert_eq!(
        CameraMetadata::try_from_global_object(&global),
        Ok(CameraMetadata {
            node_id: 9,
            object_serial: 43,
            name: "Front Camera Description".to_string(),
        })
    );
}

#[test]
fn test_camera_metadata_try_from_global_object_falls_back_to_node_name() {
    let props = pw::properties::properties! {
        *pw::keys::OBJECT_SERIAL => "44",
        "node.name" => "front-camera-device"
    };
    let global = node_global_factory(11, Some(props));

    assert_eq!(
        CameraMetadata::try_from_global_object(&global),
        Ok(CameraMetadata {
            node_id: 11,
            object_serial: 44,
            name: "front-camera-device".to_string(),
        })
    );
}

#[test]
fn test_camera_metadata_try_from_global_object_defaults_missing_name() {
    let props = pw::properties::properties! {
        *pw::keys::OBJECT_SERIAL => "45"
    };
    let global = node_global_factory(13, Some(props));

    assert_eq!(
        CameraMetadata::try_from_global_object(&global),
        Ok(CameraMetadata {
            node_id: 13,
            object_serial: 45,
            name: "".to_string(),
        })
    );
}

#[test]
fn test_camera_metadata_try_from_global_object_rejects_missing_serial() {
    let props = pw::properties::properties! {
        "node.name" => "front-camera-device"
    };
    let global = node_global_factory(11, Some(props));

    assert_eq!(
        CameraMetadata::try_from_global_object(&global),
        Err(CameraMetadataError::MissingObjectSerial)
    );
}

#[test]
fn test_camera_metadata_try_from_global_object_rejects_invalid_serial() {
    let props = pw::properties::properties! {
        *pw::keys::OBJECT_SERIAL => "not-a-number",
        "node.name" => "front-camera-device"
    };
    let global = node_global_factory(11, Some(props));

    assert_eq!(
        CameraMetadata::try_from_global_object(&global),
        Err(CameraMetadataError::InvalidObjectSerial(
            "not-a-number".to_string()
        ))
    );
}
