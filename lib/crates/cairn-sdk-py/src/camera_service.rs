use cairn_sdk::camera_service;
use pyo3::prelude::{Bound, PyRef, PyResult};
use pyo3::types::PyModule;
use pyo3::{pyclass, pymethods};
use tokio::runtime::Runtime;

use crate::camera::PyCamera;
use crate::util::{PyCameraMetadata, build_runtime, map_camera_error, map_transport_error};

#[pyclass(unsendable, module = "cairn_sdk", name = "CameraService")]
pub struct PyCameraService {
    runtime: Runtime,
    inner: camera_service::CameraService,
}

#[pymethods]
impl PyCameraService {
    #[new]
    fn new() -> PyResult<Self> {
        let runtime = build_runtime()?;
        let inner = runtime
            .block_on(camera_service::CameraService::new(None))
            .map_err(map_transport_error)?;

        Ok(Self { runtime, inner })
    }

    fn list_camera_metadata(&mut self) -> PyResult<Vec<PyCameraMetadata>> {
        let cameras = self
            .runtime
            .block_on(self.inner.list_camera_metadata())
            .map_err(map_transport_error)?;

        Ok(cameras.into_iter().map(PyCameraMetadata::from).collect())
    }

    fn open(&self, camera: PyRef<'_, PyCameraMetadata>) -> PyResult<PyCamera> {
        let camera = self
            .inner
            .open(&camera_service::CameraMetadata::from(&*camera))
            .map_err(map_camera_error)?;

        Ok(PyCamera { inner: camera })
    }
}

pub(crate) fn add_camera_service_bindings(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PyCameraService>()?;
    Ok(())
}
