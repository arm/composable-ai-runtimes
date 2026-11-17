// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

#![warn(missing_docs)]
//! Client types for discovering devices exposed by the Cairn media service.

mod client;
mod stream_configuration;

mod media {
    include!("generated/cairn.media.v1.rs");
}

#[cfg(test)]
mod client_tests;

pub use client::{Camera, Device, DeviceSelector, DeviceType, Media, MediaError};
pub use stream_configuration::{
    AudioFormat, DeviceStreamConfiguration, DeviceStreamFormat, DeviceStreamFormatFilter,
    FrameRate, Resolution, StreamConfiguration, StreamFormat, StreamFormatFilter,
};
