# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from enum import Enum, auto
from threading import Lock
from time import monotonic
from typing import Callable, Final

import gi
from loguru import logger

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

from perception_service.gstreamer.glib_dispatcher import (  # noqa: E402
    GLibTaskDispatcher,
)
from perception_service.errors import (  # noqa: E402
    FailedPreconditionError,
    InternalError,
    NotFoundError,
    ResourceExhaustedError,
)
from perception_service.gstreamer.errors import (  # noqa: E402
    PipelineError,
    RuntimeUnavailableError,
)
from perception_service.gstreamer.runtime_policy import validate_runtime_limits  # noqa: E402
from perception_service.pipeline_types import (  # noqa: E402
    PipelineEventSink,
    RuntimePipelineEvent,
    RuntimePipelineEventKind,
)

STATE_CHANGE_TIMEOUT_SECONDS: Final = 5
MAX_PIPELINES: Final = 16


@dataclass
class ManagedPipeline:
    pipeline: Gst.Pipeline
    bus: Gst.Bus
    session_id: str
    event_sink: PipelineEventSink
    signal_watch_added: bool = False
    bus_handler_id: int | None = None
    null_state_confirmed: bool = False

    def emit_event(
        self,
        kind: RuntimePipelineEventKind,
        message: str | None = None,
        source_name: str | None = None,
    ) -> None:
        self.event_sink(
            RuntimePipelineEvent(self.session_id, kind, message, source_name)
        )


def _log_bus_message(session_id: str, message: Gst.Message) -> None:
    if message.type == Gst.MessageType.ERROR:
        error, debug = message.parse_error()
        logger.error(
            "Pipeline {} failed in {}: {}; {}",
            session_id,
            message.src.get_name(),
            error.message,
            debug or "no debug details",
        )
    elif message.type == Gst.MessageType.EOS:
        logger.info("Pipeline {} reached end of stream", session_id)
    elif message.type == Gst.MessageType.STATE_CHANGED:
        old_state, new_state, _ = message.parse_state_changed()
        logger.info(
            "Pipeline {} changed state from {} to {}",
            session_id,
            old_state.value_nick,
            new_state.value_nick,
        )


def _error_message(message: Gst.Message) -> str:
    try:
        error, _ = message.parse_error()
        return error.message
    except Exception:
        return "GStreamer pipeline error"


def _release_bus_resources(managed: ManagedPipeline) -> None:
    errors: list[Exception] = []
    if managed.bus_handler_id is not None:
        try:
            managed.bus.disconnect(managed.bus_handler_id)
        except Exception as error:
            errors.append(error)
        else:
            managed.bus_handler_id = None

    if managed.signal_watch_added:
        try:
            managed.bus.remove_signal_watch()
        except Exception as error:
            errors.append(error)
        else:
            managed.signal_watch_added = False

    if errors:
        if len(errors) == 1:
            raise errors[0]
        raise ExceptionGroup(
            f"pipeline {managed.session_id!r} release failed",
            errors,
        )


def _process_bus_message(managed: ManagedPipeline, message: Gst.Message) -> None:
    if message.type == Gst.MessageType.ERROR:
        managed.emit_event(
            RuntimePipelineEventKind.ERROR,
            _error_message(message),
            message.src.get_name() if message.src is not None else None,
        )
        _log_bus_message(managed.session_id, message)
    elif message.type == Gst.MessageType.EOS:
        managed.emit_event(RuntimePipelineEventKind.END_OF_STREAM)
        _log_bus_message(managed.session_id, message)
    elif (
        message.type == Gst.MessageType.STATE_CHANGED
        and message.src == managed.pipeline
    ):
        _log_bus_message(managed.session_id, message)


class RuntimeState(Enum):
    RUNNING = auto()
    CLOSING = auto()
    CLOSED = auto()


def parse_pipeline(description: str) -> Gst.Pipeline:
    element = Gst.parse_launch(description)
    if not isinstance(element, Gst.Pipeline):
        raise TypeError("GStreamer description did not create a pipeline")
    return element


