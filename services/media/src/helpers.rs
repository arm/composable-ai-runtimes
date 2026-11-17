// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use crate::device::DeviceType;
use pipewire as pw;

pub(crate) fn should_include_device<P>(
    global: &pw::registry::GlobalObject<P>,
    device_type: Option<DeviceType>,
) -> bool
where
    P: AsRef<pw::spa::utils::dict::DictRef>,
{
    if let Some(device_type) = device_type {
        is_device_type(global, &device_type)
    } else {
        is_device_type(global, &DeviceType::Camera)
            || is_device_type(global, &DeviceType::Microphone)
            || is_device_type(global, &DeviceType::Speaker)
    }
}

pub fn is_device_type<P>(global: &pw::registry::GlobalObject<P>, device_type: &DeviceType) -> bool
where
    P: AsRef<pw::spa::utils::dict::DictRef>,
{
    if global.type_ != pw::types::ObjectType::Node {
        return false;
    }

    global.props.as_ref().is_some_and(|props| {
        props.as_ref().get(&pw::keys::MEDIA_CLASS) == Some(device_type.media_class())
    })
}
