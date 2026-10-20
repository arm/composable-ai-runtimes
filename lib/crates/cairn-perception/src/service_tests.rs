// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::time::Duration;
use tokio::time::timeout;
use tonic::Code;
use tonic::transport::Server;
use tonic::transport::server::TcpIncoming;
use tonic_health::ServingStatus;

use crate::mock_perception_service::{
    MockDeploymentResponse, MockGetResponse, MockListResponse, MockServerHandle, MockStopResponse,
    MockValidationResponse, start_mock_server,
};
use crate::perception;
use crate::test_helpers::stream_configuration;
use crate::workflow::PerceptionWorkflow;
use crate::{
    DebugPorts, PerceptionService, PerceptionServiceError, PerceptionSession, ResolvedStage,
    ResolvedStageRole, SessionTopics, ValidationIssue, ValidationSeverity,
};
use perception::perception_service_client::PerceptionServiceClient;
use perception::{
    DebugPorts as ProtoDebugPorts, DeployWorkflowRequest, DeployWorkflowResponse,
    DeploymentAccepted, DeploymentRejected, GetSessionRequest,
    PerceptionSession as ProtoPerceptionSession, ResolvedStage as ProtoResolvedStage,
    ResolvedStageRole as ProtoResolvedStageRole, SessionTopics as ProtoSessionTopics,
    StopSessionRequest, ValidateWorkflowResponse, ValidationIssue as ProtoValidationIssue,
    ValidationSeverity as ProtoValidationSeverity, deploy_workflow_response,
};

async fn connect_to_mock_server(server: &MockServerHandle) -> PerceptionService {
    PerceptionService::new(Some(server.endpoint().to_owned()))
        .await
        .expect("failed to create client")
}

#[tokio::test]
async fn get_session_sends_id_and_maps_session_metadata() {
    let server = start_mock_server().await;
    server.set_get_response(MockGetResponse::Success(ProtoPerceptionSession {
        id: "session-z".to_string(),
        workflow_name: "front-door".to_string(),
        stages: vec![ProtoResolvedStage {
            id: "inference-1".to_string(),
            name: "objects".to_string(),
            role: ProtoResolvedStageRole::Processing as i32,
            controllable: true,
            model_id: Some("yolov11".to_string()),
        }],
        debug_endpoint: Some(ProtoDebugPorts {
            http_port: 9999,
            ws_port: 8000,
            ctrl_port: 8001,
        }),
        topics: Some(ProtoSessionTopics {
            results: "custom.results".to_string(),
            events: "custom.events".to_string(),
        }),
    }));
    let mut service = connect_to_mock_server(&server).await;

    let session = service
        .get_session("session-z")
        .await
        .expect("getting session failed");

    assert_eq!(
        server.get_request(),
        Some(GetSessionRequest {
            session_id: "session-z".to_string(),
        })
    );
    assert_eq!(session.id(), "session-z");
    assert_eq!(session.workflow_name(), "front-door");
    assert_eq!(
        session.stages(),
        &[ResolvedStage {
            id: "inference-1".to_string(),
            name: "objects".to_string(),
            role: ResolvedStageRole::Processing,
            controllable: true,
            model_id: Some("yolov11".to_string()),
        }]
    );
    assert_eq!(
        session.debug_endpoint(),
        Some(&DebugPorts {
            http_port: 9999,
            ws_port: 8000,
            ctrl_port: 8001,
        })
    );
    assert_eq!(
        session.topics(),
        &SessionTopics {
            results: Some("custom.results".to_string()),
            events: Some("custom.events".to_string()),
        }
    );
    server.stop().await;
}

#[tokio::test]
async fn get_session_rejects_a_response_without_an_id() {
    let server = start_mock_server().await;
    server.set_get_response(MockGetResponse::Success(ProtoPerceptionSession {
        topics: Some(ProtoSessionTopics::default()),
        ..Default::default()
    }));
    let mut service = connect_to_mock_server(&server).await;

    let error = service
        .get_session("session-z")
        .await
        .expect_err("invalid session should fail");

    assert_eq!(
        error,
        PerceptionServiceError::InvalidResponse(
            "invalid perception service response: session is missing an ID".to_string(),
        )
    );
    server.stop().await;
}

