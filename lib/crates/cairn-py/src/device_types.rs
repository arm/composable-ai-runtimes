// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use cairn::media;
use pyo3::{Py, PyRef, PyResult, Python, pyclass, pymethods};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pyclass_complex_enum, gen_stub_pymethods};

use crate::camera_types::{PyFrameRate, PyResolution, PyStreamFormat, PyStreamFormatFilter};

/// An audio stream format.
#[gen_stub_pyclass(module = "cairn.media")]
#[pyclass(skip_from_py_object, module = "cairn", name = "AudioFormat")]
pub struct PyAudioFormat(media::AudioFormat);

#[gen_stub_pymethods]
#[pymethods]
impl PyAudioFormat {
    /// Create an audio format from caller-supplied values.
    #[new]
    fn new(
        sample_rate: u32,
        channels: u32,
        sample_format: String,
        channel_layout: Vec<String>,
        interleaved: bool,
    ) -> Self {
        Self(media::AudioFormat {
            sample_rate,
            channels,
            sample_format,
            channel_layout,
            interleaved,
        })
    }

    /// Samples per second per channel.
    #[getter]
    fn sample_rate(&self) -> u32 {
        self.0.sample_rate
    }

    /// Number of audio channels.
    #[getter]
    fn channels(&self) -> u32 {
        self.0.channels
    }

    /// Audio sample format name, such as F32LE.
    #[getter]
    fn sample_format(&self) -> &str {
        &self.0.sample_format
    }

    /// Ordered channel names, such as FL and FR.
    #[getter]
    fn channel_layout(&self) -> Vec<String> {
        self.0.channel_layout.clone()
    }

    /// Whether samples from different channels are interleaved.
    #[getter]
    fn interleaved(&self) -> bool {
        self.0.interleaved
    }
}

/// A video or audio stream format.
#[gen_stub_pyclass_complex_enum(module = "cairn.media")]
#[pyclass(skip_from_py_object, module = "cairn", name = "DeviceStreamFormat")]
pub enum PyDeviceStreamFormat {
    Video(Py<PyStreamFormat>),
    Audio(Py<PyAudioFormat>),
}

impl PyDeviceStreamFormat {
    fn to_rust(&self, py: Python<'_>) -> media::DeviceStreamFormat {
        match self {
            Self::Video(format) => {
                let format = format.borrow(py);
                media::DeviceStreamFormat::Video(media::StreamFormat {
                    resolution: media::Resolution {
                        width: format.resolution.width,
                        height: format.resolution.height,
                    },
                    pixel_format: format.pixel_format.clone(),
                    frame_rate: media::FrameRate {
                        numerator: format.frame_rate.numerator,
                        denominator: format.frame_rate.denominator,
                    },
                })
            }
            Self::Audio(format) => media::DeviceStreamFormat::Audio(format.borrow(py).0.clone()),
        }
    }
}

/// Optional video format constraints. Audio filtering is not supported.
#[gen_stub_pyclass_complex_enum(module = "cairn.media")]
#[pyclass(
    skip_from_py_object,
    module = "cairn",
    name = "DeviceStreamFormatFilter"
)]
pub enum PyDeviceStreamFormatFilter {
    Video(Py<PyStreamFormatFilter>),
}

impl PyDeviceStreamFormatFilter {
    pub(crate) fn to_rust(&self, py: Python<'_>) -> media::DeviceStreamFormatFilter {
        let Self::Video(filter) = self;
        media::DeviceStreamFormatFilter::Video((&*filter.borrow(py)).into())
    }
}

/// An immutable device configuration, discovered or supplied by the caller.
#[gen_stub_pyclass(module = "cairn.media")]
#[pyclass(
    skip_from_py_object,
    module = "cairn",
    name = "DeviceStreamConfiguration"
)]
pub struct PyDeviceStreamConfiguration(pub(crate) media::DeviceStreamConfiguration);

#[gen_stub_pymethods]
#[pymethods]
impl PyDeviceStreamConfiguration {
    /// Create a configuration without querying or validating device capabilities.
    #[new]
    fn new(
        py: Python<'_>,
        target: String,
        device_id: u64,
        format: PyRef<'_, PyDeviceStreamFormat>,
    ) -> Self {
        Self(media::DeviceStreamConfiguration::new(
            target,
            device_id,
            format.to_rust(py),
        ))
    }

    /// Opaque target to pass unchanged to the consuming service.
    #[getter]
    fn target(&self) -> &str {
        self.0.target()
    }

    /// Identifier of the device associated with this configuration.
    #[getter]
    fn device_id(&self) -> u64 {
        self.0.device_id()
    }

    /// The audio or video stream format.
    #[getter]
    fn format(&self, py: Python<'_>) -> PyResult<PyDeviceStreamFormat> {
        match self.0.format() {
            media::DeviceStreamFormat::Video(format) => Ok(PyDeviceStreamFormat::Video(Py::new(
                py,
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
                },
            )?)),
            media::DeviceStreamFormat::Audio(format) => Ok(PyDeviceStreamFormat::Audio(Py::new(
                py,
                PyAudioFormat(format.clone()),
            )?)),
        }
    }
}
