#[cfg(test)]
mod tests {
    use super::super::grpc_bridge::concordia::inference_service_server::{
        InferenceService as InferenceServiceTrait, InferenceServiceServer,
    };
    use super::super::grpc_bridge::{GrpcBridge, concordia};
    use super::super::{BrickType, ConcordiaError, RunBrickOptions, RunBrickOutput};
    use concordia::{
        AudioOutput as ProtoAudioOutput, Detection as ProtoDetection,
        ObjDetectionOutput as ProtoObjDetectionOutput, RunBrickRequest, RunBrickResponse,
    };
    use tokio::sync::oneshot;
    use tokio::task::JoinHandle;
    use tonic::Request;
    use tonic::transport::Server;
    use tonic::transport::server::TcpIncoming;
    use tonic::{Response, Status};

    struct MockInferenceService;

    #[tonic::async_trait]
    impl InferenceServiceTrait for MockInferenceService {
        async fn list_bricks(
            &self,
            _request: Request<concordia::ListBricksRequest>,
        ) -> Result<Response<concordia::ListBricksResponse>, Status> {
            // list_bricks is no longer in the user API so we don't connect it
            // however this path is still needed to satisfy the tonic implementation
            Err(Status::unimplemented(
                "list_bricks is not exercised in these tests",
            ))
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
                    output: Some(concordia::run_brick_response::Output::Audio(
                        ProtoAudioOutput {
                            left_channel: vec![0.1, 0.2],
                            right_channel: vec![0.3, 0.4],
                        },
                    )),
                })),
                "yolo" => Ok(Response::new(RunBrickResponse {
                    output: Some(concordia::run_brick_response::Output::Detections(
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
    async fn grpc_bridge_run_brick_maps_audio_proto_to_library_type() {
        let server = start_mock_server().await;
        let mut grpc_bridge = GrpcBridge::connect(server.endpoint())
            .await
            .expect("failed to create gRPC bridge");

        let output = grpc_bridge
            .run_brick(
                BrickType::Tts,
                "kokoro".to_string(),
                RunBrickOptions::Text {
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
    async fn grpc_bridge_run_brick_maps_detections_proto_to_library_type() {
        let server = start_mock_server().await;
        let mut grpc_bridge = GrpcBridge::connect(server.endpoint())
            .await
            .expect("failed to create gRPC bridge");

        let output = grpc_bridge
            .run_brick(
                BrickType::ObjectDetection,
                "yolo".to_string(),
                RunBrickOptions::Image {
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
    async fn grpc_bridge_run_brick_returns_service_error_when_output_missing() {
        let server = start_mock_server().await;
        let mut grpc_bridge = GrpcBridge::connect(server.endpoint())
            .await
            .expect("failed to create gRPC bridge");

        let result = grpc_bridge
            .run_brick(
                BrickType::Tts,
                "missing".to_string(),
                RunBrickOptions::Text {
                    text: "hello".to_string(),
                },
            )
            .await;

        match result {
            Ok(_) => panic!("expected missing output to return an error"),
            Err(err) => assert_eq!(
                err,
                ConcordiaError::ServiceError {
                    message: "run_brick returned response without output".to_string(),
                }
            ),
        }

        server.stop_server().await;
    }

    #[tokio::test]
    async fn grpc_bridge_run_brick_maps_status_to_library_error() {
        let server = start_mock_server().await;
        let mut grpc_bridge = GrpcBridge::connect(server.endpoint())
            .await
            .expect("failed to create gRPC bridge");

        let result = grpc_bridge
            .run_brick(
                BrickType::Tts,
                "unsupported".to_string(),
                RunBrickOptions::Text {
                    text: "hello".to_string(),
                },
            )
            .await;

        match result {
            Ok(_) => panic!("expected unsupported variant to return an error"),
            Err(err) => assert_eq!(
                err,
                ConcordiaError::ServiceError {
                    message: "unsupported variant".to_string(),
                }
            ),
        }

        server.stop_server().await;
    }

    #[tokio::test]
    async fn grpc_bridge_connect_returns_grpc_error_for_unreachable_endpoint() {
        match GrpcBridge::connect("http://127.0.0.1:1").await {
            Ok(_) => panic!("expected client creation to fail"),
            Err(ConcordiaError::GrpcError { message }) => {
                assert!(!message.is_empty(), "expected connection error message")
            }
            Err(err) => panic!("unexpected error type: {err:?}"),
        }
    }
}
