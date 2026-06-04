use pipewire::{self as pw, registry::GlobalObject, spa::utils::dict::DictRef};
use thiserror::Error;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CameraMetadata {
    pub node_id: u32,
    pub object_serial: u64,
    pub name: String,
}

#[derive(Debug, Error, Eq, PartialEq)]
pub enum CameraMetadataError {
    #[error("camera node missing object serial")]
    MissingObjectSerial,
    #[error("camera node has invalid object serial: {0}")]
    InvalidObjectSerial(String),
}

impl CameraMetadata {
    pub fn try_from_global_object<P>(
        global_obj: &GlobalObject<P>,
    ) -> Result<Self, CameraMetadataError>
    where
        P: AsRef<DictRef>,
    {
        Ok(Self {
            node_id: global_obj.id,
            object_serial: get_object_serial(global_obj)?,
            name: global_obj
                .props
                .as_ref()
                .and_then(|props| {
                    props
                        .as_ref()
                        .get(&pw::keys::NODE_NICK)
                        .or_else(|| props.as_ref().get(&pw::keys::NODE_DESCRIPTION))
                        .or_else(|| props.as_ref().get(&pw::keys::NODE_NAME))
                })
                .unwrap_or("")
                .to_string(),
        })
    }
}

fn get_object_serial<P>(global_obj: &GlobalObject<P>) -> Result<u64, CameraMetadataError>
where
    P: AsRef<DictRef>,
{
    let serial = global_obj
        .props
        .as_ref()
        .and_then(|props| props.as_ref().get(&pw::keys::OBJECT_SERIAL))
        .ok_or(CameraMetadataError::MissingObjectSerial)?;

    serial
        .parse()
        .map_err(|_| CameraMetadataError::InvalidObjectSerial(serial.to_string()))
}
