use tonic::Request;
use tonic::transport::Channel;

mod concordia {
    tonic::include_proto!("cairn.concordia.inference.v1");
}

use concordia::inference_service_client::InferenceServiceClient;
use concordia::{ListBricksRequest, RunBrickRequest};

#[derive(Debug, PartialEq)]
pub enum BrickType {
    Unspecified,
    Tts,
    ObjectDetection,
}

#[derive(Debug, PartialEq)]
pub struct BrickSpec {
    pub brick_type: BrickType,
    pub brick_variant: String,
}

#[derive(Debug, PartialEq)]
pub enum RunBrickInput {
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
pub struct ObjDetectionOutput {
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
    Detections(ObjDetectionOutput),
}

pub struct InferenceService {
    client: InferenceServiceClient<Channel>,
}

impl InferenceService {
    pub async fn new(endpoint: String) -> Result<Self, tonic::Status> {
        let client = InferenceServiceClient::connect(endpoint)
            .await
            .map_err(|e| tonic::Status::unavailable(e.to_string()))?;

        Ok(Self { client })
    }

    // we have to do a mutable borrow of the client due to the way tonic's generated client works
    pub async fn list_bricks(&mut self) -> Result<Vec<BrickSpec>, tonic::Status> {
        let response = self
            .client
            .list_bricks(Request::new(ListBricksRequest {}))
            .await?
            .into_inner();

        Ok(response.bricks.into_iter().map(map_brick_spec).collect())
    }

