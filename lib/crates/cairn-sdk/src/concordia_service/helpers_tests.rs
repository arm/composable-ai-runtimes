#[cfg(test)]
mod tests {
    use super::super::helpers::{parse_brick_type, parse_brick_variant};
    use super::super::{BrickType, ConcordiaError};

    #[test]
    fn parse_brick_type_accepts_supported_aliases() {
        assert_eq!(parse_brick_type("tts"), Ok(BrickType::Tts));
        assert_eq!(parse_brick_type("text_to_speech"), Ok(BrickType::Tts));
        assert_eq!(
            parse_brick_type("object-detection"),
            Ok(BrickType::ObjectDetection)
        );
    }

    #[test]
    fn parse_brick_type_rejects_unsupported_values() {
        assert_eq!(
            parse_brick_type("not-a-brick"),
            Err(ConcordiaError::ServiceError {
                message: "unsupported brick_type 'not-a-brick', expected one of: unspecified, tts, text_to_speech, object_detection".to_string(),
            })
        );
    }

    #[test]
    fn parse_brick_variant_accepts_supported_values() {
        assert_eq!(parse_brick_variant(" kokoro "), Ok("kokoro".to_string()));
        assert_eq!(parse_brick_variant("YOLO"), Ok("yolo".to_string()));
        assert_eq!(
            parse_brick_variant("KittenTTS"),
            Ok("kittentts".to_string())
        );
    }

    #[test]
    fn parse_brick_variant_rejects_unsupported_values() {
        assert_eq!(
            parse_brick_variant("custom"),
            Err(ConcordiaError::ServiceError {
                message:
                    "unsupported brick_variant 'custom', expected one of: kokoro, kittentts, yolo"
                        .to_string(),
            })
        );
        assert_eq!(
            parse_brick_variant("   "),
            Err(ConcordiaError::ServiceError {
                message:
                    "unsupported brick_variant '   ', expected one of: kokoro, kittentts, yolo"
                        .to_string(),
            })
        );
    }
}
