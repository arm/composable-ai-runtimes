// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use super::parameters::{FrameRate, Resolution, StreamFormat, StreamFormatFilter};
use super::snapshot::{SnapshotCamera, SnapshotError, list_camera_formats, list_cameras};
use tokio::task;
use tonic::{Request, Response, Status};

pub mod pipewire {
    tonic::include_proto!("camera.pipewire.v1");
}

use pipewire::camera_service_server::CameraService;
use pipewire::{
    ListCamerasResponse, ListRequest, StreamConfigurationRequest, StreamConfigurationResponse,
};
use tracing::{debug, warn};

#[derive(Clone, Copy)]
pub(crate) struct CameraServiceProvider {
    pub(crate) list_cameras: fn() -> Result<Vec<SnapshotCamera>, SnapshotError>,
    pub(crate) list_camera_formats:
        fn(u64, Option<StreamFormatFilter>) -> Result<(u64, Vec<StreamFormat>), SnapshotError>,
}

impl Default for CameraServiceProvider {
    fn default() -> Self {
        Self {
            list_cameras,
            list_camera_formats,
        }
    }
}

#[derive(Clone, Default)]
pub struct CameraApiService {
    pub(crate) provider: CameraServiceProvider,
}

impl From<SnapshotCamera> for pipewire::Camera {
    fn from(camera: SnapshotCamera) -> Self {
        Self {
            id: camera.object_serial,
            name: camera.name,
        }
    }
}

impl From<pipewire::StreamFormat> for StreamFormatFilter {
    fn from(format: pipewire::StreamFormat) -> Self {
        Self {
            resolution: format.resolution.map(|resolution| Resolution {
                width: resolution.width,
                height: resolution.height,
            }),
            pixel_format: format.pixel_format,
            frame_rate: format.frame_rate.map(|frame_rate| FrameRate {
                numerator: frame_rate.numerator,
                denominator: frame_rate.denominator,
            }),
        }
    }
}

impl From<StreamFormat> for pipewire::StreamFormat {
    fn from(format: StreamFormat) -> Self {
        Self {
            resolution: Some(pipewire::Resolution {
                width: format.resolution.width,
                height: format.resolution.height,
            }),
            pixel_format: format.pixel_format,
            frame_rate: Some(pipewire::FrameRate {
                numerator: format.frame_rate.numerator,
                denominator: format.frame_rate.denominator,
            }),
        }
    }
}

pub(crate) fn map_snapshot_error(err: SnapshotError) -> Status {
    match err {
        SnapshotError::NotFound(camera_id) => {
            Status::not_found(format!("camera {camera_id} was not found"))
        }
        SnapshotError::Unavailable(message) => Status::unavailable(message),
    }
}

pub(super) fn validate_stream_configuration_request(
    request: &StreamConfigurationRequest,
) -> Result<(), Status> {
    if request.camera_id == 0 {
        return Err(Status::invalid_argument(
            "camera_id must be greater than zero",
        ));
    }

    if let Some(format) = &request.format {
        if format
            .resolution
            .as_ref()
            .is_some_and(|resolution| resolution.width == 0 || resolution.height == 0)
        {
            return Err(Status::invalid_argument(
                "resolution width and height must be greater than zero",
            ));
        }

        if format
            .frame_rate
            .as_ref()
            .is_some_and(|frame_rate| frame_rate.numerator == 0 || frame_rate.denominator == 0)
        {
            return Err(Status::invalid_argument(
                "frame rate numerator and denominator must be greater than zero",
            ));
        }

        if !format.pixel_format.is_empty()
            && !format
                .pixel_format
                .chars()
                .all(|character| character.is_ascii_alphanumeric() || character == '_')
        {
            return Err(Status::invalid_argument(
                "pixel_format contains invalid characters",
            ));
        }
    }

    Ok(())
}

#[tonic::async_trait]
impl CameraService for CameraApiService {
    async fn list_cameras(
        &self,
        request: Request<ListRequest>,
    ) -> Result<Response<ListCamerasResponse>, Status> {
        let remote_addr = request.remote_addr();
        debug!(?remote_addr, "listing cameras");

        let cameras = task::spawn_blocking(self.provider.list_cameras)
            .await
            .map_err(|err| {
                warn!(?remote_addr, error = %err, "camera listing task failed");
                Status::unavailable(format!("camera listing task failed: {err}"))
            })?
            .map_err(|err| {
                warn!(?remote_addr, error = %err, "failed to list cameras");
                map_snapshot_error(err)
            })?;
        let camera_count = cameras.len();
        let cameras = cameras.into_iter().map(pipewire::Camera::from).collect();

        let response = Response::new(ListCamerasResponse { cameras });

        debug!(?remote_addr, camera_count, "listed cameras");

        Ok(response)
    }

    async fn get_stream_configurations(
        &self,
        request: Request<StreamConfigurationRequest>,
    ) -> Result<Response<StreamConfigurationResponse>, Status> {
        let remote_addr = request.remote_addr();

        let request = request.into_inner();
        validate_stream_configuration_request(&request)?;
        let camera_id = request.camera_id;
        let filter = request.format.map(StreamFormatFilter::from);
        let list_camera_formats = self.provider.list_camera_formats;

        let (target, formats) = task::spawn_blocking(move || {
            list_camera_formats(camera_id, filter)
        })
        .await
        .map_err(|err| {
            warn!(?remote_addr, error = %err, "camera format collection task failed");
            Status::unavailable(format!("camera format collection task failed: {err}"))
        })?
        .map_err(|err| {
            warn!(?remote_addr, error = %err, camera_id, "failed to collect camera formats");
            map_snapshot_error(err)
        })?;

        let target = target.to_string();
        let configuration_count = formats.len();
        let configurations = formats
            .into_iter()
            .map(|format| pipewire::StreamConfiguration {
                target: target.clone(),
                camera_id,
                format: Some(format.into()),
            })
            .collect();

        debug!(
            ?remote_addr,
            camera_id, configuration_count, "listed stream configurations"
        );

        Ok(Response::new(StreamConfigurationResponse {
            configurations,
        }))
    }
}
