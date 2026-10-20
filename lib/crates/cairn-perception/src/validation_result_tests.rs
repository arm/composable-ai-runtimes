// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use crate::perception::{
    ResolvedStage as ProtoResolvedStage, ValidationIssue as ProtoValidationIssue,
};
use crate::{ResolvedStage, ResolvedStageRole, ValidationIssue, ValidationSeverity};

#[test]
fn validation_issue_from_proto_preserves_unknown_severity() {
    let issue = ValidationIssue::from(ProtoValidationIssue {
        severity: 99,
        code: String::new(),
        message: String::new(),
        field_path: None,
        stage_id: None,
    });

    assert_eq!(issue.severity, ValidationSeverity::Unknown(99));
}

#[test]
fn resolved_stage_from_proto_preserves_unknown_role() {
    let stage = ResolvedStage::from(ProtoResolvedStage {
        id: String::new(),
        name: String::new(),
        role: 99,
        controllable: false,
        model_id: None,
    });

    assert_eq!(stage.role, ResolvedStageRole::Unknown(99));
}
