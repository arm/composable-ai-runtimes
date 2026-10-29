# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import asyncio
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from cairn import (
    FrameRate,
    Notification,
    NotificationService,
    Resolution,
    StreamConfiguration,
    StreamFormat,
)
from cairn.perception import (
    DeploymentValidationError,
    FrameContext,
    PerceptionError,
    PerceptionResult,
    PerceptionService,
    PerceptionSession,
    PerceptionWorkflow,
    ServiceInfo,
    SessionState,
    ValidationResult,
)

pytestmark = pytest.mark.e2e
PERCEPTION_ROOT = Path(__file__).resolve().parents[2] / "services/perception"
RESULT_ROUTER_SETTLE_SECONDS = 1
STOPPED_RESULT_QUIESCENCE_SECONDS = 2
COMPOSE_COMMAND = (
    "docker",
    "compose",
    "-f",
    "compose.yaml",
    "-f",
    "tests/e2e/compose.yaml",
)
COMPOSE_ENVIRONMENT = {
    **os.environ,
    "COMPOSE_PROJECT_NAME": f"python-sdk-e2e-{os.getpid()}",
}


def test_python_sdk_deploys_a_working_perception_workflow(
    perception_stack: tuple[str, str],
) -> None:
    perception_endpoint, messaging_endpoint = perception_stack
    source = StreamConfiguration(
        "gstreamer-test-source",
        7,
        StreamFormat(Resolution(640, 480), "YUY2", FrameRate(30, 1)),
    )
    workflow = PerceptionWorkflow("python-sdk-e2e", source, output_events=False)
    workflow.infer("objects", "yolo26n-320")

    async def run() -> tuple[
        ServiceInfo,
        PerceptionSession,
        Notification,
        PerceptionResult,
        str,
        ValidationResult,
    ]:
        service = await PerceptionService.connect(perception_endpoint)
        service_info = await service.get_service_info()

        validation = await service.validate(workflow)

        session = await service.deploy(workflow)
        result_topic = session.topics.results
        if result_topic is None:
            raise AssertionError("deployed session did not expose a results topic")

        received: asyncio.Queue[Notification] = asyncio.Queue()
        async with await NotificationService.connect(messaging_endpoint) as notifications:
            await notifications.subscribe(result_topic, received.put)
            notification = await asyncio.wait_for(received.get(), timeout=30)
            result = PerceptionResult.decode(notification.payload)

            await session.stop()
            await asyncio.sleep(RESULT_ROUTER_SETTLE_SECONDS)
            while not received.empty():
                received.get_nowait()
            await assert_workflow_stops_publishing_results(
                received,
                timeout_seconds=STOPPED_RESULT_QUIESCENCE_SECONDS,
            )

        return (
            service_info,
            session,
            notification,
            result,
            result_topic,
            validation,
        )

    (
        service_info,
        session,
        notification,
        result,
        result_topic,
        validation,
    ) = asyncio.run(run())

    assert service_info.api_version == "v1"
    assert service_info.service_version
    assert session.id
    assert validation.valid
    assert not validation.errors
    assert session.workflow_name == "python-sdk-e2e"
    assert session.topics.events is None
    assert any(
        stage.name == "objects" and stage.model_id == "yolo26n-320"
        for stage in session.stages
    )
    assert notification.channel == result_topic
    assert notification.payload
    frame_contexts = [
        entry for entry in result.entries if isinstance(entry, FrameContext)
    ]
    assert frame_contexts
    assert all(entry.schema_major == 1 for entry in frame_contexts)


def test_python_sdk_lists_running_and_stopped_sessions(
    perception_stack: tuple[str, str],
) -> None:
    perception_endpoint, _ = perception_stack
    source = StreamConfiguration(
        "gstreamer-test-source",
        7,
        StreamFormat(Resolution(640, 480), "YUY2", FrameRate(30, 1)),
    )
    workflow = PerceptionWorkflow("python-sdk-list-sessions", source)
    workflow.infer("objects", "yolo26n-320")

    async def run() -> None:
        service = await PerceptionService.connect(perception_endpoint)
        assert await service.list_sessions() == []

        session = await service.deploy(workflow)
        try:
            listed = await service.list_sessions()
            assert [(item.id, item.workflow_name) for item in listed] == [
                (session.id, "python-sdk-list-sessions")
            ]
        finally:
            await session.stop()

        stopped = await service.list_sessions()
        assert [item.id for item in stopped] == [session.id]

    asyncio.run(run())


