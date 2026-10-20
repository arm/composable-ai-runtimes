// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use crate::output::DebugOutput;
use crate::perception::{
    InferenceStage as ProtoInferenceStage, SourceSpec, WorkflowSpec,
    source_spec::Source as ProtoSource,
};
use cairn_camera::StreamConfiguration;

/// Identifies a stage added to a workflow.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StageHandle {
    /// Generated stage identifier.
    pub id: String,
    /// User-facing stage name.
    pub name: String,
}

/// A workflow specification built locally for validation or deployment.
///
/// Start with a camera-discovered stream configuration, add inference stages, then
/// validate or deploy with [`crate::PerceptionService`]. Building a workflow does not
/// contact the service; models must already be registered there.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PerceptionWorkflow {
    pub(crate) name: String,
    pub(crate) source_configuration: StreamConfiguration,
    pub(crate) stages: Vec<InferenceStage>,
    pub(crate) debug_output: Option<DebugOutput>,
    pub(crate) output_events: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct InferenceStage {
    pub id: String,
    pub name: String,
    pub model_id: String,
}

impl PerceptionWorkflow {
    /// Creates a workflow, taking ownership of the camera source configuration.
    pub fn new(name: impl Into<String>, source_configuration: StreamConfiguration) -> Self {
        Self {
            name: name.into(),
            source_configuration,
            stages: Vec::new(),
            debug_output: None,
            output_events: true,
        }
    }

    /// Adds an inference stage and returns its generated handle.
    ///
    /// `model_id` is the model package directory name registered by the service.
    pub fn infer(&mut self, name: impl Into<String>, model_id: impl Into<String>) -> StageHandle {
        let id = format!("inference-{}", self.stages.len() + 1);
        let name = name.into();
        self.stages.push(InferenceStage {
            id: id.clone(),
            name: name.clone(),
            model_id: model_id.into(),
        });

        StageHandle { id, name }
    }

    /// Enables debug output with the requested ports.
    pub fn set_debug_output(&mut self, output: DebugOutput) {
        self.debug_output = Some(output);
    }

    /// Selects whether the service publishes lifecycle events (enabled by default).
    pub fn set_output_events(&mut self, enabled: bool) {
        self.output_events = enabled;
    }
}

impl From<&PerceptionWorkflow> for WorkflowSpec {
    fn from(workflow: &PerceptionWorkflow) -> Self {
        Self {
            name: workflow.name.clone(),
            source: Some(SourceSpec {
                source: Some(ProtoSource::Camera((&workflow.source_configuration).into())),
            }),
            stages: workflow.stages.iter().map(Into::into).collect(),
            output: workflow.debug_output.map(Into::into),
            output_events: Some(workflow.output_events),
        }
    }
}

impl From<&InferenceStage> for ProtoInferenceStage {
    fn from(stage: &InferenceStage) -> Self {
        Self {
            id: stage.id.clone(),
            name: stage.name.clone(),
            model_id: stage.model_id.clone(),
        }
    }
}
