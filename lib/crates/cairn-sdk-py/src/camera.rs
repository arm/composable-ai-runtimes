use crate::util::{PyFrame, add_camera_shared_bindings, map_camera_error};
use cairn_sdk::camera_service;
use pyo3::prelude::{Bound, PyRef, PyResult, Python};
use pyo3::types::{PyAny, PyModule, PyModuleMethods};
use pyo3::{pyclass, pymethods};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
use std::cell::Cell;
use std::time::Duration;

const DEFAULT_TIMEOUT_MS: u64 = 5_000;

enum PyCameraInner {
    OneShot(camera_service::Camera),
    Session(camera_service::CameraSession),
}

/// Handle for reading frames from an opened camera.
#[gen_stub_pyclass]
#[pyclass(unsendable, module = "cairn_sdk", name = "Camera")]
pub struct PyCamera {
    inner: PyCameraInner,
    closed: Cell<bool>,
}

impl PyCamera {
    pub(crate) fn one_shot(inner: camera_service::Camera) -> Self {
        Self {
            inner: PyCameraInner::OneShot(inner),
            closed: Cell::new(false),
        }
    }

    pub(crate) fn session(inner: camera_service::CameraSession) -> Self {
        Self {
            inner: PyCameraInner::Session(inner),
            closed: Cell::new(false),
        }
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl PyCamera {
    /// Return the latest frame available from this camera handle.
    ///
    /// Parameters
    /// ----------
    /// timeout_ms:
    ///     Maximum time to wait for a frame, in milliseconds. Defaults to 5000.
    ///
    /// Returns
    /// -------
    /// Frame
    ///     The most recent frame captured for this camera.
    ///
    /// The returned `Frame` exposes the pixel data and basic image metadata.
    #[pyo3(signature = (timeout_ms=DEFAULT_TIMEOUT_MS))]
    #[pyo3(text_signature = "($self, timeout_ms=5000)")]
    #[gen_stub(override_return_type(type_repr = "'Frame'"))]
    fn get_latest_frame(&self, py: Python<'_>, timeout_ms: u64) -> PyResult<PyFrame> {
        let timeout = Duration::from_millis(timeout_ms);
        let frame = match &self.inner {
            PyCameraInner::OneShot(camera) => {
                if self.closed.get() {
                    return Err(map_camera_error(
                        camera_service::CameraError::CaptureFailed(
                            "camera session is closed".to_string(),
                        ),
                    ));
                }
                camera.get_latest_frame_with_timeout(timeout)
            }
            PyCameraInner::Session(camera) => camera.get_latest_frame_with_timeout(timeout),
        }
        .map_err(map_camera_error)?;

        Ok(PyFrame::from_rust(py, frame))
    }

    /// Close this camera handle and release any active capture session.
    #[pyo3(text_signature = "($self)")]
    fn close(&self) -> PyResult<()> {
        if self.closed.replace(true) {
            return Ok(());
        }

        match &self.inner {
            PyCameraInner::OneShot(_) => Ok(()),
            PyCameraInner::Session(camera) => camera.close().map_err(map_camera_error),
        }
    }

    /// Whether this camera handle has been closed.
    #[getter]
    fn closed(&self) -> bool {
        self.closed.get()
            || matches!(&self.inner, PyCameraInner::Session(camera) if camera.is_closed())
    }

    /// Enter a `with` block using this camera handle.
    #[gen_stub(override_return_type(type_repr = "'Camera'"))]
    fn __enter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    /// Exit a `with` block and close this camera handle.
    #[gen_stub(override_return_type(type_repr = "bool"))]
    #[pyo3(signature = (_exc_type=None, _exc_value=None, _traceback=None))]
    fn __exit__(
        &self,
        _exc_type: Option<&Bound<'_, PyAny>>,
        _exc_value: Option<&Bound<'_, PyAny>>,
        _traceback: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<bool> {
        self.close()?;
        Ok(false)
    }
}

pub(crate) fn add_camera_bindings(module: &Bound<'_, PyModule>) -> PyResult<()> {
    add_camera_shared_bindings(module)?;
    module.add_class::<PyCamera>()?;
    Ok(())
}
