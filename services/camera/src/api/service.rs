use super::snapshot::{SnapshotCamera, SnapshotError, list_camera_metadata};
use tokio::task;
use tonic::{Request, Response, Status};

pub(super) mod pipewire {
    tonic::include_proto!("camera.pipewire.v1");
}

use pipewire::camera_service_server::CameraService;
use pipewire::{ListCamerasResponse, ListRequest};
use tracing::{debug, warn};

pub struct CameraApiService;

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

        let cameras = task::spawn_blocking(list_camera_metadata)
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

        let response = Response::new(ListCamerasResponse {
            cameras: cameras.into_iter().map(pipewire::Camera::from).collect(),
        });

        debug!(?remote_addr, camera_count, "listed cameras");

        Ok(response)
    }
}
