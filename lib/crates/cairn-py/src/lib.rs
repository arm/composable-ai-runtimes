// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

mod camera;
mod camera_service;
mod camera_types;
mod notification_service;
mod perception_result;
mod perception_result_models;
mod perception_service;

use pyo3::prelude::{Bound, PyResult};
use pyo3::pymodule;
use pyo3::types::{PyModule, PyModuleMethods};
use pyo3_stub_gen::{Result as StubResult, StubInfo};
use std::path::Path;

/// Python interface for the Cairn library.
///
/// Use this module to access Camera, Notification, and Perception services.
#[pymodule]
fn _bindings(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("__doc__", "Python bindings for the Cairn library.")?;
    camera_service::register(module)?;
    notification_service::register(module)?;
    perception_service::register(module)?;
    Ok(())
}

pyo3_stub_gen::module_doc!(
    "cairn",
    "Python interface for the Cairn library.\n\nUse this module to access Camera, Notification, and Perception services."
);

pyo3_stub_gen::reexport_module_members!(
    "cairn" from "cairn.camera";
    "Camera", "CameraService", "FrameRate", "Resolution", "StreamConfiguration",
    "StreamFormat", "StreamFormatFilter"
);
pyo3_stub_gen::reexport_module_members!(
    "cairn" from "cairn.notification";
    "Notification", "NotificationService", "NotificationSubscription"
);

pub fn stub_info() -> StubResult<StubInfo> {
    let project_root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .nth(2)
        .expect("crate manifest should be nested under the lib project root");

    // Stubs describe the public package re-exports, not the private _bindings module.
    StubInfo::from_project_root(
        "cairn".to_string(),
        project_root.join("python"),
        true,
        Default::default(),
    )
}
