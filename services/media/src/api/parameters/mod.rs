// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

mod audio_format;
mod frame_rate;
mod pixel_format;
mod resolution;
mod spa_format_tools;
mod stream_format;

#[cfg(test)]
mod audio_format_test;
#[cfg(test)]
mod spa_format_tools_test;

pub(super) use audio_format::{AudioStreamFormat, audio_formats_from_pod};
pub(crate) use frame_rate::FrameRate;
pub(crate) use resolution::Resolution;
#[allow(unused_imports)]
pub(crate) use stream_format::{StreamFormat, StreamFormatFilter, stream_formats_from_enum_format};

pub(crate) enum DeviceStreamFormat {
    Video(StreamFormat),
    Audio(AudioStreamFormat),
}
