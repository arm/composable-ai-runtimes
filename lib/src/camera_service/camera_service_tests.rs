use tokio::sync::oneshot;
use tokio::task::JoinHandle;
use tonic::Request;
use tonic::transport::Server;
use tonic::transport::server::TcpIncoming;
use tonic::{Response, Status};

use super::camera_service::pipewire::pipewire_service_server::{
    PipewireService, PipewireServiceServer,
};
use super::camera_service::pipewire::{
    Camera as ProtoCamera, ListCamerasResponse, ListRequest, ListStreamsResponse,
    Stream as ProtoStream,
};
use super::*;

struct MockPipewireService;

#[tonic::async_trait]
impl PipewireService for MockPipewireService {
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

    async fn list_streams(
        &self,
        _request: Request<ListRequest>,
    ) -> Result<Response<ListStreamsResponse>, Status> {
        Ok(Response::new(ListStreamsResponse {
            streams: vec![
                ProtoStream {
                    link_id: 10,
                    camera_node_id: 20,
                    consumer_node_id: 30,
                    camera_name: "front".to_string(),
                    consumer_name: "inference".to_string(),
                },
                ProtoStream {
                    link_id: 11,
                    camera_node_id: 21,
                    consumer_node_id: 31,
                    camera_name: "rear".to_string(),
                    consumer_name: "recording".to_string(),
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
            .add_service(PipewireServiceServer::new(MockPipewireService))
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
    let mut service = CameraService::new(server.endpoint().to_string())
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
async fn list_streams_maps_proto_to_library_type() {
    let server = start_mock_server().await;
    let mut service = CameraService::new(server.endpoint().to_string())
        .await
        .expect("failed to create client");

    let streams = service.list_streams().await.expect("list_streams failed");
    assert_eq!(streams.len(), 2);
    assert_eq!(streams[0].link_id, 10);
    assert_eq!(streams[0].camera_node_id, 20);
    assert_eq!(streams[0].consumer_node_id, 30);
    assert_eq!(streams[0].camera_name, "front");
    assert_eq!(streams[0].consumer_name, "inference");
    assert_eq!(streams[1].link_id, 11);
    assert_eq!(streams[1].camera_node_id, 21);
    assert_eq!(streams[1].consumer_node_id, 31);
    assert_eq!(streams[1].camera_name, "rear");
    assert_eq!(streams[1].consumer_name, "recording");

    server.stop_server().await;
}

#[tokio::test]
async fn new_returns_unavailable_for_unreachable_endpoint() {
    match CameraService::new("http://127.0.0.1:1".to_string()).await {
        Ok(_) => panic!("expected client creation to fail"),
        Err(err) => assert_eq!(err.code(), tonic::Code::Unavailable),
    }
}
