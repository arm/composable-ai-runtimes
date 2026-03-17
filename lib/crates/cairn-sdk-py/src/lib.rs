mod camera;
mod camera_service;
mod util;

use pyo3::prelude::{Bound, PyResult};
use pyo3::pymodule;
use pyo3::types::PyModule;

#[pymodule]
fn _bindings(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("__doc__", "Python bindings for the Cairn SDK.")?;
    camera::add_camera_bindings(module)?;
    camera_service::add_camera_service_bindings(module)?;
    Ok(())
}
