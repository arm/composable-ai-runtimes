# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import signal
from collections.abc import Iterator
from concurrent import futures
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, call

import grpc
import pytest
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

import perception_service.service as service_module
from cairn.perception.v1 import perception_pb2, perception_pb2_grpc
from perception_service.gstreamer.errors import PipelineError, RuntimeUnavailableError
from perception_service.messaging.lifecycle import (
    LifecyclePublisher,
    SessionState,
    StageState,
)
from perception_service.opk.config import OpkCommEndpoint
from perception_service.opk.endpoint_pool import OpkCommEndpointPool
from perception_service.opk.result_router import OpkResultRouter, ResultRoutingError
from perception_service.pipeline_manager import PipelineManager
from perception_service.pipeline_store import PipelineStore
from perception_service.pipeline_types import PipelineEventSink
from perception_service.service import (
    GSTREAMER_SERVICE_NAME,
    PERCEPTION_SERVICE_NAME,
    SERVER_SHUTDOWN_GRACE_SECONDS,
    PerceptionHealthServicer,
    PerceptionService,
    create_server,
)
from perception_service.workflow.model_registry import ModelRegistry
from perception_service.workflow.stage import StageDependencies, StageFactory
from perception_service.workflow.stages.inference import InferenceStageDefinition
from perception_service.workflow.stages.output import OpkSinkStageDefinition
from perception_service.workflow.stages.opk_comm import OpkCommStageDefinition
from perception_service.workflow.stages.opk_performance import (
    OpkPerformanceStageDefinition,
)
from perception_service.workflow.stages.source import CameraSourceDefinition
from tests.helpers import MODEL_VALIDATOR

if TYPE_CHECKING:
    from perception_service.gstreamer.runtime import GStreamerRuntime

pytestmark = pytest.mark.unit

EXPECTED_PIPELINE_DESCRIPTION = (
    "test-source ! test-inference ! opkperformance ! "
    "opkcomm method=websocket ws-port=7001 endpoint=/ws ! fakesink sync=false"
)


class TestCameraSourceDefinition(CameraSourceDefinition):
    __test__ = False

    def validate(self) -> tuple[bool, list[perception_pb2.ValidationIssue]]:
        return True, []

    def construct(self) -> tuple[str, ...]:
        return ("test-source",)


class TestInferenceStageDefinition(InferenceStageDefinition):
    __test__ = False

    def __init__(self, source_definition: perception_pb2.InferenceStage) -> None:
        self._source_definition = source_definition

    def validate(self) -> tuple[bool, list[perception_pb2.ValidationIssue]]:
        return True, []

    def construct(self) -> tuple[str, ...]:
        return ("test-inference",)


class PipelineRuntimeStub:
    def __init__(self) -> None:
        self.pipeline_descriptions: list[str] = []
        self.stop_requests: list[str] = []
        self.element_state_requests: list[tuple[str, str, bool]] = []
        self.create_error: Exception | None = None
        self.stop_error: Exception | None = None
        self.ready = True
        self.element_state_error: Exception | None = None

    def start_pipeline(
        self,
        session_id: str,
        description: str,
        event_sink: PipelineEventSink | None = None,
    ) -> None:
        self.pipeline_descriptions.append(description)
        if self.create_error is not None:
            raise self.create_error

    def stop_pipeline(self, session_id: str) -> None:
        self.stop_requests.append(session_id)
        if self.stop_error is not None:
            raise self.stop_error

    def is_ready(self) -> bool:
        return self.ready

    def set_inference_stage_active(
        self,
        session_id: str,
        stage_id: str,
        active: bool,
    ) -> bool:
        self.element_state_requests.append((session_id, stage_id, active))
        if self.element_state_error is not None:
            raise self.element_state_error
        return active


class BlockingReadinessRuntimeStub(PipelineRuntimeStub):
    def __init__(self) -> None:
        super().__init__()
        self.first_sample_started = Event()
        self.release_first_sample = Event()
        self.readiness_calls = 0
        self._readiness_call_lock = Lock()

    def is_ready(self) -> bool:
        with self._readiness_call_lock:
            call_index = self.readiness_calls
            self.readiness_calls += 1

        if call_index == 0:
            self.first_sample_started.set()
            self.release_first_sample.wait(timeout=1)
            return False
        return True


