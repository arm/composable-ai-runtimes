# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event, Thread, current_thread

import pytest

from perception_service.gstreamer.glib_dispatcher import GLibTaskDispatcher
from perception_service.gstreamer.errors import (
    DispatcherUnavailableError,
    DispatcherUsageError,
)

pytestmark = pytest.mark.integration


def test_dispatcher_readiness_tracks_lifecycle() -> None:
    dispatcher = GLibTaskDispatcher(command_queue_timeout_seconds=1)
    try:
        assert dispatcher.is_ready()
    finally:
        dispatcher.close()

    assert not dispatcher.is_ready()


def test_dispatcher_executes_tasks_on_its_worker_thread() -> None:
    dispatcher = GLibTaskDispatcher(command_queue_timeout_seconds=1)
    try:
        worker_thread = dispatcher.execute(
            "inspect worker thread",
            current_thread,
        )
    finally:
        dispatcher.close()

    assert worker_thread is not current_thread()


def test_dispatcher_rejects_tasks_after_closure() -> None:
    dispatcher = GLibTaskDispatcher(command_queue_timeout_seconds=1)
    dispatcher.close()

    with pytest.raises(DispatcherUnavailableError, match="closing or closed"):
        dispatcher.execute(
            "inspect worker thread",
            current_thread,
        )


def test_dispatcher_rejects_a_second_live_instance() -> None:
    dispatcher = GLibTaskDispatcher(command_queue_timeout_seconds=1)

    try:
        with pytest.raises(DispatcherUsageError, match="already running"):
            GLibTaskDispatcher(command_queue_timeout_seconds=1)
    finally:
        dispatcher.close()


def test_dispatcher_allows_a_replacement_after_closure() -> None:
    dispatcher = GLibTaskDispatcher(command_queue_timeout_seconds=1)
    dispatcher.close()

    replacement = GLibTaskDispatcher(command_queue_timeout_seconds=1)
    try:
        worker_thread = replacement.execute(
            "inspect worker thread",
            current_thread,
        )
    finally:
        replacement.close()

    assert worker_thread is not current_thread()


def test_dispatcher_close_can_be_retried_after_a_running_task_finishes() -> None:
    task_started = Event()
    allow_task_to_finish = Event()
    task_completion: Future[None] = Future()
    dispatcher = GLibTaskDispatcher(command_queue_timeout_seconds=0.01)

    def block_until_released() -> None:
        task_started.set()
        allow_task_to_finish.wait(timeout=1)

    def run_blocking_task() -> None:
        try:
            dispatcher.execute(
                "run blocking task",
                block_until_released,
            )
        except Exception as error:
            task_completion.set_exception(error)
        else:
            task_completion.set_result(None)

    worker = Thread(target=run_blocking_task)
    worker.start()
    try:
        assert task_started.wait(timeout=1)
        with pytest.raises(RuntimeError, match="could not begin shutdown"):
            dispatcher.close()

        allow_task_to_finish.set()
        worker.join(timeout=1)
        task_completion.result()
        dispatcher.close()
    finally:
        allow_task_to_finish.set()
        worker.join(timeout=1)
        dispatcher.close()

    assert not worker.is_alive()


def test_dispatcher_executes_many_concurrent_tasks() -> None:
    dispatcher = GLibTaskDispatcher(command_queue_timeout_seconds=5)

    def dispatch(value: int) -> int:
        return dispatcher.execute("return value", lambda: value)

    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(dispatch, range(32)))
    finally:
        dispatcher.close()

    assert results == list(range(32))
