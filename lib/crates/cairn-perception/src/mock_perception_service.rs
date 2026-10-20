// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use std::sync::{Arc, Mutex};

use tokio::sync::oneshot;
use tokio::task::JoinHandle;
use tonic::transport::Server;
use tonic::transport::server::TcpIncoming;
use tonic::{Code, Request, Response, Status};

use crate::perception;
use crate::perception::perception_service_server::{
    PerceptionService as ProtoPerceptionService, PerceptionServiceServer,
};
use crate::perception::{
    DeployWorkflowRequest, DeployWorkflowResponse, GetSessionRequest,
    PerceptionSession as ProtoPerceptionSession, SessionSnapshot as ProtoSessionSnapshot,
    StopSessionRequest, ValidateWorkflowResponse,
};

#[derive(Clone)]
pub(crate) enum MockValidationResponse {
    Success(ValidateWorkflowResponse),
    Failure { code: Code, message: &'static str },
}

#[derive(Clone)]
pub(crate) enum MockDeploymentResponse {
    Success(DeployWorkflowResponse),
}

#[derive(Clone)]
pub(crate) enum MockStopResponse {
    Success(ProtoPerceptionSession),
    Failure { code: Code, message: &'static str },
}

#[derive(Clone)]
pub(crate) enum MockListResponse {
    Success(perception::ListSessionsResponse),
    Failure { code: Code, message: &'static str },
}

#[derive(Clone)]
pub(crate) enum MockGetResponse {
    Success(ProtoPerceptionSession),
    Failure { code: Code, message: &'static str },
}

#[derive(Clone)]
pub(crate) enum MockSnapshotResponse {
    Success(ProtoSessionSnapshot),
    Failure { code: Code, message: &'static str },
}

struct MockPerceptionService {
    get_response: Arc<Mutex<Option<MockGetResponse>>>,
    get_request: Arc<Mutex<Option<GetSessionRequest>>>,
    list_response: Arc<Mutex<Option<MockListResponse>>>,
    validation_response: Arc<Mutex<Option<MockValidationResponse>>>,
    deployment_response: Arc<Mutex<Option<MockDeploymentResponse>>>,
    deployment_request: Arc<Mutex<Option<DeployWorkflowRequest>>>,
    stage_control_response: Arc<Mutex<Option<Result<ProtoPerceptionSession, Status>>>>,
    enable_stage_request: Arc<Mutex<Option<perception::StageControlRequest>>>,
    disable_stage_request: Arc<Mutex<Option<perception::StageControlRequest>>>,
    stop_response: Arc<Mutex<Option<MockStopResponse>>>,
    stop_request: Arc<Mutex<Option<StopSessionRequest>>>,
    session_snapshot_response: Arc<Mutex<Option<MockSnapshotResponse>>>,
    session_snapshot_request: Arc<Mutex<Option<GetSessionRequest>>>,
}

#[tonic::async_trait]
impl ProtoPerceptionService for MockPerceptionService {
    async fn get_service_info(
        &self,
        _request: Request<perception::GetServiceInfoRequest>,
    ) -> Result<Response<perception::GetServiceInfoResponse>, Status> {
        Ok(Response::new(perception::GetServiceInfoResponse {
            api_version: "v1".to_string(),
            service_version: "0.1.0".to_string(),
            sessions_survive_restart: false,
        }))
    }

    async fn validate_workflow(
        &self,
        _request: Request<perception::ValidateWorkflowRequest>,
    ) -> Result<Response<ValidateWorkflowResponse>, Status> {
        let response = self
            .validation_response
            .lock()
            .expect("validation response mutex is in a bad state")
            .clone()
            .ok_or_else(|| Status::failed_precondition("validation response not configured"))?;
        match response {
            MockValidationResponse::Success(response) => Ok(Response::new(response)),
            MockValidationResponse::Failure { code, message } => Err(Status::new(code, message)),
        }
    }

    async fn deploy_workflow(
        &self,
        request: Request<DeployWorkflowRequest>,
    ) -> Result<Response<DeployWorkflowResponse>, Status> {
        *self
            .deployment_request
            .lock()
            .expect("deployment request mutex is in a bad state") = Some(request.into_inner());
        let response = self
            .deployment_response
            .lock()
            .expect("deployment response mutex is in a bad state")
            .clone()
            .ok_or_else(|| Status::failed_precondition("deployment response not configured"))?;
        match response {
            MockDeploymentResponse::Success(response) => Ok(Response::new(response)),
        }
    }

    async fn get_session(
        &self,
        request: Request<GetSessionRequest>,
    ) -> Result<Response<ProtoPerceptionSession>, Status> {
        *self
            .get_request
            .lock()
            .expect("get request mutex is in a bad state") = Some(request.into_inner());
        let response = self
            .get_response
            .lock()
            .expect("get response mutex is in a bad state")
            .clone()
            .ok_or_else(|| Status::failed_precondition("get response not configured"))?;
        match response {
            MockGetResponse::Success(response) => Ok(Response::new(response)),
            MockGetResponse::Failure { code, message } => Err(Status::new(code, message)),
        }
    }

