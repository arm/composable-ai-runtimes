# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0


class ServiceError(Exception):
    """Base class for failures exposed at a service transport boundary."""


class ResourceExhaustedError(ServiceError):
    """The service has insufficient capacity for the requested operation."""


class NotFoundError(ServiceError):
    """A resource named by the request does not exist."""


class FailedPreconditionError(ServiceError):
    """The resource exists but cannot perform the requested operation."""


class UnavailableError(ServiceError):
    """A runtime dependency is temporarily unable to serve the request."""


class InternalError(ServiceError):
    """A known operation failed for an unexpected internal reason."""
