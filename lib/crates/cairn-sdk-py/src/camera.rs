use crate::util::{PyFrame, add_camera_shared_bindings, map_camera_error};
use cairn_sdk::camera_service;
use pyo3::prelude::{Bound, PyResult, Python};
use pyo3::types::{PyModule, PyModuleMethods};
use pyo3::{pyclass, pymethods};

#[pyclass(unsendable, module = "cairn_sdk", name = "Camera")]
pub struct PyCamera {
    pub(crate) inner: camera_service::Camera,
}

#[pymethods]
impl PyCamera {
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
