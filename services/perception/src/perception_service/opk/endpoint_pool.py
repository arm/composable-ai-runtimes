# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import threading
from types import TracebackType

from perception_service.errors import InternalError, ResourceExhaustedError
from perception_service.opk.config import OpkCommEndpoint


class OpkCommEndpointLease:
    def __init__(
        self,
        pool: OpkCommEndpointPool,
        endpoint: OpkCommEndpoint,
    ) -> None:
        self._pool = pool
        self.endpoint = endpoint
        self._claimed = False
        self._released = False

    def claim(self) -> None:
        if self._claimed or self._released:
            raise InternalError("opkcomm endpoint lease is no longer available")
        self._claimed = True

    def release(self) -> None:
        if self._released:
            return
        self._pool._release(self.endpoint)
        self._released = True

    def __enter__(self) -> OpkCommEndpointLease:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not self._claimed:
            self.release()


class OpkCommEndpointPool:
    def __init__(self, first_endpoint: OpkCommEndpoint, size: int) -> None:
        if size < 1:
            raise ValueError("opkcomm endpoint pool size must be positive")
        if first_endpoint.port + size - 1 > 65535:
            raise ValueError("opkcomm port range exceeds 65535")
        self._first_endpoint = first_endpoint
        self._size = size
        self._lock = threading.Lock()
        self._reserved_ports: set[int] = set()

    def reserve(self) -> OpkCommEndpointLease:
        with self._lock:
            for port in range(
                self._first_endpoint.port,
                self._first_endpoint.port + self._size,
            ):
                if port not in self._reserved_ports:
                    self._reserved_ports.add(port)
                    return OpkCommEndpointLease(
                        self,
                        OpkCommEndpoint(self._first_endpoint.host, port),
                    )
        raise ResourceExhaustedError("all opkcomm result connections are in use")

    def _release(self, endpoint: OpkCommEndpoint) -> None:
        with self._lock:
            self._reserved_ports.discard(endpoint.port)
