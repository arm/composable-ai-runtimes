// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::sync::Arc;
use tonic::Request;
use tonic::transport::{Channel, Endpoint};
use tonic_health::pb::{
    HealthCheckRequest, health_check_response::ServingStatus, health_client::HealthClient,
};

pub(crate) mod pipewire {
    include!("generated/camera.pipewire.v1.rs");
}

use pipewire::ListRequest;
use pipewire::camera_service_client::CameraServiceClient;

const DEFAULT_CAMERA_SERVICE_ENDPOINT: &str = "http://127.0.0.1:50051";

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

/// An error returned by the camera service client.
#[derive(Debug)]
pub enum CameraServiceError {
    /// The client could not connect to the service or complete a request.
    Transport(String),
    /// The camera service returned an incomplete response.
    InvalidResponse(String),
}

impl std::fmt::Display for CameraServiceError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Transport(message) => f.write_str(message),
            Self::InvalidResponse(message) => f.write_str(message),
        }
    }
}

impl std::error::Error for CameraServiceError {}

fn transport_error(message: impl Into<String>) -> CameraServiceError {
    CameraServiceError::Transport(message.into())
}

fn map_tonic_status(error: tonic::Status) -> CameraServiceError {
    transport_error(format!("{}: {}", error.code(), error.message()))
}

/// Describes a camera reported by the camera service.
pub struct Camera {
    /// The camera identifier assigned by the service.
    pub id: u64,
    /// The human-readable camera name.
    pub name: String,
    service: CameraService,
}

impl Camera {
    /// Discover configurations for this camera, optionally constrained by a filter.
    ///
    /// # Errors
    ///
    /// Returns [`CameraServiceError::Transport`] if discovery fails, or
    /// [`CameraServiceError::InvalidResponse`] if the response is incomplete.
    pub async fn get_stream_configurations(
        &self,
        filter: Option<StreamFormatFilter>,
    ) -> Result<Vec<StreamConfiguration>, CameraServiceError> {
        let mut service = self.service.clone();
        service.get_stream_configurations(self.id, filter).await
    }
}

/// A frame's dimensions in pixels.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Resolution {
    /// Frame width in pixels.
    pub width: u32,
    /// Frame height in pixels.
    pub height: u32,
}

/// Frames per second expressed as an exact fraction.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FrameRate {
    /// Fraction numerator.
    pub numerator: u32,
    /// Fraction denominator.
    pub denominator: u32,
}

/// A concrete camera stream format.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StreamFormat {
    /// Frame dimensions.
    pub resolution: Resolution,
    /// PipeWire pixel format name.
    pub pixel_format: String,
    /// Frames per second.
    pub frame_rate: FrameRate,
}

/// Optional constraints on stream configuration discovery.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct StreamFormatFilter {
    /// Requested frame dimensions, or any dimensions when absent.
    pub resolution: Option<Resolution>,
    /// Requested pixel format, or any format when absent.
    pub pixel_format: Option<String>,
    /// Requested frame rate, or any rate when absent.
    pub frame_rate: Option<FrameRate>,
}

/// An immutable camera stream configuration, discovered or supplied by the caller.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StreamConfiguration {
    target: String,
    camera_id: u64,
    format: StreamFormat,
}

impl StreamConfiguration {
    /// Creates a configuration from caller-supplied values without camera discovery.
    ///
    /// Values are preserved unchanged. The caller must ensure that the target,
    /// camera, and format are supported; the consuming service validates the request.
    pub fn new(target: impl Into<String>, camera_id: u64, format: StreamFormat) -> Self {
        Self {
            target: target.into(),
            camera_id,
            format,
        }
    }

    /// Returns the opaque PipeWire target to pass unchanged to consumers.
    pub fn target(&self) -> &str {
        &self.target
    }

    /// Returns the camera identifier associated with this configuration.
    pub fn camera_id(&self) -> u64 {
        self.camera_id
    }

    /// Returns the concrete stream format.
    pub fn format(&self) -> &StreamFormat {
        &self.format
    }
}

impl From<StreamFormatFilter> for pipewire::StreamFormat {
    fn from(filter: StreamFormatFilter) -> Self {
        Self {
            resolution: filter.resolution.map(|value| pipewire::Resolution {
                width: value.width,
                height: value.height,
            }),
            pixel_format: filter.pixel_format.unwrap_or_default(),
            frame_rate: filter.frame_rate.map(|value| pipewire::FrameRate {
                numerator: value.numerator,
                denominator: value.denominator,
            }),
        }
    }
}

impl TryFrom<pipewire::StreamConfiguration> for StreamConfiguration {
    type Error = CameraServiceError;

    fn try_from(value: pipewire::StreamConfiguration) -> Result<Self, Self::Error> {
        let format = value.format.ok_or_else(|| {
            CameraServiceError::InvalidResponse("stream configuration is missing its format".into())
        })?;
        let resolution = format.resolution.ok_or_else(|| {
            CameraServiceError::InvalidResponse("stream format is missing its resolution".into())
        })?;
        let frame_rate = format.frame_rate.ok_or_else(|| {
            CameraServiceError::InvalidResponse("stream format is missing its frame rate".into())
        })?;
        Ok(Self::new(
            value.target,
            value.camera_id,
            StreamFormat {
                pixel_format: format.pixel_format,
                resolution: Resolution {
                    width: resolution.width,
                    height: resolution.height,
                },
                frame_rate: FrameRate {
                    numerator: frame_rate.numerator,
                    denominator: frame_rate.denominator,
                },
            },
        ))
    }
}

/// A client for discovering cameras exposed by the Cairn camera service.
#[derive(Clone)]
pub struct CameraService {
    client: Arc<CameraServiceClient<Channel>>,
}

impl CameraService {
    /// Discover stream configurations for a camera, optionally filtered by format.
    ///
    /// # Errors
    ///
    /// Returns [`CameraServiceError::Transport`] if the request fails, or
    /// [`CameraServiceError::InvalidResponse`] if the response omits a required
    /// format, resolution, or frame rate.
    pub async fn get_stream_configurations(
        &mut self,
        camera_id: u64,
        filter: Option<StreamFormatFilter>,
    ) -> Result<Vec<StreamConfiguration>, CameraServiceError> {
        let mut client = self.client.as_ref().clone();
        let response = client
            .get_stream_configurations(Request::new(pipewire::StreamConfigurationRequest {
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

    /// Connects to the camera service.
    ///
    /// Pass `None` to use the default endpoint, `http://127.0.0.1:50051`.
    ///
    /// # Errors
    ///
    /// Returns [`CameraServiceError::Transport`] when the client cannot connect to the endpoint.
    pub async fn new(endpoint: Option<String>) -> Result<Self, CameraServiceError> {
        let endpoint = endpoint.unwrap_or_else(|| DEFAULT_CAMERA_SERVICE_ENDPOINT.to_string());
        let channel = wait_for_serving(&endpoint)
            .await
            .map_err(CameraServiceError::Transport)?;
        Ok(Self {
            client: Arc::new(CameraServiceClient::new(channel)),
        })
    }

    /// Returns metadata for the cameras currently reported by the service.
    ///
    /// # Errors
    ///
    /// Returns [`CameraServiceError::Transport`] when the request fails.
    pub async fn list_cameras(&mut self) -> Result<Vec<Camera>, CameraServiceError> {
        let mut client = self.client.as_ref().clone();
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
