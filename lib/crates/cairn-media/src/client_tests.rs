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

use super::media;
use super::media::device_stream_configuration::Format;
use super::media::media_service_server::{MediaService as ProtoMediaService, MediaServiceServer};
use super::media::{Camera as ProtoCamera, ListCamerasResponse, ListRequest};
use super::{
    AudioFormat, DeviceSelector, DeviceStreamConfiguration, DeviceStreamFormat,
    DeviceStreamFormatFilter, DeviceType, FrameRate, Media, MediaError, Resolution, StreamFormat,
    StreamFormatFilter,
};

#[test]
fn stream_configuration_new_preserves_supplied_fields() {
    let format = DeviceStreamFormat::Video(StreamFormat {
        resolution: Resolution {
            width: 1920,
            height: 1080,
        },
        pixel_format: "NV12".into(),
        frame_rate: FrameRate {
            numerator: 30_000,
            denominator: 1_001,
        },
    });

    let configuration = DeviceStreamConfiguration::new("opaque/pipewire:target", 7, format.clone());

    assert_eq!(configuration.target(), "opaque/pipewire:target");
    assert_eq!(configuration.device_id(), 7);
    assert_eq!(configuration.format(), &format);
}

#[test]
fn video_device_filter_preserves_unspecified_constraints() {
    let filter = media::device_stream_configuration_request::Filter::from(
        DeviceStreamFormatFilter::Video(StreamFormatFilter::default()),
    );
    let media::device_stream_configuration_request::Filter::VideoFormat(format) = filter;

    assert_eq!(format.pixel_format, "");
    assert!(format.resolution.is_none());
    assert!(format.frame_rate.is_none());
}

struct MockMediaService {
    devices: Result<Vec<media::Device>, Status>,
}

#[tonic::async_trait]
impl ProtoMediaService for MockMediaService {
    async fn list_devices(
        &self,
        request: Request<media::ListDevicesRequest>,
    ) -> Result<Response<media::ListDevicesResponse>, Status> {
        let device_type = request.into_inner().device_type;
        let devices = self.devices.clone()?;
        Ok(Response::new(media::ListDevicesResponse {
            devices: devices
                .into_iter()
                .filter(|device| device_type.is_none_or(|value| device.device_type == value))
                .collect(),
        }))
    }

    async fn get_device_stream_configurations(
        &self,
        request: Request<media::DeviceStreamConfigurationRequest>,
    ) -> Result<Response<media::DeviceStreamConfigurationResponse>, Status> {
        let request = request.into_inner();
        let device_id = request.device_id;
        assert_eq!(request.filter.is_some(), matches!(device_id, 10 | 11));
        if let Some(media::device_stream_configuration_request::Filter::VideoFormat(filter)) =
            request.filter
        {
            assert_eq!(filter.pixel_format, "RGB");
            assert_eq!(
                filter.resolution,
                Some(media::Resolution {
                    width: 640,
                    height: 480
                })
            );
            assert_eq!(
                filter.frame_rate,
                Some(media::FrameRate {
                    numerator: 30000,
                    denominator: 1001
                })
            );
        }
        let format = match device_id {
            7 | 11 | 95 | 96 => Some(Format::VideoFormat(media::StreamFormat {
                resolution: (device_id != 96).then_some(media::Resolution {
                    width: 640,
                    height: 480,
                }),
                pixel_format: "RGB".into(),
                frame_rate: (device_id != 95).then_some(media::FrameRate {
                    numerator: 30_000,
                    denominator: 1_001,
                }),
            })),
            8 | 9 => Some(Format::AudioFormat(media::AudioFormat {
                sample_rate: 48_000,
                channels: 2,
                sample_format: if device_id == 8 { "F32LE" } else { "F32P" }.into(),
                channel_layout: vec!["FL".into(), "FR".into()],
                interleaved: device_id == 8,
            })),
            10 => {
                return Ok(Response::new(media::DeviceStreamConfigurationResponse {
                    configurations: vec![],
                }));
            }
            94 => return Err(Status::invalid_argument("invalid device filter")),
            97 => None,
            98 => return Err(Status::unavailable("PipeWire unavailable")),
            99 => return Err(Status::not_found("device not found")),
            _ => return Err(Status::invalid_argument("unexpected device ID")),
        };
        Ok(Response::new(media::DeviceStreamConfigurationResponse {
            configurations: vec![media::DeviceStreamConfiguration {
                target: format!("opaque:{device_id}"),
                device_id,
                format,
            }],
        }))
    }

    async fn get_stream_configurations(
        &self,
        _request: Request<media::StreamConfigurationRequest>,
    ) -> Result<Response<media::StreamConfigurationResponse>, Status> {
        Err(Status::unimplemented("tests use device configurations"))
    }

