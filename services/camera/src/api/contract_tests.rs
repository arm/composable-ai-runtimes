// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use super::parameters::{FrameRate, Resolution, StreamFormat, StreamFormatFilter};
use super::snapshot::{SnapshotCamera, SnapshotError};
use super::{
    server::serving_health_service,
    service::{
        CameraApiService, CameraServiceProvider, pipewire,
        pipewire::camera_service_client::CameraServiceClient,
        pipewire::camera_service_server::CameraServiceServer,
    },
};
use tokio::{net::TcpListener, sync::oneshot, task::JoinHandle};
use tokio_stream::wrappers::TcpListenerStream;
use tonic::{Code, transport::Channel, transport::Server};
use tonic_health::pb::HealthCheckRequest;
use tonic_health::pb::health_check_response;
use tonic_health::pb::health_client::HealthClient;

const TEST_CAMERA_ID: u64 = 101;
const TEST_CAMERA_TARGET: u64 = 52;

struct RunningServer {
    client: CameraServiceClient<Channel>,
    health_client: HealthClient<Channel>,
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
            object_serial: TEST_CAMERA_ID,
            name: "front-door".to_string(),
        },
        SnapshotCamera {
            object_serial: 202,
            name: "loading-bay".to_string(),
        },
    ])
}

fn camera_formats(
    _camera_id: u64,
    _filter: Option<StreamFormatFilter>,
) -> Result<(u64, Vec<StreamFormat>), SnapshotError> {
    Ok((
        TEST_CAMERA_TARGET,
        vec![StreamFormat {
            resolution: Resolution {
                width: 1920,
                height: 1080,
            },
            pixel_format: "RGB".to_string(),
            frame_rate: FrameRate {
                numerator: 30,
                denominator: 1,
            },
        }],
    ))
}

fn requested_camera_formats(
    _camera_id: u64,
    filter: Option<StreamFormatFilter>,
) -> Result<(u64, Vec<StreamFormat>), SnapshotError> {
    let filter = filter.expect("provider should receive the requested format filter");
    let resolution = filter
        .resolution
        .expect("provider should receive the requested resolution");
    let frame_rate = filter
        .frame_rate
        .expect("provider should receive the requested frame rate");
    Ok((
        TEST_CAMERA_TARGET,
        vec![StreamFormat {
            resolution: Resolution {
                width: resolution.width,
                height: resolution.height,
            },
            pixel_format: filter.pixel_format,
            frame_rate: FrameRate {
                numerator: frame_rate.numerator,
                denominator: frame_rate.denominator,
            },
        }],
    ))
}

fn no_camera_formats(
    _camera_id: u64,
    _filter: Option<StreamFormatFilter>,
) -> Result<(u64, Vec<StreamFormat>), SnapshotError> {
    Ok((TEST_CAMERA_TARGET, Vec::new()))
}

fn missing_camera_formats(
    camera_id: u64,
    _filter: Option<StreamFormatFilter>,
) -> Result<(u64, Vec<StreamFormat>), SnapshotError> {
    Err(SnapshotError::NotFound(camera_id))
}

fn unavailable_camera_formats(
    _camera_id: u64,
    _filter: Option<StreamFormatFilter>,
) -> Result<(u64, Vec<StreamFormat>), SnapshotError> {
    Err(SnapshotError::Unavailable(
        "fake provider unavailable".to_string(),
    ))
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

    let (_health_reporter, health_service) = serving_health_service().await;
    let service = CameraServiceServer::new(CameraApiService { provider });
    let task = tokio::spawn(async move {
        Server::builder()
            .add_service(service)
            .add_service(health_service)
            .serve_with_incoming_shutdown(TcpListenerStream::new(listener), async {
                let _ = shutdown_rx.await;
            })
            .await
    });

    let client = CameraServiceClient::connect(format!("http://{addr}"))
        .await
        .expect("client should connect to the test server");
    let health_channel = Channel::from_shared(format!("http://{addr}"))
        .expect("health endpoint should be valid")
        .connect()
        .await
        .expect("health client should connect to the test server");
    let health_client = HealthClient::new(health_channel);

    RunningServer {
        client,
        health_client,
        shutdown,
        task,
    }
}

#[tokio::test]
async fn list_cameras_returns_provider_camera_identities() {
    let mut server = start_server(CameraServiceProvider {
        list_cameras: listed_cameras,
        ..Default::default()
    })
    .await;

    let response = server.client.list_cameras(pipewire::ListRequest {}).await;

    server.shutdown().await;

    let response = response.expect("list_cameras should succeed");

    let identities = response
        .into_inner()
        .cameras
        .into_iter()
        .map(|camera| (camera.id, camera.name))
        .collect::<Vec<_>>();

    assert_eq!(
        identities,
        vec![
            (TEST_CAMERA_ID, "front-door".to_string()),
            (202, "loading-bay".to_string())
        ]
    );
}

#[tokio::test]
async fn list_cameras_maps_provider_failure_to_unavailable() {
    let mut server = start_server(CameraServiceProvider {
        list_cameras: unavailable_cameras,
        ..Default::default()
    })
    .await;

    let err = server.client.list_cameras(pipewire::ListRequest {}).await;

    server.shutdown().await;

    let err = err.expect_err("list_cameras should fail");

    assert_eq!(err.code(), Code::Unavailable);
    assert_eq!(err.message(), "fake provider unavailable");
}