    async fn list_sessions(
        &self,
        _request: Request<perception::ListSessionsRequest>,
    ) -> Result<Response<perception::ListSessionsResponse>, Status> {
        let response = self
            .list_response
            .lock()
            .expect("list response mutex is in a bad state")
            .clone()
            .ok_or_else(|| Status::failed_precondition("list response not configured"))?;
        match response {
            MockListResponse::Success(response) => Ok(Response::new(response)),
            MockListResponse::Failure { code, message } => Err(Status::new(code, message)),
        }
    }

    async fn get_session_snapshot(
        &self,
        request: Request<GetSessionRequest>,
    ) -> Result<Response<ProtoSessionSnapshot>, Status> {
        *self
            .session_snapshot_request
            .lock()
            .expect("snapshot request mutex is in a bad state") = Some(request.into_inner());
        let response = self
            .session_snapshot_response
            .lock()
            .expect("snapshot response mutex is in a bad state")
            .clone()
            .ok_or_else(|| Status::failed_precondition("snapshot response not configured"))?;
        match response {
            MockSnapshotResponse::Success(response) => Ok(Response::new(response)),
            MockSnapshotResponse::Failure { code, message } => Err(Status::new(code, message)),
        }
    }

    async fn stop_session(
        &self,
        request: Request<StopSessionRequest>,
    ) -> Result<Response<ProtoPerceptionSession>, Status> {
        *self
            .stop_request
            .lock()
            .expect("stop request mutex is in a bad state") = Some(request.into_inner());
        let response = self
            .stop_response
            .lock()
            .expect("stop response mutex is in a bad state")
            .clone()
            .ok_or_else(|| Status::failed_precondition("stop response not configured"))?;
        match response {
            MockStopResponse::Success(response) => Ok(Response::new(response)),
            MockStopResponse::Failure { code, message } => Err(Status::new(code, message)),
        }
    }

    async fn enable_stage(
        &self,
        request: Request<perception::StageControlRequest>,
    ) -> Result<Response<ProtoPerceptionSession>, Status> {
        *self
            .enable_stage_request
            .lock()
            .expect("stage request mutex poisoned") = Some(request.into_inner());
        self.stage_control_response
            .lock()
            .expect("stage response mutex poisoned")
            .clone()
            .ok_or_else(|| Status::failed_precondition("stage response not configured"))?
            .map(Response::new)
    }

    async fn disable_stage(
        &self,
        request: Request<perception::StageControlRequest>,
    ) -> Result<Response<ProtoPerceptionSession>, Status> {
        *self
            .disable_stage_request
            .lock()
            .expect("stage request mutex poisoned") = Some(request.into_inner());
        self.stage_control_response
            .lock()
            .expect("stage response mutex poisoned")
            .clone()
            .ok_or_else(|| Status::failed_precondition("stage response not configured"))?
            .map(Response::new)
    }
}

pub(crate) struct MockServerHandle {
    endpoint: String,
    get_response: Arc<Mutex<Option<MockGetResponse>>>,
    get_request: Arc<Mutex<Option<GetSessionRequest>>>,
    list_response: Arc<Mutex<Option<MockListResponse>>>,
    validation_response: Arc<Mutex<Option<MockValidationResponse>>>,
    deployment_response: Arc<Mutex<Option<MockDeploymentResponse>>>,
    deployment_request: Arc<Mutex<Option<DeployWorkflowRequest>>>,
    stage_control_response: Arc<Mutex<Option<Result<ProtoPerceptionSession, Status>>>>,
    enable_stage_request: Arc<Mutex<Option<perception::StageControlRequest>>>,
    disable_stage_request: Arc<Mutex<Option<perception::StageControlRequest>>>,
    stop_response: Arc<Mutex<Option<MockStopResponse>>>,
    stop_request: Arc<Mutex<Option<StopSessionRequest>>>,
    session_snapshot_response: Arc<Mutex<Option<MockSnapshotResponse>>>,
    session_snapshot_request: Arc<Mutex<Option<GetSessionRequest>>>,
    shutdown_sender: oneshot::Sender<()>,
    task: JoinHandle<()>,
}

impl MockServerHandle {
    pub(crate) fn endpoint(&self) -> &str {
        &self.endpoint
    }

    pub(crate) fn set_get_response(&self, response: MockGetResponse) {
        *self
            .get_response
            .lock()
            .expect("get response mutex is in a bad state") = Some(response);
    }

    pub(crate) fn get_request(&self) -> Option<GetSessionRequest> {
        self.get_request
            .lock()
            .expect("get request mutex is in a bad state")
            .clone()
    }

    pub(crate) fn set_list_response(&self, response: MockListResponse) {
        *self
            .list_response
            .lock()
            .expect("list response mutex is in a bad state") = Some(response);
    }

