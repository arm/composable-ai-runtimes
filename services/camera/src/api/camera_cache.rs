// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use super::snapshot::SnapshotCamera;
use std::collections::HashMap;

#[derive(Default)]
pub(crate) struct CameraCache {
    cameras: HashMap<u32, SnapshotCamera>,
}

impl CameraCache {
    pub(crate) fn insert(&mut self, node_id: u32, camera: SnapshotCamera) {
        self.cameras.insert(node_id, camera);
    }

    pub(crate) fn remove(&mut self, node_id: u32) {
        self.cameras.remove(&node_id);
    }

    pub(crate) fn to_vec(&self) -> Vec<SnapshotCamera> {
        let mut cameras = self.cameras.values().cloned().collect::<Vec<_>>();
        cameras.sort_by_key(|camera| camera.object_serial);
        cameras
    }
}
