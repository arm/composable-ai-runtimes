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

const DEFAULT_CAMERA_SERVICE_ENDPOINT: &str = "http://127.0.0.1:50051";

#[derive(Debug)]
pub enum CameraServiceError {
    Transport(String),
}

impl std::fmt::Display for CameraServiceError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Transport(message) => f.write_str(message),
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
    pub async fn new(endpoint: Option<String>) -> Result<Self, CameraServiceError> {
        let endpoint = endpoint.unwrap_or_else(|| DEFAULT_CAMERA_SERVICE_ENDPOINT.to_string());
        let client = PipewireServiceClient::connect(endpoint)
            .await
            .map_err(|error| transport_error(error.to_string()))?;

        Ok(Self { client })
    }

    pub fn open(&self, camera: &CameraMetadata) -> Result<Camera, CameraError> {
        Camera::new(camera.id, CameraOptions::default())
    }

    pub async fn list_camera_metadata(
        &mut self,
    ) -> Result<Vec<CameraMetadata>, CameraServiceError> {
        let response = self
            .client
            .list_cameras(Request::new(ListRequest {}))
            .await
            .map_err(map_tonic_status)?
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
