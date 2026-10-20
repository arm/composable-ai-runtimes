# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Callable
from concurrent.futures import Future, wait
from enum import Enum, auto
from threading import Event, Lock, Thread, current_thread
from typing import ClassVar, Final

import gi
from loguru import logger

gi.require_version("GLib", "2.0")
from gi.repository import GLib  # noqa: E402

from perception_service.gstreamer.dispatcher import wait_for_command  # noqa: E402
from perception_service.gstreamer.errors import (  # noqa: E402
    DispatcherUnavailableError,
    DispatcherUsageError,
)

COMMAND_QUEUE_TIMEOUT_SECONDS: Final = 10


class DispatcherState(Enum):
    RUNNING = auto()
    CLOSING = auto()
    CLOSED = auto()


class GLibTaskDispatcher:
    _active_dispatcher: ClassVar["GLibTaskDispatcher | None"] = None
    _active_dispatcher_lock: ClassVar[Lock] = Lock()

    def __init__(
        self,
        command_queue_timeout_seconds: float = COMMAND_QUEUE_TIMEOUT_SECONDS,
    ) -> None:
        if command_queue_timeout_seconds <= 0:
            raise ValueError("command queue timeout must be positive")

        self._context = GLib.MainContext.new()
        self._loop = GLib.MainLoop.new(self._context, False)
        self._command_queue_timeout_seconds = command_queue_timeout_seconds
        self._started = Event()
        self._close_completion: Future[None] | None = None
        self._state = DispatcherState.RUNNING
        self._state_lock = Lock()
        self._command_lock = Lock()
        self._thread = Thread(
            target=self._run,
            name="gstreamer-dispatcher",
            daemon=True,
        )

        self._claim_active_dispatcher()
        try:
            self._thread.start()
        except Exception:
            self._release_active_dispatcher()
            raise

        if not self._started.wait(timeout=command_queue_timeout_seconds):
            self._release_active_dispatcher()
            raise RuntimeError("GLib dispatcher thread failed to start")
        logger.info("GLib task dispatcher started")

    def execute[T](
        self,
        operation: str,
        callback: Callable[[], T],
    ) -> T:
        self._ensure_external_caller()
        self._ensure_running()
        if not self._command_lock.acquire(timeout=self._command_queue_timeout_seconds):
            raise DispatcherUnavailableError(f"timed out waiting to {operation}")
        try:
            self._ensure_running()
            completion: Future[T] = Future()
            self._schedule(lambda: self._run_task(callback, completion))
            return wait_for_command(
                completion,
                operation,
                self._command_queue_timeout_seconds,
            )
        finally:
            self._command_lock.release()

    def is_ready(self) -> bool:
        with self._state_lock:
            return self._state == DispatcherState.RUNNING and self._thread.is_alive()

    def close(self) -> None:
        self._ensure_external_caller()
        with self._state_lock:
            if self._state == DispatcherState.CLOSED:
                self._release_active_dispatcher()
                return
            if self._state == DispatcherState.CLOSING:
                completion = self._close_completion
                owns_close = False
            else:
                self._state = DispatcherState.CLOSING
                completion = Future()
                self._close_completion = completion
                owns_close = True

        assert completion is not None
        if owns_close:
            self._run_close_attempt(completion)

        done, _ = wait(
            (completion,),
            timeout=self._command_queue_timeout_seconds,
        )
        if not done:
            raise RuntimeError("GLib dispatcher failed to finish shutdown")
        completion.result()

        self._thread.join(timeout=self._command_queue_timeout_seconds)
        if self._thread.is_alive():
            raise RuntimeError("GLib dispatcher thread failed to stop")
        self._release_active_dispatcher()
        logger.info("GLib task dispatcher stopped")

    def _run(self) -> None:
        self._context.push_thread_default()
        self._started.set()
        try:
            self._loop.run()
        finally:
            self._context.pop_thread_default()
            with self._state_lock:
                self._state = DispatcherState.CLOSED

    def _run_task[T](
        self,
        callback: Callable[[], T],
        completion: Future[T],
    ) -> bool:
        if not completion.set_running_or_notify_cancel():
            return GLib.SOURCE_REMOVE

        try:
            completion.set_result(callback())
        except Exception as error:
            completion.set_exception(error)

        return GLib.SOURCE_REMOVE

    def _run_close_attempt(
        self,
        completion: Future[None],
    ) -> None:
        if not self._command_lock.acquire(timeout=self._command_queue_timeout_seconds):
            error = RuntimeError("GLib dispatcher could not begin shutdown")
            completion.set_exception(error)
            self._finish_failed_close()
            return

        try:
            self._schedule(lambda: self._quit(completion))
        except Exception as error:
            completion.set_exception(error)
            self._finish_failed_close()
        finally:
            self._command_lock.release()

    def _quit(self, completion: Future[None]) -> bool:
        if completion.set_running_or_notify_cancel():
            completion.set_result(None)
            self._loop.quit()
        return GLib.SOURCE_REMOVE

    def _finish_failed_close(self) -> None:
        with self._state_lock:
            if self._state == DispatcherState.CLOSING:
                self._state = DispatcherState.RUNNING
                self._close_completion = None

    def _schedule(self, callback: Callable[[], bool]) -> None:
        source = GLib.idle_source_new()
        source.set_callback(callback)
        source.attach(self._context)

    def _ensure_running(self) -> None:
        with self._state_lock:
            if self._state != DispatcherState.RUNNING:
                raise DispatcherUnavailableError("GLib dispatcher is closing or closed")

    def _ensure_external_caller(self) -> None:
        if current_thread() is self._thread:
            raise DispatcherUsageError(
                "cannot wait for a dispatcher command on the GLib thread"
            )

    def _claim_active_dispatcher(self) -> None:
        with self._active_dispatcher_lock:
            if self._active_dispatcher is not None:
                raise DispatcherUsageError("a GLib task dispatcher is already running")
            self.__class__._active_dispatcher = self

    def _release_active_dispatcher(self) -> None:
        with self._active_dispatcher_lock:
            if self._active_dispatcher is self:
                self.__class__._active_dispatcher = None
