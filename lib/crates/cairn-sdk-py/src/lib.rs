mod camera;
mod camera_service;
mod util;

use pyo3::prelude::{Bound, PyResult};
use pyo3::pymodule;
use pyo3::types::{PyModule, PyModuleMethods};
use pyo3_stub_gen::{Result as StubResult, StubInfo};
use std::path::Path;

/// Python interface for the Cairn SDK.
///
/// Use this module to discover cameras, open a camera and read its frames.
#[pymodule]
fn _bindings(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("__doc__", "Python bindings for the Cairn SDK.")?;
    camera::add_camera_bindings(module)?;
    camera_service::add_camera_service_bindings(module)?;
    Ok(())
}

pyo3_stub_gen::module_doc!(
    "cairn_sdk",
    "Python interface for the Cairn SDK.\n\nUse this module to discover cameras, open a camera and read its frames."
);

pub fn stub_info() -> StubResult<StubInfo> {
    let project_root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .nth(2)
        .expect("crate manifest should be nested under the lib project root");

    StubInfo::from_pyproject_toml(project_root.join("pyproject.toml"))
}