def create_test_stage_factory(
    dependencies: StageDependencies,
    *,
    include_additive_stages: bool = False,
    validate_models: bool = False,
) -> StageFactory:
    stage_factory = StageFactory(dependencies)
    stage_factory.register_stage(
        perception_pb2.StreamConfiguration,
        lambda definition, _: TestCameraSourceDefinition(definition),
    )
    if validate_models:
        stage_factory.register_stage(
            perception_pb2.InferenceStage,
            lambda definition, stage_dependencies: InferenceStageDefinition(
                definition,
                stage_dependencies.model_registry,
            ),
        )
    else:
        stage_factory.register_stage(
            perception_pb2.InferenceStage,
            lambda definition, _: TestInferenceStageDefinition(definition),
        )
    if include_additive_stages:
        stage_factory.register_additive_stage(lambda _: OpkPerformanceStageDefinition())
        stage_factory.register_additive_stage(
            lambda stage_dependencies: OpkCommStageDefinition(
                stage_dependencies.opk_comm_endpoint
            )
        )
    stage_factory.register_stage(
        perception_pb2.DebugOutput,
        lambda definition, _: OpkSinkStageDefinition(definition),
    )
    return stage_factory


def workflow() -> perception_pb2.WorkflowSpec:
    return perception_pb2.WorkflowSpec(
        name="camera-inference",
        source=perception_pb2.SourceSpec(camera=perception_pb2.StreamConfiguration()),
        stages=[
            perception_pb2.InferenceStage(
                id="objects",
                name="objects",
                model_id="yolov11",
            )
        ],
    )


def create_result_router_stub() -> MagicMock:
    result_router = MagicMock(spec=OpkResultRouter)
    return result_router


def create_lifecycle_stub() -> MagicMock:
    lifecycle = MagicMock(spec=LifecyclePublisher)
    lifecycle.start_session.return_value = ""
    return lifecycle


@pytest.fixture
def pipeline_runtime() -> PipelineRuntimeStub:
    return PipelineRuntimeStub()


@pytest.fixture(autouse=True)
def fixed_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service_module, "uuid4", lambda: "pipeline-123")


@contextmanager
def running_perception_stub(
    pipeline_runtime: PipelineRuntimeStub,
    model_registry: ModelRegistry,
    *,
    validate_models: bool = False,
    result_router: OpkResultRouter | None = None,
    endpoint_pool: OpkCommEndpointPool | None = None,
    lifecycle: LifecyclePublisher | None = None,
    max_workers: int = 1,
) -> Iterator[perception_pb2_grpc.PerceptionServiceStub]:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    if result_router is None:
        result_router = create_result_router_stub()
    if endpoint_pool is None:
        endpoint_pool = OpkCommEndpointPool(OpkCommEndpoint(), 1)
    if lifecycle is None:
        lifecycle = create_lifecycle_stub()
    perception_pb2_grpc.add_PerceptionServiceServicer_to_server(
        PerceptionService(
            PipelineManager(
                cast("GStreamerRuntime", pipeline_runtime), PipelineStore()
            ),
            create_test_stage_factory(
                StageDependencies(
                    model_registry=model_registry,
                    opk_comm_endpoint=OpkCommEndpoint(),
                ),
                include_additive_stages=True,
                validate_models=validate_models,
            ),
            result_router,
            endpoint_pool,
            lifecycle,
        ),
        server,
    )
    port = server.add_insecure_port("127.0.0.1:0")
    assert port != 0
    server.start()

    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    try:
        yield perception_pb2_grpc.PerceptionServiceStub(channel)
    finally:
        channel.close()
        server.stop(grace=0).wait()


@pytest.fixture
def perception_stub(
    pipeline_runtime: PipelineRuntimeStub,
) -> Iterator[perception_pb2_grpc.PerceptionServiceStub]:
    with running_perception_stub(
        pipeline_runtime, ModelRegistry([], MODEL_VALIDATOR)
    ) as stub:
        yield stub


@dataclass(frozen=True)
class ServiceClients:
    perception: perception_pb2_grpc.PerceptionServiceStub
    health: health_pb2_grpc.HealthStub
    health_service: PerceptionHealthServicer