    pub async fn run_brick(
        &mut self,
        brick: BrickSpec,
        input: RunBrickInput,
    ) -> Result<RunBrickOutput, tonic::Status> {
        let request = RunBrickRequest {
            brick: Some(concordia::BrickSpec {
                r#type: map_brick_type_to_proto(brick.brick_type),
                brick_variant: brick.brick_variant,
            }),
            input: Some(match input {
                RunBrickInput::Text { text } => {
                    concordia::run_brick_request::Input::Text(concordia::TextInput { text })
                }
                RunBrickInput::Image { image_bytes } => {
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
                Ok(RunBrickOutput::Detections(ObjDetectionOutput {
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
            None => Err(tonic::Status::internal(
                "run_brick returned response without output oneof",
            )),
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

fn map_brick_type_from_proto(raw: i32) -> BrickType {
    match concordia::BrickType::try_from(raw) {
        Ok(concordia::BrickType::Unspecified) => BrickType::Unspecified,
        Ok(concordia::BrickType::Tts) => BrickType::Tts,
        Ok(concordia::BrickType::ObjectDetection) => BrickType::ObjectDetection,
        Err(_) => BrickType::Unspecified,
    }
}

fn map_brick_spec(proto_brick: concordia::BrickSpec) -> BrickSpec {
    BrickSpec {
        brick_type: map_brick_type_from_proto(proto_brick.r#type),
        brick_variant: proto_brick.brick_variant,
    }
}

#[cfg(test)]
mod tests {
    use super::concordia::inference_service_server::{
        InferenceService as InferenceServiceTrait, InferenceServiceServer,
    };
    use super::concordia::{
        AudioOutput as ProtoAudioOutput, BrickSpec as ProtoBrickSpec, Detection as ProtoDetection,
        ListBricksRequest, ListBricksResponse, ObjDetectionOutput as ProtoObjDetectionOutput,
        RunBrickRequest, RunBrickResponse,
    };
    use super::*;
    use tokio::sync::oneshot;
    use tokio::task::JoinHandle;
    use tonic::transport::Server;
    use tonic::transport::server::TcpIncoming;
    use tonic::{Response, Status};

    struct MockInferenceService;

    #[tonic::async_trait]
    impl InferenceServiceTrait for MockInferenceService {
        async fn list_bricks(
            &self,
            _request: Request<ListBricksRequest>,
        ) -> Result<Response<ListBricksResponse>, Status> {
            Ok(Response::new(ListBricksResponse {
                bricks: vec![
                    ProtoBrickSpec {
                        r#type: super::concordia::BrickType::Tts as i32,
                        brick_variant: "kokoro".to_string(),
                    },
                    ProtoBrickSpec {
                        r#type: super::concordia::BrickType::ObjectDetection as i32,
                        brick_variant: "yolo".to_string(),
                    },
                ],
            }))
        }

        async fn run_brick(
            &self,
            request: Request<RunBrickRequest>,
        ) -> Result<Response<RunBrickResponse>, Status> {
            let brick = request
                .into_inner()
                .brick
                .ok_or_else(|| Status::invalid_argument("brick is required"))?;

            match brick.brick_variant.as_str() {
                "kokoro" => Ok(Response::new(RunBrickResponse {
                    output: Some(super::concordia::run_brick_response::Output::Audio(
                        ProtoAudioOutput {
                            left_channel: vec![0.1, 0.2],
                            right_channel: vec![0.3, 0.4],
                        },
                    )),
                })),
                "yolo" => Ok(Response::new(RunBrickResponse {
                    output: Some(super::concordia::run_brick_response::Output::Detections(
                        ProtoObjDetectionOutput {
                            detections: vec![ProtoDetection {
                                r#box: vec![0.1, 0.2, 0.3, 0.4],
                                class_id: 7,
                                score: 0.9,
                                class_name: "person".to_string(),
                            }],
                        },
                    )),
                })),
                "missing" => Ok(Response::new(RunBrickResponse { output: None })),
                _ => Err(Status::invalid_argument("unsupported variant")),
            }
        }
    }

    struct MockServerHandle {
        endpoint: String,
        shutdown_sender: oneshot::Sender<()>,
        task: JoinHandle<()>,
    }

    impl MockServerHandle {
        fn endpoint(&self) -> &str {
            &self.endpoint
        }

        async fn stop_server(self) {
            let _ = self.shutdown_sender.send(());
            self.task
                .await
                .expect("mock gRPC server task did not shut down cleanly");
        }
    }

    async fn start_mock_server() -> MockServerHandle {
        let addr = "127.0.0.1:0"
            .parse()
            .expect("invalid test listener address");
        let incoming = TcpIncoming::bind(addr).expect("failed to bind test listener");
        let bound_addr = incoming
            .local_addr()
            .expect("failed to read test listener address");

        let (shutdown_sender, shutdown_receiver) = oneshot::channel::<()>();
        let task = tokio::spawn(async move {
            Server::builder()
                .add_service(InferenceServiceServer::new(MockInferenceService))
                .serve_with_incoming_shutdown(incoming, async move {
                    let _ = shutdown_receiver.await;
                })
                .await
                .expect("test server failed");
        });

        MockServerHandle {
            endpoint: format!("http://{bound_addr}"),
            shutdown_sender,
            task,
        }
    }

    #[tokio::test]
    async fn list_bricks_maps_proto_to_library_type() {
        let server = start_mock_server().await;
        let mut service = super::InferenceService::new(server.endpoint().to_string())
            .await
            .expect("failed to create client");

        let bricks = service.list_bricks().await.expect("list_bricks failed");

        assert_eq!(bricks.len(), 2);
        assert_eq!(bricks[0].brick_type, BrickType::Tts);
        assert_eq!(bricks[0].brick_variant, "kokoro");
        assert_eq!(bricks[1].brick_type, BrickType::ObjectDetection);
        assert_eq!(bricks[1].brick_variant, "yolo");

        server.stop_server().await;
    }

    #[test]
    fn map_unknown_brick_type_to_unspecified() {
        let mapped = map_brick_spec(ProtoBrickSpec {
            r#type: 99,
            brick_variant: "experimental".to_string(),
        });

        assert_eq!(mapped.brick_type, BrickType::Unspecified);
        assert_eq!(mapped.brick_variant, "experimental");
    }

    #[tokio::test]
    async fn run_brick_maps_audio_proto_to_library_type() {
        let server = start_mock_server().await;
        let mut service = super::InferenceService::new(server.endpoint().to_string())
            .await
            .expect("failed to create client");

        let output = service
            .run_brick(
                BrickSpec {
                    brick_type: BrickType::Tts,
                    brick_variant: "kokoro".to_string(),
                },
                RunBrickInput::Text {
                    text: "hello".to_string(),
                },
            )
            .await
            .expect("run_brick failed");

        match output {
            RunBrickOutput::Audio(audio) => {
                assert_eq!(audio.left_channel, vec![0.1, 0.2]);
                assert_eq!(audio.right_channel, vec![0.3, 0.4]);
            }
            _ => panic!("expected audio output"),
        }

        server.stop_server().await;
    }

    #[tokio::test]
    async fn run_brick_maps_detections_proto_to_library_type() {
        let server = start_mock_server().await;
        let mut service = super::InferenceService::new(server.endpoint().to_string())
            .await
            .expect("failed to create client");

        let output = service
            .run_brick(
                BrickSpec {
                    brick_type: BrickType::ObjectDetection,
                    brick_variant: "yolo".to_string(),
                },
                RunBrickInput::Image {
                    image_bytes: vec![1, 2, 3],
                },
            )
            .await
            .expect("run_brick failed");

        match output {
            RunBrickOutput::Detections(detections) => {
                assert_eq!(detections.detections.len(), 1);
                assert_eq!(detections.detections[0].r#box, vec![0.1, 0.2, 0.3, 0.4]);
                assert_eq!(detections.detections[0].class_id, 7);
                assert_eq!(detections.detections[0].score, 0.9);
                assert_eq!(detections.detections[0].class_name, "person");
            }
            _ => panic!("expected detections output"),
        }

        server.stop_server().await;
    }

    #[tokio::test]
    async fn run_brick_returns_internal_when_output_missing() {
        let server = start_mock_server().await;
        let mut service = super::InferenceService::new(server.endpoint().to_string())
            .await
            .expect("failed to create client");

        let result = service
            .run_brick(
                BrickSpec {
                    brick_type: BrickType::Tts,
                    brick_variant: "missing".to_string(),
                },
                RunBrickInput::Text {
                    text: "hello".to_string(),
                },
            )
            .await;

        match result {
            Ok(_) => panic!("expected missing output to return an error"),
            Err(err) => assert_eq!(err.code(), tonic::Code::Internal),
        }

        server.stop_server().await;
    }

    #[tokio::test]
    async fn new_returns_unavailable_for_unreachable_endpoint() {
        match super::InferenceService::new("http://127.0.0.1:1".to_string()).await {
            Ok(_) => panic!("expected client creation to fail"),
            Err(err) => assert_eq!(err.code(), tonic::Code::Unavailable),
        }
    }
}
