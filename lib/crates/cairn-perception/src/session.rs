// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use crate::perception::{
    GetSessionRequest, PerceptionSession as ProtoPerceptionSession,
    SessionSnapshot as ProtoSessionSnapshot, SessionState as ProtoSessionState,
    SessionStatus as ProtoSessionStatus, SessionTopics as ProtoSessionTopics, StageControlRequest,
    StatusInfo as ProtoStatusInfo, StopSessionRequest,
    perception_service_client::PerceptionServiceClient,
};
use crate::service::PerceptionServiceError;
use crate::validation_result::ResolvedStage;
use tonic::Request;
use tonic::transport::Channel;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
/// Debug ports allocated to a perception session.
pub struct DebugPorts {
    /// HTTP debug port.
    pub http_port: u32,
    /// WebSocket debug port.
    pub ws_port: u32,
    /// Control protocol debug port.
    pub ctrl_port: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
/// Redis topics allocated to a perception session.
pub struct SessionTopics {
    /// Topic carrying inference results, when allocated.
    pub results: Option<String>,
    /// Topic carrying session events, when allocated.
    pub events: Option<String>,
}

impl From<ProtoSessionTopics> for SessionTopics {
    fn from(topics: ProtoSessionTopics) -> Self {
        Self {
            results: (!topics.results.is_empty()).then_some(topics.results),
            events: (!topics.events.is_empty()).then_some(topics.events),
        }
    }
}

/// Lifecycle state of a perception session.
pub enum SessionState {
    /// The service did not specify a lifecycle state.
    Unspecified,
    /// The session is starting.
    Starting,
    /// The session is running.
    Running,
    /// The session is stopping.
    Stopping,
    /// The session has stopped.
    Stopped,
    /// The session failed.
    Failed,
    /// A lifecycle state not recognized by this SDK version.
    Unknown(i32),
}

/// Additional information reported with a session status. It is normally populated when an error has
/// occurred in the session.
pub struct StatusInfo {
    /// Machine-readable status code.
    pub code: String,
    /// Human-readable status message.
    pub message: String,
}

/// Current lifecycle status of a perception session.
pub struct SessionStatus {
    /// Current lifecycle state.
    pub state: SessionState,
    /// Additional status information, when supplied by the service.
    pub info: Option<StatusInfo>,
}

/// A snapshot of a perception session's current state.
pub struct SessionSnapshot {
    /// Current session status.
    pub status: SessionStatus,
    /// IDs of stages that are currently disabled.
    pub disabled_stage_ids: Vec<String>,
}

/// A handle to a remote perception session.
#[derive(Debug, Clone)]
pub struct PerceptionSession {
    id: String,
    workflow_name: String,
    stages: Vec<ResolvedStage>,
    debug_endpoint: Option<DebugPorts>,
    topics: SessionTopics,
    client: PerceptionServiceClient<Channel>,
}

impl PerceptionSession {
    /// Returns the remote session identifier.
    pub fn id(&self) -> &str {
        &self.id
    }

    /// Returns the deployed workflow name.
    pub fn workflow_name(&self) -> &str {
        &self.workflow_name
    }

    /// Returns the resolved stages in this session.
    pub fn stages(&self) -> &[ResolvedStage] {
        &self.stages
    }

    /// Returns the allocated debug endpoint, when enabled.
    pub fn debug_endpoint(&self) -> Option<&DebugPorts> {
        self.debug_endpoint.as_ref()
    }

    /// Returns the session topic allocation.
    ///
    /// Individual topic names are absent when the service did not allocate them.
    pub fn topics(&self) -> &SessionTopics {
        &self.topics
    }

    /// Returns the current snapshot of this remote session.
    ///
    /// # Errors
    ///
    /// Returns [`PerceptionServiceError::Rpc`] when the request fails or the response omits
    /// its status.
    pub async fn get_status(&self) -> Result<SessionSnapshot, PerceptionServiceError> {
        let mut client = self.client.clone();
        let response = client
            .get_session_snapshot(Request::new(GetSessionRequest {
                session_id: self.id.clone(),
            }))
            .await
            .map_err(|error| {
                PerceptionServiceError::Rpc(format!(
                    "failed to get perception session status: {:?}: {}",
                    error.code(),
                    error.message()
                ))
            })?
            .into_inner();

        SessionSnapshot::try_from(response)
    }

    /// Requests shutdown of the remote session.
    ///
    /// Stopping an already stopped session is a no-op.
    ///
    /// # Errors
    ///
    /// Returns [`PerceptionServiceError::Rpc`] when the stop request fails.
    pub async fn stop(&self) -> Result<(), PerceptionServiceError> {
        let mut client = self.client.clone();
        client
            .stop_session(Request::new(StopSessionRequest {
                session_id: self.id.clone(),
            }))
            .await
            .map_err(|error| {
                PerceptionServiceError::Rpc(format!(
                    "failed to stop perception session: {:?}: {}",
                    error.code(),
                    error.message()
                ))
            })?;
        Ok(())
    }

