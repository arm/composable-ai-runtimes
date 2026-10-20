// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use crate::perception::{
    ResolvedStage as ProtoResolvedStage, ValidateWorkflowResponse,
    ValidationIssue as ProtoValidationIssue,
};

/// Severity assigned to a workflow validation issue.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ValidationSeverity {
    /// The service did not specify a severity.
    Unspecified,
    /// The issue prevents the workflow from being deployed.
    Error,
    /// The issue does not prevent deployment but may require attention.
    Warning,
    /// A severity value not recognized by this SDK version.
    Unknown(i32),
}

/// A problem found while validating a workflow.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidationIssue {
    /// Severity assigned by the service.
    pub severity: ValidationSeverity,
    /// Machine-readable issue code.
    pub code: String,
    /// Human-readable description of the issue.
    pub message: String,
    /// Path to the invalid workflow field, when available.
    pub field_path: Option<String>,
    /// ID of the affected stage, when available.
    pub stage_id: Option<String>,
}

/// Role of a resolved workflow stage.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ResolvedStageRole {
    /// The service did not specify a role.
    Unspecified,
    /// A stage that supplies input to the workflow.
    Source,
    /// A stage that processes workflow data.
    Processing,
    /// A stage that publishes workflow output.
    Output,
    /// A role value not recognized by this SDK version.
    Unknown(i32),
}

/// A workflow stage resolved by the Perception service.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResolvedStage {
    /// Service-assigned stage identifier.
    pub id: String,
    /// User-facing stage name.
    pub name: String,
    /// Role performed by the stage.
    pub role: ResolvedStageRole,
    /// Whether the running stage can be enabled or disabled.
    pub controllable: bool,
    /// Model used by the stage, when applicable.
    pub model_id: Option<String>,
}

/// Result returned after validating a workflow.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidationResult {
    /// Whether the workflow is valid.
    pub valid: bool,
    /// Issues found while validating the workflow.
    pub issues: Vec<ValidationIssue>,
    /// Stages resolved from the workflow specification.
    pub stages: Vec<ResolvedStage>,
}

impl From<ValidateWorkflowResponse> for ValidationResult {
    fn from(response: ValidateWorkflowResponse) -> Self {
        Self {
            valid: response.valid,
            issues: response.issues.into_iter().map(Into::into).collect(),
            stages: response.stages.into_iter().map(Into::into).collect(),
        }
    }
}

impl From<ProtoValidationIssue> for ValidationIssue {
    fn from(issue: ProtoValidationIssue) -> Self {
        Self {
            severity: match crate::perception::ValidationSeverity::try_from(issue.severity) {
                Ok(crate::perception::ValidationSeverity::Error) => ValidationSeverity::Error,
                Ok(crate::perception::ValidationSeverity::Warning) => ValidationSeverity::Warning,
                Ok(crate::perception::ValidationSeverity::Unspecified) => {
                    ValidationSeverity::Unspecified
                }
                Err(value) => ValidationSeverity::Unknown(value.0),
            },
            code: issue.code,
            message: issue.message,
            field_path: issue.field_path,
            stage_id: issue.stage_id,
        }
    }
}

impl From<ProtoResolvedStage> for ResolvedStage {
    fn from(stage: ProtoResolvedStage) -> Self {
        Self {
            id: stage.id,
            name: stage.name,
            role: match crate::perception::ResolvedStageRole::try_from(stage.role) {
                Ok(crate::perception::ResolvedStageRole::Source) => ResolvedStageRole::Source,
                Ok(crate::perception::ResolvedStageRole::Processing) => {
                    ResolvedStageRole::Processing
                }
                Ok(crate::perception::ResolvedStageRole::Output) => ResolvedStageRole::Output,
                Ok(crate::perception::ResolvedStageRole::Unspecified) => {
                    ResolvedStageRole::Unspecified
                }
                Err(value) => ResolvedStageRole::Unknown(value.0),
            },
            controllable: stage.controllable,
            model_id: stage.model_id,
        }
    }
}
