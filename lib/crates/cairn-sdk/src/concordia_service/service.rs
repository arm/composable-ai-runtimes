use super::grpc_bridge::GrpcBridge;
use super::helpers::{parse_brick_type, parse_brick_variant};
use std::error::Error;
use std::fmt::{Display, Formatter};

const DEFAULT_CONCORDIA_SERVICE_ENDPOINT: &str = "http://127.0.0.1:50052";

#[derive(Debug, PartialEq)]
pub enum BrickType {
    Unspecified,
    Tts,
    ObjectDetection,
}

#[derive(Debug, PartialEq)]
pub enum RunBrickOptions {
    Text { text: String },
    Image { image_bytes: Vec<u8> },
}

#[derive(Debug, PartialEq)]
pub struct Detection {
    pub r#box: Vec<f32>,
    pub class_id: i32,
    pub score: f32,
    pub class_name: String,
}

#[derive(Debug, PartialEq)]
pub struct ObjectDetectionOutput {
    pub detections: Vec<Detection>,
}

#[derive(Debug, PartialEq)]
pub struct AudioOutput {
    pub left_channel: Vec<f32>,
    pub right_channel: Vec<f32>,
}

#[derive(Debug, PartialEq)]
pub enum RunBrickOutput {
    Audio(AudioOutput),
    Detections(ObjectDetectionOutput),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ConcordiaError {
    GrpcError { message: String },
    ServiceError { message: String },
}

impl Display for ConcordiaError {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        match self {
            ConcordiaError::GrpcError { message } => {
                write!(
                    f,
                    "gRPC error while handling concordia inference call: {message}"
                )
            }
            ConcordiaError::ServiceError { message } => {
                write!(
                    f,
                    "concordia service error while handling inference: {message}"
                )
            }
        }
    }
}

impl Error for ConcordiaError {}

pub struct ConcordiaService {
    pub(super) grpc_bridge: GrpcBridge,
}

impl ConcordiaService {
    pub async fn new(endpoint: Option<String>) -> Result<Self, ConcordiaError> {
        let endpoint = endpoint.unwrap_or_else(|| DEFAULT_CONCORDIA_SERVICE_ENDPOINT.to_string());

        Ok(Self {
            grpc_bridge: GrpcBridge::connect(&endpoint).await?,
        })
    }

    pub async fn run_brick(
        &mut self,
        brick_type: &str,
        brick_variant: &str,
        options: RunBrickOptions,
    ) -> Result<RunBrickOutput, ConcordiaError> {
        let brick_type = parse_brick_type(brick_type)?;
        let brick_variant = parse_brick_variant(brick_variant)?;
        self.grpc_bridge
            .run_brick(brick_type, brick_variant, options)
            .await
    }
}