@contextmanager
def running_service_clients(
    pipeline_runtime: PipelineRuntimeStub,
) -> Iterator[ServiceClients]:
    model_registry = ModelRegistry([], MODEL_VALIDATOR)
    result_router = create_result_router_stub()
    pipeline_manager = PipelineManager(
        cast("GStreamerRuntime", pipeline_runtime), PipelineStore()
    )
    service = PerceptionService(
        pipeline_manager,
        create_test_stage_factory(
            StageDependencies(
                model_registry=model_registry,
                opk_comm_endpoint=OpkCommEndpoint(),
            )
        ),
        result_router,
        OpkCommEndpointPool(OpkCommEndpoint(), 1),
        create_lifecycle_stub(),
    )
    server, health_service = create_server(service, pipeline_manager, max_workers=1)
    port = server.add_insecure_port("127.0.0.1:0")
    assert port != 0
    server.start()

    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    try:
        yield ServiceClients(
            perception=perception_pb2_grpc.PerceptionServiceStub(channel),
            health=health_pb2_grpc.HealthStub(channel),
            health_service=health_service,
        )
    finally:
        channel.close()
        server.stop(grace=0).wait()


@pytest.mark.parametrize("service_name", ["", PERCEPTION_SERVICE_NAME])
def test_create_server_registers_readiness_as_not_serving(
    pipeline_runtime: PipelineRuntimeStub,
    service_name: str,
) -> None:
    with running_service_clients(pipeline_runtime) as clients:
        response = clients.health.Check(
            health_pb2.HealthCheckRequest(service=service_name),
            timeout=1,
        )

    assert response.status == health_pb2.HealthCheckResponse.NOT_SERVING


def test_health_rejects_unregistered_service(
    pipeline_runtime: PipelineRuntimeStub,
) -> None:
    with (
        running_service_clients(pipeline_runtime) as clients,
        pytest.raises(grpc.RpcError) as error,
    ):
        clients.health.Check(
            health_pb2.HealthCheckRequest(service="unknown.Service"), timeout=1
        )

    assert isinstance(error.value, grpc.Call)
    assert error.value.code() == grpc.StatusCode.NOT_FOUND


def test_health_reflects_runtime_failure_and_recovery(
    pipeline_runtime: PipelineRuntimeStub,
) -> None:
    with running_service_clients(pipeline_runtime) as clients:
        clients.health_service.mark_api_ready()
        clients.health_service.refresh_runtime()

        for service_name in ("", PERCEPTION_SERVICE_NAME, GSTREAMER_SERVICE_NAME):
            response = clients.health.Check(
                health_pb2.HealthCheckRequest(service=service_name), timeout=1
            )
            assert response.status == health_pb2.HealthCheckResponse.SERVING

        pipeline_runtime.ready = False
        aggregate = clients.health.Check(
            health_pb2.HealthCheckRequest(service=""), timeout=1
        )
        api = clients.health.Check(
            health_pb2.HealthCheckRequest(service=PERCEPTION_SERVICE_NAME), timeout=1
        )
        gstreamer = clients.health.Check(
            health_pb2.HealthCheckRequest(service=GSTREAMER_SERVICE_NAME), timeout=1
        )

        assert aggregate.status == health_pb2.HealthCheckResponse.NOT_SERVING
        assert api.status == health_pb2.HealthCheckResponse.SERVING
        assert gstreamer.status == health_pb2.HealthCheckResponse.NOT_SERVING

        pipeline_runtime.ready = True
        aggregate = clients.health.Check(
            health_pb2.HealthCheckRequest(service=""), timeout=1
        )
        gstreamer = clients.health.Check(
            health_pb2.HealthCheckRequest(service=GSTREAMER_SERVICE_NAME), timeout=1
        )

        assert aggregate.status == health_pb2.HealthCheckResponse.SERVING
        assert gstreamer.status == health_pb2.HealthCheckResponse.SERVING


