use cairn_sdk::camera_service;
use pyo3::prelude::{Bound, PyRef, PyResult};
use pyo3::types::{PyModule, PyModuleMethods};
use pyo3::{pyclass, pymethods};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
use tokio::runtime::Runtime;

use crate::camera::PyCamera;
use crate::util::{PyCameraMetadata, build_runtime, map_camera_error, map_transport_error};

/// Class for discovering cameras and opening a camera connection.
///
/// Create `CameraService()`, call `list_camera_metadata()` to inspect available
/// cameras, then pass one of those results to `open()`.
#[gen_stub_pyclass]
#[pyclass(unsendable, module = "cairn_sdk", name = "CameraService")]
pub struct PyCameraService {
    runtime: Runtime,
    inner: camera_service::CameraService,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyCameraService {
    /// Create a camera service client.
    ///
    /// Returns
    /// -------
    /// CameraService
    ///     A service handle that can discover cameras and open them.
    #[new]
    #[pyo3(text_signature = "()")]
    #[gen_stub(override_return_type(type_repr = "'CameraService'"))]
    fn new() -> PyResult<Self> {
        let runtime = build_runtime()?;
        let inner = runtime
            .block_on(camera_service::CameraService::new(None))
            .map_err(map_transport_error)?;

        Ok(Self { runtime, inner })
    }

    /// Return metadata describing the cameras that are currently available.
    ///
    /// Returns
    /// -------
    /// list[CameraMetadata]
    ///     Camera descriptors that can be passed to `open()`.
    #[pyo3(text_signature = "($self)")]
    fn list_camera_metadata(&mut self) -> PyResult<Vec<PyCameraMetadata>> {
        let cameras = self
            .runtime
            .block_on(self.inner.list_camera_metadata())
            .map_err(map_transport_error)?;

        Ok(cameras.into_iter().map(PyCameraMetadata::from).collect())
    }

    /// Open a camera using a `CameraMetadata` object returned by `CameraService.list_camera_metadata()`.
    ///
    /// Parameters
    /// ----------
    /// camera:
    ///     The CameraMetadata object describing the camera to open the connection to.
    ///     `list_camera_metadata()`.
    ///
    /// Returns
    /// -------
    /// Camera
    ///     An opened camera handle that can be used to read frames.
    #[pyo3(text_signature = "($self, camera)")]
    fn open(
        &self,
        #[gen_stub(override_type(type_repr = "CameraMetadata"))] camera: PyRef<
            '_,
            PyCameraMetadata,
        >,
    ) -> PyResult<PyCamera> {
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
