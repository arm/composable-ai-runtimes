use cairn_sdk::camera_service;
use pyo3::prelude::{Bound, PyRef, PyResult};
use pyo3::types::{PyModule, PyModuleMethods};
use pyo3::{pyclass, pymethods};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
use tokio::runtime::Runtime;

use crate::camera::PyCamera;
use crate::util::{PyCameraMetadata, build_runtime, map_camera_error, map_transport_error};

/// Client for the Cairn camera service.
///
/// Connects to the camera service over gRPC, lists the cameras it reports, and
/// opens a camera handle for frame capture.
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
    /// Parameters
    /// ----------
    /// endpoint:
    ///     Camera service gRPC endpoint. Defaults to
    ///     `http://127.0.0.1:50051`.
    ///
    /// Returns
    /// -------
    /// CameraService
    ///     A service handle that can discover cameras and open them.
    #[new]
    #[pyo3(signature = (endpoint=None))]
    #[pyo3(text_signature = "(endpoint=None)")]
    #[gen_stub(override_return_type(type_repr = "'CameraService'"))]
    fn new(endpoint: Option<String>) -> PyResult<Self> {
        let runtime = build_runtime()?;
        let inner = runtime
            .block_on(camera_service::CameraService::new(endpoint))
            .map_err(map_transport_error)?;

        Ok(Self { runtime, inner })
    }

    /// List the cameras currently reported by the camera service.
    ///
    /// Returns
    /// -------
    /// list[CameraMetadata]
    ///     Camera descriptors returned by the camera service.
    #[pyo3(text_signature = "($self)")]
    fn list_camera_metadata(&mut self) -> PyResult<Vec<PyCameraMetadata>> {
        let cameras = self
            .runtime
            .block_on(self.inner.list_camera_metadata())
            .map_err(map_transport_error)?;

        Ok(cameras.into_iter().map(PyCameraMetadata::from).collect())
    }

    /// Open a camera returned by `list_camera_metadata()`.
    ///
    /// This compatibility API captures each frame with a short-lived PipeWire
    /// stream. Prefer `open_session()` for live camera loops.
    ///
    /// Parameters
    /// ----------
    /// camera:
    ///     Camera metadata returned by `list_camera_metadata()`.
    ///
    /// Returns
    /// -------
    /// Camera
    ///     A camera handle that can read frames.
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

        Ok(PyCamera::one_shot(camera))
    }

    /// Open a persistent camera session returned by `list_camera_metadata()`.
    ///
    /// Use this API for live camera loops. The returned camera supports
    /// `close()` and Python `with` blocks.
    ///
    /// Parameters
    /// ----------
    /// camera:
    ///     Camera metadata returned by `list_camera_metadata()`.
    ///
    /// Returns
    /// -------
    /// Camera
    ///     A camera handle backed by one persistent PipeWire capture session.
    #[pyo3(text_signature = "($self, camera)")]
    fn open_session(
        &self,
        #[gen_stub(override_type(type_repr = "CameraMetadata"))] camera: PyRef<
            '_,
            PyCameraMetadata,
        >,
    ) -> PyResult<PyCamera> {
        let camera = self
            .inner
            .open_session(&camera_service::CameraMetadata::from(&*camera))
            .map_err(map_camera_error)?;

        Ok(PyCamera::session(camera))
    }
}

pub(crate) fn add_camera_service_bindings(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PyCameraService>()?;
    Ok(())
}
