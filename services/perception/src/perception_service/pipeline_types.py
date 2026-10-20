# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto


class RuntimePipelineEventKind(Enum):
    ATTACHED = auto()
    PLAYING = auto()
    ERROR = auto()
    END_OF_STREAM = auto()
    RELEASED = auto()


@dataclass(frozen=True)
class RuntimePipelineEvent:
    session_id: str
    kind: RuntimePipelineEventKind
    message: str | None = None
    source_name: str | None = None


PipelineEventSink = Callable[[RuntimePipelineEvent], None]


class PipelineState(Enum):
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    STOPPED = auto()
    FAILED = auto()


@dataclass(frozen=True)
class PipelineStatus:
    state: PipelineState
    message: str | None = None


@dataclass(frozen=True)
class PipelineSnapshot:
    session_id: str
    status: PipelineStatus
