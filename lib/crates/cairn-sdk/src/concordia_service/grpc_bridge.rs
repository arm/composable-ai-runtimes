use tonic::Request;
use tonic::transport::Channel;

use super::service::{
    AudioOutput, BrickType, ConcordiaError, Detection, ObjectDetectionOutput, RunBrickOptions,
    RunBrickOutput,
};

pub(super) mod concordia {
    tonic::include_proto!("cairn.concordia.inference.v1");
}

use concordia::RunBrickRequest;
use concordia::inference_service_client::InferenceServiceClient;

pub(super) struct GrpcBridge {
    client: InferenceServiceClient<Channel>,
}

impl GrpcBridge {
    pub(super) async fn connect(endpoint: &str) -> Result<Self, ConcordiaError> {
        let client = InferenceServiceClient::connect(endpoint.to_string())
            .await
            .map_err(|error| ConcordiaError::GrpcError {
                message: error.to_string(),
            })?;

        Ok(Self { client })
    }

    pub(super) async fn run_brick(
        &mut self,
        brick_type: BrickType,
        brick_variant: String,
        input: RunBrickOptions,
    ) -> Result<RunBrickOutput, ConcordiaError> {
        let request = RunBrickRequest {
            brick: Some(concordia::BrickSpec {
                r#type: map_brick_type_to_proto(brick_type),
                brick_variant,
            }),
            input: Some(match input {
                RunBrickOptions::Text { text } => {
                    concordia::run_brick_request::Input::Text(concordia::TextInput { text })
                }
                RunBrickOptions::Image { image_bytes } => {
                    concordia::run_brick_request::Input::Image(concordia::ImageInput {
                        image_bytes,
                    })
                }
            }),
        };

        let response = self
            .client
            .run_brick(Request::new(request))
            .await?
            .into_inner();

        match response.output {
            Some(concordia::run_brick_response::Output::Audio(audio)) => {
                Ok(RunBrickOutput::Audio(AudioOutput {
                    left_channel: audio.left_channel,
                    right_channel: audio.right_channel,
                }))
            }
            Some(concordia::run_brick_response::Output::Detections(detections)) => {
                Ok(RunBrickOutput::Detections(ObjectDetectionOutput {
                    detections: detections
                        .detections
                        .into_iter()
                        .map(|d| Detection {
                            r#box: d.r#box,
                            class_id: d.class_id,
                            score: d.score,
                            class_name: d.class_name,
                        })
                        .collect(),
                }))
            }
            None => Err(ConcordiaError::ServiceError {
                message: "run_brick returned response without output".to_string(),
            }),
        }
    }
}

impl From<tonic::Status> for ConcordiaError {
    fn from(status: tonic::Status) -> Self {
        ConcordiaError::ServiceError {
            message: status.message().to_string(),
        }
    }
}

fn map_brick_type_to_proto(value: BrickType) -> i32 {
    match value {
        BrickType::Unspecified => concordia::BrickType::Unspecified as i32,
        BrickType::Tts => concordia::BrickType::Tts as i32,
        BrickType::ObjectDetection => concordia::BrickType::ObjectDetection as i32,
    }
}
