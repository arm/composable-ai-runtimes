use super::snapshot::{SnapshotCamera, SnapshotError, list_camera_metadata};
use tokio::task;
use tonic::{Request, Response, Status};

pub mod pipewire {
    tonic::include_proto!("camera.pipewire.v1");
}

use pipewire::camera_service_server::CameraService;
use pipewire::{ListCamerasResponse, ListRequest};
use tracing::{debug, warn};

#[derive(Clone, Copy)]
pub(crate) struct CameraServiceProvider {
    pub(crate) list_cameras: fn() -> Result<Vec<SnapshotCamera>, SnapshotError>,
}

impl Default for CameraServiceProvider {
    fn default() -> Self {
        Self {
            list_cameras: list_camera_metadata,
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
            supported_formats: camera
                .supported_formats
                .into_iter()
                .map(|format| format.to_string())
                .collect(),
        }
    }
}

pub(crate) fn map_snapshot_error(err: SnapshotError) -> Status {
    match err {
        SnapshotError::Unavailable(message) => Status::unavailable(message),
    }
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
}
