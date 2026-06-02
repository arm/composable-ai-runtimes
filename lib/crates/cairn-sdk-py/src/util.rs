use cairn_sdk::camera_service;
use numpy::{IntoPyArray, PyArray1};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::{Bound, Py, PyErr, PyResult, Python};
use pyo3::types::{PyModule, PyModuleMethods};
use pyo3::{pyclass, pymethods};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
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

/// Information about a camera returned by `CameraService.list_camera_metadata()`.
///
/// Attributes
/// ----------
/// id:
///     Camera identifier used when opening the camera.
/// name:
///     Human-readable camera name.
/// supported_formats:
///     Pixel formats reported by the camera service.
#[gen_stub_pyclass]
#[pyclass(skip_from_py_object, module = "cairn_sdk", name = "CameraMetadata")]
#[derive(Clone)]
pub struct PyCameraMetadata {
    #[pyo3(get)]
    id: u32,
    #[pyo3(get)]
    name: String,
    #[pyo3(get)]
    supported_formats: Vec<String>,
}

impl From<camera_service::CameraMetadata> for PyCameraMetadata {
    fn from(value: camera_service::CameraMetadata) -> Self {
        Self {
            id: value.id,
            name: value.name,
            supported_formats: value.supported_formats,
        }
    }
}

impl From<&PyCameraMetadata> for camera_service::CameraMetadata {
    fn from(value: &PyCameraMetadata) -> Self {
        camera_service::CameraMetadata {
            id: value.id,
            name: value.name.clone(),
            supported_formats: value.supported_formats.clone(),
        }
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl PyCameraMetadata {
    /// Return a string representation of the camera metadata.
    #[gen_stub(skip)]
    fn __repr__(&self) -> String {
        format!("CameraMetadata(id={}, name={:?})", self.id, self.name)
    }
}

/// Frame data returned by `Camera.get_latest_frame()`.
///
/// Attributes
/// ----------
/// pixels:
///     Frame bytes as a one-dimensional NumPy array of `uint8`.
/// width:
///     Frame width in pixels.
/// height:
///     Frame height in pixels.
/// stride:
///     Number of bytes in each image row.
/// pixel_format:
///     Pixel format name for the frame data.
#[gen_stub_pyclass]
#[pyclass(unsendable, module = "cairn_sdk", name = "Frame")]
pub struct PyFrame {
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

#[gen_stub_pymethods]
#[pymethods]
impl PyFrame {
    /// Frame bytes as a one-dimensional NumPy array of `uint8`.
    ///
    /// Returns
    /// -------
    /// numpy.typing.NDArray[numpy.uint8]
    ///     The raw pixel buffer for the frame.
    #[getter]
    #[gen_stub(override_return_type(type_repr = "numpy.typing.NDArray[numpy.uint8]", imports=("numpy", "numpy.typing")))]
    fn pixels(&self, py: Python<'_>) -> Py<PyArray1<u8>> {
        self.pixels.clone_ref(py)
    }

    /// Return a string representation of the frame metadata.
    #[gen_stub(skip)]
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
