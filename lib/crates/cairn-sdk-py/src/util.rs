use cairn_sdk::camera_service;
use numpy::{IntoPyArray, PyArray1};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::{Bound, Py, PyErr, PyResult, Python};
use pyo3::types::PyModule;
use pyo3::{pyclass, pymethods};
use tokio::runtime::{Builder, Runtime};

pub(crate) fn map_camera_error(error: camera_service::CameraError) -> PyErr {
    match error {
        camera_service::CameraError::Validation(message) => PyValueError::new_err(message),
        camera_service::CameraError::CaptureFailed(message) => PyRuntimeError::new_err(message),
    }
}

pub(crate) fn map_transport_error(error: camera_service::CameraServiceError) -> PyErr {
    match error {
        camera_service::CameraServiceError::Transport(message) => PyRuntimeError::new_err(message),
    }
}

pub(crate) fn build_runtime() -> PyResult<Runtime> {
    Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|error| PyRuntimeError::new_err(error.to_string()))
}

fn pixel_format_name(pixel_format: camera_service::CapturePixelFormat) -> &'static str {
    match pixel_format {
        camera_service::CapturePixelFormat::Yuy2 => "YUY2",
        camera_service::CapturePixelFormat::Uyvy => "UYVY",
        camera_service::CapturePixelFormat::Rgb => "RGB",
        camera_service::CapturePixelFormat::Bgr => "BGR",
        camera_service::CapturePixelFormat::Rgba => "RGBA",
        camera_service::CapturePixelFormat::Bgra => "BGRA",
    }
}

#[pyclass(module = "cairn_sdk", name = "CameraMetadata")]
#[derive(Clone)]
pub struct PyCameraMetadata {
    #[pyo3(get)]
    id: u32,
    #[pyo3(get)]
    name: String,
}

impl From<camera_service::CameraMetadata> for PyCameraMetadata {
    fn from(value: camera_service::CameraMetadata) -> Self {
        Self {
            id: value.id,
            name: value.name,
        }
    }
}

impl From<&PyCameraMetadata> for camera_service::CameraMetadata {
    fn from(value: &PyCameraMetadata) -> Self {
        camera_service::CameraMetadata {
            id: value.id,
            name: value.name.clone(),
        }
    }
}

#[pymethods]
impl PyCameraMetadata {
    fn __repr__(&self) -> String {
        format!("CameraMetadata(id={}, name={:?})", self.id, self.name)
    }
}

#[pyclass(unsendable, module = "cairn_sdk", name = "Frame")]
pub struct PyFrame {
    #[pyo3(get)]
    pixels: Py<PyArray1<u8>>,
    bytes_len: usize,
    #[pyo3(get)]
    width: u32,
    #[pyo3(get)]
    height: u32,
    #[pyo3(get)]
    stride: i32,
    #[pyo3(get)]
    pixel_format: String,
}

impl PyFrame {
    pub(crate) fn from_rust(py: Python<'_>, value: camera_service::CapturedFrame) -> Self {
        let bytes_len = value.pixels.len();
        let pixel_format = pixel_format_name(value.pixel_format).to_string();
        let pixels = value.pixels.into_pyarray(py).unbind();

        Self {
            pixels,
            bytes_len,
            width: value.width,
            height: value.height,
            stride: value.stride,
            pixel_format,
        }
    }
}

#[pymethods]
impl PyFrame {
    fn __repr__(&self) -> String {
        format!(
            "Frame(width={}, height={}, stride={}, pixel_format={:?}, bytes={})",
            self.width, self.height, self.stride, self.pixel_format, self.bytes_len
        )
    }
}

pub(crate) fn add_camera_shared_bindings(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PyCameraMetadata>()?;
    module.add_class::<PyFrame>()?;
    Ok(())
}
