// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use crate::output::DebugOutput;
use crate::perception::{
    InferenceStage as ProtoInferenceStage, SourceSpec, WorkflowSpec, source_spec,
};
use crate::test_helpers::stream_configuration;
use crate::workflow::PerceptionWorkflow;

#[test]
fn workflow_spec_from_workflow_maps_source_and_inference_stages() {
    let source_configuration = stream_configuration();
    let mut workflow = PerceptionWorkflow::new("front-door", source_configuration.clone());
    workflow.set_output_events(false);
    workflow.infer("objects", "yolov11");
    workflow.infer("people", "yolov8");

    let spec = WorkflowSpec::from(&workflow);

    assert_eq!(spec.name, "front-door");
    assert_eq!(
        spec.source,
        Some(SourceSpec {
            source: Some(source_spec::Source::Camera((&source_configuration).into())),
        })
    );
    assert_eq!(
        spec.stages,
        vec![
            ProtoInferenceStage {
                id: "inference-1".to_string(),
                name: "objects".to_string(),
                model_id: "yolov11".to_string(),
            },
            ProtoInferenceStage {
                id: "inference-2".to_string(),
                name: "people".to_string(),
                model_id: "yolov8".to_string(),
            },
        ]
    );
    assert_eq!(spec.output, None);
    assert_eq!(spec.output_events, Some(false));
}

#[test]
fn workflow_spec_from_workflow_maps_debug_output() {
    let mut workflow = PerceptionWorkflow::new("front-door", stream_configuration());
    workflow.set_debug_output(DebugOutput {
        http_port: 9999,
        ws_port: 8000,
        ctrl_port: 8001,
    });

    let spec = WorkflowSpec::from(&workflow);

    assert_eq!(
        spec.output,
        Some(crate::perception::OutputSpec {
            output: Some(crate::perception::output_spec::Output::Debug(
                crate::perception::DebugOutput {
                    http_port: 9999,
                    ws_port: 8000,
                    ctrl_port: 8001,
                },
            )),
        })
    );
    assert_eq!(spec.output_events, Some(true));
}