    /// Requests that an inference stage in this session be disabled.
    ///
    /// Use the stage ID from a workflow's `StageHandle` or [`Self::stages`],
    /// not a model ID or display name. No retained stage handle is required.
    ///
    /// # Errors
    ///
    /// Returns [`PerceptionServiceError::Rpc`] when the request fails.
    pub async fn disable_stage(&self, stage_id: &str) -> Result<(), PerceptionServiceError> {
        let mut client = self.client.clone();
        client
            .disable_stage(Request::new(StageControlRequest {
                session_id: self.id.clone(),
                stage_id: stage_id.to_string(),
            }))
            .await
            .map_err(|error| {
                PerceptionServiceError::Rpc(format!(
                    "failed to disable perception stage: {:?}: {}",
                    error.code(),
                    error.message()
                ))
            })?;
        Ok(())
    }

    /// Requests that an inference stage in this session be enabled.
    ///
    /// Use the stage ID from a workflow's `StageHandle` or [`Self::stages`],
    /// not a model ID or display name. No retained stage handle is required.
    ///
    /// # Errors
    ///
    /// Returns [`PerceptionServiceError::Rpc`] when the request fails.
    pub async fn enable_stage(&self, stage_id: &str) -> Result<(), PerceptionServiceError> {
        let mut client = self.client.clone();
        client
            .enable_stage(Request::new(StageControlRequest {
                session_id: self.id.clone(),
                stage_id: stage_id.to_string(),
            }))
            .await
            .map_err(|error| {
                PerceptionServiceError::Rpc(format!(
                    "failed to enable perception stage: {:?}: {}",
                    error.code(),
                    error.message()
                ))
            })?;
        Ok(())
    }

    pub(crate) fn from_proto(
        session: ProtoPerceptionSession,
        client: PerceptionServiceClient<Channel>,
    ) -> Result<Self, PerceptionServiceError> {
        if session.id.is_empty() {
            return Err(PerceptionServiceError::InvalidResponse(
                "invalid perception service response: session is missing an ID".to_string(),
            ));
        }

        let topics = session.topics.map(SessionTopics::from).unwrap_or_default();

        Ok(Self::new(
            session.id,
            session.workflow_name,
            session.stages.into_iter().map(Into::into).collect(),
            session.debug_endpoint.map(|ports| DebugPorts {
                http_port: ports.http_port,
                ws_port: ports.ws_port,
                ctrl_port: ports.ctrl_port,
            }),
            topics,
            client,
        ))
    }

    pub(crate) fn new(
        id: String,
        workflow_name: String,
        stages: Vec<ResolvedStage>,
        debug_endpoint: Option<DebugPorts>,
        topics: SessionTopics,
        client: PerceptionServiceClient<Channel>,
    ) -> Self {
        Self {
            id,
            workflow_name,
            stages,
            debug_endpoint,
            topics,
            client,
        }
    }
}

impl TryFrom<ProtoSessionSnapshot> for SessionSnapshot {
    type Error = PerceptionServiceError;

    fn try_from(snapshot: ProtoSessionSnapshot) -> Result<Self, Self::Error> {
        let status = snapshot.status.ok_or_else(|| {
            PerceptionServiceError::Rpc(
                "invalid perception service response: session snapshot is missing status"
                    .to_string(),
            )
        })?;

        Ok(Self {
            status: status.into(),
            disabled_stage_ids: snapshot.disabled_stage_ids,
        })
    }
}

impl From<ProtoSessionStatus> for SessionStatus {
    fn from(status: ProtoSessionStatus) -> Self {
        Self {
            state: match ProtoSessionState::try_from(status.state) {
                Ok(ProtoSessionState::Unspecified) => SessionState::Unspecified,
                Ok(ProtoSessionState::Starting) => SessionState::Starting,
                Ok(ProtoSessionState::Running) => SessionState::Running,
                Ok(ProtoSessionState::Stopping) => SessionState::Stopping,
                Ok(ProtoSessionState::Stopped) => SessionState::Stopped,
                Ok(ProtoSessionState::Failed) => SessionState::Failed,
                Err(value) => SessionState::Unknown(value.0),
            },
            info: status.info.map(Into::into),
        }
    }
}

impl From<ProtoStatusInfo> for StatusInfo {
    fn from(info: ProtoStatusInfo) -> Self {
        Self {
            code: info.code,
            message: info.message,
        }
    }
}
