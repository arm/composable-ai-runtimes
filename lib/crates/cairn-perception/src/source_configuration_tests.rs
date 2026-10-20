// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use crate::perception::{WorkflowSpec, source_spec::Source};
use crate::test_helpers::stream_configuration;
use crate::workflow::PerceptionWorkflow;

#[test]
fn workflow_preserves_configuration_fields_in_perception_proto() {
    let configuration = stream_configuration();
    let workflow = PerceptionWorkflow::new("front-door", configuration.clone());

    let proto = WorkflowSpec::from(&workflow);

    let Some(Source::Camera(actual)) = proto.source.unwrap().source else {
        panic!("expected a camera source");
    };
    assert_eq!(actual.camera_id, configuration.camera_id());
    assert_eq!(actual.target, configuration.target());

    let actual_format = actual.format.unwrap();
    let actual_resolution = actual_format.resolution.unwrap();
    let actual_frame_rate = actual_format.frame_rate.unwrap();
    let expected_format = configuration.format();
    assert_eq!(actual_format.pixel_format, expected_format.pixel_format);
    assert_eq!(actual_resolution.width, expected_format.resolution.width);
    assert_eq!(actual_resolution.height, expected_format.resolution.height);
    assert_eq!(
        actual_frame_rate.numerator,
        expected_format.frame_rate.numerator
    );
    assert_eq!(
        actual_frame_rate.denominator,
        expected_format.frame_rate.denominator
    );
}
