use std::fmt;

#[derive(Debug, PartialEq, Eq)]
pub struct CameraMetadata {
    pub id: u32,
    pub name: String,
}

#[derive(Debug)]
pub enum SnapshotError {
    Unavailable(String),
}

impl std::fmt::Display for SnapshotError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Unavailable(message) => f.write_str(message),
        }
    }
}

impl std::error::Error for SnapshotError {}

pub fn list_camera_metadata() -> Result<Vec<CameraMetadata>, SnapshotError> {
    Ok(vec![])
}
