# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from concurrent.futures import Future
from threading import Event, Thread
from time import sleep

import pytest

from perception_service.gstreamer.dispatcher import wait_for_command
from perception_service.gstreamer.errors import DispatcherUnavailableError

pytestmark = pytest.mark.unit


def test_wait_for_command_returns_completed_result() -> None:
    completion: Future[str] = Future()
    completion.set_result("created")

    result = wait_for_command(
        completion,
        operation="create pipeline",
        command_queue_timeout_seconds=0.01,
    )

    assert result == "created"


def test_wait_for_command_propagates_command_error() -> None:
    completion: Future[None] = Future()
    completion.set_exception(ValueError("invalid pipeline"))

    with pytest.raises(ValueError, match="invalid pipeline"):
        wait_for_command(
            completion,
            operation="create pipeline",
            command_queue_timeout_seconds=0.01,
        )


def test_wait_for_command_cancels_queued_command_after_timeout() -> None:
    completion: Future[None] = Future()

    with pytest.raises(DispatcherUnavailableError, match="before the task dispatcher"):
        wait_for_command(
            completion,
            operation="create pipeline",
            command_queue_timeout_seconds=0.001,
        )

    assert completion.cancelled()


def test_wait_for_command_waits_for_started_command() -> None:
    completion: Future[str] = Future()
    command_started = Event()

    def complete_command() -> None:
        if completion.set_running_or_notify_cancel():
            command_started.set()
            sleep(0.005)
            completion.set_result("playing")

    worker = Thread(target=complete_command)
    worker.start()
    assert command_started.wait(timeout=1)

    result = wait_for_command(
        completion,
        operation="create pipeline",
        command_queue_timeout_seconds=0.001,
    )
    worker.join(timeout=1)

    assert result == "playing"
    assert not worker.is_alive()