class GStreamerRuntime:
    def __init__(
        self,
        dispatcher: GLibTaskDispatcher,
        state_change_timeout_seconds: float = STATE_CHANGE_TIMEOUT_SECONDS,
        max_pipelines: int = MAX_PIPELINES,
    ) -> None:
        validate_runtime_limits(
            state_change_timeout_seconds,
            max_pipelines,
        )

        Gst.init(None)  # loads plugins from GST_PLUGIN_PATH.
        self._pipelines: dict[str, ManagedPipeline] = {}
        self._max_pipelines = max_pipelines
        self._state_change_timeout_seconds = state_change_timeout_seconds
        self._state_change_timeout = int(state_change_timeout_seconds * Gst.SECOND)
        self._dispatcher = dispatcher
        self._state = RuntimeState.RUNNING
        self._state_lock = Lock()
        self._close_lock = Lock()

    def start_pipeline(
        self,
        session_id: str,
        description: str,
        event_sink: PipelineEventSink | None = None,
    ) -> None:
        self._dispatch(
            "start pipeline",
            lambda: self._start_pipeline(
                session_id,
                description,
                event_sink or (lambda _event: None),
            ),
        )

    def _start_pipeline(
        self,
        session_id: str,
        description: str,
        event_sink: PipelineEventSink,
    ) -> None:
        try:
            if session_id in self._pipelines:
                raise InternalError(f"pipeline already exists with ID {session_id!r}")
            if len(self._pipelines) >= self._max_pipelines:
                raise ResourceExhaustedError("GStreamer runtime has reached its pipeline limit")

            pipeline = parse_pipeline(description)
            bus = pipeline.get_bus()
        except Exception as error:
            event_sink(
                RuntimePipelineEvent(
                    session_id, RuntimePipelineEventKind.ERROR, str(error)
                )
            )
            raise

        managed = ManagedPipeline(
            pipeline=pipeline,
            bus=bus,
            session_id=session_id,
            event_sink=event_sink,
        )
        self._pipelines[session_id] = managed

        try:
            managed.emit_event(RuntimePipelineEventKind.ATTACHED)
            self._start_playback(managed)
            managed.emit_event(RuntimePipelineEventKind.PLAYING)
        except Exception:
            self._cleanup_after_failed_start(managed)
            raise

        logger.info("Pipeline {} started", session_id)

    def _start_playback(self, managed: ManagedPipeline) -> None:
        try:
            managed.bus.add_signal_watch()
            managed.signal_watch_added = True
            managed.bus_handler_id = managed.bus.connect(
                "message",
                self._on_bus_message,
                managed.session_id,
            )

            if (
                managed.pipeline.set_state(Gst.State.PLAYING)
                == Gst.StateChangeReturn.FAILURE
            ):
                raise PipelineError(f"pipeline {managed.session_id!r} failed to start")

            state_result, state, _ = managed.pipeline.get_state(
                self._state_change_timeout
            )
            if (
                state_result == Gst.StateChangeReturn.FAILURE
                or state != Gst.State.PLAYING
            ):
                raise PipelineError(
                    f"pipeline {managed.session_id!r} did not reach PLAYING "
                    "before the timeout"
                )
        except Exception as startup_error:
            try:
                managed.emit_event(
                    RuntimePipelineEventKind.ERROR,
                    str(startup_error),
                )
            except Exception as sink_error:
                raise sink_error from startup_error
            raise

    def _cleanup_after_failed_start(
        self,
        managed: ManagedPipeline,
    ) -> None:
        try:
            self._cleanup_pipeline(managed)
        except Exception as error:
            logger.error(
                "Pipeline {} cleanup after startup failure was incomplete and "
                "was retained for retry: {}",
                managed.session_id,
                error,
            )

    def stop_pipeline(self, session_id: str) -> None:
        """Stop or no-op if already stopped"""
        self._dispatch("stop pipeline", lambda: self._stop_pipeline(session_id))

    def set_inference_stage_active(
        self,
        session_id: str,
        stage_id: str,
        active: bool,
    ) -> bool:
        return self._dispatch(
            "set inference stage active",
            lambda: self._set_inference_stage_active(session_id, stage_id, active),
        )

    def _set_inference_stage_active(
        self,
        session_id: str,
        stage_id: str,
        active: bool,
    ) -> bool:
        managed = self._pipelines.get(session_id)
        if managed is None:
            raise NotFoundError(f"pipeline not found: {session_id!r}")
        stage = managed.pipeline.get_by_name(stage_id)

        if stage is None:
            raise NotFoundError(
                f"stage not found in pipeline {session_id!r}: {stage_id!r}"
            )
        factory = stage.get_factory()
        if factory is None or factory.get_name() != "opkinfer":
            raise FailedPreconditionError(
                f"stage is not an opkinfer element: {stage_id!r}"
            )
        stage.set_property("active", active)
        return bool(stage.get_property("active"))

    def _stop_pipeline(self, session_id: str) -> None:
        managed = self._pipelines.get(session_id)
        if managed is not None:
            self._cleanup_pipeline(managed)

    def _cleanup_pipeline(
        self,
        managed: ManagedPipeline,
    ) -> None:
        self._set_pipeline_null(managed)
        self._release_pipeline(managed)

    def _release_pipeline(
        self,
        managed: ManagedPipeline,
    ) -> None:
        _release_bus_resources(managed)

        managed.emit_event(RuntimePipelineEventKind.RELEASED)
        self._pipelines.pop(managed.session_id, None)
        logger.info("Pipeline {} stopped", managed.session_id)

    def _set_pipeline_null(
        self,
        managed: ManagedPipeline,
    ) -> None:
        if not managed.null_state_confirmed:
            self._request_pipeline_null(managed)
            self._wait_for_pipeline_null(
                managed,
                self._state_change_timeout,
            )
            managed.null_state_confirmed = True

    def _request_pipeline_null(
        self,
        managed: ManagedPipeline,
    ) -> None:
        if managed.pipeline.set_state(Gst.State.NULL) == Gst.StateChangeReturn.FAILURE:
            raise PipelineError(
                f"pipeline {managed.session_id!r} rejected the stop request"
            )

    def _wait_for_pipeline_null(
        self,
        managed: ManagedPipeline,
        timeout: int,
    ) -> None:
        state_result, state, _ = managed.pipeline.get_state(timeout)
        if state_result == Gst.StateChangeReturn.FAILURE or state != Gst.State.NULL:
            raise PipelineError(
                f"pipeline {managed.session_id!r} did not reach NULL before the timeout"
            )

    def _on_bus_message(
        self,
        bus: Gst.Bus,
        message: Gst.Message,
        session_id: str,
    ) -> None:
        managed = self._pipelines.get(session_id)
        if managed is None or bus != managed.bus:
            return

        _process_bus_message(managed, message)

    def has_pipeline(self, session_id: str) -> bool:
        """Return whether the runtime currently owns the native pipeline."""

        return self._dispatch(
            "inspect pipeline",
            lambda: session_id in self._pipelines,
        )

    def is_ready(self) -> bool:
        with self._state_lock:
            runtime_running = self._state == RuntimeState.RUNNING
        return runtime_running and self._dispatcher.is_ready()

    def close(self) -> None:
        """Stop every pipeline and close the dispatcher."""

        with self._close_lock:
            with self._state_lock:
                if self._state == RuntimeState.CLOSED:
                    return
                self._state = RuntimeState.CLOSING
            try:
                self._dispatcher.execute(
                    "stop all pipelines",
                    self._stop_all_pipelines,
                )
            except Exception:
                self._restore_running()
                raise

            self._dispatcher.close()
            with self._state_lock:
                self._state = RuntimeState.CLOSED
            logger.info("GStreamer runtime shutdown completed")

    def _restore_running(self) -> None:
        with self._state_lock:
            self._state = RuntimeState.RUNNING

    def _stop_all_pipelines(self) -> None:
        logger.info(
            "GStreamer runtime shutdown started with {} pipeline(s)",
            len(self._pipelines),
        )
        deadline = monotonic() + self._state_change_timeout_seconds
        errors: list[Exception] = []
        stopping: list[ManagedPipeline] = []

        for managed in self._pipelines.values():
            if managed.null_state_confirmed:
                stopping.append(managed)
                continue
            try:
                self._request_pipeline_null(managed)
            except Exception as error:
                errors.append(error)
            else:
                stopping.append(managed)

        for managed in stopping:
            try:
                if not managed.null_state_confirmed:
                    remaining_seconds = max(0.0, deadline - monotonic())
                    self._wait_for_pipeline_null(
                        managed,
                        int(remaining_seconds * Gst.SECOND),
                    )
                    managed.null_state_confirmed = True
                self._release_pipeline(managed)
            except Exception as error:
                errors.append(error)

        if errors:
            raise PipelineError(
                f"failed to stop {len(errors)} pipeline(s) during shutdown"
            )

    def _dispatch[T](self, operation: str, callback: Callable[[], T]) -> T:
        self._ensure_running()
        return self._dispatcher.execute(
            operation,
            lambda: self._run_command(callback),
        )

    def _run_command[T](self, callback: Callable[[], T]) -> T:
        self._ensure_running()
        return callback()

    def _ensure_running(self) -> None:
        with self._state_lock:
            if self._state != RuntimeState.RUNNING:
                raise RuntimeUnavailableError("GStreamer runtime is closing or closed")

    def __enter__(self) -> "GStreamerRuntime":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
