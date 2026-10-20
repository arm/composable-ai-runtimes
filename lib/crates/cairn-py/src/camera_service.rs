// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use cairn::camera_service;
use pyo3::prelude::{Bound, PyResult};
use pyo3::types::{PyAnyMethods, PyModule, PyModuleMethods};
use pyo3::{pyclass, pymethods};
use pyo3_async_runtimes::tokio as tokio_runtime;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};

use crate::camera::{PyCamera, add_camera_bindings, map_transport_error};
use crate::camera_types::{
    PyStreamConfiguration, PyStreamFormatFilter, add_stream_configuration_bindings,
};

/// Client for the Cairn camera service.
///
/// Connects over gRPC to discover cameras and their stream configurations.
#[gen_stub_pyclass(module = "cairn.camera")]
#[pyclass(unsendable, module = "cairn", name = "CameraService")]
pub struct PyCameraService {
    inner: camera_service::CameraService,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyCameraService {
    /// Discover stream configurations for a camera, optionally filtered by format.
    #[pyo3(signature = (camera_id, filter=None))]
    fn get_stream_configurations(
        &mut self,
        camera_id: u64,
        filter: Option<pyo3::PyRef<'_, PyStreamFormatFilter>>,
    ) -> PyResult<Vec<PyStreamConfiguration>> {
        let filter = filter
            .as_deref()
            .map(camera_service::StreamFormatFilter::from);
        tokio_runtime::get_runtime()
            .block_on(self.inner.get_stream_configurations(camera_id, filter))
            .map(|values| {
                values
                    .into_iter()
                    .map(PyStreamConfiguration::from)
                    .collect()
            })
            .map_err(map_transport_error)
    }

    /// Create a camera service client.
    #[new]
    #[pyo3(signature = (endpoint=None))]
    #[pyo3(text_signature = "(endpoint=None)")]
    #[gen_stub(override_return_type(type_repr = "'CameraService'"))]
    fn new(py: pyo3::Python<'_>, endpoint: Option<String>) -> PyResult<Self> {
        let inner = py
            .detach(|| {
                tokio_runtime::get_runtime().block_on(camera_service::CameraService::new(endpoint))
            })
            .map_err(map_transport_error)?;

        Ok(Self { inner })
    }

    /// List the cameras currently reported by the camera service.
    #[pyo3(text_signature = "($self)")]
    fn list_cameras(&mut self) -> PyResult<Vec<PyCamera>> {
        let cameras = tokio_runtime::get_runtime()
            .block_on(self.inner.list_cameras())
            .map_err(map_transport_error)?;

        Ok(cameras.into_iter().map(PyCamera::new).collect())
    }
}

pub(crate) fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let module = PyModule::new(parent.py(), "cairn.camera")?;
    add_camera_bindings(&module)?;
    add_stream_configuration_bindings(&module)?;
    module.add_class::<PyCameraService>()?;
    parent.add_submodule(&module)?;
    parent
        .py()
        .import("sys")?
        .getattr("modules")?
        .set_item("cairn.camera", module)?;
    Ok(())
}

pyo3_stub_gen::module_doc!(
    "cairn.camera",
    "Python interface for camera discovery and stream configurations."
);
