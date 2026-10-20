// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use cairn_camera::{FrameRate, Resolution, StreamConfiguration, StreamFormat};

pub(crate) fn stream_configuration() -> StreamConfiguration {
    StreamConfiguration::new(
        "opaque/pipewire:target",
        7,
        StreamFormat {
            resolution: Resolution {
                width: 1920,
                height: 1080,
            },
            frame_rate: FrameRate {
                numerator: 30_000,
                denominator: 1_001,
            },
            pixel_format: "NV12".into(),
        },
    )
}
