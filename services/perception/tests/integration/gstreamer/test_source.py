# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import gi
import pytest

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

from cairn.perception.v1 import perception_pb2  # noqa: E402
from perception_service.workflow.stages.source import (  # noqa: E402
    CameraSourceDefinition,
)

pytestmark = pytest.mark.integration


@pytest.mark.pipewiresrc
def test_constructed_pipewire_source_parses_with_strict_properties_and_caps() -> None:
    target = 'camera target "front" ! fakesink'
    source = perception_pb2.StreamConfiguration(
        target=target,
        format=perception_pb2.StreamFormat(
            resolution=perception_pb2.Resolution(width=640, height=480),
            frame_rate=perception_pb2.FrameRate(numerator=30, denominator=1),
            pixel_format="YUY2",
        ),
    )
    description = " ! ".join(
        (*CameraSourceDefinition(source).construct(), "fakesink sync=false")
    )

    pipeline = Gst.parse_launch(description)

    assert isinstance(pipeline, Gst.Pipeline)
    pipewire_source = pipeline.get_by_name("pipewiresrc0")
    assert pipewire_source is not None
    assert pipewire_source.get_property("target-object") == target

    stream_properties = pipewire_source.get_property("stream-properties")
    assert stream_properties is not None
    assert stream_properties.get_value("media.class") == "Stream/Input/Video"
    assert stream_properties.get_value("node.dont-fallback") is True
    assert stream_properties.get_value("node.dont-reconnect") is True
    assert stream_properties.get_value("node.linger") is False
    assert stream_properties.get_value("state.restore-target") is False

    input_filter = pipeline.get_by_name("capsfilter0")
    output_filter = pipeline.get_by_name("capsfilter1")
    assert input_filter is not None
    assert output_filter is not None
    input_caps = input_filter.get_property("caps")
    output_caps = output_filter.get_property("caps")
    assert input_caps.to_string() == (
        "video/x-raw, format=(string)YUY2, width=(int)640, height=(int)480, "
        "framerate=(fraction)30/1"
    )
    assert output_caps.to_string() == (
        "video/x-raw, format=(string)BGRA, width=(int)640, height=(int)480, "
        "framerate=(fraction)30/1"
    )