#[tokio::test]
async fn get_session_defaults_missing_topics() {
    let server = start_mock_server().await;
    server.set_get_response(MockGetResponse::Success(ProtoPerceptionSession {
        id: "session-z".to_string(),
        ..Default::default()
    }));
    let mut service = connect_to_mock_server(&server).await;

    let session = service
        .get_session("session-z")
        .await
        .expect("session without topics should use default topics");

    assert_eq!(session.topics(), &SessionTopics::default());
    server.stop().await;
}

#[tokio::test]
async fn get_session_maps_not_found_to_an_rpc_error() {
    let server = start_mock_server().await;
    server.set_get_response(MockGetResponse::Failure {
        code: Code::NotFound,
        message: "session not found",
    });
    let mut service = connect_to_mock_server(&server).await;

    let error = service
        .get_session("missing-session")
        .await
        .expect_err("missing session should fail");

    assert_eq!(
        error,
        PerceptionServiceError::Rpc(
            "failed to get perception session: NotFound: session not found".to_string(),
        )
    );
    server.stop().await;
}

#[tokio::test]
async fn list_sessions_returns_empty_list_if_no_sessions_recorded() {
    let server = start_mock_server().await;
    server.set_list_response(MockListResponse::Success(
        perception::ListSessionsResponse {
            sessions: Vec::new(),
        },
    ));
    let mut service = connect_to_mock_server(&server).await;

    let sessions = service
        .list_sessions()
        .await
        .expect("listing sessions failed");

    assert!(sessions.is_empty());
    server.stop().await;
}

#[test]
fn session_topics_maps_empty_topic_names_to_none_independently() {
    assert_eq!(
        SessionTopics::from(ProtoSessionTopics {
            results: String::new(),
            events: "custom.events".to_string(),
        }),
        SessionTopics {
            results: None,
            events: Some("custom.events".to_string()),
        }
    );
    assert_eq!(
        SessionTopics::from(ProtoSessionTopics {
            results: "custom.results".to_string(),
            events: String::new(),
        }),
        SessionTopics {
            results: Some("custom.results".to_string()),
            events: None,
        }
    );
}

#[tokio::test]
async fn list_sessions_maps_session_metadata() {
    let server = start_mock_server().await;
    server.set_list_response(MockListResponse::Success(
        perception::ListSessionsResponse {
            sessions: vec![ProtoPerceptionSession {
                id: "session-z".to_string(),
                workflow_name: "front-door".to_string(),
                stages: vec![ProtoResolvedStage {
                    id: "inference-1".to_string(),
                    name: "objects".to_string(),
                    role: ProtoResolvedStageRole::Processing as i32,
                    controllable: true,
                    model_id: Some("yolov11".to_string()),
                }],
                debug_endpoint: Some(ProtoDebugPorts {
                    http_port: 9999,
                    ws_port: 8000,
                    ctrl_port: 8001,
                }),
                topics: Some(ProtoSessionTopics {
                    results: "custom.results".to_string(),
                    events: "custom.events".to_string(),
                }),
            }],
        },
    ));
    let mut service = connect_to_mock_server(&server).await;

    let sessions = service
        .list_sessions()
        .await
        .expect("listing sessions failed");
    assert_eq!(sessions.len(), 1);
    assert_eq!(sessions[0].id(), "session-z");
    assert_eq!(sessions[0].workflow_name(), "front-door");
    assert_eq!(
        sessions[0].stages(),
        &[ResolvedStage {
            id: "inference-1".to_string(),
            name: "objects".to_string(),
            role: ResolvedStageRole::Processing,
            controllable: true,
            model_id: Some("yolov11".to_string()),
        }]
    );
    assert_eq!(
        sessions[0].debug_endpoint(),
        Some(&DebugPorts {
            http_port: 9999,
            ws_port: 8000,
            ctrl_port: 8001,
        })
    );
    assert_eq!(
        sessions[0].topics(),
        &SessionTopics {
            results: Some("custom.results".to_string()),
            events: Some("custom.events".to_string()),
        }
    );
    server.stop().await;
}

