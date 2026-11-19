// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use crate::media;
use crate::media::media_service_client::MediaServiceClient;
use crate::media::{DeviceType as ProtoDeviceType, ListRequest};
use crate::stream_configuration::{
    DeviceStreamConfiguration, DeviceStreamFormatFilter, StreamConfiguration, StreamFormatFilter,
};
use tonic::Request;
use tonic::transport::{Channel, Endpoint};
use tonic_health::pb::{
    HealthCheckRequest, health_check_response::ServingStatus, health_client::HealthClient,
};

const DEFAULT_MEDIA_SERVICE_ENDPOINT: &str = "http://127.0.0.1:50051";

pub(super) async fn wait_for_serving(endpoint: &str) -> Result<Channel, String> {
    let ready_channel = async {
        let channel = Endpoint::from_shared(endpoint.to_owned())
            .map_err(|error| error.to_string())?
            .connect()
            .await
            .map_err(|error| error.to_string())?;
        let mut updates = HealthClient::new(channel.clone())
            .watch(HealthCheckRequest::default())
            .await
            .map_err(|error| error.to_string())?
            .into_inner();
        while let Some(response) = updates.message().await.map_err(|error| error.to_string())? {
            if response.status() == ServingStatus::Serving {
                return Ok(channel);
            }
        }
        Err("health watch ended before SERVING".to_string())
    };
    tokio::time::timeout(std::time::Duration::from_secs(30), ready_channel)
        .await
        .map_err(|_| format!("service at {endpoint} did not report SERVING within 30s"))?
        .map_err(|error| format!("health watch at {endpoint} failed: {error}"))
}

/// An error returned by the media service client.
#[derive(Debug)]
pub enum MediaError {
    /// No device with the requested ID is currently present.
    NotFound(u64),
    /// The client could not connect to the service or complete a request.
    Transport(String),
    /// The media service returned an incomplete response.
    InvalidResponse(String),
}

impl std::fmt::Display for MediaError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::NotFound(device_id) => write!(f, "device {device_id} was not found"),
            Self::Transport(message) => f.write_str(message),
            Self::InvalidResponse(message) => f.write_str(message),
        }
    }
}

impl std::error::Error for MediaError {}

fn transport_error(message: impl Into<String>) -> MediaError {
    MediaError::Transport(message.into())
}

fn map_tonic_status(error: tonic::Status) -> MediaError {
    transport_error(format!("{}: {}", error.code(), error.message()))
}

/// The kind of media device.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DeviceType {
    /// A video capture device.
    Camera,
    /// An audio capture device.
    Microphone,
    /// An audio playback device.
    Speaker,
}

impl From<DeviceType> for ProtoDeviceType {
    fn from(value: DeviceType) -> Self {
        match value {
            DeviceType::Camera => Self::Camera,
            DeviceType::Microphone => Self::Microphone,
            DeviceType::Speaker => Self::Speaker,
        }
    }
}

/// Selects a media device by ID or type.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DeviceSelector {
    /// ID of the device to select.
    Id(u64),
    /// Type of the device to select.
    Type(DeviceType),
}

/// Describes a device reported by the media service.
pub struct Device {
    /// The device identifier assigned by the service.
    pub id: u64,
    /// The human-readable device name.
    pub name: String,
    /// The kind of device.
    pub device_type: DeviceType,
    service: Media,
}

impl Device {
    /// Returns supported configurations, optionally constrained by a format filter.
    /// Video filters apply only to cameras; pass `None` for unfiltered discovery.
    ///
    /// # Errors
    ///
    /// Returns [`MediaError::Transport`] if discovery fails, or
    /// [`MediaError::InvalidResponse`] if a configuration is incomplete.
    pub async fn get_stream_configurations(
        &self,
        filter: Option<DeviceStreamFormatFilter>,
    ) -> Result<Vec<DeviceStreamConfiguration>, MediaError> {
        self.service
            .get_device_stream_configurations(self.id, filter)
            .await
    }
}

/// Describes a camera reported by the media service.
pub struct Camera {
    /// The camera identifier assigned by the service.
    pub id: u64,
    /// The human-readable camera name.
    pub name: String,
    service: Media,
}

impl Camera {
    /// Discover configurations for this camera, optionally constrained by a filter.
    ///
    /// # Errors
    ///
    /// Returns [`MediaError::Transport`] if discovery fails, or
    /// [`MediaError::InvalidResponse`] if the response is incomplete.
    pub async fn get_stream_configurations(
        &self,
        filter: Option<StreamFormatFilter>,
    ) -> Result<Vec<StreamConfiguration>, MediaError> {
        let mut service = self.service.clone();
        service.get_stream_configurations(self.id, filter).await
    }
}

/// A client for discovering devices exposed by the Cairn media service.
#[derive(Clone)]
pub struct Media {
    client: MediaServiceClient<Channel>,
}

