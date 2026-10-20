# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import json
import subprocess
import time
from collections.abc import Callable

import grpc
import pytest
from grpc_health.v1 import health_pb2, health_pb2_grpc
from open_perception_kit import packet
from redis import Redis
from redis.client import PubSub

from cairn.messaging.v1.messaging_pb2 import CairnEvent
from cairn.perception.v1 import perception_pb2, perception_pb2_grpc
from perception_service.messaging import EVENT_ORIGIN
from perception_service.messaging.result_publisher import RESULT_EVENT_TYPE

pytestmark = pytest.mark.e2e

PIPEWIRE_TARGET = "gstreamer-test-source"
RPC_TIMEOUT_SECONDS = 30
READINESS_TIMEOUT_SECONDS = 30


def inspect_container(container_id: str, template: str) -> str:
    completed = subprocess.run(
        ["docker", "inspect", "--format", template, container_id],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def deploy_workflow(
    stub: perception_pb2_grpc.PerceptionServiceStub,
    name: str,
    *,
    debug: bool = False,
    model_id: str = "yolo26n-320",
) -> perception_pb2.PerceptionSession:
    response = stub.DeployWorkflow(
        perception_pb2.DeployWorkflowRequest(
            workflow=perception_pb2.WorkflowSpec(
                name=name,
                source=perception_pb2.SourceSpec(
                    camera=perception_pb2.StreamConfiguration(
                        target=PIPEWIRE_TARGET,
                        format=perception_pb2.StreamFormat(
                            resolution=perception_pb2.Resolution(width=640, height=480),
                            frame_rate=perception_pb2.FrameRate(
                                numerator=30,
                                denominator=1,
                            ),
                            pixel_format="YUY2",
                        ),
                    )
                ),
                stages=[
                    perception_pb2.InferenceStage(
                        id="objects",
                        name="objects",
                        model_id=model_id,
                    )
                ],
                output=(
                    perception_pb2.OutputSpec(debug=perception_pb2.DebugOutput())
                    if debug
                    else None
                ),
            ),
        ),
        timeout=RPC_TIMEOUT_SECONDS,
    )
    assert response.WhichOneof("outcome") == "accepted"
    return response.accepted.session


def stop_workflow(
    stub: perception_pb2_grpc.PerceptionServiceStub,
    session: perception_pb2.PerceptionSession,
) -> None:
    response = stub.StopSession(
        perception_pb2.StopSessionRequest(session_id=session.id),
        timeout=RPC_TIMEOUT_SECONDS,
    )
    assert response.id == session.id


def wait_for_result_event(pubsub: PubSub, channel: str) -> CairnEvent:
    deadline = time.monotonic() + READINESS_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
        if message is not None and message.get("channel") == channel.encode():
            return CairnEvent.FromString(message["data"])
    raise TimeoutError(f"Timed out waiting for a result on {channel}")


def wait_for_event_types(
    pubsub: PubSub,
    channel: str,
    expected_types: list[str],
) -> list[CairnEvent]:
    events: list[CairnEvent] = []
    deadline = time.monotonic() + READINESS_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
        if message is None or message.get("channel") != channel.encode():
            continue
        event = CairnEvent.FromString(message["data"])
        if event.event_type == expected_types[len(events)]:
            events.append(event)
            if len(events) == len(expected_types):
                return events
    raise TimeoutError(f"Timed out waiting for lifecycle events on {channel}")


def assert_lifecycle_event(
    event: CairnEvent,
    session: perception_pb2.PerceptionSession,
    *,
    event_type: str,
    state: str,
    stage_id: str | None = None,
) -> None:
    assert event.origin == EVENT_ORIGIN
    assert event.event_type == event_type
    assert event.topic == session.topics.events
    assert event.HasField("timestamp")
    payload = json.loads(event.payload)
    assert payload == {
        "session_id": session.id,
        **({"stage_id": stage_id} if stage_id is not None else {}),
        "state": state,
    }


def test_packaged_service_is_ready(
    e2e_health_stub: health_pb2_grpc.HealthStub,
    e2e_compose_command: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    health_response = e2e_health_stub.Check(
        health_pb2.HealthCheckRequest(service=""),
        timeout=RPC_TIMEOUT_SECONDS,
    )
    assert health_response.status == health_pb2.HealthCheckResponse.SERVING

    for service in ("pipewire-source", "perception-service", "messaging-service"):
        container_id = e2e_compose_command(
            "ps", "--all", "--quiet", service
        ).stdout.strip()
        assert container_id, f"Docker Compose did not report {service}"
        assert inspect_container(container_id, "{{.State.Status}}") == "running"


@pytest.mark.parametrize("e2e_grpc_address", ["empty-models"], indirect=True)
def test_packaged_service_is_ready_without_models(
    e2e_health_stub: health_pb2_grpc.HealthStub,
) -> None:
    response = e2e_health_stub.Check(
        health_pb2.HealthCheckRequest(service=""),
        timeout=RPC_TIMEOUT_SECONDS,
    )
    assert response.status == health_pb2.HealthCheckResponse.SERVING


def test_byom_blazeface_result_and_stop(
    e2e_perception_stub: perception_pb2_grpc.PerceptionServiceStub,
    e2e_redis_url: Callable[[], str],
) -> None:
    with (
        Redis.from_url(e2e_redis_url(), decode_responses=False) as redis_client,
        redis_client.pubsub() as result_messages,
    ):
        result_messages.psubscribe("cairn.perception.sessions.*.results")
        result_messages.get_message(timeout=1)
        session = deploy_workflow(
            e2e_perception_stub,
            "e2e-byom-blazeface",
            model_id="byom-blazeface",
        )
        try:
            event = wait_for_result_event(result_messages, session.topics.results)
            envelope = packet.decode(event.payload)
            assert envelope.valid(), envelope.error()
            (payload,) = envelope.for_each(
                packet.external_key("com.arm.example.blazeface.faces.v1")
            )
            faces = json.loads(bytes(payload))["faces"]
            assert isinstance(faces, list)
            assert len(faces) > 0, "No faces detected"
        finally:
            stop_workflow(e2e_perception_stub, session)


def test_deploy_result_and_stop(
    e2e_perception_stub: perception_pb2_grpc.PerceptionServiceStub,
    e2e_redis_url: Callable[[], str],
) -> None:
    with Redis.from_url(e2e_redis_url(), decode_responses=False) as redis_client:
        with (
            redis_client.pubsub() as result_messages,
            redis_client.pubsub() as lifecycle_messages,
        ):
            result_messages.psubscribe("cairn.perception.sessions.*.results")
            lifecycle_messages.psubscribe("cairn.perception.sessions.*.events")
            result_messages.get_message(timeout=1)
            lifecycle_messages.get_message(timeout=1)
            session = deploy_workflow(
                e2e_perception_stub,
                "e2e-workflow",
                debug=True,
            )
            started = wait_for_event_types(
                lifecycle_messages,
                session.topics.events,
                [
                    "cairn.perception.session.starting",
                    "cairn.perception.session.running",
                ],
            )
            event = wait_for_result_event(result_messages, session.topics.results)
            stop_workflow(e2e_perception_stub, session)
            stopped = wait_for_event_types(
                lifecycle_messages,
                session.topics.events,
                [
                    "cairn.perception.session.stopping",
                    "cairn.perception.session.stopped",
                ],
            )

    assert event.origin == EVENT_ORIGIN
    assert event.event_type == RESULT_EVENT_TYPE
    assert event.topic == session.topics.results
    assert event.HasField("timestamp")
    assert event.payload
    assert session.debug_endpoint == perception_pb2.DebugPorts(
        http_port=9999,
        ws_port=8000,
        ctrl_port=8001,
    )
    for lifecycle_event, state in zip(
        [*started, *stopped],
        ["starting", "running", "stopping", "stopped"],
        strict=True,
    ):
        assert_lifecycle_event(
            lifecycle_event,
            session,
            event_type=f"cairn.perception.session.{state}",
            state=state,
        )


def test_stage_control(
    e2e_perception_stub: perception_pb2_grpc.PerceptionServiceStub,
    e2e_redis_url: Callable[[], str],
) -> None:
    with Redis.from_url(e2e_redis_url(), decode_responses=False) as redis_client:
        with redis_client.pubsub() as lifecycle_messages:
            lifecycle_messages.psubscribe("cairn.perception.sessions.*.events")
            lifecycle_messages.get_message(timeout=1)
            session = deploy_workflow(
                e2e_perception_stub,
                "e2e-stage-control-workflow",
            )
            disabled = e2e_perception_stub.DisableStage(
                perception_pb2.StageControlRequest(
                    session_id=session.id,
                    stage_id="objects",
                ),
                timeout=RPC_TIMEOUT_SECONDS,
            )
            enabled = e2e_perception_stub.EnableStage(
                perception_pb2.StageControlRequest(
                    session_id=session.id,
                    stage_id="objects",
                ),
                timeout=RPC_TIMEOUT_SECONDS,
            )
            disabled_event, enabled_event = wait_for_event_types(
                lifecycle_messages,
                session.topics.events,
                [
                    "cairn.perception.stage.disabled",
                    "cairn.perception.stage.enabled",
                ],
            )

    assert (disabled.id, enabled.id) == (session.id, session.id)
    assert_lifecycle_event(
        disabled_event,
        session,
        event_type="cairn.perception.stage.disabled",
        state="disabled",
        stage_id="objects",
    )
    assert_lifecycle_event(
        enabled_event,
        session,
        event_type="cairn.perception.stage.enabled",
        state="enabled",
        stage_id="objects",
    )
    stop_workflow(e2e_perception_stub, session)


def test_concurrent_result_sessions_are_isolated(
    e2e_perception_stub: perception_pb2_grpc.PerceptionServiceStub,
    e2e_redis_url: Callable[[], str],
) -> None:
    with Redis.from_url(e2e_redis_url(), decode_responses=False) as redis_client:
        with redis_client.pubsub() as pubsub:
            pubsub.psubscribe("cairn.perception.sessions.*.results")
            pubsub.get_message(timeout=1)
            first = deploy_workflow(e2e_perception_stub, "e2e-workflow-a")
            second = deploy_workflow(e2e_perception_stub, "e2e-workflow-b")
            first_event = wait_for_result_event(pubsub, first.topics.results)
            second_event = wait_for_result_event(pubsub, second.topics.results)

        stop_workflow(e2e_perception_stub, first)
        with pytest.raises(grpc.RpcError) as error:
            e2e_perception_stub.DisableStage(
                perception_pb2.StageControlRequest(
                    session_id=first.id,
                    stage_id="objects",
                ),
                timeout=RPC_TIMEOUT_SECONDS,
            )
        assert isinstance(error.value, grpc.Call)
        assert error.value.code() == grpc.StatusCode.NOT_FOUND

        with redis_client.pubsub() as pubsub:
            pubsub.subscribe(second.topics.results)
            pubsub.get_message(timeout=1)
            remaining_event = wait_for_result_event(pubsub, second.topics.results)

    assert first.id != second.id
    assert first.topics.results != second.topics.results
    assert first_event.topic == first.topics.results
    assert second_event.topic == second.topics.results
    assert remaining_event.topic == second.topics.results
    stop_workflow(e2e_perception_stub, second)


def test_result_publication_recovers_after_redis_restart(
    e2e_perception_stub: perception_pb2_grpc.PerceptionServiceStub,
    e2e_compose_command: Callable[..., subprocess.CompletedProcess[str]],
    e2e_redis_url: Callable[[], str],
) -> None:
    with Redis.from_url(e2e_redis_url(), decode_responses=False) as redis_client:
        with redis_client.pubsub() as pubsub:
            pubsub.psubscribe("cairn.perception.sessions.*.results")
            pubsub.get_message(timeout=1)
            session = deploy_workflow(e2e_perception_stub, "e2e-recovery-workflow")
            wait_for_result_event(pubsub, session.topics.results)

    e2e_compose_command("stop", "--timeout", "5", "messaging-service")
    try:
        e2e_compose_command(
            "up", "--detach", "--wait", "--no-build", "messaging-service"
        )
        with Redis.from_url(e2e_redis_url(), decode_responses=False) as redis_client:
            with redis_client.pubsub() as pubsub:
                pubsub.subscribe(session.topics.results)
                pubsub.get_message(timeout=1)
                recovered_event = wait_for_result_event(
                    pubsub,
                    session.topics.results,
                )
    finally:
        e2e_compose_command(
            "up", "--detach", "--wait", "--no-build", "messaging-service"
        )
        stop_workflow(e2e_perception_stub, session)

    assert recovered_event.topic == session.topics.results
    assert recovered_event.payload