def test_concurrent_runtime_refreshes_publish_in_sample_order() -> None:
    runtime = BlockingReadinessRuntimeStub()
    health_service = PerceptionHealthServicer(runtime)
    health_service.mark_api_ready()

    failure_refresh = Thread(target=health_service.refresh_runtime)
    failure_refresh.start()
    assert runtime.first_sample_started.wait(timeout=1)

    transition_lock_was_available = health_service._transition_lock.acquire(
        blocking=False
    )
    if transition_lock_was_available:
        health_service._transition_lock.release()

    recovery_refresh = Thread(target=health_service.refresh_runtime)
    recovery_refresh.start()
    runtime.release_first_sample.set()
    failure_refresh.join(timeout=1)
    recovery_refresh.join(timeout=1)

    assert not transition_lock_was_available
    assert not failure_refresh.is_alive()
    assert not recovery_refresh.is_alive()
    assert runtime.readiness_calls == 2

    context = MagicMock()
    for service_name in ("", GSTREAMER_SERVICE_NAME):
        response = health.HealthServicer.Check(
            health_service,
            health_pb2.HealthCheckRequest(service=service_name),
            context,
        )
        assert response.status == health_pb2.HealthCheckResponse.SERVING


def test_rejected_workflow_does_not_change_readiness(
    pipeline_runtime: PipelineRuntimeStub,
) -> None:
    with running_service_clients(pipeline_runtime) as clients:
        clients.health_service.mark_api_ready()
        clients.health_service.refresh_runtime()

        response = clients.perception.DeployWorkflow(
            perception_pb2.DeployWorkflowRequest(
                workflow=perception_pb2.WorkflowSpec(name="invalid")
            ),
            timeout=1,
        )
        health_response = clients.health.Check(
            health_pb2.HealthCheckRequest(service=""), timeout=1
        )

    assert response.WhichOneof("outcome") == "rejected"
    assert health_response.status == health_pb2.HealthCheckResponse.SERVING


def expected_resolved_stages(
    *,
    include_debug_output: bool = False,
) -> list[perception_pb2.ResolvedStage]:
    stages = [
        perception_pb2.ResolvedStage(
            id="source:camera",
            name="pipewire_source",
            role=perception_pb2.RESOLVED_STAGE_ROLE_SOURCE,
        ),
        perception_pb2.ResolvedStage(
            id="objects",
            name="objects",
            role=perception_pb2.RESOLVED_STAGE_ROLE_PROCESSING,
            controllable=True,
            model_id="yolov11",
        ),
    ]
    if include_debug_output:
        stages.append(
            perception_pb2.ResolvedStage(
                id="output:debug",
                name="opksink",
                role=perception_pb2.RESOLVED_STAGE_ROLE_OUTPUT,
            )
        )
    return stages


def test_get_service_info_returns_v1_metadata(
    perception_stub: perception_pb2_grpc.PerceptionServiceStub,
) -> None:
    response = perception_stub.GetServiceInfo(
        perception_pb2.GetServiceInfoRequest(),
        timeout=1,
    )

    assert response == perception_pb2.GetServiceInfoResponse(
        api_version="v1",
        service_version="0.0.2",
        sessions_survive_restart=False,
    )


def test_validate_workflow_returns_resolved_stages_without_starting_pipeline(
    perception_stub: perception_pb2_grpc.PerceptionServiceStub,
    pipeline_runtime: PipelineRuntimeStub,
) -> None:
    response = perception_stub.ValidateWorkflow(
        perception_pb2.ValidateWorkflowRequest(workflow=workflow()),
        timeout=1,
    )

    assert response.valid
    assert response.issues == []
    assert response.stages == expected_resolved_stages()
    assert pipeline_runtime.pipeline_descriptions == []


def test_validate_workflow_rejects_model_that_is_not_installed(
    pipeline_runtime: PipelineRuntimeStub,
) -> None:
    with running_perception_stub(
        pipeline_runtime,
        ModelRegistry([], MODEL_VALIDATOR),
        validate_models=True,
    ) as stub:
        response = stub.ValidateWorkflow(
            perception_pb2.ValidateWorkflowRequest(workflow=workflow()),
            timeout=1,
        )

    assert not response.valid
    assert [issue.code for issue in response.issues] == ["MODEL_NOT_FOUND"]
    assert response.issues[0].field_path == "stages.model_id"
    assert response.issues[0].stage_id == "objects"
    assert pipeline_runtime.pipeline_descriptions == []