#[tokio::test]
async fn health_check_reports_serving() {
    let mut server = start_server(CameraServiceProvider {
        list_cameras: unavailable_cameras,
        ..Default::default()
    })
    .await;

    let response = server
        .health_client
        .check(HealthCheckRequest::default())
        .await
        .expect("health check should succeed")
        .into_inner();

    server.shutdown().await;

    assert_eq!(
        health_check_response::ServingStatus::try_from(response.status)
            .expect("health status should be known"),
        health_check_response::ServingStatus::Serving
    );
}

#[tokio::test]
async fn get_stream_configurations_returns_provider_formats() {
    let mut server = start_server(CameraServiceProvider {
        list_camera_formats: camera_formats,
        ..Default::default()
    })
    .await;

    let response = server
        .client
        .get_stream_configurations(pipewire::StreamConfigurationRequest {
            camera_id: TEST_CAMERA_ID,
            format: None,
        })
        .await;

    server.shutdown().await;

    let configurations = response
        .expect("get_stream_configurations should succeed")
        .into_inner()
        .configurations;

    let expected = vec![pipewire::StreamConfiguration {
        target: TEST_CAMERA_TARGET.to_string(),
        camera_id: TEST_CAMERA_ID,
        format: Some(pipewire::StreamFormat {
            resolution: Some(pipewire::Resolution {
                width: 1920,
                height: 1080,
            }),
            pixel_format: "RGB".to_string(),
            frame_rate: Some(pipewire::FrameRate {
                numerator: 30,
                denominator: 1,
            }),
        }),
    }];

    assert_eq!(configurations, expected);
}

#[tokio::test]
async fn get_stream_configurations_passes_filter_to_provider() {
    let mut server = start_server(CameraServiceProvider {
        list_camera_formats: requested_camera_formats,
        ..Default::default()
    })
    .await;
    let requested_format = pipewire::StreamFormat {
        resolution: Some(pipewire::Resolution {
            width: 1280,
            height: 720,
        }),
        pixel_format: "YUY2".to_string(),
        frame_rate: Some(pipewire::FrameRate {
            numerator: 45,
            denominator: 1,
        }),
    };

    let response = server
        .client
        .get_stream_configurations(pipewire::StreamConfigurationRequest {
            camera_id: TEST_CAMERA_ID,
            format: Some(requested_format.clone()),
        })
        .await;

    server.shutdown().await;

    let configurations = response
        .expect("get_stream_configurations should succeed")
        .into_inner()
        .configurations;
    assert_eq!(
        configurations,
        vec![pipewire::StreamConfiguration {
            target: TEST_CAMERA_TARGET.to_string(),
            camera_id: TEST_CAMERA_ID,
            format: Some(requested_format),
        }]
    );
}

#[tokio::test]
async fn get_stream_configurations_returns_empty_response() {
    let mut server = start_server(CameraServiceProvider {
        list_camera_formats: no_camera_formats,
        ..Default::default()
    })
    .await;

    let response = server
        .client
        .get_stream_configurations(pipewire::StreamConfigurationRequest {
            camera_id: TEST_CAMERA_ID,
            format: None,
        })
        .await;

    server.shutdown().await;

    let configurations = response
        .expect("get_stream_configurations should succeed")
        .into_inner()
        .configurations;

    assert!(configurations.is_empty());
}

#[tokio::test]
async fn get_stream_configurations_maps_not_found() {
    let mut server = start_server(CameraServiceProvider {
        list_camera_formats: missing_camera_formats,
        ..Default::default()
    })
    .await;

    let err = server
        .client
        .get_stream_configurations(pipewire::StreamConfigurationRequest {
            camera_id: TEST_CAMERA_ID,
            format: None,
        })
        .await;

    server.shutdown().await;

    let err = err.expect_err("get_stream_configurations should fail");

    assert_eq!(err.code(), Code::NotFound);
    assert_eq!(
        err.message(),
        format!("camera {TEST_CAMERA_ID} was not found")
    );
}

#[tokio::test]
async fn get_stream_configurations_rejects_invalid_request() {
    let mut server = start_server(CameraServiceProvider {
        list_camera_formats: camera_formats,
        ..Default::default()
    })
    .await;

    let err = server
        .client
        .get_stream_configurations(pipewire::StreamConfigurationRequest {
            camera_id: 0,
            format: None,
        })
        .await;

    server.shutdown().await;

    let err = err.expect_err("get_stream_configurations should fail");

    assert_eq!(err.code(), Code::InvalidArgument);
    assert_eq!(err.message(), "camera_id must be greater than zero");
}

#[tokio::test]
async fn get_stream_configurations_maps_provider_failure_to_unavailable() {
    let mut server = start_server(CameraServiceProvider {
        list_camera_formats: unavailable_camera_formats,
        ..Default::default()
    })
    .await;

    let err = server
        .client
        .get_stream_configurations(pipewire::StreamConfigurationRequest {
            camera_id: TEST_CAMERA_ID,
            format: None,
        })
        .await;

    server.shutdown().await;

    let err = err.expect_err("get_stream_configurations should fail");

    assert_eq!(err.code(), Code::Unavailable);
    assert_eq!(err.message(), "fake provider unavailable");
}