def test_python_sdk_gets_a_session_from_the_service(
    perception_stack: tuple[str, str],
) -> None:
    perception_endpoint, _ = perception_stack
    source = StreamConfiguration(
        "gstreamer-test-source",
        7,
        StreamFormat(Resolution(640, 480), "YUY2", FrameRate(30, 1)),
    )
    workflow = PerceptionWorkflow("python-sdk-get-session", source)
    workflow.infer("objects", "yolo26n-320")

    async def run() -> None:
        service = await PerceptionService.connect(perception_endpoint)
        session = await service.deploy(workflow)
        try:
            fetched = await service.get_session(session.id)
            assert fetched.id == session.id
            assert fetched.workflow_name == "python-sdk-get-session"
            assert any(
                stage.name == "objects" and stage.model_id == "yolo26n-320"
                for stage in fetched.stages
            )
        finally:
            await session.stop()

        stopped = await service.get_session(session.id)
        assert stopped.id == session.id

    asyncio.run(run())


def test_python_sdk_rejects_a_missing_session(
    perception_stack: tuple[str, str],
) -> None:
    perception_endpoint, _ = perception_stack

    async def run() -> None:
        service = await PerceptionService.connect(perception_endpoint)
        with pytest.raises(
            PerceptionError,
            match="NotFound: requested resource was not found",
        ):
            await service.get_session("missing-session")

    asyncio.run(run())


def test_python_sdk_controls_perception_stages(
    perception_stack: tuple[str, str],
) -> None:
    perception_endpoint, messaging_endpoint = perception_stack
    source = StreamConfiguration(
        "gstreamer-test-source",
        7,
        StreamFormat(Resolution(640, 480), "YUY2", FrameRate(30, 1)),
    )
    workflow = PerceptionWorkflow("python-sdk-stage-control-e2e", source, output_events=False)
    stage = workflow.infer("objects", "yolo26n-320")

    async def run() -> None:
        service = await PerceptionService.connect(perception_endpoint)
        session = await service.deploy(workflow)
        try:
            result_topic = session.topics.results
            if result_topic is None:
                raise AssertionError("deployed session did not expose a results topic")

            received: asyncio.Queue[Notification] = asyncio.Queue()
            async with NotificationService(messaging_endpoint) as notifications:
                await notifications.subscribe(result_topic, received.put)
                await asyncio.wait_for(received.get(), timeout=30)

                assert await session.disable_stage(stage.id) is None
                for control in (session.disable_stage, session.enable_stage):
                    with pytest.raises(PerceptionError):
                        await control("missing-stage")
                resolved_stage = next(item for item in session.stages if item.id == stage.id)
                assert resolved_stage.controllable
                assert await session.enable_stage(resolved_stage.id) is None
                while not received.empty():
                    received.get_nowait()
                await asyncio.wait_for(received.get(), timeout=30)
        finally:
            await session.stop()

    asyncio.run(run())


def test_python_sdk_reads_session_status_from_the_service(
    perception_stack: tuple[str, str],
) -> None:
    perception_endpoint, _ = perception_stack
    source = StreamConfiguration(
        "gstreamer-test-source",
        7,
        StreamFormat(Resolution(640, 480), "YUY2", FrameRate(30, 1)),
    )
    workflow = PerceptionWorkflow("python-sdk-session-status", source)
    workflow.infer("objects", "yolo26n-320")

    async def run() -> None:
        service = await PerceptionService.connect(perception_endpoint)
        session = await service.deploy(workflow)
        try:
            running = await session.get_status()
            assert running.status.state in (
                SessionState.Starting,
                SessionState.Running,
            )
            assert running.disabled_stage_ids == []
        finally:
            await session.stop()

        stopped = await session.get_status()
        assert stopped.status.state == SessionState.Stopped

    asyncio.run(run())


