// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use cairn::camera_service;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};

/// Frame dimensions in pixels.
#[gen_stub_pyclass(module = "cairn.camera")]
#[pyclass(skip_from_py_object, module = "cairn", name = "Resolution", get_all)]
#[derive(Clone)]
pub struct PyResolution {
    /// Frame width in pixels.
    pub width: u32,
    /// Frame height in pixels.
    pub height: u32,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyResolution {
    /// Create frame dimensions in pixels.
    #[new]
    fn new(width: u32, height: u32) -> Self {
        Self { width, height }
    }
}

/// Frames per second as an exact fraction.
#[gen_stub_pyclass(module = "cairn.camera")]
#[pyclass(skip_from_py_object, module = "cairn", name = "FrameRate", get_all)]
#[derive(Clone)]
pub struct PyFrameRate {
    /// Numerator of the frames-per-second fraction.
    pub numerator: u32,
    /// Denominator of the frames-per-second fraction.
    pub denominator: u32,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyFrameRate {
    /// Create a frame-rate fraction.
    #[new]
    fn new(numerator: u32, denominator: u32) -> Self {
        Self {
            numerator,
            denominator,
        }
    }
}

/// Optional constraints for camera stream configuration discovery.
#[gen_stub_pyclass(module = "cairn.camera")]
#[pyclass(
    skip_from_py_object,
    module = "cairn",
    name = "StreamFormatFilter",
    get_all
)]
#[derive(Clone)]
pub struct PyStreamFormatFilter {
    /// Requested dimensions, or None to leave the resolution unconstrained.
    pub resolution: Option<PyResolution>,
    /// Requested PipeWire pixel format, or None to leave it unconstrained.
    pub pixel_format: Option<String>,
    /// Requested frame rate, or None to leave it unconstrained.
    pub frame_rate: Option<PyFrameRate>,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyStreamFormatFilter {
    /// Create a discovery filter with optional resolution, pixel-format, and frame-rate constraints.
    #[new]
    #[pyo3(signature = (resolution=None, pixel_format=None, frame_rate=None))]
    fn new(
        resolution: Option<PyRef<'_, PyResolution>>,
        pixel_format: Option<String>,
        frame_rate: Option<PyRef<'_, PyFrameRate>>,
    ) -> Self {
        Self {
            resolution: resolution.map(|value| value.clone()),
            pixel_format,
            frame_rate: frame_rate.map(|value| value.clone()),
        }
    }
}

impl From<&PyStreamFormatFilter> for camera_service::StreamFormatFilter {
    fn from(value: &PyStreamFormatFilter) -> Self {
        Self {
            resolution: value
                .resolution
                .as_ref()
                .map(|value| camera_service::Resolution {
                    width: value.width,
                    height: value.height,
                }),
            pixel_format: value.pixel_format.clone(),
            frame_rate: value
                .frame_rate
                .as_ref()
                .map(|value| camera_service::FrameRate {
                    numerator: value.numerator,
                    denominator: value.denominator,
                }),
        }
    }
}

/// A concrete camera stream format.
#[gen_stub_pyclass(module = "cairn.camera")]
#[pyclass(skip_from_py_object, module = "cairn", name = "StreamFormat", get_all)]
#[derive(Clone)]
pub struct PyStreamFormat {
    /// Frame dimensions in pixels.
    pub resolution: PyResolution,
    /// PipeWire pixel format name.
    pub pixel_format: String,
    /// Frames per second as an exact fraction.
    pub frame_rate: PyFrameRate,
}

#[gen_stub_pymethods]
#[pymethods]
impl PyStreamFormat {
    /// Create a complete camera stream format.
    #[new]
    fn new(
        resolution: PyRef<'_, PyResolution>,
        pixel_format: String,
        frame_rate: PyRef<'_, PyFrameRate>,
    ) -> Self {
        Self {
            resolution: resolution.clone(),
            pixel_format,
            frame_rate: frame_rate.clone(),
        }
    }
}

/// An immutable camera stream configuration, discovered or supplied by the caller.
#[gen_stub_pyclass(module = "cairn.camera")]
#[pyclass(skip_from_py_object, module = "cairn", name = "StreamConfiguration")]
#[derive(Clone)]
pub struct PyStreamConfiguration(pub(crate) camera_service::StreamConfiguration);

#[gen_stub_pymethods]
#[pymethods]
impl PyStreamConfiguration {
    /// Create a camera stream configuration from caller-supplied values.
    /// Prefer CameraService.get_stream_configurations() to obtain configurations advertised by a camera. This constructor does not query the camera or validate format support.
    #[new]
    fn new(target: String, camera_id: u64, format: PyRef<'_, PyStreamFormat>) -> Self {
        Self(camera_service::StreamConfiguration::new(
            target,
            camera_id,
            camera_service::StreamFormat {
                resolution: camera_service::Resolution {
                    width: format.resolution.width,
                    height: format.resolution.height,
                },
                pixel_format: format.pixel_format.clone(),
                frame_rate: camera_service::FrameRate {
                    numerator: format.frame_rate.numerator,
                    denominator: format.frame_rate.denominator,
                },
            },
        ))
    }

    /// Opaque PipeWire target to pass unchanged to the consuming service.
    #[getter]
    fn target(&self) -> &str {
        self.0.target()
    }

    /// Identifier of the camera associated with this configuration.
    #[getter]
    fn camera_id(&self) -> u64 {
        self.0.camera_id()
    }

    /// Resolution, pixel format, and frame rate to request from the camera.
    #[getter]
    fn format(&self) -> PyStreamFormat {
        let format = self.0.format();
        PyStreamFormat {
            resolution: PyResolution {
                width: format.resolution.width,
                height: format.resolution.height,
            },
            pixel_format: format.pixel_format.clone(),
            frame_rate: PyFrameRate {
                numerator: format.frame_rate.numerator,
                denominator: format.frame_rate.denominator,
            },
        }
    }
}

impl From<camera_service::StreamConfiguration> for PyStreamConfiguration {
    fn from(value: camera_service::StreamConfiguration) -> Self {
        Self(value)
    }
}

pub(crate) fn add_stream_configuration_bindings(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PyResolution>()?;
    module.add_class::<PyFrameRate>()?;
    module.add_class::<PyStreamFormatFilter>()?;
    module.add_class::<PyStreamFormat>()?;
    module.add_class::<PyStreamConfiguration>()?;
    Ok(())
}