#[tokio::test]
async fn list_sessions_preserves_response_order() {
    let server = start_mock_server().await;
    server.set_list_response(MockListResponse::Success(
        perception::ListSessionsResponse {
            sessions: vec![
                ProtoPerceptionSession {
                    id: "session-z".to_string(),
                    topics: Some(ProtoSessionTopics::default()),
                    ..Default::default()
                },
                ProtoPerceptionSession {
                    id: "session-a".to_string(),
                    topics: Some(ProtoSessionTopics::default()),
                    ..Default::default()
                },
            ],
        },
    ));
    let mut service = connect_to_mock_server(&server).await;

    let sessions = service
        .list_sessions()
        .await
        .expect("listing sessions failed");

    assert_eq!(
        sessions
            .iter()
            .map(PerceptionSession::id)
            .collect::<Vec<_>>(),
        ["session-z", "session-a"]
    );
    assert!(
        sessions
            .iter()
            .all(|session| session.topics() == &SessionTopics::default())
    );
    server.stop().await;
}

#[tokio::test]
async fn list_sessions_rejects_a_session_without_an_id() {
    let server = start_mock_server().await;
    server.set_list_response(MockListResponse::Success(
        perception::ListSessionsResponse {
            sessions: vec![ProtoPerceptionSession {
                topics: Some(ProtoSessionTopics::default()),
                ..Default::default()
            }],
        },
    ));
    let mut service = connect_to_mock_server(&server).await;

    let error = service
        .list_sessions()
        .await
        .expect_err("invalid list should fail");

    assert_eq!(
        error,
        PerceptionServiceError::InvalidResponse(
            "invalid perception service response: session is missing an ID".to_string(),
        )
    );
    server.stop().await;
}

#[tokio::test]
async fn list_sessions_maps_unavailable_to_an_rpc_error() {
    let server = start_mock_server().await;
    server.set_list_response(MockListResponse::Failure {
        code: Code::Unavailable,
        message: "runtime unavailable",
    });
    let mut service = connect_to_mock_server(&server).await;

    let error = service
        .list_sessions()
        .await
        .expect_err("listing should fail");

    assert_eq!(
        error,
        PerceptionServiceError::Rpc(
            "failed to list perception sessions: Unavailable: runtime unavailable".to_string(),
        )
    );
    server.stop().await;
}

#[tokio::test]
async fn get_service_info_maps_proto_to_library_type() {
    let server = start_mock_server().await;
    let mut service = connect_to_mock_server(&server).await;

    let info = service
        .get_service_info()
        .await
        .expect("get_service_info failed");

    assert_eq!(info.api_version, "v1");
    assert_eq!(info.service_version, "0.1.0");
    assert!(!info.sessions_survive_restart);

    server.stop().await;
}

#[tokio::test]
async fn validate_maps_valid_response() {
    let server = start_mock_server().await;
    server.set_validation_response(MockValidationResponse::Success(ValidateWorkflowResponse {
        valid: true,
        issues: Vec::new(),
        stages: vec![
            ProtoResolvedStage {
                id: "source:camera".to_string(),
                name: "pipewire_source".to_string(),
                role: ProtoResolvedStageRole::Source as i32,
                controllable: false,
                model_id: None,
            },
            ProtoResolvedStage {
                id: "inference-1".to_string(),
                name: "objects".to_string(),
                role: ProtoResolvedStageRole::Processing as i32,
                controllable: true,
                model_id: Some("yolov11".to_string()),
            },
            ProtoResolvedStage {
                id: "output:debug".to_string(),
                name: "opksink".to_string(),
                role: ProtoResolvedStageRole::Output as i32,
                controllable: false,
                model_id: None,
            },
        ],
    }));
    let mut service = connect_to_mock_server(&server).await;
    let workflow = PerceptionWorkflow::new("front-door", stream_configuration());
    let expected_stages = vec![
        ResolvedStage {
            id: "source:camera".to_string(),
            name: "pipewire_source".to_string(),
            role: ResolvedStageRole::Source,
            controllable: false,
            model_id: None,
        },
        ResolvedStage {
            id: "inference-1".to_string(),
            name: "objects".to_string(),
            role: ResolvedStageRole::Processing,
            controllable: true,
            model_id: Some("yolov11".to_string()),
        },
        ResolvedStage {
            id: "output:debug".to_string(),
            name: "opksink".to_string(),
            role: ResolvedStageRole::Output,
            controllable: false,
            model_id: None,
        },
    ];

    let validation = service
        .validate(&workflow)
        .await
        .expect("workflow validation failed");

    assert!(validation.valid);
    assert!(validation.issues.is_empty());
    assert_eq!(validation.stages, expected_stages);
    server.stop().await;
}