def test_deploy_workflow_starts_compiled_pipeline(
    perception_stub: perception_pb2_grpc.PerceptionServiceStub,
    pipeline_runtime: PipelineRuntimeStub,
) -> None:
    response = perception_stub.DeployWorkflow(
        perception_pb2.DeployWorkflowRequest(workflow=workflow()),
        timeout=1,
    )

    assert pipeline_runtime.pipeline_descriptions == [EXPECTED_PIPELINE_DESCRIPTION]
    assert response == perception_pb2.DeployWorkflowResponse(
        accepted=perception_pb2.DeploymentAccepted(
            session=perception_pb2.PerceptionSession(
                id="pipeline-123",
                workflow_name="camera-inference",
                stages=expected_resolved_stages(),
                topics=perception_pb2.SessionTopics(
                    results="cairn.perception.sessions.pipeline-123.results",
                ),
            ),
        ),
    )


def test_deploy_invalid_workflow_does_not_start_pipeline(
    perception_stub: perception_pb2_grpc.PerceptionServiceStub,
    pipeline_runtime: PipelineRuntimeStub,
) -> None:
    response = perception_stub.DeployWorkflow(
        perception_pb2.DeployWorkflowRequest(
            workflow=perception_pb2.WorkflowSpec(name="invalid")
        ),
        timeout=1,
    )

    assert response.WhichOneof("outcome") == "rejected"
    assert [issue.code for issue in response.rejected.issues] == [
        "SOURCE_REQUIRED",
        "INFERENCE_STAGE_REQUIRED",
    ]
    assert pipeline_runtime.pipeline_descriptions == []


def test_deploy_debug_output_returns_resolved_endpoint(
    perception_stub: perception_pb2_grpc.PerceptionServiceStub,
    pipeline_runtime: PipelineRuntimeStub,
) -> None:
    request_workflow = workflow()
    request_workflow.output.debug.CopyFrom(
        perception_pb2.DebugOutput(
            http_port=10000,
            ws_port=10001,
            ctrl_port=10002,
        )
    )

    response = perception_stub.DeployWorkflow(
        perception_pb2.DeployWorkflowRequest(workflow=request_workflow),
        timeout=1,
    )

    assert pipeline_runtime.pipeline_descriptions == [
        (
            "test-source ! test-inference ! opkperformance ! "
            "opkcomm method=websocket ws-port=7001 endpoint=/ws ! "
            "opkosd enabled=true ! "
            "opksink http-port=10000 ws-port=10001 ctrl-port=10002"
        )
    ]
    assert response == perception_pb2.DeployWorkflowResponse(
        accepted=perception_pb2.DeploymentAccepted(
            session=perception_pb2.PerceptionSession(
                id="pipeline-123",
                workflow_name="camera-inference",
                stages=expected_resolved_stages(include_debug_output=True),
                debug_endpoint=perception_pb2.DebugPorts(
                    http_port=10000,
                    ws_port=10001,
                    ctrl_port=10002,
                ),
                topics=perception_pb2.SessionTopics(
                    results="cairn.perception.sessions.pipeline-123.results",
                ),
            ),
        ),
    )


def test_deploy_invalid_debug_port_does_not_start_pipeline(
    perception_stub: perception_pb2_grpc.PerceptionServiceStub,
    pipeline_runtime: PipelineRuntimeStub,
) -> None:
    request_workflow = workflow()
    request_workflow.output.debug.http_port = 65536

    response = perception_stub.DeployWorkflow(
        perception_pb2.DeployWorkflowRequest(workflow=request_workflow),
        timeout=1,
    )

    assert response.WhichOneof("outcome") == "rejected"
    assert [issue.code for issue in response.rejected.issues] == ["DEBUG_PORT_INVALID"]
    assert response.rejected.issues[0].field_path == "output.debug.http_port"
    assert pipeline_runtime.pipeline_descriptions == []



@pytest.mark.parametrize(
    "runtime_error",
    [
        PipelineError("pipeline operation failed"),
        RuntimeUnavailableError("runtime unavailable"),
    ],
)
def test_runtime_start_failure_returns_unavailable(
    runtime_error: Exception,
    perception_stub: perception_pb2_grpc.PerceptionServiceStub,
    pipeline_runtime: PipelineRuntimeStub,
) -> None:
    pipeline_runtime.create_error = runtime_error

    with pytest.raises(grpc.RpcError) as error:
        perception_stub.DeployWorkflow(
            perception_pb2.DeployWorkflowRequest(workflow=workflow()),
            timeout=1,
        )

    assert isinstance(error.value, grpc.Call)
    assert error.value.code() == grpc.StatusCode.UNAVAILABLE
    assert error.value.details() == "runtime dependency is unavailable"


