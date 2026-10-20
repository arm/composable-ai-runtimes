# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from perception_service.errors import InternalError, UnavailableError


class PipelineError(UnavailableError):
    pass


class RuntimeUnavailableError(UnavailableError):
    pass


class DispatcherUnavailableError(UnavailableError):
    pass


class DispatcherUsageError(InternalError):
    pass
