# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import pytest

from perception_service.gstreamer.glib_dispatcher import GLibTaskDispatcher
from perception_service.gstreamer.runtime import GStreamerRuntime
from perception_service.pipeline_manager import PipelineManager
from perception_service.pipeline_store import PipelineStore
from perception_service.pipeline_types import PipelineState

pytestmark = pytest.mark.integration


def test_manager_tracks_real_runtime_start_and_stop() -> None:
    with GStreamerRuntime(GLibTaskDispatcher()) as runtime:
        manager = PipelineManager(runtime, PipelineStore())
        session_id = "pipeline-1"
        manager.start_pipeline(
            session_id,
            "videotestsrc is-live=true ! fakesink sync=false",
        )

        running = manager.get_pipeline(session_id)
        manager.stop_pipeline(session_id)
        stopped = manager.get_pipeline(session_id)

    assert running is not None
    assert running.status.state == PipelineState.RUNNING
    assert stopped is not None
    assert stopped.status.state == PipelineState.STOPPED
