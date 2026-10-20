// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use tonic::{Code, Status};

use crate::mock_perception_service::{MockServerHandle, MockSnapshotResponse, start_mock_server};
use crate::perception::{
    GetSessionRequest, PerceptionSession as ProtoPerceptionSession,
    SessionSnapshot as ProtoSessionSnapshot, SessionState as ProtoSessionState,
    SessionStatus as ProtoSessionStatus, StageControlRequest, StatusInfo as ProtoStatusInfo,
};
use crate::{
    PerceptionServiceError, PerceptionSession, SessionSnapshot, SessionState, SessionStatus,
    SessionTopics,
};

async fn connect_test_session(server: &MockServerHandle) -> PerceptionSession {
    let client = crate::perception::perception_service_client::PerceptionServiceClient::connect(
        server.endpoint().to_owned(),
    )
    .await
    .expect("failed to connect client");

    PerceptionSession::new(
        "session-123".to_string(),
        "front-door".to_string(),
        Vec::new(),
        None,
        SessionTopics::default(),
        client,
    )
}

#[tokio::test]
async fn get_status_sends_the_session_id_and_maps_the_snapshot() {
    let server = start_mock_server().await;
    server.set_session_snapshot_response(MockSnapshotResponse::Success(ProtoSessionSnapshot {
        status: Some(ProtoSessionStatus {
            state: ProtoSessionState::Running as i32,
            info: None,
        }),
        disabled_stage_ids: vec!["inference-a".to_string()],
    }));
    let session = connect_test_session(&server).await;
    let snapshot = session.get_status().await.expect("getting status failed");

    assert_eq!(
        server.session_snapshot_request(),
        Some(GetSessionRequest {
            session_id: "session-123".to_string(),
        })
    );
    assert!(matches!(snapshot.status.state, SessionState::Running));
    assert_eq!(snapshot.disabled_stage_ids, ["inference-a"]);
    server.stop().await;
}

#[tokio::test]
async fn get_status_rejects_a_snapshot_without_status() {
    let server = start_mock_server().await;
    server.set_session_snapshot_response(MockSnapshotResponse::Success(ProtoSessionSnapshot {
        status: None,
        disabled_stage_ids: Vec::new(),
    }));
    let session = connect_test_session(&server).await;
    let error = match session.get_status().await {
        Ok(_) => panic!("snapshot without a status should fail"),
        Err(error) => error,
    };

    assert_eq!(
        error,
        PerceptionServiceError::Rpc(
            "invalid perception service response: session snapshot is missing status".to_string(),
        )
    );
    server.stop().await;
}

#[tokio::test]
async fn get_status_maps_grpc_status_to_service_error() {
    let server = start_mock_server().await;
    server.set_session_snapshot_response(MockSnapshotResponse::Failure {
        code: Code::Unavailable,
        message: "runtime unavailable",
    });
    let session = connect_test_session(&server).await;
    let error = match session.get_status().await {
        Ok(_) => panic!("unavailable request should fail"),
        Err(error) => error,
    };

    assert_eq!(
        error,
        PerceptionServiceError::Rpc(
            "failed to get perception session status: Unavailable: runtime unavailable".to_string(),
        )
    );
    server.stop().await;
}

#[test]
fn session_snapshot_maps_status_and_disabled_stages() {
    let snapshot = SessionSnapshot::try_from(ProtoSessionSnapshot {
        status: Some(ProtoSessionStatus {
            state: ProtoSessionState::Running as i32,
            info: Some(ProtoStatusInfo {
                code: "READY".to_string(),
                message: "session is processing frames".to_string(),
            }),
        }),
        disabled_stage_ids: vec!["inference-a".to_string(), "inference-b".to_string()],
    })
    .expect("snapshot should be valid");

    assert!(matches!(snapshot.status.state, SessionState::Running));
    let info = snapshot.status.info.expect("status info should be present");
    assert_eq!(info.code, "READY");
    assert_eq!(info.message, "session is processing frames");
    assert_eq!(snapshot.disabled_stage_ids, ["inference-a", "inference-b"]);
}

#[test]
fn session_snapshot_rejects_missing_status() {
    let result = SessionSnapshot::try_from(ProtoSessionSnapshot {
        status: None,
        disabled_stage_ids: Vec::new(),
    });
    let error = match result {
        Ok(_) => panic!("snapshot without a status should fail"),
        Err(error) => error,
    };

    assert_eq!(
        error,
        PerceptionServiceError::Rpc(
            "invalid perception service response: session snapshot is missing status".to_string(),
        )
    );
}

#[test]
fn session_status_maps_known_states_and_absent_info() {
    macro_rules! assert_state {
        ($proto_state:expr, $expected_state:pat) => {{
            let status = SessionStatus::from(ProtoSessionStatus {
                state: $proto_state as i32,
                info: None,
            });

            assert!(status.info.is_none());
            assert!(matches!(status.state, $expected_state));
        }};
    }

    assert_state!(ProtoSessionState::Unspecified, SessionState::Unspecified);
    assert_state!(ProtoSessionState::Starting, SessionState::Starting);
    assert_state!(ProtoSessionState::Running, SessionState::Running);
    assert_state!(ProtoSessionState::Stopping, SessionState::Stopping);
    assert_state!(ProtoSessionState::Stopped, SessionState::Stopped);
    assert_state!(ProtoSessionState::Failed, SessionState::Failed);
}

#[test]
fn session_status_preserves_unknown_state() {
    let status = SessionStatus::from(ProtoSessionStatus {
        state: 99,
        info: None,
    });

    assert!(matches!(status.state, SessionState::Unknown(99)));
}

#[tokio::test]
async fn disable_stage_forwards_ids() {
    let server = start_mock_server().await;
    let session = connect_test_session(&server).await;
    server.set_stage_control_response(Ok(ProtoPerceptionSession::default()));

    session
        .disable_stage("inference-1")
        .await
        .expect("stage control failed");
    assert_eq!(
        server.disable_stage_request(),
        Some(StageControlRequest {
            session_id: "session-123".to_string(),
            stage_id: "inference-1".to_string(),
        })
    );

    server.stop().await;
}

#[tokio::test]
async fn disable_stage_maps_grpc_status_to_service_error() {
    let server = start_mock_server().await;
    let session = connect_test_session(&server).await;
    server.set_stage_control_response(Err(Status::not_found("stage not found")));
    assert_eq!(
        session.disable_stage("missing-stage").await.unwrap_err(),
        PerceptionServiceError::Rpc(
            "failed to disable perception stage: NotFound: stage not found".to_string()
        )
    );
    server.stop().await;
}

#[tokio::test]
async fn enable_stage_forwards_ids() {
    let server = start_mock_server().await;
    let session = connect_test_session(&server).await;
    server.set_stage_control_response(Ok(ProtoPerceptionSession::default()));

    session
        .enable_stage("inference-1")
        .await
        .expect("stage control failed");
    assert_eq!(
        server.enable_stage_request(),
        Some(StageControlRequest {
            session_id: "session-123".to_string(),
            stage_id: "inference-1".to_string(),
        })
    );

    server.stop().await;
}

#[tokio::test]
async fn enable_stage_maps_grpc_status_to_service_error() {
    let server = start_mock_server().await;
    let session = connect_test_session(&server).await;
    server.set_stage_control_response(Err(Status::not_found("stage not found")));
    assert_eq!(
        session.enable_stage("missing-stage").await.unwrap_err(),
        PerceptionServiceError::Rpc(
            "failed to enable perception stage: NotFound: stage not found".to_string()
        )
    );
    server.stop().await;
}
