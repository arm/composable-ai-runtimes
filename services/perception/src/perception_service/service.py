# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import signal
from collections.abc import Generator
from concurrent import futures
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from enum import Enum, auto
from threading import Event, Lock
from types import FrameType
from typing import Final, Self
from uuid import uuid4

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from loguru import logger

from cairn.perception.v1 import perception_pb2, perception_pb2_grpc
from perception_service.messaging.lifecycle import (
    LifecyclePublisher,
    SessionState,
    StageState,
)
from perception_service.messaging.topics import session_topic
from perception_service.opk.config import OpkCommEndpoint
from perception_service.opk.endpoint_pool import (
    OpkCommEndpointLease,
    OpkCommEndpointPool,
)
from perception_service.opk.result_router import OpkResultRouter
from perception_service.pipeline_manager import PipelineEvent, PipelineManager
from perception_service.pipeline_types import (
    PipelineState,
    PipelineStatus,
    RuntimePipelineEventKind,
)
from perception_service.readiness import (
    ReadinessController,
    ReadinessSnapshot,
    RuntimeReadiness,
)
from perception_service.errors import (
    FailedPreconditionError,
    InternalError,
    NotFoundError,
    UnavailableError,
)
from perception_service.rpc import handle_rpc_errors
from perception_service.workflow.issues import ValidationCode, validation_error
from perception_service.workflow.pipeline import (
    CompiledPipeline,
    PipelineBuilder,
    PipelineBuildError,
    PipelineConstructionError,
    workflow_publishes_events,
)
from perception_service.workflow.stage import (
    StageConstructionError,
    StageFactory,
    UnsupportedStageError,
)
from perception_service.workflow.stages.output import OpkSinkStageDefinition
from perception_service.workflow.validation import validate_pipeline, validate_workflow

SERVER_SHUTDOWN_GRACE_SECONDS: Final = 5
SERVICE_VERSION: Final = "0.0.2"
PERCEPTION_SERVICE_NAME: Final = perception_pb2.DESCRIPTOR.services_by_name[
    "PerceptionService"
].full_name
GSTREAMER_SERVICE_NAME: Final = "cairn.perception.runtime.gstreamer"
DEFAULT_GRPC_MAX_WORKERS: Final = 8


@dataclass(frozen=True)
class _SessionMetadata:
    """Immutable user-visible metadata for one compiled session."""

    session_id: str
    workflow_name: str
    resolved_stages: tuple[perception_pb2.ResolvedStage, ...]
    debug_endpoint: perception_pb2.DebugPorts | None
    events_topic: str = ""

    @classmethod
    def from_pipeline(
        cls,
        session_id: str,
        workflow_name: str,
        pipeline: CompiledPipeline,
    ) -> Self:
        resolved_stages: list[perception_pb2.ResolvedStage] = []
        for stage in pipeline.resolved_stages:
            copied_stage = perception_pb2.ResolvedStage()
            copied_stage.CopyFrom(stage)
            resolved_stages.append(copied_stage)

        debug_stage = next(
            (
                stage
                for stage in pipeline.stages
                if isinstance(stage, OpkSinkStageDefinition)
            ),
            None,
        )
        debug_endpoint = None
        if debug_stage is not None:
            debug_endpoint = perception_pb2.DebugPorts()
            debug_endpoint.CopyFrom(debug_stage.debug_ports)

        return cls(
            session_id,
            workflow_name,
            tuple(resolved_stages),
            debug_endpoint,
        )

    def to_proto(self) -> perception_pb2.PerceptionSession:
        session = perception_pb2.PerceptionSession(
            id=self.session_id,
            workflow_name=self.workflow_name,
            stages=self.resolved_stages,
            topics=perception_pb2.SessionTopics(
                results=session_topic(self.session_id, "results"),
                events=self.events_topic,
            ),
        )
        if self.debug_endpoint is not None:
            session.debug_endpoint.CopyFrom(self.debug_endpoint)
        return session


class _SessionPhase(Enum):
    """Resource-ownership phase for one session record."""

    DEPLOYING = auto()  # Pipeline and result routing are being established.
    ACCEPTED_OWNED = auto()  # Accepted session still owns runtime resources.
    REJECTED_CLEANUP_PENDING = auto()  # Rejected session awaits resource cleanup.
    ACCEPTED_RELEASED = auto()  # Resources released; accepted-session metadata retained.

    def is_accepted(self) -> bool:
        return self in (
            _SessionPhase.ACCEPTED_OWNED,
            _SessionPhase.ACCEPTED_RELEASED,
        )


