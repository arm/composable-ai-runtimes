use tonic::Request;
use tonic::transport::Channel;

use super::pipewire_client::{
    CameraError, CameraOptions, CapturedFrame, capture_single_frame, validate_camera_options,
};

pub(super) mod pipewire {
    tonic::include_proto!("camera.pipewire.v1");
}

use pipewire::ListRequest;
use pipewire::pipewire_service_client::PipewireServiceClient;

pub struct CameraMetadata {
    pub id: u32,
    pub name: String,
}

#[derive(Debug, Clone)]
pub struct Camera {
    camera_id: u32,
    options: CameraOptions,
}

impl Camera {
    pub fn new(camera_id: u32, options: CameraOptions) -> Result<Self, CameraError> {
        validate_camera_options(camera_id, &options)?;

        Ok(Self { camera_id, options })
    }

    pub fn get_latest_frame(&self) -> Result<CapturedFrame, CameraError> {
        capture_single_frame(self.camera_id, &self.options)
    }
}

pub struct CameraService {
    client: PipewireServiceClient<Channel>,
}

impl CameraService {
    pub async fn new(endpoint: String) -> Result<Self, tonic::Status> {
        let client = PipewireServiceClient::connect(endpoint)
            .await
            .map_err(|e| tonic::Status::unavailable(e.to_string()))?;

        Ok(Self { client })
    }

    pub async fn list_cameras(&mut self) -> Result<Vec<CameraMetadata>, tonic::Status> {
        let response = self
            .client
            .list_cameras(Request::new(ListRequest {}))
            .await?
            .into_inner();
        Ok(response
            .cameras
            .into_iter()
            .map(|proto_camera| CameraMetadata {
                id: proto_camera.id,
                name: proto_camera.name,
            })
            .collect())
    }
}
