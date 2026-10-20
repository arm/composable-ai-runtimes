// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use crate::perception::perception_service_client::PerceptionServiceClient;
use crate::perception::{
    DeployWorkflowRequest, DeployWorkflowResponse, GetServiceInfoRequest, GetSessionRequest,
    ListSessionsRequest, PerceptionSession as ProtoPerceptionSession, ValidateWorkflowRequest,
    deploy_workflow_response,
};
use crate::session::PerceptionSession;
use crate::validation_result::{ValidationIssue, ValidationResult};
use crate::workflow::PerceptionWorkflow;
use tonic::Request;
use tonic::transport::{Channel, Endpoint};
use tonic_health::pb::{
    HealthCheckRequest, health_check_response::ServingStatus, health_client::HealthClient,
};

const DEFAULT_PERCEPTION_SERVICE_ENDPOINT: &str = "http://127.0.0.1:50053";

pub(super) async fn wait_for_serving(endpoint: &str) -> Result<Channel, String> {
    let ready_channel = async {
        let channel = Endpoint::from_shared(endpoint.to_owned())
            .map_err(|error| error.to_string())?
            .connect()
            .await
            .map_err(|error| error.to_string())?;
        let mut updates = HealthClient::new(channel.clone())
            .watch(HealthCheckRequest::default())
            .await
            .map_err(|error| error.to_string())?
            .into_inner();
        while let Some(response) = updates.message().await.map_err(|error| error.to_string())? {
            if response.status() == ServingStatus::Serving {
                return Ok(channel);
            }
        }
        Err("health watch ended before SERVING".to_string())
    };
    tokio::time::timeout(std::time::Duration::from_secs(30), ready_channel)
        .await
        .map_err(|_| format!("service at {endpoint} did not report SERVING within 30s"))?
        .map_err(|error| format!("health watch at {endpoint} failed: {error}"))
}

/// An error returned by the Perception service client.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum PerceptionServiceError {
    /// The client could not connect to the service.
    Transport(String),
    /// The service returned a response that cannot be represented by the library.
    InvalidResponse(String),
    /// An RPC failed or returned an unusable response.
    Rpc(String),
    /// The service rejected a workflow.
    Workflow(Vec<ValidationIssue>),
}

impl std::fmt::Display for PerceptionServiceError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Transport(message) => formatter.write_str(message),
            Self::InvalidResponse(message) => formatter.write_str(message),
            Self::Rpc(message) => formatter.write_str(message),
            Self::Workflow(issues) => {
                write!(
                    formatter,
                    "invalid perception workflow: {}",
                    issues
                        .iter()
                        .map(|issue| format!("{}: {}", issue.code, issue.message))
                        .collect::<Vec<_>>()
                        .join("; ")
                )
            }
        }
    }
}

impl std::error::Error for PerceptionServiceError {}

/// Version and capability information reported by the Perception service.
pub struct ServiceInfo {
    /// The API version implemented by the service.
    pub api_version: String,
    /// The version of the running service.
    pub service_version: String,
    /// Whether active sessions persist when the service restarts.
    pub sessions_survive_restart: bool,
}

/// An asynchronous client for validating and deploying Perception workflows.
pub struct PerceptionService {
    client: PerceptionServiceClient<Channel>,
}

impl PerceptionService {
    /// Connects to the Perception service.
    ///
    /// Pass `None` to use the default endpoint, `http://127.0.0.1:50053`.
    ///
    /// # Errors
    ///
    /// Returns [`PerceptionServiceError::Transport`] when the client cannot connect to the
    /// endpoint.
    pub async fn new(endpoint: Option<String>) -> Result<Self, PerceptionServiceError> {
        let endpoint = endpoint.unwrap_or_else(|| DEFAULT_PERCEPTION_SERVICE_ENDPOINT.to_string());
        let channel = wait_for_serving(&endpoint).await.map_err(|error| {
            PerceptionServiceError::Transport(format!(
                "failed to connect to perception service at {endpoint}: {error}"
            ))
        })?;
        Ok(Self {
            client: PerceptionServiceClient::new(channel),
        })
    }

    /// Returns version and capability information for the connected service.
    ///
    /// # Errors
    ///
    /// Returns [`PerceptionServiceError::Rpc`] when the request fails.
    pub async fn get_service_info(&mut self) -> Result<ServiceInfo, PerceptionServiceError> {
        let response = self
            .client
            .get_service_info(Request::new(GetServiceInfoRequest {}))
            .await
            .map_err(|error| {
                PerceptionServiceError::Rpc(format!(
                    "failed to get perception service info: {}: {}",
                    error.code(),
                    error.message()
                ))
            })?
            .into_inner();
        Ok(ServiceInfo {
            api_version: response.api_version,
            service_version: response.service_version,
            sessions_survive_restart: response.sessions_survive_restart,
        })
    }

