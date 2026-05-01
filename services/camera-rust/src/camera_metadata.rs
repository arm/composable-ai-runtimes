use pipewire::{self as pw, registry::GlobalObject, spa::utils::dict::DictRef};
use serde::Serialize;

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub struct CameraMetadata {
    pub id: u32,
    pub name: String,
}

impl CameraMetadata {
    pub fn from_global_object<P>(global_obj: &GlobalObject<P>) -> Self
    where
        P: AsRef<DictRef>,
    {
        Self {
            id: global_obj.id,
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
        }
    }
}