@dataclass
class _SessionRecord:
    """Mutable lifecycle and resource ownership for one session."""

    metadata: _SessionMetadata
    pending_lease: OpkCommEndpointLease | None
    phase: _SessionPhase = _SessionPhase.DEPLOYING
    failure_cleanup_future: futures.Future[None] | None = field(default=None, repr=False)
    disabled_stage_ids: set[str] = field(default_factory=set)
    operation_lock: Lock = field(default_factory=Lock, repr=False)


def _project_status(status: PipelineStatus) -> perception_pb2.SessionStatus:
    projected = perception_pb2.SessionStatus(
        state={
            PipelineState.STARTING: perception_pb2.SESSION_STATE_STARTING,
            PipelineState.RUNNING: perception_pb2.SESSION_STATE_RUNNING,
            PipelineState.STOPPING: perception_pb2.SESSION_STATE_STOPPING,
            PipelineState.STOPPED: perception_pb2.SESSION_STATE_STOPPED,
            PipelineState.FAILED: perception_pb2.SESSION_STATE_FAILED,
        }[status.state]
    )
    if status.message:
        projected.info.message = status.message
    return projected


class PerceptionService(perception_pb2_grpc.PerceptionServiceServicer):
    """Own sessions without waiting for operation locks under ``_records_lock``."""

    def __init__(
        self,
        pipeline_manager: PipelineManager,
        stage_factory: StageFactory,
        result_router: OpkResultRouter,
        endpoint_pool: OpkCommEndpointPool,
        lifecycle: LifecyclePublisher,
    ) -> None:
        self._pipeline_manager = pipeline_manager
        self._pipeline_builder = PipelineBuilder(stage_factory)
        self._result_router = result_router
        self._endpoint_pool = endpoint_pool
        self._records: dict[str, _SessionRecord] = {}
        self._records_lock = Lock()
        self._closed = False
        self._failure_cleanup = futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="perception-failure-cleanup"
        )
        self._lifecycle = lifecycle
        self._pipeline_manager.subscribe(self._on_pipeline_event)

    @handle_rpc_errors
    def GetServiceInfo(
        self,
        request: perception_pb2.GetServiceInfoRequest,
        context: grpc.ServicerContext,
    ) -> perception_pb2.GetServiceInfoResponse:
        return perception_pb2.GetServiceInfoResponse(
            api_version="v1",
            service_version=SERVICE_VERSION,
            sessions_survive_restart=False,
        )

    @handle_rpc_errors
    def ValidateWorkflow(
        self,
        request: perception_pb2.ValidateWorkflowRequest,
        context: grpc.ServicerContext,
    ) -> perception_pb2.ValidateWorkflowResponse:
        compiled_pipeline, issues = self._compile_workflow(request.workflow)
        return perception_pb2.ValidateWorkflowResponse(
            valid=compiled_pipeline is not None,
            issues=issues,
            stages=(
                compiled_pipeline.resolved_stages
                if compiled_pipeline is not None
                else []
            ),
        )

    @handle_rpc_errors
    def DeployWorkflow(
        self,
        request: perception_pb2.DeployWorkflowRequest,
        context: grpc.ServicerContext,
    ) -> perception_pb2.DeployWorkflowResponse:
        with self._records_lock:
            if self._closed:
                raise UnavailableError("workflow session manager is closed")
        self._retry_rejected_cleanup()
        lease = self._endpoint_pool.reserve()

        with lease:
            compiled_pipeline, issues = self._compile_workflow(
                request.workflow, lease.endpoint
            )
            if compiled_pipeline is None:
                return perception_pb2.DeployWorkflowResponse(
                    rejected=perception_pb2.DeploymentRejected(issues=issues),
                )

            metadata = self._deploy_session(request.workflow, compiled_pipeline, lease)

        return perception_pb2.DeployWorkflowResponse(
            accepted=perception_pb2.DeploymentAccepted(
                session=metadata.to_proto()
            ),
        )

    def _deploy_session(
        self,
        workflow: perception_pb2.WorkflowSpec,
        compiled_pipeline: CompiledPipeline,
        lease: OpkCommEndpointLease,
    ) -> _SessionMetadata:
        session_id = str(uuid4())
        record = _SessionRecord(
            _SessionMetadata.from_pipeline(session_id, workflow.name, compiled_pipeline),
            lease,
        )
        with record.operation_lock:
            with self._records_lock:
                if self._closed:
                    raise UnavailableError("workflow session manager is closed")
                if session_id in self._records:
                    raise InternalError(
                        f"session already exists with ID {session_id!r}"
                    )
                lease.claim()
                self._records[session_id] = record

            try:
                events_topic = self._lifecycle.start_session(
                    session_id,
                    (stage.id for stage in record.metadata.resolved_stages),
                    enabled=workflow_publishes_events(workflow),
                )
                record.metadata = replace(record.metadata, events_topic=events_topic)
            except Exception:
                self._discard_rejected_record(record)
                self._publish_failed_session(session_id)
                raise

            try:
                self._pipeline_manager.start_pipeline(
                    session_id, compiled_pipeline.description
                )
                self._result_router.start(session_id, lease)
            except Exception:
                self._reject_and_cleanup(record, "deployment failure")
                raise

            with self._records_lock:
                record.phase = _SessionPhase.ACCEPTED_OWNED
                record.pending_lease = None
            self._lifecycle.publish_session(session_id, SessionState.RUNNING)

        return record.metadata

    @handle_rpc_errors
    def GetSession(
        self,
        request: perception_pb2.GetSessionRequest,
        context: grpc.ServicerContext,
    ) -> perception_pb2.PerceptionSession:
        with self._records_lock:
            record = self._records.get(request.session_id)
            metadata = (
                record.metadata
                if record is not None and record.phase.is_accepted()
                else None
            )
        if metadata is None:
            raise NotFoundError(f"session not found: {request.session_id!r}")
        return metadata.to_proto()

    @handle_rpc_errors
    def ListSessions(
        self,
        request: perception_pb2.ListSessionsRequest,
        context: grpc.ServicerContext,
    ) -> perception_pb2.ListSessionsResponse:
        with self._records_lock:
            metadata = tuple(
                record.metadata
                for record in self._records.values()
                if record.phase.is_accepted()
            )
        return perception_pb2.ListSessionsResponse(
            sessions=tuple(item.to_proto() for item in metadata)
        )

    @handle_rpc_errors
    def GetSessionSnapshot(
        self,
        request: perception_pb2.GetSessionRequest,
        context: grpc.ServicerContext,
    ) -> perception_pb2.SessionSnapshot:
        with self._records_lock:
            record = self._records.get(request.session_id)
            if record is None or not record.phase.is_accepted():
                raise NotFoundError(f"session not found: {request.session_id!r}")
            disabled_stage_ids = tuple(sorted(record.disabled_stage_ids))

        snapshot = self._pipeline_manager.get_pipeline(request.session_id)
        if snapshot is None or snapshot.session_id != request.session_id:
            raise InternalError(
                f"authoritative pipeline status missing for session {request.session_id!r}"
            )
        return perception_pb2.SessionSnapshot(
            status=_project_status(snapshot.status),
            disabled_stage_ids=disabled_stage_ids,
        )

    @handle_rpc_errors
    def StopSession(
        self,
        request: perception_pb2.StopSessionRequest,
        context: grpc.ServicerContext,
    ) -> perception_pb2.PerceptionSession:
        session_id = request.session_id
        with self._records_lock:
            record = self._records.get(session_id)
        if record is None:
            return perception_pb2.PerceptionSession(id=session_id)

        with self._session_operation(record) as phase:
            if phase is None:
                return perception_pb2.PerceptionSession(id=session_id)

            self._lifecycle.publish_session(session_id, SessionState.STOPPING)
            try:
                if phase is _SessionPhase.ACCEPTED_OWNED:
                    self._cleanup_accepted_record(record)
                elif phase is _SessionPhase.REJECTED_CLEANUP_PENDING:
                    self._cleanup_rejected_record(record, "explicit session stop")
            except Exception:
                self._publish_failed_session(session_id)
                raise
            self._lifecycle.publish_session(session_id, SessionState.STOPPED)

        return perception_pb2.PerceptionSession(id=session_id)

    @handle_rpc_errors
    def EnableStage(  # noqa: N802
        self,
        request: perception_pb2.StageControlRequest,
        context: grpc.ServicerContext,
    ) -> perception_pb2.PerceptionSession:
        return self._set_inference_stage_state(request, active=True)

    @handle_rpc_errors
    def DisableStage(  # noqa: N802
        self,
        request: perception_pb2.StageControlRequest,
        context: grpc.ServicerContext,
    ) -> perception_pb2.PerceptionSession:
        return self._set_inference_stage_state(request, active=False)

    @contextmanager
    def _session_operation(
        self, record: _SessionRecord
    ) -> Generator[_SessionPhase | None]:
        """Yield the current phase under the session lock, or None for a stale record."""
        with record.operation_lock:
            with self._records_lock:
                if self._closed:
                    raise UnavailableError("workflow session manager is closed")
                phase = (
                    record.phase
                    if self._records.get(record.metadata.session_id) is record
                    else None
                )
            yield phase

    def _set_inference_stage_state(
        self,
        request: perception_pb2.StageControlRequest,
        *,
        active: bool,
    ) -> perception_pb2.PerceptionSession:
        session_id, stage_id = request.session_id, request.stage_id
        with self._records_lock:
            record = self._records.get(session_id)
            if record is None or record.phase is _SessionPhase.ACCEPTED_RELEASED:
                raise NotFoundError(f"stage or session not found: {stage_id!r}")

        with self._session_operation(record) as phase:
            if phase is not _SessionPhase.ACCEPTED_OWNED:
                raise NotFoundError(f"stage or session not found: {stage_id!r}")
            stage = next(
                (
                    item
                    for item in record.metadata.resolved_stages
                    if item.id == stage_id
                ),
                None,
            )
            if stage is None:
                raise NotFoundError(f"stage or session not found: {stage_id!r}")
            if not stage.controllable:
                raise FailedPreconditionError(
                    f"stage is not an inference stage: {stage_id!r}"
                )

            actual_active = self._pipeline_manager.set_inference_stage_active(
                session_id, stage_id, active
            )

            with self._records_lock:
                if actual_active:
                    record.disabled_stage_ids.discard(stage_id)
                else:
                    record.disabled_stage_ids.add(stage_id)

            self._lifecycle.publish_stage(
                session_id,
                stage_id,
                StageState.ENABLED if actual_active else StageState.DISABLED,
            )

        return perception_pb2.PerceptionSession(id=session_id)

    def _on_pipeline_event(self, event: PipelineEvent) -> None:
        if (
            not event.from_runtime
            or event.kind is not RuntimePipelineEventKind.ERROR
            or event.snapshot.status.state is not PipelineState.FAILED
        ):
            return

        session_id = event.snapshot.session_id
        try:
            self._lifecycle.publish_session(
                session_id, SessionState.FAILED, event.source_name
            )
        finally:
            # Native callbacks may hold the manager event lock on the GLib thread.
            # Submit only; cleanup must wait for deployment outside this callback.
            with self._records_lock:
                record = self._records.get(session_id)
                if (
                    not self._closed
                    and record is not None
                    and record.phase is not _SessionPhase.ACCEPTED_RELEASED
                    and (
                        record.failure_cleanup_future is None
                        or record.failure_cleanup_future.done()
                    )
                ):
                    record.failure_cleanup_future = self._failure_cleanup.submit(
                        self._cleanup_failed_record, record
                    )

    def _cleanup_failed_record(self, record: _SessionRecord) -> None:
        with record.operation_lock:
            with self._records_lock:
                if (
                    self._closed
                    or self._records.get(record.metadata.session_id) is not record
                ):
                    return
                phase = record.phase
            try:
                if phase is _SessionPhase.ACCEPTED_OWNED:
                    self._cleanup_accepted_record(record)
                elif phase is _SessionPhase.REJECTED_CLEANUP_PENDING:
                    self._cleanup_rejected_record(record, "native pipeline failure")
            except Exception:
                logger.exception(
                    "Failed to automatically clean up session {}; retaining ownership "
                    "for a cleanup retry",
                    record.metadata.session_id,
                )

    def _publish_failed_session(self, session_id: str) -> None:
        try:
            self._lifecycle.publish_session(session_id, SessionState.FAILED)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to publish failed state for session {}", session_id
            )

    def begin_shutdown(self) -> None:
        with self._records_lock:
            if self._closed:
                return
            self._closed = True
            records = tuple(self._records.values())

        # Leave queued cleanup to runtime/router close; drain running work without locks.
        self._failure_cleanup.shutdown(wait=True, cancel_futures=True)

        # Finish admitted operations before their shared runtime and router close.
        for record in records:
            with record.operation_lock:
                pass

    def _reject_and_cleanup(self, record: _SessionRecord, reason: str) -> None:
        with self._records_lock:
            record.phase = _SessionPhase.REJECTED_CLEANUP_PENDING
        try:
            self._cleanup_rejected_record(record, reason)
        except Exception:
            logger.exception(
                "Failed to clean up rejected session {} after {}; "
                "retaining OPK endpoint for a later cleanup attempt",
                record.metadata.session_id,
                reason,
            )
        self._publish_failed_session(record.metadata.session_id)

    def _retry_rejected_cleanup(self) -> None:
        with self._records_lock:
            records = tuple(
                record
                for record in self._records.values()
                if record.phase is _SessionPhase.REJECTED_CLEANUP_PENDING
            )

        for record in records:
            with self._session_operation(record) as phase:
                if phase is not _SessionPhase.REJECTED_CLEANUP_PENDING:
                    continue
                try:
                    self._cleanup_rejected_record(record, "pre-deployment retry")
                except Exception:
                    logger.exception(
                        "Failed pre-deployment cleanup for rejected session {}; "
                        "retaining OPK endpoint for a later cleanup attempt",
                        record.metadata.session_id,
                    )

    def _cleanup_accepted_record(self, record: _SessionRecord) -> None:
        self._pipeline_manager.stop_pipeline(record.metadata.session_id)
        self._result_router.stop(record.metadata.session_id)
        with self._records_lock:
            record.phase = _SessionPhase.ACCEPTED_RELEASED

    def _cleanup_rejected_record(self, record: _SessionRecord, reason: str) -> None:
        self._pipeline_manager.stop_pipeline(record.metadata.session_id)
        self._pipeline_manager.discard_pipeline(record.metadata.session_id)
        self._discard_rejected_record(record)
        logger.info(
            "Cleaned up rejected session {} after {}",
            record.metadata.session_id,
            reason,
        )

    def _discard_rejected_record(self, record: _SessionRecord) -> None:
        lease = record.pending_lease
        if lease is not None:
            lease.release()
        with self._records_lock:
            if self._records.get(record.metadata.session_id) is record:
                del self._records[record.metadata.session_id]

    def _compile_workflow(
        self,
        workflow: perception_pb2.WorkflowSpec,
        opk_comm_endpoint: OpkCommEndpoint | None = None,
    ) -> tuple[CompiledPipeline | None, list[perception_pb2.ValidationIssue]]:
        workflow_valid, issues = validate_workflow(workflow)
        if not workflow_valid:
            return None, issues

        try:
            pipeline = self._pipeline_builder.build_pipeline(
                workflow,
                opk_comm_endpoint,
            )
        except PipelineBuildError as error:
            issues.append(
                validation_error(
                    ValidationCode.INVALID_WORKFLOW_STRUCTURE,
                    str(error),
                    error.field_path,
                )
            )
            return None, issues
        except UnsupportedStageError as error:
            issues.append(
                validation_error(
                    ValidationCode.UNSUPPORTED_STAGE,
                    str(error),
                    "workflow",
                )
            )
            return None, issues

        pipeline_valid, pipeline_issues = validate_pipeline(pipeline)
        issues.extend(pipeline_issues)
        if not pipeline_valid:
            return None, issues

        try:
            compiled_pipeline = pipeline.compile()
        except StageConstructionError as error:
            issues.append(
                validation_error(
                    ValidationCode.PIPELINE_CONSTRUCTION_FAILED,
                    str(error),
                    error.field_path,
                    error.stage_id,
                )
            )
            return None, issues
        except PipelineConstructionError as error:
            issues.append(
                validation_error(
                    ValidationCode.PIPELINE_CONSTRUCTION_FAILED,
                    str(error) or "workflow pipeline construction is not implemented",
                    "workflow",
                )
            )
            return None, issues

        return compiled_pipeline, issues


