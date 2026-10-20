# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import pytest

from perception_service.readiness import ReadinessController, ReadinessSnapshot

pytestmark = pytest.mark.unit


class RuntimeReadinessStub:
    def __init__(self) -> None:
        self.ready = True

    def is_ready(self) -> bool:
        return self.ready


def test_readiness_lifecycle_tracks_failure_and_recovery() -> None:
    runtime = RuntimeReadinessStub()
    controller = ReadinessController(runtime)

    assert controller.snapshot() == ReadinessSnapshot(
        api=False,
        gstreamer=False,
    )

    assert controller.set_api_ready() == ReadinessSnapshot(
        api=True,
        gstreamer=False,
    )
    assert controller.refresh_runtime() == ReadinessSnapshot(
        api=True,
        gstreamer=True,
    )

    runtime.ready = False
    assert controller.refresh_runtime() == ReadinessSnapshot(
        api=True,
        gstreamer=False,
    )

    runtime.ready = True
    assert controller.refresh_runtime() == ReadinessSnapshot(
        api=True,
        gstreamer=True,
    )


def test_shutdown_is_permanent() -> None:
    runtime = RuntimeReadinessStub()
    controller = ReadinessController(runtime)
    controller.set_api_ready()
    controller.refresh_runtime()

    assert controller.begin_shutdown() == ReadinessSnapshot(
        api=False,
        gstreamer=False,
    )
    assert controller.set_api_ready() == ReadinessSnapshot(
        api=False,
        gstreamer=False,
    )
    assert controller.refresh_runtime() == ReadinessSnapshot(
        api=False,
        gstreamer=False,
    )
