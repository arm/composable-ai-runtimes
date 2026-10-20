# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from threading import Lock
from typing import Protocol


class RuntimeReadiness(Protocol):
    def is_ready(self) -> bool: ...


@dataclass(frozen=True)
class ReadinessSnapshot:
    api: bool
    gstreamer: bool

    @property
    def aggregate(self) -> bool:
        return self.api and self.gstreamer


class ReadinessController:
    def __init__(self, runtime: RuntimeReadiness) -> None:
        self._runtime = runtime
        self._api_ready = False
        self._gstreamer_ready = False
        self._shutting_down = False
        self._lock = Lock()

    def set_api_ready(self) -> ReadinessSnapshot:
        with self._lock:
            if not self._shutting_down:
                self._api_ready = True
            return self._snapshot()

    def refresh_runtime(self) -> ReadinessSnapshot:
        runtime_ready = self._runtime.is_ready()
        with self._lock:
            if not self._shutting_down:
                self._gstreamer_ready = runtime_ready
            return self._snapshot()

    def begin_shutdown(self) -> ReadinessSnapshot:
        with self._lock:
            self._shutting_down = True
            self._api_ready = False
            self._gstreamer_ready = False
            return self._snapshot()

    def snapshot(self) -> ReadinessSnapshot:
        with self._lock:
            return self._snapshot()

    def _snapshot(self) -> ReadinessSnapshot:
        return ReadinessSnapshot(
            api=self._api_ready,
            gstreamer=self._gstreamer_ready,
        )
