// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use crate::perception::{FrameRate, Resolution, StreamConfiguration, StreamFormat};

impl From<&cairn_camera::StreamConfiguration> for StreamConfiguration {
    fn from(configuration: &cairn_camera::StreamConfiguration) -> Self {
        let format = configuration.format();
        Self {
            target: configuration.target().to_owned(),
            camera_id: configuration.camera_id(),
            format: Some(StreamFormat {
                resolution: Some(Resolution {
                    width: format.resolution.width,
                    height: format.resolution.height,
                }),
                frame_rate: Some(FrameRate {
                    numerator: format.frame_rate.numerator,
                    denominator: format.frame_rate.denominator,
                }),
                pixel_format: format.pixel_format.clone(),
            }),
        }
    }
}
