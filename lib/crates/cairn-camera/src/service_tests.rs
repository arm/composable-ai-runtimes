// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::time::Duration;
use tokio::sync::oneshot;
use tokio::task::JoinHandle;
use tokio::time::timeout;
use tonic::Request;
use tonic::transport::Server;
use tonic::transport::server::TcpIncoming;
use tonic::{Response, Status};
use tonic_health::ServingStatus;

use super::service::pipewire;
use super::service::pipewire::camera_service_server::{
    CameraService as ProtoCameraService, CameraServiceServer,
};
use super::service::pipewire::{Camera as ProtoCamera, ListCamerasResponse, ListRequest};
use super::*;

#[test]
fn stream_configuration_new_preserves_supplied_fields() {
    let format = StreamFormat {
        resolution: Resolution {
            width: 1920,
            height: 1080,
        },
        pixel_format: "NV12".into(),
        frame_rate: FrameRate {
            numerator: 30_000,
            denominator: 1_001,
        },
    };

    let configuration = StreamConfiguration::new("opaque/pipewire:target", 7, format.clone());

    assert_eq!(configuration.target(), "opaque/pipewire:target");
    assert_eq!(configuration.camera_id(), 7);
    assert_eq!(configuration.format(), &format);
}

#[test]
fn absent_pixel_format_uses_the_protobuf_default() {
    let format = pipewire::StreamFormat::from(StreamFormatFilter::default());

    assert_eq!(format.pixel_format, "");
}

struct MockCameraService;

#[tonic::async_trait]
impl ProtoCameraService for MockCameraService {
    async fn get_stream_configurations(
        &self,
        request: Request<pipewire::StreamConfigurationRequest>,
    ) -> Result<Response<pipewire::StreamConfigurationResponse>, Status> {
        let request = request.into_inner();
        if request.camera_id == 0 {
            return Err(Status::invalid_argument(
                "camera_id must be greater than zero",
            ));
        }
        if request.camera_id == 99 {
            return Err(Status::not_found("camera not found"));
        }
        if request.camera_id == 98 {
            return Err(Status::unavailable("PipeWire unavailable"));
        }
        if request.camera_id == 97 {
            return Ok(Response::new(pipewire::StreamConfigurationResponse {
                configurations: vec![pipewire::StreamConfiguration {
                    target: "7".into(),
                    camera_id: 7,
                    format: None,
                }],
            }));
        }
        assert!(matches!(request.camera_id, 7 | 8));
        if request.camera_id == 8 {
            assert!(
                request.format.is_some(),
                "the client dropped the requested filter"
            );
        }
        if let Some(filter) = request.format {
            if filter.pixel_format == "unsupported" {
                return Ok(Response::new(pipewire::StreamConfigurationResponse {
                    configurations: vec![],
                }));
            }
            assert_eq!(filter.pixel_format, "RGB");
            assert_eq!(
                filter.resolution,
                Some(pipewire::Resolution {
                    width: 640,
                    height: 480
                })
            );
            assert_eq!(
                filter.frame_rate,
                Some(pipewire::FrameRate {
                    numerator: 30000,
                    denominator: 1001
                })
            );
        }
        Ok(Response::new(pipewire::StreamConfigurationResponse {
            configurations: vec![pipewire::StreamConfiguration {
                target: "42".into(),
                camera_id: 7,
                format: Some(pipewire::StreamFormat {
                    resolution: Some(pipewire::Resolution {
                        width: 640,
                        height: 480,
                    }),
                    pixel_format: "RGB".into(),
                    frame_rate: Some(pipewire::FrameRate {
                        numerator: 30000,
                        denominator: 1001,
                    }),
                }),
            }],
        }))
    }

