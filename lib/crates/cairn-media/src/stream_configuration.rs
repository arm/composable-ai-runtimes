// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use crate::client::MediaError;
use crate::media;

/// A frame's dimensions in pixels.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Resolution {
    /// Frame width in pixels.
    pub width: u32,
    /// Frame height in pixels.
    pub height: u32,
}

/// Frames per second expressed as an exact fraction.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FrameRate {
    /// Fraction numerator.
    pub numerator: u32,
    /// Fraction denominator.
    pub denominator: u32,
}

/// A video stream format.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StreamFormat {
    /// Frame dimensions.
    pub resolution: Resolution,
    /// PipeWire pixel format name.
    pub pixel_format: String,
    /// Frames per second.
    pub frame_rate: FrameRate,
}

/// An audio stream format.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AudioFormat {
    /// Samples per second per channel.
    pub sample_rate: u32,
    /// Number of audio channels.
    pub channels: u32,
    /// Audio sample format name, such as `F32LE`.
    pub sample_format: String,
    /// Ordered channel names, such as `FL` and `FR`.
    pub channel_layout: Vec<String>,
    /// Whether samples from different channels are interleaved.
    pub interleaved: bool,
}

impl From<media::AudioFormat> for AudioFormat {
    fn from(value: media::AudioFormat) -> Self {
        Self {
            sample_rate: value.sample_rate,
            channels: value.channels,
            sample_format: value.sample_format,
            channel_layout: value.channel_layout,
            interleaved: value.interleaved,
        }
    }
}

/// A video or audio format.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum DeviceStreamFormat {
    /// A video stream format.
    Video(StreamFormat),
    /// A microphone or speaker stream format.
    Audio(AudioFormat),
}

/// An immutable device configuration for handoff to a consuming service.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DeviceStreamConfiguration {
    target: String,
    device_id: u64,
    format: DeviceStreamFormat,
}

impl DeviceStreamConfiguration {
    /// Creates a configuration without querying or validating device capabilities.
    pub fn new(target: impl Into<String>, device_id: u64, format: DeviceStreamFormat) -> Self {
        Self {
            target: target.into(),
            device_id,
            format,
        }
    }

    /// Returns the opaque PipeWire target to pass unchanged to consumers.
    pub fn target(&self) -> &str {
        &self.target
    }

    /// Returns the associated device ID.
    pub fn device_id(&self) -> u64 {
        self.device_id
    }

    /// Returns the audio or video format.
    pub fn format(&self) -> &DeviceStreamFormat {
        &self.format
    }
}

impl TryFrom<media::DeviceStreamConfiguration> for DeviceStreamConfiguration {
    type Error = MediaError;

    fn try_from(value: media::DeviceStreamConfiguration) -> Result<Self, Self::Error> {
        let format = match value.format {
            Some(media::device_stream_configuration::Format::VideoFormat(format)) => {
                DeviceStreamFormat::Video(format.try_into()?)
            }
            Some(media::device_stream_configuration::Format::AudioFormat(format)) => {
                DeviceStreamFormat::Audio(format.into())
            }
            None => {
                return Err(MediaError::InvalidResponse(
                    "device stream configuration is missing its format".into(),
                ));
            }
        };
        Ok(Self::new(value.target, value.device_id, format))
    }
}

/// Optional constraints on stream configuration discovery.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct StreamFormatFilter {
    /// Requested frame dimensions, or any dimensions when absent.
    pub resolution: Option<Resolution>,
    /// Requested pixel format, or any format when absent.
    pub pixel_format: Option<String>,
    /// Requested frame rate, or any rate when absent.
    pub frame_rate: Option<FrameRate>,
}

/// Constraints on device stream configuration discovery.
#[derive(Clone, Debug)]
pub enum DeviceStreamFormatFilter {
    /// Video stream format constraints; invalid for microphones and speakers.
    Video(StreamFormatFilter),
}

impl From<DeviceStreamFormatFilter> for media::device_stream_configuration_request::Filter {
    fn from(filter: DeviceStreamFormatFilter) -> Self {
        match filter {
            DeviceStreamFormatFilter::Video(format) => Self::VideoFormat(format.into()),
        }
    }
}

/// An immutable camera stream configuration, discovered or supplied by the caller.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StreamConfiguration {
    target: String,
    camera_id: u64,
    format: StreamFormat,
}

impl StreamConfiguration {
    /// Creates a configuration from caller-supplied values without camera discovery.
    ///
    /// Values are preserved unchanged. The caller must ensure that the target,
    /// camera, and format are supported; the consuming service validates the request.
    pub fn new(target: impl Into<String>, camera_id: u64, format: StreamFormat) -> Self {
        Self {
            target: target.into(),
            camera_id,
            format,
        }
    }

    /// Returns the opaque PipeWire target to pass unchanged to consumers.
    pub fn target(&self) -> &str {
        &self.target
    }

    /// Returns the camera identifier associated with this configuration.
    pub fn camera_id(&self) -> u64 {
        self.camera_id
    }

    /// Returns the stream format.
    pub fn format(&self) -> &StreamFormat {
        &self.format
    }
}

impl From<StreamFormatFilter> for media::StreamFormat {
    fn from(filter: StreamFormatFilter) -> Self {
        Self {
            resolution: filter.resolution.map(|value| media::Resolution {
                width: value.width,
                height: value.height,
            }),
            pixel_format: filter.pixel_format.unwrap_or_default(),
            frame_rate: filter.frame_rate.map(|value| media::FrameRate {
                numerator: value.numerator,
                denominator: value.denominator,
            }),
        }
    }
}

impl TryFrom<media::StreamConfiguration> for StreamConfiguration {
    type Error = MediaError;

    fn try_from(value: media::StreamConfiguration) -> Result<Self, Self::Error> {
        let format = value.format.ok_or_else(|| {
            MediaError::InvalidResponse("stream configuration is missing its format".into())
        })?;
        Ok(Self::new(value.target, value.camera_id, format.try_into()?))
    }
}

impl TryFrom<media::StreamFormat> for StreamFormat {
    type Error = MediaError;

    fn try_from(value: media::StreamFormat) -> Result<Self, Self::Error> {
        let resolution = value.resolution.ok_or_else(|| {
            MediaError::InvalidResponse("stream format is missing its resolution".into())
        })?;
        let frame_rate = value.frame_rate.ok_or_else(|| {
            MediaError::InvalidResponse("stream format is missing its frame rate".into())
        })?;
        Ok(Self {
            pixel_format: value.pixel_format,
            resolution: Resolution {
                width: resolution.width,
                height: resolution.height,
            },
            frame_rate: FrameRate {
                numerator: frame_rate.numerator,
                denominator: frame_rate.denominator,
            },
        })
    }
}
