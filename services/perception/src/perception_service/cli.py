# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import argparse
from collections.abc import Sequence
from math import isfinite
from pathlib import Path

from perception_service.opk.config import (
    DEFAULT_OPK_COMM_HOST,
    DEFAULT_OPK_COMM_PORT,
    OpkCommEndpoint,
)


def optional_path(value: str) -> Path | None:
    return Path(value) if value else None


def opk_comm_host(value: str) -> str:
    try:
        return OpkCommEndpoint(host=value).host
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def tcp_port(value: str) -> int:
    try:
        return OpkCommEndpoint(port=int(value)).port
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive number") from error
    if not isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive number")
    return parsed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Perception gRPC service")
    parser.add_argument("--host", default="0.0.0.0", help="host interface to bind")
    parser.add_argument("--port", type=int, default=50053, help="port to bind")
    parser.add_argument(
        "--model-path",
        action="append",
        type=Path,
        help="model package or parent directory; may be supplied more than once",
    )
    parser.add_argument(
        "--model-schema-path",
        type=optional_path,
        help=(
            "OPK JSON schema directory used to validate model packages; "
            "omit or pass an empty value to skip JSON Schema validation"
        ),
    )
    parser.add_argument(
        "--opk-comm-host",
        type=opk_comm_host,
        default=DEFAULT_OPK_COMM_HOST,
        help="host used to consume the internal opkcomm WebSocket stream",
    )
    parser.add_argument(
        "--opk-comm-first-port",
        type=tcp_port,
        default=DEFAULT_OPK_COMM_PORT,
        help="first port in the internal opkcomm WebSocket range",
    )
    parser.add_argument(
        "--redis-url",
        default="redis://messaging-service:6379/0",
        help="Redis endpoint for event publication",
    )
    parser.add_argument(
        "--redis-queue-size",
        type=positive_int,
        default=64,
        help="maximum number of pending messages per event queue",
    )
    parser.add_argument(
        "--redis-timeout",
        type=positive_float,
        default=1.0,
        help="Redis connect and socket timeout in seconds",
    )
    return parser.parse_args(argv)