def _statuses(snapshot: ReadinessSnapshot) -> dict[str, int]:
    serving = health_pb2.HealthCheckResponse.SERVING
    not_serving = health_pb2.HealthCheckResponse.NOT_SERVING
    return {
        "": serving if snapshot.aggregate else not_serving,
        PERCEPTION_SERVICE_NAME: serving if snapshot.api else not_serving,
        GSTREAMER_SERVICE_NAME: serving if snapshot.gstreamer else not_serving,
    }


class PerceptionHealthServicer(health.HealthServicer):
    def __init__(self, runtime: RuntimeReadiness) -> None:
        super().__init__()
        self._controller = ReadinessController(runtime)
        self._published_statuses: dict[str, int] = {}
        self._transition_lock = Lock()
        with self._transition_lock:
            self._publish_locked(
                self._controller.snapshot(),
                log_transitions=False,
            )

    def mark_api_ready(self) -> None:
        with self._transition_lock:
            self._publish_locked(self._controller.set_api_ready())

    def refresh_runtime(self) -> None:
        with self._transition_lock:
            self._publish_locked(self._controller.refresh_runtime())

    def Check(
        self,
        request: health_pb2.HealthCheckRequest,
        context: grpc.ServicerContext,
    ) -> health_pb2.HealthCheckResponse:
        if request.service in {"", GSTREAMER_SERVICE_NAME}:
            self.refresh_runtime()
        return super().Check(request, context)

    def enter_graceful_shutdown(self) -> None:
        with self._transition_lock:
            statuses = _statuses(self._controller.begin_shutdown())
            self._log_transitions(statuses)
            super().enter_graceful_shutdown()
            self._published_statuses = statuses

    def _publish_locked(
        self,
        snapshot: ReadinessSnapshot,
        *,
        log_transitions: bool = True,
    ) -> None:
        statuses = _statuses(snapshot)
        if log_transitions:
            self._log_transitions(statuses)
        for service_name, status in statuses.items():
            if self._published_statuses.get(service_name) == status:
                continue
            self.set(service_name, status)
        self._published_statuses = statuses

    def _log_transitions(self, statuses: dict[str, int]) -> None:
        for service_name, status in statuses.items():
            previous_status = self._published_statuses.get(service_name)
            if previous_status is None or previous_status == status:
                continue
            logger.info(
                "Perception readiness {} changed to {}",
                service_name or "aggregate",
                health_pb2.HealthCheckResponse.ServingStatus.Name(status),
            )


