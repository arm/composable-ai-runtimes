// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

#![warn(missing_docs)]
//! Client types for discovering cameras exposed by the Cairn camera service.

mod service;

#[cfg(test)]
mod service_tests;

pub use service::{
    Camera, CameraService, CameraServiceError, FrameRate, Resolution, StreamConfiguration,
    StreamFormat, StreamFormatFilter,
};