def test_unexpected_runtime_start_failure_returns_internal(
    perception_stub: perception_pb2_grpc.PerceptionServiceStub,
    pipeline_runtime: PipelineRuntimeStub,
) -> None:
    pipeline_runtime.create_error = ValueError("unexpected failure")

    with pytest.raises(grpc.RpcError) as error:
        perception_stub.DeployWorkflow(
            perception_pb2.DeployWorkflowRequest(workflow=workflow()),
            timeout=1,
        )

    assert isinstance(error.value, grpc.Call)
    assert error.value.code() == grpc.StatusCode.INTERNAL
    assert error.value.details() == "internal server error"


@pytest.mark.parametrize(
    "runtime_error",
    [
        PipelineError("pipeline operation failed"),
        RuntimeUnavailableError("runtime unavailable"),
    ],
)
def test_runtime_stop_failure_returns_unavailable(
    runtime_error: Exception,
    perception_stub: perception_pb2_grpc.PerceptionServiceStub,
    pipeline_runtime: PipelineRuntimeStub,
) -> None:
    perception_stub.DeployWorkflow(
        perception_pb2.DeployWorkflowRequest(workflow=workflow()), timeout=1
    )
    pipeline_runtime.stop_error = runtime_error

    with pytest.raises(grpc.RpcError) as error:
        perception_stub.StopSession(
            perception_pb2.StopSessionRequest(session_id="pipeline-123"),
            timeout=1,
        )

    assert pipeline_runtime.stop_requests == ["pipeline-123"]
    assert isinstance(error.value, grpc.Call)
    assert error.value.code() == grpc.StatusCode.UNAVAILABLE
    assert error.value.details() == "runtime dependency is unavailable"


def test_unexpected_runtime_stop_failure_returns_internal(
    perception_stub: perception_pb2_grpc.PerceptionServiceStub,
    pipeline_runtime: PipelineRuntimeStub,
) -> None:
    perception_stub.DeployWorkflow(
        perception_pb2.DeployWorkflowRequest(workflow=workflow()), timeout=1
    )
    pipeline_runtime.stop_error = ValueError("unexpected failure")

    with pytest.raises(grpc.RpcError) as error:
        perception_stub.StopSession(
            perception_pb2.StopSessionRequest(session_id="pipeline-123"),
            timeout=1,
        )

    assert pipeline_runtime.stop_requests == ["pipeline-123"]
    assert isinstance(error.value, grpc.Call)
    assert error.value.code() == grpc.StatusCode.INTERNAL
    assert error.value.details() == "internal server error"


@pytest.mark.parametrize(
    ("runtime_error", "router_error", "expected_status"),
    [
        (PipelineError("startup timed out"), None, grpc.StatusCode.UNAVAILABLE),
        (None, ResultRoutingError("router failed"), grpc.StatusCode.INTERNAL),
    ],
    ids=["runtime-start", "router-start"],
)
def test_failed_startup_cleanup_retains_endpoint_until_retry(
    monkeypatch: pytest.MonkeyPatch,
    pipeline_runtime: PipelineRuntimeStub,
    runtime_error: Exception | None,
    router_error: Exception | None,
    expected_status: grpc.StatusCode,
) -> None:
    pipeline_runtime.create_error = runtime_error
    pipeline_runtime.stop_error = RuntimeError("cleanup failed")
    result_router = create_result_router_stub()
    result_router.start.side_effect = router_error
    endpoint_pool = OpkCommEndpointPool(OpkCommEndpoint(), 1)

    with running_perception_stub(
        pipeline_runtime,
        ModelRegistry([], MODEL_VALIDATOR),
        result_router=result_router,
        endpoint_pool=endpoint_pool,
    ) as stub:
        with pytest.raises(grpc.RpcError) as startup_error:
            stub.DeployWorkflow(
                perception_pb2.DeployWorkflowRequest(workflow=workflow()),
                timeout=1,
            )
        with pytest.raises(grpc.RpcError) as capacity_error:
            stub.DeployWorkflow(
                perception_pb2.DeployWorkflowRequest(workflow=workflow()),
                timeout=1,
            )
        pipeline_runtime.create_error = None
        pipeline_runtime.stop_error = None
        stub.StopSession(
            perception_pb2.StopSessionRequest(session_id="pipeline-123"),
            timeout=1,
        )
        result_router.start.side_effect = None
        monkeypatch.setattr(service_module, "uuid4", lambda: "recovered-session")
        recovered = stub.DeployWorkflow(
            perception_pb2.DeployWorkflowRequest(workflow=workflow()),
            timeout=1,
        )

    assert isinstance(startup_error.value, grpc.Call)
    assert startup_error.value.code() == expected_status
    assert isinstance(capacity_error.value, grpc.Call)
    assert capacity_error.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
    assert recovered.WhichOneof("outcome") == "accepted"



