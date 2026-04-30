use super::snapshot::{SnapshotError, list_camera_metadata};
use tokio::task;
use tonic::{Request, Response, Status};

pub(super) mod pipewire {
    tonic::include_proto!("camera.pipewire.v1");
}

use pipewire::camera_service_server::CameraService;
use pipewire::{ListCamerasResponse, ListRequest};

pub struct CameraApiService;

pub(crate) fn map_snapshot_error(err: SnapshotError) -> Status {
    match err {
        SnapshotError::Unavailable(message) => Status::unavailable(message),
    }
}

#[tonic::async_trait]
impl CameraService for CameraApiService {
    async fn list_cameras(
        &self,
        _request: Request<ListRequest>,
    ) -> Result<Response<ListCamerasResponse>, Status> {
        let cameras = task::spawn_blocking(list_camera_metadata)
            .await
            .map_err(|err| Status::unavailable(format!("camera snapshot task failed: {err}")))?
            .map_err(map_snapshot_error)?;

        Ok(Response::new(ListCamerasResponse {
            cameras: cameras
                .into_iter()
                .map(|camera| pipewire::Camera {
                    id: camera.id,
                    name: camera.name,
                })
                .collect(),
        }))
    }
}