    /// Validates a workflow without deploying it.
    ///
    /// An invalid workflow is returned as a successful [`ValidationResult`] with `valid` set to
    /// `false` and details in its `issues` field.
    ///
    /// # Errors
    ///
    /// Returns [`PerceptionServiceError::Rpc`] when the validation RPC fails.
    pub async fn validate(
        &mut self,
        workflow: &PerceptionWorkflow,
    ) -> Result<ValidationResult, PerceptionServiceError> {
        let response = self
            .client
            .validate_workflow(Request::new(ValidateWorkflowRequest {
                workflow: Some(workflow.into()),
            }))
            .await
            .map_err(|error| {
                PerceptionServiceError::Rpc(format!(
                    "failed to validate perception workflow: {:?}: {}",
                    error.code(),
                    error.message()
                ))
            })?
            .into_inner();

        Ok(response.into())
    }

    /// Deploys a workflow and returns its session handle.
    ///
    /// Workflow rejection returns [`PerceptionServiceError::Workflow`] with validation issues.
    /// A successful response provides a session handle, not a guarantee of ongoing health.
    ///
    /// # Errors
    ///
    /// Returns an error when the deployment RPC fails or its response is invalid.
    pub async fn deploy(
        &mut self,
        workflow: &PerceptionWorkflow,
    ) -> Result<PerceptionSession, PerceptionServiceError> {
        let request = DeployWorkflowRequest {
            workflow: Some(workflow.into()),
        };
        let response = self
            .client
            .deploy_workflow(Request::new(request))
            .await
            .map_err(|error| {
                PerceptionServiceError::Rpc(format!(
                    "failed to deploy perception workflow: {:?}: {}",
                    error.code(),
                    error.message()
                ))
            })?
            .into_inner();

        let session = proto_session_from_response(response)?;
        PerceptionSession::from_proto(session, self.client.clone())
    }

    /// Returns a handle for the requested session.
    ///
    /// # Errors
    ///
    /// Returns [`PerceptionServiceError::InvalidResponse`] if the returned session has an empty
    /// ID.
    /// Returns [`PerceptionServiceError::Rpc`] if the RPC fails.
    pub async fn get_session(
        &mut self,
        session_id: impl Into<String>,
    ) -> Result<PerceptionSession, PerceptionServiceError> {
        let session = self
            .client
            .get_session(Request::new(GetSessionRequest {
                session_id: session_id.into(),
            }))
            .await
            .map_err(|error| {
                PerceptionServiceError::Rpc(format!(
                    "failed to get perception session: {:?}: {}",
                    error.code(),
                    error.message()
                ))
            })?
            .into_inner();

        PerceptionSession::from_proto(session, self.client.clone())
    }

    /// Returns handles for the sessions reported by the service, in response order.
    ///
    /// Returns an empty vector when the service reports no sessions.
    ///
    /// # Errors
    ///
    /// Returns [`PerceptionServiceError::InvalidResponse`] if any returned session has an empty
    /// ID. Returns [`PerceptionServiceError::Rpc`] if the RPC fails.
    /// Servers without `ListSessions` support return an `UNIMPLEMENTED` RPC error.
    pub async fn list_sessions(
        &mut self,
    ) -> Result<Vec<PerceptionSession>, PerceptionServiceError> {
        let response = self
            .client
            .list_sessions(Request::new(ListSessionsRequest {}))
            .await
            .map_err(|error| {
                PerceptionServiceError::Rpc(format!(
                    "failed to list perception sessions: {:?}: {}",
                    error.code(),
                    error.message()
                ))
            })?
            .into_inner();

        response
            .sessions
            .into_iter()
            .map(|session| PerceptionSession::from_proto(session, self.client.clone()))
            .collect()
    }
}

fn proto_session_from_response(
    response: DeployWorkflowResponse,
) -> Result<ProtoPerceptionSession, PerceptionServiceError> {
    match response.outcome {
        Some(deploy_workflow_response::Outcome::Accepted(accepted)) => accepted
            .session
            .ok_or_else(|| {
                PerceptionServiceError::Rpc(
                    "invalid perception service response: accepted deployment response is missing a session"
                        .to_string(),
                )
            }),
        Some(deploy_workflow_response::Outcome::Rejected(rejected)) => Err(
            PerceptionServiceError::Workflow(rejected.issues.into_iter().map(Into::into).collect()),
        ),
        None => Err(PerceptionServiceError::Rpc(
            "invalid perception service response: deployment response is missing an outcome"
                .to_string(),
        )),
    }
}