#[tokio::test]
async fn validate_returns_invalid_result_with_issues() {
    let server = start_mock_server().await;
    server.set_validation_response(MockValidationResponse::Success(ValidateWorkflowResponse {
        valid: false,
        issues: vec![ProtoValidationIssue {
            severity: ProtoValidationSeverity::Error as i32,
            code: "MODEL_NOT_FOUND".to_string(),
            message: "model 'missing' is unavailable".to_string(),
            field_path: Some("stages[0].model_id".to_string()),
            stage_id: Some("inference-1".to_string()),
        }],
        stages: Vec::new(),
    }));
    let mut service = connect_to_mock_server(&server).await;
    let mut workflow = PerceptionWorkflow::new("front-door", stream_configuration());
    workflow.infer("objects", "missing");
    let expected_issues = vec![ValidationIssue {
        severity: ValidationSeverity::Error,
        code: "MODEL_NOT_FOUND".to_string(),
        message: "model 'missing' is unavailable".to_string(),
        field_path: Some("stages[0].model_id".to_string()),
        stage_id: Some("inference-1".to_string()),
    }];

    let validation = service
        .validate(&workflow)
        .await
        .expect("workflow validation failed");

    assert!(!validation.valid);
    assert_eq!(validation.issues, expected_issues);
    assert!(validation.stages.is_empty());

    server.stop().await;
}

#[tokio::test]
async fn validate_maps_grpc_status_to_service_error() {
    let server = start_mock_server().await;
    server.set_validation_response(MockValidationResponse::Failure {
        code: Code::Unavailable,
        message: "runtime unavailable",
    });
    let mut service = connect_to_mock_server(&server).await;
    let workflow = PerceptionWorkflow::new("front-door", stream_configuration());
    let expected_error = PerceptionServiceError::Rpc(
        "failed to validate perception workflow: Unavailable: runtime unavailable".to_string(),
    );

    let error = service
        .validate(&workflow)
        .await
        .expect_err("workflow validation should fail");

    assert_eq!(error, expected_error);

    server.stop().await;
}

#[tokio::test]
async fn stop_sends_session_id() {
    let server = start_mock_server().await;
    server.set_stop_response(MockStopResponse::Success(ProtoPerceptionSession {
        id: "session-123".to_string(),
        ..Default::default()
    }));
    let client = PerceptionServiceClient::connect(server.endpoint().to_owned())
        .await
        .expect("failed to connect client");
    let session = PerceptionSession::new(
        "session-123".to_string(),
        "front-door".to_string(),
        Vec::new(),
        None,
        SessionTopics::default(),
        client,
    );
    let expected_request = StopSessionRequest {
        session_id: "session-123".to_string(),
    };

    session
        .stop()
        .await
        .expect("stopping session should succeed");

    assert_eq!(
        server
            .stop_request()
            .expect("stop request should be received"),
        expected_request
    );

    server.stop().await;
}

#[tokio::test]
async fn stop_maps_grpc_status_to_service_error() {
    let server = start_mock_server().await;
    server.set_stop_response(MockStopResponse::Failure {
        code: Code::Unavailable,
        message: "runtime unavailable",
    });
    let client = PerceptionServiceClient::connect(server.endpoint().to_owned())
        .await
        .expect("failed to connect client");
    let session = PerceptionSession::new(
        "session-123".to_string(),
        "front-door".to_string(),
        Vec::new(),
        None,
        SessionTopics::default(),
        client,
    );
    let expected_error = PerceptionServiceError::Rpc(
        "failed to stop perception session: Unavailable: runtime unavailable".to_string(),
    );

    let error = session
        .stop()
        .await
        .expect_err("stopping session should fail");

    assert_eq!(error, expected_error);

    server.stop().await;
}

