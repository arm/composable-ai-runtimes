// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::sync::Arc;

use cairn::media;
use pyo3::{Bound, PyAny, PyRef, PyResult, Python, pyclass, pymethods};
use pyo3_async_runtimes::tokio as tokio_runtime;
use pyo3_stub_gen::derive::{
    gen_stub_pyclass, gen_stub_pyclass_complex_enum, gen_stub_pyclass_enum, gen_stub_pymethods,
};

use crate::camera::map_media_error;
use crate::device_types::{PyDeviceStreamConfiguration, PyDeviceStreamFormatFilter};

/// The kind of media device.
#[gen_stub_pyclass_enum(module = "cairn.media")]
#[pyclass(
    from_py_object,
    module = "cairn",
    name = "DeviceType",
    frozen,
    eq,
    hash
)]
#[derive(Clone, PartialEq, Hash)]
pub enum PyDeviceType {
    Camera,
    Microphone,
    Speaker,
}

impl From<PyDeviceType> for media::DeviceType {
    fn from(value: PyDeviceType) -> Self {
        match value {
            PyDeviceType::Camera => Self::Camera,
            PyDeviceType::Microphone => Self::Microphone,
            PyDeviceType::Speaker => Self::Speaker,
        }
    }
}

/// Select a device by ID or type.
#[gen_stub_pyclass_complex_enum(module = "cairn.media")]
#[pyclass(skip_from_py_object, module = "cairn", name = "DeviceSelector")]
pub enum PyDeviceSelector {
    Id(u64),
    Type(PyDeviceType),
}

impl From<&PyDeviceSelector> for media::DeviceSelector {
    fn from(value: &PyDeviceSelector) -> Self {
        match value {
            PyDeviceSelector::Id(id) => Self::Id(*id),
            PyDeviceSelector::Type(device_type) => Self::Type(device_type.clone().into()),
        }
    }
}

/// A device reported by the media service.
#[gen_stub_pyclass(module = "cairn.media")]
#[pyclass(skip_from_py_object, module = "cairn", name = "Device")]
pub struct PyDevice {
    device: Arc<media::Device>,
}

impl From<media::Device> for PyDevice {
    fn from(device: media::Device) -> Self {
        Self {
            device: Arc::new(device),
        }
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl PyDevice {
    /// Return supported configurations. None means unfiltered discovery; video filters apply only to cameras.
    #[pyo3(signature = (filter=None))]
    #[gen_stub(override_return_type(
        type_repr = "collections.abc.Awaitable[builtins.list[DeviceStreamConfiguration]]",
        imports = ("collections.abc", "builtins")
    ))]
    fn get_stream_configurations<'py>(
        &self,
        py: Python<'py>,
        filter: Option<PyRef<'_, PyDeviceStreamFormatFilter>>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let filter = filter.map(|filter| filter.to_rust(py));
        let device = Arc::clone(&self.device);
        tokio_runtime::future_into_py(py, async move {
            device
                .get_stream_configurations(filter)
                .await
                .map(|configurations| {
                    configurations
                        .into_iter()
                        .map(PyDeviceStreamConfiguration)
                        .collect::<Vec<_>>()
                })
                .map_err(map_media_error)
        })
    }

    /// Device identifier reported by the media service.
    #[getter]
    fn id(&self) -> u64 {
        self.device.id
    }

    /// Human-readable device name.
    #[getter]
    fn name(&self) -> &str {
        &self.device.name
    }

    /// Whether this device is a camera, microphone, or speaker.
    #[getter]
    fn device_type(&self) -> PyDeviceType {
        match self.device.device_type {
            media::DeviceType::Camera => PyDeviceType::Camera,
            media::DeviceType::Microphone => PyDeviceType::Microphone,
            media::DeviceType::Speaker => PyDeviceType::Speaker,
        }
    }
}
