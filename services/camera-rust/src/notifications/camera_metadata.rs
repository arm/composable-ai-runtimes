use pipewire::{registry::GlobalObject, spa::utils::dict::DictRef};
use serde::Serialize;

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub struct CameraMetadata {
    pub id: u32,
    pub name: String,
}

impl CameraMetadata {
    pub fn from_global_object(global_obj: &GlobalObject<&DictRef>) -> Self {
        Self {
            id: global_obj.id,
            name: global_obj
                .props
                .and_then(|props| props.get("node.nick").map(str::to_owned))
                .unwrap_or_else(|| "unknown".to_string()),
        }
    }
}
