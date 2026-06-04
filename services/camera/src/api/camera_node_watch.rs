use pipewire as pw;
use pipewire::node::NodeListener;
use std::cell::RefCell;
use std::rc::Rc;

use super::parameters::camera_formats_from_enum_format;
use super::snapshot::SnapshotSupportedFormat;

pub(super) struct CameraNodeWatch {
    pub(super) node_id: u32,
    node: pw::node::Node,
    formats: Rc<RefCell<Vec<SnapshotSupportedFormat>>>,
    _listener: NodeListener,
}

impl CameraNodeWatch {
    pub(super) fn new(node_id: u32, camera_node: pw::node::Node) -> CameraNodeWatch {
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

                for format in camera_formats_from_enum_format(camera_format_param) {
                    listener_formats.borrow_mut().push(format);
                }
            })
            .register();

        CameraNodeWatch {
            node_id,
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

    pub(super) fn take_collected_formats(&self) -> Vec<SnapshotSupportedFormat> {
        std::mem::take(&mut self.formats.borrow_mut())
    }
}
