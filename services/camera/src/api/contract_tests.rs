use super::service::{
    CameraApiService, CameraServiceProvider, pipewire,
    pipewire::camera_service_client::CameraServiceClient,
    pipewire::camera_service_server::CameraServiceServer,
};
use super::snapshot::{SnapshotCamera, SnapshotError, SnapshotSupportedFormat};
use ::pipewire::spa::param::format::MediaSubtype;
use ::pipewire::spa::param::video::VideoFormat;
use tokio::{net::TcpListener, sync::oneshot, task::JoinHandle};
use tokio_stream::wrappers::TcpListenerStream;
use tonic::{Code, transport::Channel, transport::Server};

struct RunningServer {
    client: CameraServiceClient<Channel>,
    shutdown: oneshot::Sender<()>,
    task: JoinHandle<Result<(), tonic::transport::Error>>,
}

impl RunningServer {
    async fn shutdown(self) {
        let _ = self.shutdown.send(());

        self.task
            .await
            .expect("server task should not panic")
            .expect("server should shut down cleanly");
    }
}

fn listed_cameras() -> Result<Vec<SnapshotCamera>, SnapshotError> {
    Ok(vec![
        SnapshotCamera {
            object_serial: 101,
            name: "front-door".to_string(),
            supported_formats: vec![SnapshotSupportedFormat::RawVideo(VideoFormat::RGB)],
        },
        SnapshotCamera {
            object_serial: 202,
            name: "loading-bay".to_string(),
            supported_formats: vec![SnapshotSupportedFormat::EncodedVideo(MediaSubtype::Mjpg)],
        },
    ])
}

fn unavailable_cameras() -> Result<Vec<SnapshotCamera>, SnapshotError> {
    Err(SnapshotError::Unavailable(
        "fake provider unavailable".to_string(),
    ))
}

async fn start_server(provider: CameraServiceProvider) -> RunningServer {
    let listener = TcpListener::bind("127.0.0.1:0")
        .await
        .expect("test server should bind to a local ephemeral port");
    let addr = listener
        .local_addr()
        .expect("test server should have a local address");
    let (shutdown, shutdown_rx) = oneshot::channel();

    let service = CameraServiceServer::new(CameraApiService { provider });
    let task = tokio::spawn(async move {
        Server::builder()
            .add_service(service)
            .serve_with_incoming_shutdown(TcpListenerStream::new(listener), async {
                let _ = shutdown_rx.await;
            })
            .await
    });

    let client = CameraServiceClient::connect(format!("http://{addr}"))
        .await
        .expect("client should connect to the test server");

    RunningServer {
        client,
        shutdown,
        task,
    }
}

#[tokio::test]
async fn list_cameras_returns_provider_camera_identities() {
    let mut server = start_server(CameraServiceProvider {
        list_cameras: listed_cameras,
    })
    .await;

    let response = server.client.list_cameras(pipewire::ListRequest {}).await;

    server.shutdown().await;

    let response = response.expect("list_cameras should succeed");

    let identities = response
        .into_inner()
        .cameras
        .into_iter()
        .map(|camera| (camera.id, camera.name, camera.supported_formats))
        .collect::<Vec<_>>();

    assert_eq!(
        identities,
        vec![
            (101, "front-door".to_string(), vec!["RGB".to_string()]),
            (202, "loading-bay".to_string(), vec!["Mjpg".to_string()])
        ]
    );
}

#[tokio::test]
async fn list_cameras_maps_provider_failure_to_unavailable() {
    let mut server = start_server(CameraServiceProvider {
        list_cameras: unavailable_cameras,
    })
    .await;

    let err = server.client.list_cameras(pipewire::ListRequest {}).await;

    server.shutdown().await;

    let err = err.expect_err("list_cameras should fail");

    assert_eq!(err.code(), Code::Unavailable);
    assert_eq!(err.message(), "fake provider unavailable");
}
