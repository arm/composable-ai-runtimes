use tokio::sync::oneshot;
use tokio::task::JoinHandle;
use tonic::Request;
use tonic::transport::Server;
use tonic::transport::server::TcpIncoming;
use tonic::{Response, Status};

use super::service::pipewire::camera_service_server::{
    CameraService as ProtoCameraService, CameraServiceServer,
};
use super::service::pipewire::{Camera as ProtoCamera, ListCamerasResponse, ListRequest};
use super::*;

struct MockCameraService;

#[tonic::async_trait]
impl ProtoCameraService for MockCameraService {
    async fn list_cameras(
        &self,
        _request: Request<ListRequest>,
    ) -> Result<Response<ListCamerasResponse>, Status> {
        Ok(Response::new(ListCamerasResponse {
            cameras: vec![
                ProtoCamera {
                    id: 7,
                    name: "front".to_string(),
                    supported_formats: vec!["RGB".to_string(), "YUY2".to_string()],
                },
                ProtoCamera {
                    id: 99,
                    name: "rear".to_string(),
                    supported_formats: Vec::new(),
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
    let task = tokio::spawn(async move {
        Server::builder()
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

    let cameras = service
        .list_camera_metadata()
        .await
        .expect("list_camera_metadata failed");
    assert_eq!(cameras.len(), 2);
    assert_eq!(cameras[0].id, 7);
    assert_eq!(cameras[0].name, "front");
    assert_eq!(cameras[0].supported_formats, ["RGB", "YUY2"]);
    assert_eq!(cameras[1].id, 99);
    assert_eq!(cameras[1].name, "rear");
    assert!(cameras[1].supported_formats.is_empty());

    server.stop_server().await;
}

#[test]
fn camera_new_rejects_invalid_options() {
    let cases = [
        (
            "zero camera id",
            0,
            CameraOptions {
                width: 640,
                height: 480,
                fps: 30,
                pixel_format: CapturePixelFormat::Yuy2,
            },
            "camera_id must be non-zero",
        ),
        (
            "zero width",
            7,
            CameraOptions {
                width: 0,
                height: 480,
                fps: 30,
                pixel_format: CapturePixelFormat::Yuy2,
            },
            "width must be greater than zero",
        ),
        (
            "zero height",
            7,
            CameraOptions {
                width: 640,
                height: 0,
                fps: 30,
                pixel_format: CapturePixelFormat::Yuy2,
            },
            "height must be greater than zero",
        ),
        (
            "zero fps",
            7,
            CameraOptions {
                width: 640,
                height: 480,
                fps: 0,
                pixel_format: CapturePixelFormat::Yuy2,
            },
            "fps must be greater than zero",
        ),
    ];

    for (case_name, camera_id, options, expected_message) in cases {
        let result = Camera::new(camera_id, options);

        match result {
            Ok(_) => panic!("expected camera creation to fail for {case_name}"),
            Err(CameraError::Validation(message)) => {
                assert_eq!(
                    message, expected_message,
                    "validation mismatch for {case_name}"
                )
            }
            Err(err) => panic!("expected validation error for {case_name}, got {err}"),
        }
    }
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
    }
}
