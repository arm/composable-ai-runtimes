// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use pipewire as pw;
use pipewire::node::NodeListener;
use std::cell::RefCell;
use std::rc::Rc;

use super::parameters::{StreamFormat, StreamFormatFilter, stream_formats_from_enum_format};

pub(super) struct StreamFormatCollector {
    node: pw::node::Node,
    formats: Rc<RefCell<Vec<StreamFormat>>>,
    _listener: NodeListener,
}

impl StreamFormatCollector {
    pub(super) fn new(
        camera_node: pw::node::Node,
        filter: Option<StreamFormatFilter>,
    ) -> StreamFormatCollector {
        let formats = Rc::new(RefCell::new(vec![]));

        let listener_formats = Rc::clone(&formats);
        let _listener = camera_node
            .add_listener_local()
            .param(move |_seq, param_type, _index, _next, param| {
                if param_type != pw::spa::param::ParamType::EnumFormat {
                    return;
                }

                let Some(camera_format_param) = param else {
                    return;
                };

                listener_formats
                    .borrow_mut()
                    .extend(stream_formats_from_enum_format(
                        camera_format_param,
                        filter.as_ref(),
                    ));
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

    pub(super) fn take_collected_formats(&self) -> Vec<StreamFormat> {
        std::mem::take(&mut self.formats.borrow_mut())
    }
}