def test_stop_session_returns_minimal_session(
    perception_stub: perception_pb2_grpc.PerceptionServiceStub,
    pipeline_runtime: PipelineRuntimeStub,
) -> None:
    perception_stub.DeployWorkflow(
        perception_pb2.DeployWorkflowRequest(workflow=workflow()), timeout=1
    )
    request = perception_pb2.StopSessionRequest(session_id="pipeline-123")

    response = perception_stub.StopSession(request, timeout=1)

    assert pipeline_runtime.stop_requests == ["pipeline-123"]
    assert response == perception_pb2.PerceptionSession(id="pipeline-123")



def test_concurrent_stage_controls_publish_matching_order(
    monkeypatch: pytest.MonkeyPatch,
    pipeline_runtime: PipelineRuntimeStub,
) -> None:
    first_publication_started = Event()
    release_first_publication = Event()
    second_runtime_change = Event()
    lifecycle = create_lifecycle_stub()

    def set_stage_active(session_id: str, stage_id: str, active: bool) -> bool:
        pipeline_runtime.element_state_requests.append((session_id, stage_id, active))
        if len(pipeline_runtime.element_state_requests) == 2:
            second_runtime_change.set()
        return active

    def publish_stage(_session_id: str, _stage_id: str, state: StageState) -> None:
        if state is StageState.DISABLED:
            first_publication_started.set()
            assert release_first_publication.wait(timeout=1)

    monkeypatch.setattr(
        pipeline_runtime,
        "set_inference_stage_active",
        set_stage_active,
    )
    lifecycle.publish_stage.side_effect = publish_stage
    request = perception_pb2.StageControlRequest(
        session_id="pipeline-123",
        stage_id="objects",
    )

    with (
        running_perception_stub(
            pipeline_runtime,
            ModelRegistry([], MODEL_VALIDATOR),
            lifecycle=lifecycle,
            max_workers=2,
        ) as stub,
        futures.ThreadPoolExecutor(max_workers=2) as executor,
    ):
        stub.DeployWorkflow(
            perception_pb2.DeployWorkflowRequest(workflow=workflow()), timeout=1
        )
        disabled = executor.submit(stub.DisableStage, request, timeout=1)
        assert first_publication_started.wait(timeout=1)
        enabled = executor.submit(stub.EnableStage, request, timeout=1)
        assert not second_runtime_change.wait(timeout=0.1)
        release_first_publication.set()
        disabled.result()
        enabled.result()

    assert pipeline_runtime.element_state_requests == [
        ("pipeline-123", "objects", False),
        ("pipeline-123", "objects", True),
    ]
    assert lifecycle.publish_stage.call_args_list == [
        call("pipeline-123", "objects", StageState.DISABLED),
        call("pipeline-123", "objects", StageState.ENABLED),
    ]


def test_result_router_follows_pipeline_lifecycle(
    pipeline_runtime: PipelineRuntimeStub,
) -> None:
    result_router = create_result_router_stub()
    service = PerceptionService(
        PipelineManager(cast("GStreamerRuntime", pipeline_runtime), PipelineStore()),
        create_test_stage_factory(
            StageDependencies(
                model_registry=ModelRegistry([], MODEL_VALIDATOR),
                opk_comm_endpoint=OpkCommEndpoint(),
            ),
            include_additive_stages=True,
        ),
        result_router,
        OpkCommEndpointPool(OpkCommEndpoint(port=7010), 1),
        create_lifecycle_stub(),
    )
    context = MagicMock(spec=grpc.ServicerContext)

    response = service.DeployWorkflow(
        perception_pb2.DeployWorkflowRequest(workflow=workflow()),
        context,
    )
    service.StopSession(
        perception_pb2.StopSessionRequest(session_id="pipeline-123"),
        context,
    )

    assert "ws-port=7010" in pipeline_runtime.pipeline_descriptions[0]
    assert response.accepted.session.topics.results == (
        "cairn.perception.sessions.pipeline-123.results"
    )
    result_router.start.assert_called_once()
    session_id, lease = result_router.start.call_args.args
    assert session_id == "pipeline-123"
    assert lease.endpoint == OpkCommEndpoint(port=7010)
    result_router.stop.assert_called_once_with("pipeline-123")