def create_server(
    service: PerceptionService,
    runtime: RuntimeReadiness,
    max_workers: int = DEFAULT_GRPC_MAX_WORKERS,
) -> tuple[grpc.Server, PerceptionHealthServicer]:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    perception_pb2_grpc.add_PerceptionServiceServicer_to_server(service, server)
    health_service = PerceptionHealthServicer(runtime)
    health_pb2_grpc.add_HealthServicer_to_server(health_service, server)
    return server, health_service


def serve(
    service: PerceptionService,
    runtime: RuntimeReadiness,
    host: str,
    port: int,
    max_workers: int = DEFAULT_GRPC_MAX_WORKERS,
) -> None:
    server, health_service = create_server(service, runtime, max_workers=max_workers)

    address = f"{host}:{port}"
    try:
        server.add_insecure_port(address)
    except RuntimeError as error:
        message = f"failed to bind Perception gRPC server to {address}"
        logger.error(message)
        raise RuntimeError(message) from error

    server.start()
    health_service.mark_api_ready()
    health_service.refresh_runtime()
    logger.info("Perception gRPC server listening on {}", address)

    shutdown_event: Event | None = None

    def stop_server() -> Event:
        nonlocal shutdown_event
        if shutdown_event is None:
            health_service.enter_graceful_shutdown()
            shutdown_event = server.stop(grace=SERVER_SHUTDOWN_GRACE_SECONDS)
        return shutdown_event

    def stop_on_sigterm(_signum: int, _frame: FrameType | None) -> None:
        logger.info("Stopping Perception gRPC server")
        stop_server()

    previous_sigterm_handler = signal.signal(signal.SIGTERM, stop_on_sigterm)
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Stopping Perception gRPC server")
        stop_server()
    finally:
        stop_server().wait()
        signal.signal(signal.SIGTERM, previous_sigterm_handler)
