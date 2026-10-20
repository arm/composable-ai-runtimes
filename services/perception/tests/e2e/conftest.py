# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import os
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

import grpc
import pytest
from grpc_health.v1 import health_pb2_grpc

from cairn.perception.v1 import perception_pb2_grpc

READINESS_TIMEOUT_SECONDS = 30
PERCEPTION_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_COMMAND = (
    "docker",
    "compose",
    "-f",
    "compose.yaml",
    "-f",
    "tests/e2e/compose.yaml",
)


def compose_command(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*COMPOSE_COMMAND, *arguments],
        cwd=PERCEPTION_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def compose_service_address(service: str, container_port: int) -> tuple[str, int]:
    address = compose_command(
        "port", service, str(container_port)
    ).stdout.strip()
    host, separator, port = address.rpartition(":")
    if not separator or not host or not port.isdecimal():
        raise RuntimeError(
            f"Docker Compose did not report a valid host address for port {container_port}"
        )
    return host, int(port)


@pytest.fixture(scope="session")
def e2e_compose_command() -> Callable[..., subprocess.CompletedProcess[str]]:
    return compose_command


@pytest.fixture
def e2e_grpc_address(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[str]:
    if getattr(request, "param", None) == "empty-models":
        tmp_path.chmod(0o755)
        monkeypatch.setenv("PERCEPTION_E2E_MODELS", str(tmp_path))
    os.environ.setdefault("COMPOSE_PROJECT_NAME", f"perception-e2e-{os.getpid()}")
    try:
        try:
            compose_command(
                "up",
                "--build",
                "--detach",
                "messaging-service",
                "perception-service",
            )
        except subprocess.CalledProcessError as error:
            raise RuntimeError(error.stderr) from error
        grpc_host, grpc_port = compose_service_address("perception-service", 50053)
        yield f"{grpc_host}:{grpc_port}"
    finally:
        if request.session.testsfailed:
            try:
                logs = compose_command("logs", "--no-color").stdout
                print("\n=== Perception E2E Compose logs ===\n" + logs)
            except subprocess.CalledProcessError as error:
                print(
                    "\n=== Failed to collect Perception E2E Compose logs ===\n"
                    + error.stderr
                )
        try:
            compose_command("down", "--volumes", "--remove-orphans")
        except subprocess.CalledProcessError as error:
            if not request.session.testsfailed:
                raise RuntimeError(error.stderr) from error


@pytest.fixture
def e2e_redis_url(e2e_grpc_address: str) -> Callable[[], str]:
    def current_url() -> str:
        host, port = compose_service_address("messaging-service", 6379)
        return f"redis://{host}:{port}/0"

    return current_url


@pytest.fixture
def e2e_channel(
    e2e_grpc_address: str,
) -> Iterator[grpc.Channel]:
    grpc_address = e2e_grpc_address

    channel = grpc.insecure_channel(grpc_address)
    try:
        try:
            grpc.channel_ready_future(channel).result(timeout=READINESS_TIMEOUT_SECONDS)
        except grpc.FutureTimeoutError as error:
            raise TimeoutError(
                f"Timed out waiting {READINESS_TIMEOUT_SECONDS} seconds for "
                f"the Perception gRPC service at {grpc_address}"
            ) from error

        yield channel
    finally:
        channel.close()


@pytest.fixture
def e2e_perception_stub(
    e2e_channel: grpc.Channel,
) -> perception_pb2_grpc.PerceptionServiceStub:
    return perception_pb2_grpc.PerceptionServiceStub(e2e_channel)


@pytest.fixture
def e2e_health_stub(e2e_channel: grpc.Channel) -> health_pb2_grpc.HealthStub:
    return health_pb2_grpc.HealthStub(e2e_channel)
