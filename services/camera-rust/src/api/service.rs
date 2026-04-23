use tonic::{Request, Response, Status};

pub(super) mod pipewire {
    tonic::include_proto!("camera.pipewire.v1");
}

use pipewire::camera_service_server::CameraService;
use pipewire::{ListCamerasResponse, ListRequest};

pub struct CameraApiService;

#[tonic::async_trait]
impl CameraService for CameraApiService {
    async fn list_cameras(
        &self,
        _request: Request<ListRequest>,
    ) -> Result<Response<ListCamerasResponse>, Status> {
        Ok(Response::new(ListCamerasResponse { cameras: vec![] }))
    }
}
