use crate::util::{PyFrame, add_camera_shared_bindings, map_camera_error};
use cairn_sdk::camera_service;
use pyo3::prelude::{Bound, PyResult, Python};
use pyo3::types::{PyModule, PyModuleMethods};
use pyo3::{pyclass, pymethods};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};

/// Handle for reading frames from an opened camera.
#[gen_stub_pyclass]
#[pyclass(unsendable, module = "cairn_sdk", name = "Camera")]
pub struct PyCamera {
    pub(crate) inner: camera_service::Camera,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyCamera {
    /// Return the latest frame available from this camera handle.
    ///
    /// Returns
    /// -------
    /// Frame
    ///     The most recent frame captured for this camera.
    ///
    /// The returned `Frame` exposes the pixel data and basic image metadata.
    #[pyo3(text_signature = "($self)")]
    #[gen_stub(override_return_type(type_repr = "'Frame'"))]
    fn get_latest_frame(&self, py: Python<'_>) -> PyResult<PyFrame> {
        self.inner
            .get_latest_frame()
            .map(|frame| PyFrame::from_rust(py, frame))
            .map_err(map_camera_error)
    }
}

pub(crate) fn add_camera_bindings(module: &Bound<'_, PyModule>) -> PyResult<()> {
    add_camera_shared_bindings(module)?;
    module.add_class::<PyCamera>()?;
    Ok(())
}