def test_result_router_stop_failure_finishes_lifecycle(
    pipeline_runtime: PipelineRuntimeStub,
) -> None:
    result_router = create_result_router_stub()
    result_router.stop.side_effect = ResultRoutingError("router unavailable")
    lifecycle = create_lifecycle_stub()

    with running_perception_stub(
        pipeline_runtime,
        ModelRegistry([], MODEL_VALIDATOR),
        result_router=result_router,
        lifecycle=lifecycle,
    ) as stub:
        stub.DeployWorkflow(
            perception_pb2.DeployWorkflowRequest(workflow=workflow()), timeout=1
        )
        lifecycle.reset_mock()
        with pytest.raises(grpc.RpcError) as error:
            stub.StopSession(
                perception_pb2.StopSessionRequest(session_id="pipeline-123"),
                timeout=1,
            )

    assert isinstance(error.value, grpc.Call)
    assert error.value.code() == grpc.StatusCode.INTERNAL
    assert error.value.details() == "internal server error"
    assert lifecycle.publish_session.call_args_list == [
        call("pipeline-123", SessionState.STOPPING),
        call("pipeline-123", SessionState.FAILED),
    ]


def test_serve_stops_on_sigterm(monkeypatch: pytest.MonkeyPatch) -> None:
    server = MagicMock()
    health_service = MagicMock()
    signal_handler = MagicMock(return_value=signal.SIG_DFL)

    def wait_for_termination() -> None:
        installed_handler = signal_handler.call_args.args[1]
        installed_handler(signal.SIGTERM, None)

    server.wait_for_termination.side_effect = wait_for_termination
    monkeypatch.setattr(
        service_module,
        "create_server",
        lambda *_args, **_kwargs: (server, health_service),
    )
    monkeypatch.setattr(service_module.signal, "signal", signal_handler)

    service_module.serve(
        MagicMock(spec=PerceptionService),
        MagicMock(spec=PipelineManager),
        "127.0.0.1",
        50053,
    )

    server.stop.assert_called_once_with(grace=SERVER_SHUTDOWN_GRACE_SECONDS)
    server.stop.return_value.wait.assert_called_once_with()
    health_service.mark_api_ready.assert_called_once_with()
    health_service.refresh_runtime.assert_called_once_with()
    health_service.enter_graceful_shutdown.assert_called_once_with()
    assert signal_handler.call_count == 2
    assert signal_handler.call_args.args == (signal.SIGTERM, signal.SIG_DFL)


@pytest.mark.parametrize("failure", ["native", "routing"])
def test_failed_deployment_cleanup_uses_session_id_without_lookup(
    pipeline_runtime: PipelineRuntimeStub,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    lookup = MagicMock(
        side_effect=AssertionError("cleanup must use its original session_id")
    )
    monkeypatch.setattr(PipelineManager, "get_pipeline", lookup)
    result_router = create_result_router_stub()
    if failure == "native":
        pipeline_runtime.create_error = RuntimeError("native failed")
    else:
        result_router.start.side_effect = RuntimeError("routing failed")
    endpoint_pool = OpkCommEndpointPool(OpkCommEndpoint(), 1)

    with running_perception_stub(
        pipeline_runtime,
        ModelRegistry([], MODEL_VALIDATOR),
        result_router=result_router,
        endpoint_pool=endpoint_pool,
    ) as stub:
        with pytest.raises(grpc.RpcError):
            stub.DeployWorkflow(
                perception_pb2.DeployWorkflowRequest(workflow=workflow()), timeout=1
            )

    session_id = "pipeline-123"
    assert pipeline_runtime.stop_requests == [session_id] * (
        2 if failure == "native" else 1
    )
    lookup.assert_not_called()
    with endpoint_pool.reserve():
        pass
