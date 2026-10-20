# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import MagicMock

import grpc
import pytest

from perception_service.errors import (
    FailedPreconditionError,
    InternalError,
    NotFoundError,
    ResourceExhaustedError,
    ServiceError,
    UnavailableError,
)
from perception_service.rpc import handle_rpc_errors

pytestmark = pytest.mark.unit


class ConcreteCapacityError(ResourceExhaustedError):
    pass


@pytest.mark.parametrize(
    ("service_error", "expected_code", "expected_details"),
    [
        (
            # A concrete subclass verifies that subsystem errors inherit their
            # category mapping without registration at the RPC boundary.
            ConcreteCapacityError("capacity details"),
            grpc.StatusCode.RESOURCE_EXHAUSTED,
            "service capacity is exhausted",
        ),
        (
            NotFoundError("lookup details"),
            grpc.StatusCode.NOT_FOUND,
            "requested resource was not found",
        ),
        (
            FailedPreconditionError("state details"),
            grpc.StatusCode.FAILED_PRECONDITION,
            "request cannot be applied to the resource",
        ),
        (
            UnavailableError("dependency details"),
            grpc.StatusCode.UNAVAILABLE,
            "runtime dependency is unavailable",
        ),
        (
            InternalError("private internal details"),
            grpc.StatusCode.INTERNAL,
            "internal server error",
        ),
    ],
)
def test_handle_rpc_errors_maps_service_errors(
    service_error: ServiceError,
    expected_code: grpc.StatusCode,
    expected_details: str,
) -> None:
    context = MagicMock(spec=grpc.ServicerContext)
    abort_error = RuntimeError("RPC aborted")
    context.abort.side_effect = abort_error

    @handle_rpc_errors
    def handler(
        _service: object,
        _request: object,
        _context: grpc.ServicerContext,
    ) -> object:
        raise service_error

    with pytest.raises(RuntimeError) as raised:
        handler(object(), object(), context)

    assert raised.value is abort_error
    context.abort.assert_called_once_with(expected_code, expected_details)
    assert str(service_error) not in expected_details


def test_handle_rpc_errors_maps_unexpected_error_to_internal() -> None:
    context = MagicMock(spec=grpc.ServicerContext)
    context.abort.side_effect = RuntimeError("RPC aborted")

    @handle_rpc_errors
    def handler(
        _service: object,
        _request: object,
        _context: grpc.ServicerContext,
    ) -> object:
        raise ValueError("private internal details")

    with pytest.raises(RuntimeError, match="RPC aborted"):
        handler(object(), object(), context)

    context.abort.assert_called_once_with(
        grpc.StatusCode.INTERNAL,
        "internal server error",
    )


def test_handle_rpc_errors_rejects_unmapped_service_error() -> None:
    class UnmappedServiceError(ServiceError):
        pass

    context = MagicMock(spec=grpc.ServicerContext)
    context.abort.side_effect = RuntimeError("RPC aborted")

    @handle_rpc_errors
    def handler(
        _service: object,
        _request: object,
        _context: grpc.ServicerContext,
    ) -> object:
        raise UnmappedServiceError("private internal details")

    with pytest.raises(RuntimeError, match="RPC aborted"):
        handler(object(), object(), context)

    context.abort.assert_called_once_with(
        grpc.StatusCode.INTERNAL,
        "internal server error",
    )