    async fn list_cameras(
        &self,
        _request: Request<ListRequest>,
    ) -> Result<Response<ListCamerasResponse>, Status> {
        Ok(Response::new(ListCamerasResponse {
            cameras: vec![
                ProtoCamera {
                    id: 7,
                    name: "front".to_string(),
                },
                ProtoCamera {
                    id: 99,
                    name: "rear".to_string(),
                },
            ],
        }))
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
    let (_, health_service) = tonic_health::server::health_reporter();
    let task = tokio::spawn(async move {
        Server::builder()
            .add_service(health_service)
            .add_service(CameraServiceServer::new(MockCameraService))
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
async fn list_cameras_maps_proto_to_library_type() {
    let server = start_mock_server().await;
    let mut service = CameraService::new(Some(server.endpoint().to_string()))
        .await
        .expect("failed to create client");

    let cameras = service.list_cameras().await.expect("list_cameras failed");
    assert_eq!(cameras.len(), 2);
    assert_eq!(cameras[0].id, 7);
    assert_eq!(cameras[0].name, "front");
    assert_eq!(cameras[1].id, 99);
    assert_eq!(cameras[1].name, "rear");

    server.stop_server().await;
}

#[tokio::test]
async fn new_returns_unavailable_for_unreachable_endpoint() {
    match CameraService::new(Some("http://127.0.0.1:1".to_string())).await {
        Ok(_) => panic!("expected client creation to fail"),
        Err(CameraServiceError::Transport(message)) => {
            assert!(
                !message.is_empty(),
                "expected unreachable endpoint to produce a transport message"
            );
        }
        Err(error) => panic!("unexpected client creation error: {error}"),
    }
}

#[tokio::test]
async fn configurations_preserve_filters_and_map_response_fields() {
    let server = start_mock_server().await;
    let mut service = CameraService::new(Some(server.endpoint().to_owned()))
        .await
        .unwrap();
    let filter = StreamFormatFilter {
        resolution: Some(Resolution {
            width: 640,
            height: 480,
        }),
        pixel_format: Some("RGB".into()),
        frame_rate: Some(FrameRate {
            numerator: 30000,
            denominator: 1001,
        }),
    };
    let mut camera = service.list_cameras().await.unwrap().remove(0);
    for filter in [None, Some(filter)] {
        let camera_id = if filter.is_some() { 8 } else { 7 };
        let configurations = service
            .get_stream_configurations(camera_id, filter.clone())
            .await
            .unwrap();
        camera.id = camera_id;
        assert_eq!(
            camera.get_stream_configurations(filter).await.unwrap(),
            configurations
        );
        assert_eq!(configurations.len(), 1);
        assert_eq!(configurations[0].target(), "42");
        assert_eq!(configurations[0].camera_id(), 7);
        assert_eq!(
            configurations[0].format(),
            &StreamFormat {
                resolution: Resolution {
                    width: 640,
                    height: 480
                },
                pixel_format: "RGB".into(),
                frame_rate: FrameRate {
                    numerator: 30000,
                    denominator: 1001
                },
            }
        );
    }
    assert!(
        service
            .get_stream_configurations(
                7,
                Some(StreamFormatFilter {
                    pixel_format: Some("unsupported".into()),
                    ..Default::default()
                })
            )
            .await
            .unwrap()
            .is_empty()
    );
    server.stop_server().await;
}

#[tokio::test]
async fn configurations_report_status_and_malformed_response_errors() {
    let server = start_mock_server().await;
    let mut service = CameraService::new(Some(server.endpoint().to_owned()))
        .await
        .unwrap();
    for (camera_id, expected) in [
        (0, "camera_id must be greater than zero"),
        (99, "camera not found"),
        (98, "PipeWire unavailable"),
        (97, "missing its format"),
    ] {
        let error = service
            .get_stream_configurations(camera_id, None)
            .await
            .unwrap_err();
        if camera_id == 97 {
            assert!(matches!(error, CameraServiceError::InvalidResponse(_)));
        } else {
            assert!(matches!(error, CameraServiceError::Transport(_)));
        }
        assert!(error.to_string().contains(expected), "{error}");
    }
    server.stop_server().await;
}

async fn start_health_server(
    status: ServingStatus,
) -> (
    String,
    tonic_health::server::HealthReporter,
    tokio::task::JoinHandle<()>,
) {
    let incoming = TcpIncoming::bind("127.0.0.1:0".parse().unwrap()).unwrap();
    let endpoint = format!("http://{}", incoming.local_addr().unwrap());
    let (reporter, health_service) = tonic_health::server::health_reporter();
    reporter.set_service_status("", status).await;
    let server = tokio::spawn(async move {
        Server::builder()
            .add_service(health_service)
            .serve_with_incoming(incoming)
            .await
            .expect("test health server failed");
    });

    (endpoint, reporter, server)
}

#[tokio::test]
async fn waits_for_serving() {
    let (endpoint, reporter, server) = start_health_server(ServingStatus::NotServing).await;
    let readiness = CameraService::new(Some(endpoint.clone()));
    tokio::pin!(readiness);
    assert!(
        timeout(Duration::from_millis(100), &mut readiness)
            .await
            .is_err(),
        "readiness must stay pending while health is NOT_SERVING"
    );

    reporter
        .set_service_status("", ServingStatus::Serving)
        .await;
    timeout(Duration::from_secs(2), readiness)
        .await
        .expect("readiness did not complete after SERVING")
        .expect("readiness failed after SERVING");

    server.abort();
    let _ = server.await;
}

#[tokio::test]
async fn accepts_already_serving() {
    let (endpoint, _reporter, server) = start_health_server(ServingStatus::Serving).await;
    timeout(
        Duration::from_secs(2),
        CameraService::new(Some(endpoint.clone())),
    )
    .await
    .expect("already-serving health did not complete readiness")
    .expect("readiness failed for an already-serving service");

    server.abort();
    let _ = server.await;
}
