// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

#![warn(missing_docs)]
//! Client types for querying the Cairn Perception service.

/// Debug output configuration.
pub mod output;
/// Perception result payload decoding.
pub mod result;
mod result_model;
mod service;
mod session;
mod source_configuration;
mod validation_result;
/// Perception workflow construction.
pub mod workflow;

pub use result::{
    DecodedEnvelopeContext, ExternalPayload, MalformedKnownPayload, PerceptionPayload,
    PerceptionResult, PerceptionResultError, UnknownPayload,
};
pub use service::{PerceptionService, PerceptionServiceError, ServiceInfo};
pub use session::{
    DebugPorts, PerceptionSession, SessionSnapshot, SessionState, SessionStatus, SessionTopics,
    StatusInfo,
};
pub use validation_result::{
    ResolvedStage, ResolvedStageRole, ValidationIssue, ValidationResult, ValidationSeverity,
};

pub(crate) mod perception {
    include!("generated/cairn.perception.v1.rs");
}

#[cfg(test)]
mod mock_perception_service;
#[cfg(test)]
mod result_tests;
#[cfg(test)]
mod service_tests;
#[cfg(test)]
mod session_tests;
#[cfg(test)]
mod source_configuration_tests;
#[cfg(test)]
mod test_helpers;
#[cfg(test)]
mod validation_result_tests;
#[cfg(test)]
mod workflow_tests;
