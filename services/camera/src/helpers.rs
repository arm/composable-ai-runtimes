// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use pipewire as pw;

pub(crate) const VIDEO_SOURCE_MEDIA_CLASS: &str = "Video/Source";

pub fn is_camera_node<P>(global: &pw::registry::GlobalObject<P>) -> bool
where
    P: AsRef<pw::spa::utils::dict::DictRef>,
{
    if global.type_ != pw::types::ObjectType::Node {
        return false;
    }

    global.props.as_ref().is_some_and(|props| {
        props.as_ref().get(&pw::keys::MEDIA_CLASS) == Some(VIDEO_SOURCE_MEDIA_CLASS)
    })
}
