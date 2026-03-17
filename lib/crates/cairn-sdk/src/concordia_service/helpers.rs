use super::service::{BrickType, ConcordiaError};

pub(crate) fn parse_brick_type(value: &str) -> Result<BrickType, ConcordiaError> {
    match value.trim().to_ascii_lowercase().as_str() {
        "unspecified" => Ok(BrickType::Unspecified),
        "tts" | "text_to_speech" | "text-to-speech" => Ok(BrickType::Tts),
        "object_detection" | "object-detection" => Ok(BrickType::ObjectDetection),
        _ => Err(ConcordiaError::ServiceError {
            message: format!(
                "unsupported brick_type '{value}', expected one of: unspecified, tts, text_to_speech, object_detection"
            ),
        }),
    }
}

pub(crate) fn parse_brick_variant(value: &str) -> Result<String, ConcordiaError> {
    match value.trim().to_ascii_lowercase().as_str() {
        "kokoro" => Ok("kokoro".to_string()),
        "kittentts" => Ok("kittentts".to_string()),
        "yolo" => Ok("yolo".to_string()),
        _ => Err(ConcordiaError::ServiceError {
            message: format!(
                "unsupported brick_variant '{value}', expected one of: kokoro, kittentts, yolo"
            ),
        }),
    }
}