impl Media {
    /// Returns all devices, optionally filtered by type.
    /// Devices with unrecognized types are omitted.
    ///
    /// # Errors
    ///
    /// Returns [`MediaError::Transport`] when discovery fails.
    pub async fn list_devices(
        &self,
        device_type: Option<DeviceType>,
    ) -> Result<Vec<Device>, MediaError> {
        let mut client = self.client.clone();
        let response = client
            .list_devices(Request::new(media::ListDevicesRequest {
                device_type: device_type.map(|value| ProtoDeviceType::from(value) as i32),
            }))
            .await
            .map_err(map_tonic_status)?
            .into_inner();
        Ok(response
            .devices
            .into_iter()
            .filter_map(|proto_device| {
                let device_type = match ProtoDeviceType::try_from(proto_device.device_type).ok()? {
                    ProtoDeviceType::Camera => DeviceType::Camera,
                    ProtoDeviceType::Microphone => DeviceType::Microphone,
                    ProtoDeviceType::Speaker => DeviceType::Speaker,
                };
                Some(Device {
                    id: proto_device.id,
                    name: proto_device.name,
                    device_type,
                    service: self.clone(),
                })
            })
            .collect())
    }

    /// Selects by ID, or returns the first device of the requested type.
    ///
    /// Type selection returns `None` when no devices match.
    /// IDs may change after a reconnect or restart.
    ///
    /// # Errors
    ///
    /// Returns [`MediaError::NotFound`] for an absent ID, or propagates
    /// discovery errors from [`Self::list_devices`].
    pub async fn get_device(&self, selector: DeviceSelector) -> Result<Option<Device>, MediaError> {
        match selector {
            DeviceSelector::Id(id) => self
                .list_devices(None)
                .await?
                .into_iter()
                .find(|device| device.id == id)
                .map(Some)
                .ok_or(MediaError::NotFound(id)),
            DeviceSelector::Type(device_type) => Ok(self
                .list_devices(Some(device_type))
                .await?
                .into_iter()
                .next()),
        }
    }

    /// Returns supported configurations, or an empty list if none match the filter.
    /// Video filters apply only to cameras; pass `None` for unfiltered discovery.
    ///
    /// # Errors
    ///
    /// Returns [`MediaError::Transport`] if the request fails, or
    /// [`MediaError::InvalidResponse`] if a configuration is incomplete.
    pub async fn get_device_stream_configurations(
        &self,
        device_id: u64,
        filter: Option<DeviceStreamFormatFilter>,
    ) -> Result<Vec<DeviceStreamConfiguration>, MediaError> {
        let mut client = self.client.clone();
        let response = client
            .get_device_stream_configurations(Request::new(
                media::DeviceStreamConfigurationRequest {
                    device_id,
                    filter: filter.map(Into::into),
                },
            ))
            .await
            .map_err(map_tonic_status)?
            .into_inner();
        response
            .configurations
            .into_iter()
            .map(DeviceStreamConfiguration::try_from)
            .collect()
    }

    /// Discover stream configurations for a camera, optionally filtered by format.
    ///
    /// # Errors
    ///
    /// Returns [`MediaError::Transport`] if the request fails, or
    /// [`MediaError::InvalidResponse`] if the response omits a required
    /// format, resolution, or frame rate.
    pub async fn get_stream_configurations(
        &mut self,
        camera_id: u64,
        filter: Option<StreamFormatFilter>,
    ) -> Result<Vec<StreamConfiguration>, MediaError> {
        let mut client = self.client.clone();
        let response = client
            .get_stream_configurations(Request::new(media::StreamConfigurationRequest {
                camera_id,
                format: filter.map(Into::into),
            }))
            .await
            .map_err(map_tonic_status)?
            .into_inner();
        response
            .configurations
            .into_iter()
            .map(StreamConfiguration::try_from)
            .collect()
    }

    /// Connects to the media service.
    ///
    /// Pass `None` to use the default endpoint, `http://127.0.0.1:50051`.
    ///
    /// # Errors
    ///
    /// Returns [`MediaError::Transport`] when the client cannot connect to the endpoint.
    pub async fn connect(endpoint: Option<String>) -> Result<Self, MediaError> {
        let endpoint = endpoint.unwrap_or_else(|| DEFAULT_MEDIA_SERVICE_ENDPOINT.to_string());
        let channel = wait_for_serving(&endpoint)
            .await
            .map_err(MediaError::Transport)?;
        Ok(Self {
            client: MediaServiceClient::new(channel),
        })
    }

    /// Returns the camera with the given ID, or the first listed camera when `None`.
    ///
    /// Returns `Ok(None)` if no ID is supplied and no cameras are available.
    /// IDs identify PipeWire objects and may change after a reconnect or restart.
    ///
    /// # Errors
    ///
    /// Returns [`MediaError::NotFound`] if the requested ID is not present,
    /// or [`MediaError::Transport`] when discovery fails.
    pub async fn get_camera(
        &mut self,
        camera_id: Option<&u64>,
    ) -> Result<Option<Camera>, MediaError> {
        let mut cameras = self.list_cameras().await?.into_iter();
        match camera_id {
            Some(&id) => cameras
                .find(|camera| camera.id == id)
                .map(Some)
                .ok_or(MediaError::NotFound(id)),
            None => Ok(cameras.next()),
        }
    }

    /// Returns metadata for the cameras currently reported by the service.
    ///
    /// # Errors
    ///
    /// Returns [`MediaError::Transport`] when the request fails.
    pub async fn list_cameras(&mut self) -> Result<Vec<Camera>, MediaError> {
        let mut client = self.client.clone();
        let response = client
            .list_cameras(Request::new(ListRequest {}))
            .await
            .map_err(map_tonic_status)?
            .into_inner();
        Ok(response
            .cameras
            .into_iter()
            .map(|proto_camera| Camera {
                id: proto_camera.id,
                name: proto_camera.name,
                service: self.clone(),
            })
            .collect())
    }
}
