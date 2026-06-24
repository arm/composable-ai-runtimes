use std::cell::{Cell, RefCell};
use std::time::Duration;

use tonic::Request;
use tonic::transport::Channel;

use super::pipewire_client::{
    CameraError, CameraOptions, CapturedFrame, DEFAULT_FRAME_TIMEOUT, PipeWireCameraSession,
    capture_single_frame, capture_single_frame_with_timeout, validate_camera_options,
    validate_frame_timeout,
};

pub(super) mod pipewire {
    tonic::include_proto!("camera.pipewire.v1");
}

use pipewire::ListRequest;
use pipewire::camera_service_client::CameraServiceClient;

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
    pub id: u64,
    pub name: String,
    pub supported_formats: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct Camera {
    camera_id: u64,
    options: CameraOptions,
}

impl Camera {
    pub fn new(camera_id: u64, options: CameraOptions) -> Result<Self, CameraError> {
        validate_camera_options(camera_id, &options)?;

        Ok(Self { camera_id, options })
    }

    pub fn get_latest_frame(&self) -> Result<CapturedFrame, CameraError> {
        capture_single_frame(self.camera_id, &self.options)
    }

    pub fn get_latest_frame_with_timeout(
        &self,
        timeout: Duration,
    ) -> Result<CapturedFrame, CameraError> {
        validate_frame_timeout(timeout)?;
        capture_single_frame_with_timeout(self.camera_id, &self.options, timeout)
    }
}

pub struct CameraSession {
    session: RefCell<Option<PipeWireCameraSession>>,
    closed: Cell<bool>,
}

impl CameraSession {
    pub fn open(camera_id: u64, options: CameraOptions) -> Result<Self, CameraError> {
        let session = PipeWireCameraSession::open(camera_id, &options)?;

        Ok(Self {
            session: RefCell::new(Some(session)),
            closed: Cell::new(false),
        })
    }

    #[cfg(test)]
    pub(crate) fn closed_for_test() -> Self {
        Self {
            session: RefCell::new(None),
            closed: Cell::new(true),
        }
    }

    pub fn get_latest_frame(&self) -> Result<CapturedFrame, CameraError> {
        self.get_latest_frame_with_timeout(DEFAULT_FRAME_TIMEOUT)
    }

    pub fn get_latest_frame_with_timeout(
        &self,
        timeout: Duration,
    ) -> Result<CapturedFrame, CameraError> {
        validate_frame_timeout(timeout)?;
        if self.closed.get() {
            return Err(CameraError::CaptureFailed(
                "camera session is closed".to_string(),
            ));
        }

        let mut session = self.session.borrow_mut();
        let session = session
            .as_mut()
            .ok_or_else(|| CameraError::CaptureFailed("camera session is closed".to_string()))?;
        session.read_frame(timeout)
    }

    pub fn close(&self) -> Result<(), CameraError> {
        if self.closed.replace(true) {
            return Ok(());
        }

        let Some(mut session) = self.session.borrow_mut().take() else {
            return Ok(());
        };
        session.close()
    }

    pub fn is_closed(&self) -> bool {
        self.closed.get()
    }
}

impl Drop for CameraSession {
    fn drop(&mut self) {
        let _ = self.close();
    }
}

pub struct CameraService {
    client: CameraServiceClient<Channel>,
}

impl CameraService {
    pub async fn new(endpoint: Option<String>) -> Result<Self, CameraServiceError> {
        let endpoint = endpoint.unwrap_or_else(|| DEFAULT_CAMERA_SERVICE_ENDPOINT.to_string());
        let client = CameraServiceClient::connect(endpoint)
            .await
            .map_err(|error| transport_error(error.to_string()))?;

        Ok(Self { client })
    }

    pub fn open(&self, camera: &CameraMetadata) -> Result<Camera, CameraError> {
        Camera::new(camera.id, CameraOptions::default())
    }

    pub fn open_session(&self, camera: &CameraMetadata) -> Result<CameraSession, CameraError> {
        CameraSession::open(camera.id, CameraOptions::default())
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
                supported_formats: proto_camera.supported_formats,
            })
            .collect())
    }
}