    async fn list_cameras(
        &self,
        _request: Request<ListRequest>,
    ) -> Result<Response<ListCamerasResponse>, Status> {
        Ok(Response::new(ListCamerasResponse {
            cameras: self
                .devices
                .clone()?
                .into_iter()
                .filter(|device| device.device_type == media::DeviceType::Camera as i32)
                .map(|device| ProtoCamera {
                    id: device.id,
                    name: device.name,
                })
                .collect(),
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
    start_mock_server_with_devices(Ok(vec![
        media::Device {
            id: 7,
            name: "front".to_string(),
            device_type: 0,
        },
        media::Device {
            id: 8,
            name: "microphone".to_string(),
            device_type: 1,
        },
        media::Device {
            id: 9,
            name: "speaker".to_string(),
            device_type: 2,
        },
        media::Device {
            id: 10,
            name: "rear".to_string(),
            device_type: 0,
        },
    ]))
    .await
}

async fn start_mock_server_with_devices(
    devices: Result<Vec<media::Device>, Status>,
) -> MockServerHandle {
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
            .add_service(MediaServiceServer::new(MockMediaService { devices }))
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
async fn device_discovery_propagates_rpc_errors() {
    for status in [
        Status::unavailable("PipeWire unavailable"),
        Status::unimplemented("device discovery is not implemented"),
    ] {
        let message = status.message().to_owned();
        let server = start_mock_server_with_devices(Err(status)).await;
        let service = Media::connect(Some(server.endpoint().to_owned()))
            .await
            .unwrap();
        for result in [
            service.list_devices(None).await.map(|_| ()),
            service.get_device(DeviceSelector::Id(7)).await.map(|_| ()),
            service
                .get_device(DeviceSelector::Type(DeviceType::Camera))
                .await
                .map(|_| ()),
        ] {
            let error = result.unwrap_err();
            assert!(matches!(error, MediaError::Transport(_)));
            assert!(error.to_string().contains(&message));
        }
        server.stop_server().await;
    }
}

#[tokio::test]
async fn list_devices_maps_metadata_and_preserves_optional_type_filter() {
    let server = start_mock_server().await;
    let service = Media::connect(Some(server.endpoint().to_string()))
        .await
        .expect("failed to create client");

    let devices = service
        .list_devices(None)
        .await
        .expect("list_devices failed");
    assert_eq!(
        devices
            .iter()
            .map(|device| (device.id, device.name.as_str(), device.device_type))
            .collect::<Vec<_>>(),
        vec![
            (7, "front", DeviceType::Camera),
            (8, "microphone", DeviceType::Microphone),
            (9, "speaker", DeviceType::Speaker),
            (10, "rear", DeviceType::Camera),
        ]
    );
    for (device_type, ids) in [
        (DeviceType::Camera, vec![7, 10]),
        (DeviceType::Microphone, vec![8]),
        (DeviceType::Speaker, vec![9]),
    ] {
        let devices = service.list_devices(Some(device_type)).await.unwrap();
        assert_eq!(
            devices.iter().map(|device| device.id).collect::<Vec<_>>(),
            ids
        );
        assert!(
            devices
                .iter()
                .all(|device| device.device_type == device_type)
        );
    }

    server.stop_server().await;
}

#[tokio::test]
async fn get_device_selects_first_of_type() {
    let server = start_mock_server().await;
    let service = Media::connect(Some(server.endpoint().to_owned()))
        .await
        .unwrap();

    for (device_type, id, name) in [
        (DeviceType::Camera, 7, "front"),
        (DeviceType::Microphone, 8, "microphone"),
        (DeviceType::Speaker, 9, "speaker"),
    ] {
        let device = service
            .get_device(DeviceSelector::Type(device_type))
            .await
            .unwrap()
            .unwrap();
        assert_eq!(
            (device.id, device.name.as_str(), device.device_type),
            (id, name, device_type)
        );
    }

    server.stop_server().await;
}

#[tokio::test]
async fn get_device_returns_none_when_no_devices_match() {
    for devices in [
        vec![],
        vec![media::Device {
            id: 7,
            name: "front".into(),
            device_type: 0,
        }],
    ] {
        let server = start_mock_server_with_devices(Ok(devices)).await;
        let service = Media::connect(Some(server.endpoint().to_owned()))
            .await
            .unwrap();

        assert!(
            service
                .list_devices(Some(DeviceType::Microphone))
                .await
                .unwrap()
                .is_empty()
        );
        assert!(
            service
                .get_device(DeviceSelector::Type(DeviceType::Microphone))
                .await
                .unwrap()
                .is_none()
        );
        assert!(matches!(
            service.get_device(DeviceSelector::Id(8)).await,
            Err(MediaError::NotFound(8))
        ));

        server.stop_server().await;
    }
}

#[tokio::test]
async fn get_device_selects_by_id() {
    let server = start_mock_server().await;
    let service = Media::connect(Some(server.endpoint().to_owned()))
        .await
        .unwrap();

    for (id, name) in [
        (10, "rear"),
        (7, "front"),
        (8, "microphone"),
        (9, "speaker"),
    ] {
        let device = service
            .get_device(DeviceSelector::Id(id))
            .await
            .unwrap()
            .unwrap();
        assert_eq!((device.id, device.name.as_str()), (id, name));
    }

    server.stop_server().await;
}

#[tokio::test]
async fn get_device_errors_when_id_is_missing() {
    let server = start_mock_server().await;
    let service = Media::connect(Some(server.endpoint().to_owned()))
        .await
        .unwrap();

    let error = service
        .get_device(DeviceSelector::Id(123))
        .await
        .map(|_| ())
        .unwrap_err();
    assert!(matches!(error, MediaError::NotFound(123)));
    assert_eq!(error.to_string(), "device 123 was not found");

    server.stop_server().await;
}

#[tokio::test]
async fn get_device_propagates_transport_failure() {
    let server = start_mock_server().await;
    let service = Media::connect(Some(server.endpoint().to_owned()))
        .await
        .unwrap();
    server.stop_server().await;

    for selector in [
        DeviceSelector::Type(DeviceType::Camera),
        DeviceSelector::Id(7),
    ] {
        assert!(matches!(
            timeout(Duration::from_secs(2), service.get_device(selector))
                .await
                .unwrap(),
            Err(MediaError::Transport(_))
        ));
    }
}

#[tokio::test]
async fn connect_returns_unavailable_for_unreachable_endpoint() {
    match Media::connect(Some("http://127.0.0.1:1".to_string())).await {
        Ok(_) => panic!("expected client creation to fail"),
        Err(MediaError::Transport(message)) => {
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
    let service = Media::connect(Some(server.endpoint().to_owned()))
        .await
        .unwrap();
    let filter = DeviceStreamFormatFilter::Video(StreamFormatFilter {
        resolution: Some(Resolution {
            width: 640,
            height: 480,
        }),
        pixel_format: Some("RGB".into()),
        frame_rate: Some(FrameRate {
            numerator: 30000,
            denominator: 1001,
        }),
    });
    let mut device = service
        .list_devices(Some(DeviceType::Camera))
        .await
        .unwrap()
        .remove(0);
    for filter in [None, Some(filter.clone())] {
        device.id = if filter.is_some() { 11 } else { 7 };
        let configurations = service
            .get_device_stream_configurations(device.id, filter.clone())
            .await
            .unwrap();
        assert_eq!(
            device.get_stream_configurations(filter).await.unwrap(),
            configurations
        );
        assert_eq!(configurations.len(), 1);
        assert_eq!(configurations[0].target(), format!("opaque:{}", device.id));
        assert_eq!(configurations[0].device_id(), device.id);
        assert_eq!(
            configurations[0].format(),
            &DeviceStreamFormat::Video(StreamFormat {
                resolution: Resolution {
                    width: 640,
                    height: 480
                },
                pixel_format: "RGB".into(),
                frame_rate: FrameRate {
                    numerator: 30000,
                    denominator: 1001
                },
            })
        );
    }
    assert!(
        service
            .get_device_stream_configurations(10, Some(filter))
            .await
            .unwrap()
            .is_empty()
    );
    server.stop_server().await;
}

#[tokio::test]
async fn configurations_report_status_and_malformed_response_errors() {
    let server = start_mock_server().await;
    let service = Media::connect(Some(server.endpoint().to_owned()))
        .await
        .unwrap();
    for (device_id, expected) in [
        (94, "invalid device filter"),
        (95, "missing its frame rate"),
        (96, "missing its resolution"),
        (97, "missing its format"),
        (98, "PipeWire unavailable"),
        (99, "device not found"),
    ] {
        let error = service
            .get_device_stream_configurations(device_id, None)
            .await
            .unwrap_err();
        if (95..=97).contains(&device_id) {
            assert!(matches!(error, MediaError::InvalidResponse(_)));
        } else {
            assert!(matches!(error, MediaError::Transport(_)));
        }
        assert!(error.to_string().contains(expected), "{error}");
    }
    server.stop_server().await;
}

#[tokio::test]
async fn audio_device_configurations_preserve_fields_and_connection() {
    let server = start_mock_server().await;
    let service = Media::connect(Some(server.endpoint().to_owned()))
        .await
        .unwrap();
    let mut devices = service.list_devices(None).await.unwrap();
    devices.retain(|device| device.device_type != DeviceType::Camera);
    assert_eq!(devices.len(), 2);
    drop(service);
    for device in devices {
        let configurations = device.get_stream_configurations(None).await.unwrap();
        assert_eq!(
            configurations,
            [DeviceStreamConfiguration::new(
                format!("opaque:{}", device.id),
                device.id,
                DeviceStreamFormat::Audio(AudioFormat {
                    sample_rate: 48_000,
                    channels: 2,
                    sample_format: if device.device_type == DeviceType::Microphone {
                        "F32LE"
                    } else {
                        "F32P"
                    }
                    .into(),
                    channel_layout: vec!["FL".into(), "FR".into()],
                    interleaved: device.device_type == DeviceType::Microphone,
                }),
            )]
        );
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
    let readiness = Media::connect(Some(endpoint.clone()));
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
        Media::connect(Some(endpoint.clone())),
    )
    .await
    .expect("already-serving health did not complete readiness")
    .expect("readiness failed for an already-serving service");

    server.abort();
    let _ = server.await;
}
