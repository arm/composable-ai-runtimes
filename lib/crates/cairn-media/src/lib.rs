// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

#![warn(missing_docs)]
//! Client types for discovering devices exposed by the Cairn media service.

mod client;

#[cfg(test)]
mod client_tests;

pub use client::{
    AudioFormat, Camera, Device, DeviceSelector, DeviceStreamConfiguration, DeviceStreamFormat,
    DeviceStreamFormatFilter, DeviceType, FrameRate, Media, MediaError, Resolution,
    StreamConfiguration, StreamFormat, StreamFormatFilter,
};
