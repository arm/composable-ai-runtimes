// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

mod camera;
mod camera_types;
mod device;
mod device_types;
mod media;
mod notifications;
mod perception;
mod perception_result;
mod perception_result_models;

use pyo3::prelude::{Bound, PyResult};
use pyo3::pymodule;
use pyo3::types::{PyModule, PyModuleMethods};
use pyo3_stub_gen::generate::{ClassDef, MemberDef};
use pyo3_stub_gen::{Result as StubResult, StubInfo, TypeInfo};
use std::any::TypeId;
use std::path::Path;

/// Python interface for the Cairn library.
///
/// Use this module to access Media, Notification, and Perception services.
#[pymodule]
fn _bindings(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("__doc__", "Python bindings for the Cairn library.")?;
    media::register(module)?;
    notifications::register(module)?;
    perception::register(module)?;
    Ok(())
}

pyo3_stub_gen::module_doc!(
    "cairn",
    "Python interface for the Cairn library.\n\nUse this module to access Media, Notification, and Perception services."
);

pyo3_stub_gen::reexport_module_members!(
    "cairn" from "cairn.media";
    "Camera", "Media", "FrameRate", "Resolution", "StreamConfiguration",
    "StreamFormat", "StreamFormatFilter", "Device", "DeviceType", "DeviceSelector",
    "AudioFormat", "DeviceStreamFormat", "DeviceStreamFormatFilter", "DeviceStreamConfiguration"
);
pyo3_stub_gen::reexport_module_members!(
    "cairn" from "cairn.notifications";
    "Notification", "Notifications", "NotificationSubscription"
);

pub fn stub_info() -> StubResult<StubInfo> {
    let project_root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .nth(2)
        .expect("crate manifest should be nested under the lib project root");

    // Stubs describe the public package re-exports, not the private _bindings module.
    let mut info = StubInfo::from_project_root(
        "cairn".to_string(),
        project_root.join("python"),
        true,
        Default::default(),
    )?;

    // PyO3's simple enums are classes with variant attributes, not enum.Enum subclasses.
    let module = info.modules.get_mut("cairn.media").expect("media module");
    let type_id = TypeId::of::<device::PyDeviceType>();
    let enum_def = module.enum_.remove(&type_id).expect("DeviceType metadata");
    module.class.insert(
        type_id,
        ClassDef {
            name: enum_def.name,
            module: enum_def.module,
            doc: enum_def.doc,
            attrs: enum_def
                .variants
                .iter()
                .map(|&(name, doc)| MemberDef {
                    name,
                    r#type: TypeInfo::with_module(
                        &format!("typing.ClassVar[{}]", enum_def.name),
                        "typing".into(),
                    ),
                    doc,
                    default: None,
                    deprecated: None,
                })
                .collect(),
            getter_setters: Default::default(),
            methods: Default::default(),
            bases: Vec::new(),
            classes: Vec::new(),
            match_args: None,
            subclass: false,
        },
    );
    Ok(info)
}
