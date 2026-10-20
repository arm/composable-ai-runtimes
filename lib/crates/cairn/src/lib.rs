// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

#![warn(missing_docs)]
//! Rust client library for interacting with Cairn runtime services.
//!
//! APIs are grouped by service. Each module re-exports the user-facing client, data, and error
//! types provided by its corresponding service crate.

/// Camera discovery client and metadata types.
pub mod camera_service {
    pub use cairn_camera::*;
}
/// Asynchronous notification client and subscription types.
pub mod notification_service {
    pub use cairn_notification::*;
}
/// Perception service client and service information types.
pub mod perception_service {
    pub use cairn_perception::*;
}
