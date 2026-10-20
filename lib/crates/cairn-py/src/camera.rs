// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use cairn::camera_service;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::{Bound, PyErr, PyResult};
use pyo3::types::{PyModule, PyModuleMethods};
use pyo3::{PyAny, Python, pyclass, pymethods};
use pyo3_async_runtimes::tokio as tokio_runtime;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
use std::sync::Arc;

use crate::camera_types::PyStreamConfiguration;

pub(crate) fn map_transport_error(error: camera_service::CameraServiceError) -> PyErr {
    match error {
        camera_service::CameraServiceError::Transport(message) => PyRuntimeError::new_err(message),
        camera_service::CameraServiceError::InvalidResponse(message) => {
            PyRuntimeError::new_err(message)
        }
    }
}

/// Information about a camera returned by `CameraService.list_cameras()`.
#[gen_stub_pyclass(module = "cairn.camera")]
#[pyclass(skip_from_py_object, module = "cairn", name = "Camera")]
pub struct PyCamera {
    camera: Arc<camera_service::Camera>,
}

impl PyCamera {
    pub(crate) fn new(camera: camera_service::Camera) -> Self {
        Self {
            camera: Arc::new(camera),
        }
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl PyCamera {
    /// Camera identifier reported by the camera service.
    #[getter]
    fn id(&self) -> u64 {
        self.camera.id
    }

    /// Human-readable camera name.
    #[getter]
    fn name(&self) -> &str {
        &self.camera.name
    }

    /// Return an awaitable resolving to supported configurations, or an empty list if none match.
    #[pyo3(signature = (resolution=None, pixel_format=None, frame_rate=None))]
    #[gen_stub(override_return_type(
        type_repr = "collections.abc.Awaitable[builtins.list[StreamConfiguration]]",
        imports = ("collections.abc", "builtins")
    ))]
    fn get_stream_configurations<'py>(
        &self,
        py: Python<'py>,
        resolution: Option<(u32, u32)>,
        pixel_format: Option<String>,
        frame_rate: Option<(u32, u32)>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let has_filter = resolution.is_some() || pixel_format.is_some() || frame_rate.is_some();
        let filter = has_filter.then(|| camera_service::StreamFormatFilter {
            resolution: resolution
                .map(|(width, height)| camera_service::Resolution { width, height }),
            pixel_format,
            frame_rate: frame_rate.map(|(numerator, denominator)| camera_service::FrameRate {
                numerator,
                denominator,
            }),
        });
        let camera = Arc::clone(&self.camera);
        tokio_runtime::future_into_py(py, async move {
            let configurations = camera
                .get_stream_configurations(filter)
                .await
                .map_err(map_transport_error)?;
            Ok(configurations
                .into_iter()
                .map(PyStreamConfiguration::from)
                .collect::<Vec<_>>())
        })
    }

    /// Return a string representation of the camera metadata.
    #[gen_stub(skip)]
    fn __repr__(&self) -> String {
        format!("Camera(id={}, name={:?})", self.camera.id, self.camera.name)
    }
}

pub(crate) fn add_camera_bindings(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PyCamera>()?;
    Ok(())
}
