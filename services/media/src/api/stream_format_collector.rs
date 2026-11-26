// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use pipewire as pw;
use pipewire::node::NodeListener;
use std::cell::RefCell;
use std::rc::Rc;

use super::parameters::{
    DeviceStreamFormat, StreamFormatFilter, audio_formats_from_pod, stream_formats_from_enum_format,
};
use crate::device::DeviceType;

pub(super) struct StreamFormatCollector {
    node: pw::node::Node,
    formats: Rc<RefCell<Vec<DeviceStreamFormat>>>,
    _listener: NodeListener,
}

impl StreamFormatCollector {
    pub(super) fn new(
        camera_node: pw::node::Node,
        device_type: DeviceType,
        filter: Option<StreamFormatFilter>,
    ) -> Self {
        let formats = Rc::new(RefCell::new(vec![]));

        let listener_formats = Rc::clone(&formats);
        let _listener = camera_node
            .add_listener_local()
            .param(move |_seq, param_type, _index, _next, param| {
                if param_type != pw::spa::param::ParamType::EnumFormat {
                    return;
                }

                let Some(format_param) = param else {
                    return;
                };

                let formats = device_formats_from_pod(device_type, format_param, filter.as_ref());
                listener_formats.borrow_mut().extend(formats);
            })
            .register();

        StreamFormatCollector {
            node: camera_node,
            formats,
            _listener,
        }
    }

    pub(super) fn request_format_collection(&self) {
        self.formats.borrow_mut().clear();
        self.node
            .enum_params(1, Some(pw::spa::param::ParamType::EnumFormat), 0, u32::MAX);
    }

    pub(super) fn take_collected_formats(&self) -> Vec<DeviceStreamFormat> {
        std::mem::take(&mut self.formats.borrow_mut())
    }
}

pub(super) fn device_formats_from_pod(
    device_type: DeviceType,
    pod: &pw::spa::pod::Pod,
    video_filter: Option<&StreamFormatFilter>,
) -> Vec<DeviceStreamFormat> {
    match device_type {
        DeviceType::Camera => stream_formats_from_enum_format(pod, video_filter)
            .into_iter()
            .map(DeviceStreamFormat::Video)
            .collect(),
        DeviceType::Microphone | DeviceType::Speaker => audio_formats_from_pod(pod)
            .into_iter()
            .map(DeviceStreamFormat::Audio)
            .collect(),
    }
}
