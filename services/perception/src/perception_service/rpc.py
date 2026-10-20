# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Callable
from functools import wraps
from typing import Never, TypeVar

import grpc
from loguru import logger

from perception_service.errors import (
    FailedPreconditionError,
    InternalError,
    NotFoundError,
    ResourceExhaustedError,
    ServiceError,
    UnavailableError,
)

ServiceT = TypeVar("ServiceT")
RequestT = TypeVar("RequestT")
ResponseT = TypeVar("ResponseT")

_ERROR_RESPONSES: tuple[
    tuple[type[ServiceError], grpc.StatusCode, str],
    ...,
] = (
    (
        ResourceExhaustedError,
        grpc.StatusCode.RESOURCE_EXHAUSTED,
        "service capacity is exhausted",
    ),
    (
        NotFoundError,
        grpc.StatusCode.NOT_FOUND,
        "requested resource was not found",
    ),
    (
        FailedPreconditionError,
        grpc.StatusCode.FAILED_PRECONDITION,
        "request cannot be applied to the resource",
    ),
    (
        UnavailableError,
        grpc.StatusCode.UNAVAILABLE,
        "runtime dependency is unavailable",
    ),
    (
        InternalError,
        grpc.StatusCode.INTERNAL,
        "internal server error",
    ),
)


def handle_rpc_errors(
    method: Callable[[ServiceT, RequestT, grpc.ServicerContext], ResponseT],
) -> Callable[[ServiceT, RequestT, grpc.ServicerContext], ResponseT]:
    """Translate service exceptions to safe gRPC errors at the RPC boundary."""

    method_name = getattr(method, "__name__", type(method).__name__)

    @wraps(method)
    def wrapped(
        service: ServiceT,
        request: RequestT,
        context: grpc.ServicerContext,
    ) -> ResponseT:
        try:
            return method(service, request, context)
        except ServiceError as error:
            response = next(
                (
                    (code, details)
                    for error_type, code, details in _ERROR_RESPONSES
                    if isinstance(error, error_type)
                ),
                None,
            )
            if response is None:
                logger.opt(exception=True).error(
                    "Unmapped service error in RPC {}",
                    method_name,
                )
                _abort_rpc(
                    context,
                    grpc.StatusCode.INTERNAL,
                    "internal server error",
                )

            code, details = response
            if code in {grpc.StatusCode.INTERNAL, grpc.StatusCode.UNAVAILABLE}:
                logger.opt(exception=True).error(
                    "RPC {} failed: {}",
                    method_name,
                    error,
                )
            else:
                logger.warning(
                    "RPC {} rejected: {}",
                    method_name,
                    error,
                )
            _abort_rpc(context, code, details)
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected failure in RPC {}", method_name)
            _abort_rpc(
                context,
                grpc.StatusCode.INTERNAL,
                "internal server error",
            )

    return wrapped


def _abort_rpc(
    context: grpc.ServicerContext,
    code: grpc.StatusCode,
    details: str,
) -> Never:
    context.abort(code, details)
    raise AssertionError("gRPC context.abort unexpectedly returned")