    pub(crate) fn set_validation_response(&self, response: MockValidationResponse) {
        *self
            .validation_response
            .lock()
            .expect("validation response mutex is in a bad state") = Some(response);
    }

    pub(crate) fn set_deployment_response(&self, response: MockDeploymentResponse) {
        *self
            .deployment_response
            .lock()
            .expect("deployment response mutex is in a bad state") = Some(response);
    }

    pub(crate) fn deployment_request(&self) -> Option<DeployWorkflowRequest> {
        self.deployment_request
            .lock()
            .expect("deployment request mutex is in a bad state")
            .clone()
    }

    pub(crate) fn set_stop_response(&self, response: MockStopResponse) {
        *self
            .stop_response
            .lock()
            .expect("stop response mutex is in a bad state") = Some(response);
    }

    pub(crate) fn stop_request(&self) -> Option<StopSessionRequest> {
        self.stop_request
            .lock()
            .expect("stop request mutex is in a bad state")
            .clone()
    }

    pub(crate) fn set_session_snapshot_response(&self, response: MockSnapshotResponse) {
        *self
            .session_snapshot_response
            .lock()
            .expect("snapshot response mutex is in a bad state") = Some(response);
    }

    pub(crate) fn session_snapshot_request(&self) -> Option<GetSessionRequest> {
        self.session_snapshot_request
            .lock()
            .expect("snapshot request mutex is in a bad state")
            .clone()
    }

    pub(crate) fn set_stage_control_response(
        &self,
        response: Result<ProtoPerceptionSession, Status>,
    ) {
        *self
            .stage_control_response
            .lock()
            .expect("stage response mutex poisoned") = Some(response);
    }

    pub(crate) fn enable_stage_request(&self) -> Option<perception::StageControlRequest> {
        self.enable_stage_request
            .lock()
            .expect("stage request mutex poisoned")
            .clone()
    }

    pub(crate) fn disable_stage_request(&self) -> Option<perception::StageControlRequest> {
        self.disable_stage_request
            .lock()
            .expect("stage request mutex poisoned")
            .clone()
    }

    pub(crate) async fn stop(self) {
        let _ = self.shutdown_sender.send(());
        self.task.await.expect("mock gRPC server failed");
    }
}

pub(crate) async fn start_mock_server() -> MockServerHandle {
    let incoming = TcpIncoming::bind("127.0.0.1:0".parse().expect("invalid address"))
        .expect("failed to bind test listener");
    let endpoint = format!(
        "http://{}",
        incoming
            .local_addr()
            .expect("failed to read listener address")
    );
    let get_response = Arc::new(Mutex::new(None));
    let get_request = Arc::new(Mutex::new(None));
    let list_response = Arc::new(Mutex::new(None));
    let validation_response = Arc::new(Mutex::new(None));
    let deployment_response = Arc::new(Mutex::new(None));
    let deployment_request = Arc::new(Mutex::new(None));
    let stage_control_response = Arc::new(Mutex::new(None));
    let enable_stage_request = Arc::new(Mutex::new(None));
    let disable_stage_request = Arc::new(Mutex::new(None));
    let stop_response = Arc::new(Mutex::new(None));
    let stop_request = Arc::new(Mutex::new(None));
    let session_snapshot_response = Arc::new(Mutex::new(None));
    let session_snapshot_request = Arc::new(Mutex::new(None));
    let (shutdown_sender, shutdown_receiver) = oneshot::channel();
    let mock_service = MockPerceptionService {
        get_response: Arc::clone(&get_response),
        get_request: Arc::clone(&get_request),
        list_response: Arc::clone(&list_response),
        validation_response: Arc::clone(&validation_response),
        deployment_response: Arc::clone(&deployment_response),
        deployment_request: Arc::clone(&deployment_request),
        stage_control_response: Arc::clone(&stage_control_response),
        enable_stage_request: Arc::clone(&enable_stage_request),
        disable_stage_request: Arc::clone(&disable_stage_request),
        stop_response: Arc::clone(&stop_response),
        stop_request: Arc::clone(&stop_request),
        session_snapshot_response: Arc::clone(&session_snapshot_response),
        session_snapshot_request: Arc::clone(&session_snapshot_request),
    };
    let (_, health_service) = tonic_health::server::health_reporter();
    let task = tokio::spawn(async move {
        Server::builder()
            .add_service(health_service)
            .add_service(PerceptionServiceServer::new(mock_service))
            .serve_with_incoming_shutdown(incoming, async move {
                let _ = shutdown_receiver.await;
            })
            .await
            .expect("mock gRPC server failed");
    });

    MockServerHandle {
        endpoint,
        get_response,
        get_request,
        list_response,
        validation_response,
        deployment_response,
        deployment_request,
        stage_control_response,
        enable_stage_request,
        disable_stage_request,
        stop_response,
        stop_request,
        session_snapshot_response,
        session_snapshot_request,
        shutdown_sender,
        task,
    }
}