fn test_workflow() -> PerceptionWorkflow {
    PerceptionWorkflow::new("front-door", stream_configuration())
}

fn accepted_deployment_response(session: ProtoPerceptionSession) -> MockDeploymentResponse {
    MockDeploymentResponse::Success(DeployWorkflowResponse {
        outcome: Some(deploy_workflow_response::Outcome::Accepted(
            DeploymentAccepted {
                session: Some(session),
            },
        )),
    })
}

#[tokio::test]
async fn deploy_sends_workflow_and_maps_session() {
    let server = start_mock_server().await;
    let expected_stages = vec![ResolvedStage {
        id: "inference-1".to_string(),
        name: "objects".to_string(),
        role: ResolvedStageRole::Processing,
        controllable: true,
        model_id: Some("yolov11".to_string()),
    }];
    let expected_debug_endpoint = DebugPorts {
        http_port: 9999,
        ws_port: 8000,
        ctrl_port: 8001,
    };
    let results_topic = "perception.sessions.session-123.results".to_string();
    let events_topic = "perception.sessions.session-123.events".to_string();
    let expected_topics = SessionTopics {
        results: Some(results_topic.clone()),
        events: Some(events_topic.clone()),
    };
    server.set_deployment_response(accepted_deployment_response(ProtoPerceptionSession {
        id: "session-123".to_string(),
        workflow_name: "front-door".to_string(),
        stages: vec![ProtoResolvedStage {
            id: "inference-1".to_string(),
            name: "objects".to_string(),
            role: ProtoResolvedStageRole::Processing as i32,
            controllable: true,
            model_id: Some("yolov11".to_string()),
        }],
        debug_endpoint: Some(ProtoDebugPorts {
            http_port: 9999,
            ws_port: 8000,
            ctrl_port: 8001,
        }),
        topics: Some(ProtoSessionTopics {
            results: results_topic,
            events: events_topic,
        }),
    }));
    let mut service = connect_to_mock_server(&server).await;
    let mut workflow = test_workflow();
    workflow.infer("objects", "yolov11");
    let expected_request = DeployWorkflowRequest {
        workflow: Some((&workflow).into()),
    };

    let session = service
        .deploy(&workflow)
        .await
        .expect("workflow deployment should succeed");

    assert_eq!(
        server
            .deployment_request()
            .expect("deployment request should be received"),
        expected_request
    );
    assert_eq!(session.id(), "session-123");
    assert_eq!(session.workflow_name(), "front-door");
    assert_eq!(session.stages(), expected_stages);
    assert_eq!(session.debug_endpoint(), Some(&expected_debug_endpoint));
    assert_eq!(session.topics(), &expected_topics);

    server.stop().await;
}

#[tokio::test]
async fn deploy_maps_rejection_issues() {
    let server = start_mock_server().await;
    server.set_deployment_response(MockDeploymentResponse::Success(DeployWorkflowResponse {
        outcome: Some(deploy_workflow_response::Outcome::Rejected(
            DeploymentRejected {
                issues: vec![ProtoValidationIssue {
                    severity: ProtoValidationSeverity::Error as i32,
                    code: "MODEL_NOT_FOUND".to_string(),
                    message: "model 'missing' is unavailable".to_string(),
                    field_path: Some("stages[0].model_id".to_string()),
                    stage_id: Some("inference-1".to_string()),
                }],
            },
        )),
    }));
    let mut service = connect_to_mock_server(&server).await;
    let workflow = test_workflow();
    let expected_error = PerceptionServiceError::Workflow(vec![ValidationIssue {
        severity: ValidationSeverity::Error,
        code: "MODEL_NOT_FOUND".to_string(),
        message: "model 'missing' is unavailable".to_string(),
        field_path: Some("stages[0].model_id".to_string()),
        stage_id: Some("inference-1".to_string()),
    }]);

    let error = service
        .deploy(&workflow)
        .await
        .expect_err("rejected deployment should return a workflow error");

    assert_eq!(error, expected_error);

    server.stop().await;
}