def test_python_sdk_get_and_list_handles_share_session_snapshot(
    perception_stack: tuple[str, str],
) -> None:
    perception_endpoint, _ = perception_stack
    source = StreamConfiguration(
        "gstreamer-test-source",
        7,
        StreamFormat(Resolution(640, 480), "YUY2", FrameRate(30, 1)),
    )
    workflow = PerceptionWorkflow("python-sdk-shared-snapshot", source)
    workflow.infer("objects", "yolo26n-320")

    async def run() -> None:
        service = await PerceptionService.connect(perception_endpoint)
        session = await service.deploy(workflow)
        try:
            fetched = await service.get_session(session.id)
            listed = next(
                handle
                for handle in await service.list_sessions()
                if handle.id == session.id
            )
        finally:
            await session.stop()

        fetched_snapshot = await fetched.get_status()
        listed_snapshot = await listed.get_status()

        fetched_info = fetched_snapshot.status.info
        listed_info = listed_snapshot.status.info
        assert (
            fetched_snapshot.status.state,
            fetched_info.code if fetched_info else None,
            fetched_info.message if fetched_info else None,
            fetched_snapshot.disabled_stage_ids,
        ) == (
            listed_snapshot.status.state,
            listed_info.code if listed_info else None,
            listed_info.message if listed_info else None,
            listed_snapshot.disabled_stage_ids,
        )

    asyncio.run(run())


def test_python_sdk_fails_to_deploy_a_broken_workflow(
    perception_stack: tuple[str, str],
) -> None:
    perception_endpoint, _ = perception_stack
    source = StreamConfiguration(
        "gstreamer-test-source",
        7,
        StreamFormat(Resolution(640, 480), "YUY2", FrameRate(30, 1)),
    )
    workflow = PerceptionWorkflow("not-a-real-workflow", source)

    async def run() -> tuple[ValidationResult, DeploymentValidationError]:
        service = await PerceptionService.connect(perception_endpoint)
        validation = await service.validate(workflow)

        with pytest.raises(DeploymentValidationError) as error:
            await service.deploy(workflow)

        return validation, error.value

    validation, error = asyncio.run(run())

    # service.validate should return errors
    expected_issues = [
        (
            "INFERENCE_STAGE_REQUIRED",
            "workflow must define at least one inference stage",
            "stages",
            None,
        )
    ]
    assert not validation.valid
    assert [
        (issue.code, issue.message, issue.field_path, issue.stage_id)
        for issue in validation.errors
    ] == expected_issues

    # and deployment should raise.
    assert [
        (issue.code, issue.message, issue.field_path, issue.stage_id)
        for issue in error.issues
    ] == expected_issues


async def assert_workflow_stops_publishing_results(
    queue: asyncio.Queue[Notification],
    *,
    timeout_seconds: float,
) -> None:
    try:
        unexpected_notification = await asyncio.wait_for(
            queue.get(),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        return

    raise AssertionError(
        "workflow continued publishing results after session.stop(): "
        f"{unexpected_notification.channel}"
    )


@pytest.fixture
def perception_stack(
    request: pytest.FixtureRequest,
) -> Iterator[tuple[str, str]]:
    try:
        compose(
            "up",
            "--build",
            "--detach",
            "--wait",
            "--wait-timeout",
            "180",
            "messaging-service",
            "perception-service",
        )
        yield (
            f"http://{published_address('perception-service', 50053)}",
            f"http://{published_address('messaging-service', 50054)}",
        )
    except BaseException as error:
        print_compose_logs()
        message = getattr(error, "stderr", None) or getattr(error, "stdout", None)
        if message:
            raise RuntimeError(message) from error
        raise
    finally:
        test_call_failed = bool(
            getattr(request.node, "_cairn_test_call_failed", False)
        )
        if test_call_failed:
            print_compose_logs()
        cleanup = subprocess.run(
            [*COMPOSE_COMMAND, "down", "--volumes", "--remove-orphans"],
            cwd=PERCEPTION_ROOT,
            env=COMPOSE_ENVIRONMENT,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if (
            cleanup.returncode
            and not test_call_failed
            and sys.exception() is None
        ):
            raise RuntimeError(cleanup.stderr)
        if cleanup.returncode:
            print(f"\n=== Docker Compose cleanup failed ===\n{cleanup.stderr}")


def print_compose_logs() -> None:
    try:
        print(
            "\n=== Python SDK E2E Compose logs ===\n"
            + compose("logs", "--no-color").stdout
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(f"\n=== Failed to collect Compose logs ===\n{error}")


def compose(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*COMPOSE_COMMAND, *arguments],
        cwd=PERCEPTION_ROOT,
        env=COMPOSE_ENVIRONMENT,
        check=True,
        capture_output=True,
        text=True,
        timeout=1800,
    )


def published_address(service: str, container_port: int) -> str:
    address = compose("port", service, str(container_port)).stdout.strip()
    host, separator, port = address.rpartition(":")
    if not separator or not host or not port.isdecimal():
        raise RuntimeError(f"Docker Compose returned an invalid address: {address}")
    return f"{host}:{port}"
