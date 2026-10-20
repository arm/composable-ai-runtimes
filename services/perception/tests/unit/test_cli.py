# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest

from perception_service.cli import parse_args

pytestmark = pytest.mark.unit


def test_parse_args_uses_local_service_defaults() -> None:
    args = parse_args([])

    assert args.host == "0.0.0.0"
    assert args.port == 50053
    assert args.model_path is None
    assert args.model_schema_path is None
    assert args.opk_comm_host == "127.0.0.1"
    assert args.opk_comm_first_port == 7001
    assert args.redis_url == "redis://messaging-service:6379/0"
    assert args.redis_queue_size == 64
    assert args.redis_timeout == 1.0


def test_parse_args_accepts_repeated_model_paths() -> None:
    args = parse_args(
        [
            "--model-path",
            "/models/parent",
            "--model-path",
            "/models/direct-model",
        ]
    )

    assert args.model_path == [
        Path("/models/parent"),
        Path("/models/direct-model"),
    ]


def test_parse_args_accepts_model_schema_path() -> None:
    args = parse_args(
        [
            "--model-schema-path",
            "/schemas",
        ]
    )

    assert args.model_schema_path == Path("/schemas")


def test_parse_args_accepts_empty_model_schema_path() -> None:
    args = parse_args(["--model-schema-path", ""])

    assert args.model_schema_path is None


def test_parse_args_accepts_opkcomm_range_start() -> None:
    args = parse_args(
        [
            "--opk-comm-host",
            "127.0.0.2",
            "--opk-comm-first-port",
            "7002",
        ]
    )

    assert args.opk_comm_host == "127.0.0.2"
    assert args.opk_comm_first_port == 7002


@pytest.mark.parametrize("port", ["not-a-port", "0", "65536"])
def test_parse_args_rejects_invalid_opkcomm_port(port: str) -> None:
    with pytest.raises(SystemExit):
        parse_args(["--opk-comm-first-port", port])


def test_parse_args_accepts_redis_overrides() -> None:
    args = parse_args(
        [
            "--redis-url",
            "redis://127.0.0.1:6379/1",
            "--redis-queue-size",
            "8",
            "--redis-timeout",
            "2.5",
        ]
    )

    assert args.redis_url == "redis://127.0.0.1:6379/1"
    assert args.redis_queue_size == 8
    assert args.redis_timeout == 2.5


@pytest.mark.parametrize("queue_size", ["not-a-number", "0", "-1"])
def test_parse_args_rejects_invalid_redis_queue_size(queue_size: str) -> None:
    with pytest.raises(SystemExit):
        parse_args(["--redis-queue-size", queue_size])


@pytest.mark.parametrize("timeout", ["not-a-number", "0", "-1", "nan", "inf"])
def test_parse_args_rejects_invalid_redis_timeout(timeout: str) -> None:
    with pytest.raises(SystemExit):
        parse_args(["--redis-timeout", timeout])