#[tokio::test]
async fn deploy_rejects_a_missing_outcome() {
    let server = start_mock_server().await;
    server.set_deployment_response(MockDeploymentResponse::Success(DeployWorkflowResponse {
        outcome: None,
    }));
    let mut service = connect_to_mock_server(&server).await;
    let workflow = test_workflow();
    let expected_error = PerceptionServiceError::Rpc(
        "invalid perception service response: deployment response is missing an outcome"
            .to_string(),
    );

    let error = service
        .deploy(&workflow)
        .await
        .expect_err("missing deployment outcome should return an RPC error");

    assert_eq!(error, expected_error);

    server.stop().await;
}

#[tokio::test]
async fn deploy_rejects_a_missing_session() {
    let server = start_mock_server().await;
    server.set_deployment_response(MockDeploymentResponse::Success(DeployWorkflowResponse {
        outcome: Some(deploy_workflow_response::Outcome::Accepted(
            DeploymentAccepted { session: None },
        )),
    }));
    let mut service = connect_to_mock_server(&server).await;
    let workflow = test_workflow();
    let expected_error = PerceptionServiceError::Rpc(
        "invalid perception service response: accepted deployment response is missing a session"
            .to_string(),
    );

    let error = service
        .deploy(&workflow)
        .await
        .expect_err("missing deployment session should return an RPC error");

    assert_eq!(error, expected_error);

    server.stop().await;
}

#[tokio::test]
async fn deploy_rejects_a_session_missing_its_id() {
    let server = start_mock_server().await;
    server.set_deployment_response(accepted_deployment_response(ProtoPerceptionSession {
        topics: Some(ProtoSessionTopics::default()),
        ..Default::default()
    }));
    let mut service = connect_to_mock_server(&server).await;
    let workflow = test_workflow();
    let expected_error = PerceptionServiceError::InvalidResponse(
        "invalid perception service response: session is missing an ID".to_string(),
    );

    let error = service
        .deploy(&workflow)
        .await
        .expect_err("session without an ID should return an invalid-response error");

    assert_eq!(error, expected_error);

    server.stop().await;
}

#[tokio::test]
async fn deploy_defaults_missing_topics() {
    let server = start_mock_server().await;
    server.set_deployment_response(accepted_deployment_response(ProtoPerceptionSession {
        id: "session-123".to_string(),
        ..Default::default()
    }));
    let mut service = connect_to_mock_server(&server).await;
    let workflow = test_workflow();

    let session = service
        .deploy(&workflow)
        .await
        .expect("session without topics should use default topics");

    assert_eq!(session.topics(), &SessionTopics::default());

    server.stop().await;
}

async fn start_health_server(
    status: ServingStatus,
) -> (
    String,
    tonic_health::server::HealthReporter,
    tokio::task::JoinHandle<()>,
) {
    let incoming = TcpIncoming::bind("127.0.0.1:0".parse().unwrap()).unwrap();
    let endpoint = format!("http://{}", incoming.local_addr().unwrap());
    let (reporter, health_service) = tonic_health::server::health_reporter();
    reporter.set_service_status("", status).await;
    let server = tokio::spawn(async move {
        Server::builder()
            .add_service(health_service)
            .serve_with_incoming(incoming)
            .await
            .expect("test health server failed");
    });

    (endpoint, reporter, server)
}

#[tokio::test]
async fn waits_for_serving() {
    let (endpoint, reporter, server) = start_health_server(ServingStatus::NotServing).await;
    let readiness = PerceptionService::new(Some(endpoint));
    tokio::pin!(readiness);
    assert!(
        timeout(Duration::from_millis(100), &mut readiness)
            .await
            .is_err(),
        "readiness must stay pending while health is NOT_SERVING"
    );

    reporter
        .set_service_status("", ServingStatus::Serving)
        .await;
    timeout(Duration::from_secs(2), readiness)
        .await
        .expect("readiness did not complete after SERVING")
        .expect("readiness failed after SERVING");

    server.abort();
    let _ = server.await;
}

#[tokio::test]
async fn accepts_already_serving() {
    let (endpoint, _reporter, server) = start_health_server(ServingStatus::Serving).await;
    timeout(
        Duration::from_secs(2),
        PerceptionService::new(Some(endpoint)),
    )
    .await
    .expect("already-serving health did not complete readiness")
    .expect("readiness failed for an already-serving service");

    server.abort();
    let _ = server.await;
}
