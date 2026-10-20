// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use crate::perception::{DebugOutput as ProtoDebugOutput, OutputSpec, output_spec};

/// Ports exposed by the optional debug output.
///
/// Zero selects the service default: HTTP 9999, WebSocket 8000, control 8001.
/// Read the resolved ports from [`crate::PerceptionSession::debug_endpoint`].
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct DebugOutput {
    /// HTTP port for the debug output.
    pub http_port: u32,
    /// WebSocket port for the debug output.
    pub ws_port: u32,
    /// Control port for the debug output.
    pub ctrl_port: u32,
}

impl From<DebugOutput> for OutputSpec {
    fn from(output: DebugOutput) -> Self {
        Self {
            output: Some(output_spec::Output::Debug(ProtoDebugOutput {
                http_port: output.http_port,
                ws_port: output.ws_port,
                ctrl_port: output.ctrl_port,
            })),
        }
    }
}
