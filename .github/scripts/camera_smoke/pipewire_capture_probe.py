# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Capture one frame from a PipeWire camera node through GStreamer."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise
from typing import TypedDict

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstVideo", "1.0")
from gi.repository import Gst, GstVideo

CAPTURE_TIMEOUT_SECONDS = 15
STATE_CHANGE_TIMEOUT_SECONDS = 10
PIPEWIRESRC_TARGET_PROPERTY = "target-object"


class ProbeError(Exception):
    """Expected capture probe failure with a human-readable message."""


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    pixel_format: str
    stride: int | None
    stride_error: str | None


class CaptureDocument(TypedDict):
    pipewire_target_object: str
    camera_name: str
    frame_bytes: int
    width: int
    height: int
    pixel_format: str
    caps: str
    stride: int | None
    stride_error: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipewire-target-object", required=True)
    parser.add_argument("--camera-name", required=True)
    return parser.parse_args()


def require_pipewiresrc() -> None:
    if Gst.ElementFactory.find("pipewiresrc") is None:
        raise ProbeError("GStreamer plugin 'pipewiresrc' is not installed")


def make_element(factory_name: str, element_name: str) -> Gst.Element:
    element = Gst.ElementFactory.make(factory_name, element_name)
    if element is None:
        raise ProbeError(f"could not create GStreamer element '{factory_name}'")
    return element


def make_capsfilter(element_name: str, caps_text: str) -> Gst.Element:
    capsfilter = make_element("capsfilter", element_name)
    caps = Gst.Caps.from_string(caps_text)
    if caps is None:
        raise ProbeError(f"could not construct GStreamer caps '{caps_text}'")
    capsfilter.set_property("caps", caps)
    return capsfilter


def make_sink() -> Gst.Element:
    sink = make_element("appsink", "sink")
    sink.set_property("sync", False)
    sink.set_property("max-buffers", 1)
    sink.set_property("drop", True)
    return sink


def link_pipeline(format_name: str, *elements: Gst.Element) -> None:
    for upstream, downstream in pairwise(elements):
        if not upstream.link(downstream):
            raise ProbeError(
                f"could not link {format_name} PipeWire capture pipeline: "
                f"{upstream.get_name()} -> {downstream.get_name()}"
            )


def build_mjpeg_pipeline(target_object: str) -> tuple[Gst.Pipeline, Gst.Element]:
    pipeline = Gst.Pipeline.new("pipewire-capture-probe")
    if pipeline is None:
        raise ProbeError("could not create GStreamer pipeline")

    source = make_element("pipewiresrc", "source")
    source.set_property(PIPEWIRESRC_TARGET_PROPERTY, target_object)
    input_capsfilter = make_capsfilter("mjpeg-filter", "image/jpeg")
    decoder = make_element("jpegdec", "decoder")
    converter = make_element("videoconvert", "converter")
    output_capsfilter = make_capsfilter("raw-video-filter", "video/x-raw")
    sink = make_sink()

    pipeline.add(source)
    pipeline.add(input_capsfilter)
    pipeline.add(decoder)
    pipeline.add(converter)
    pipeline.add(output_capsfilter)
    pipeline.add(sink)
    link_pipeline(
        "MJPEG",
        source,
        input_capsfilter,
        decoder,
        converter,
        output_capsfilter,
        sink,
    )

    return pipeline, sink


def build_yuy2_pipeline(target_object: str) -> tuple[Gst.Pipeline, Gst.Element]:
    pipeline = Gst.Pipeline.new("pipewire-capture-probe")
    if pipeline is None:
        raise ProbeError("could not create GStreamer pipeline")

    source = make_element("pipewiresrc", "source")
    source.set_property(PIPEWIRESRC_TARGET_PROPERTY, target_object)
    input_capsfilter = make_capsfilter("yuy2-filter", "video/x-raw,format=YUY2")
    converter = make_element("videoconvert", "converter")
    output_capsfilter = make_capsfilter("raw-video-filter", "video/x-raw")
    sink = make_sink()

    pipeline.add(source)
    pipeline.add(input_capsfilter)
    pipeline.add(converter)
    pipeline.add(output_capsfilter)
    pipeline.add(sink)
    link_pipeline("YUY2", source, input_capsfilter, converter, output_capsfilter, sink)

    return pipeline, sink


def get_bus_error_message(pipeline: Gst.Pipeline) -> str | None:
    bus = pipeline.get_bus()
    if bus is None:
        return None
    message = bus.pop_filtered(Gst.MessageType.ERROR)
    if message is None:
        return None
    error, debug = message.parse_error()
    if debug:
        return f"{error.message}; debug: {debug}"
    return error.message


def start_pipeline(pipeline: Gst.Pipeline) -> None:
    state_change = pipeline.set_state(Gst.State.PLAYING)
    if state_change == Gst.StateChangeReturn.FAILURE:
        detail = get_bus_error_message(pipeline)
        if detail:
            raise ProbeError(f"failed to start GStreamer pipeline: {detail}")
        raise ProbeError("failed to start GStreamer pipeline")

    timeout = STATE_CHANGE_TIMEOUT_SECONDS * Gst.SECOND
    result, state, _pending = pipeline.get_state(timeout)
    if result == Gst.StateChangeReturn.FAILURE:
        detail = get_bus_error_message(pipeline)
        if detail:
            raise ProbeError(f"GStreamer pipeline failed before capture: {detail}")
        raise ProbeError("GStreamer pipeline failed before capture")
    if state != Gst.State.PLAYING:
        raise ProbeError("GStreamer pipeline did not reach PLAYING state")


def pull_sample(pipeline: Gst.Pipeline, sink: Gst.Element) -> Gst.Sample:
    timeout = CAPTURE_TIMEOUT_SECONDS * Gst.SECOND
    sample = sink.emit("try-pull-sample", timeout)
    if sample is None:
        detail = get_bus_error_message(pipeline)
        if detail:
            raise ProbeError(
                "GStreamer pipeline failed while waiting for a frame: " + detail
            )
        raise ProbeError("timed out waiting for a PipeWire frame")
    return sample


def parse_video_info(caps: Gst.Caps) -> VideoInfo:
    if caps.is_empty() or caps.get_size() < 1:
        raise ProbeError("captured sample did not include valid caps")

    structure = caps.get_structure(0)
    if structure is None:
        raise ProbeError("captured sample caps did not include a structure")

    success, width = structure.get_int("width")
    if not success or width <= 0:
        raise ProbeError("captured sample caps did not include a valid width")

    success, height = structure.get_int("height")
    if not success or height <= 0:
        raise ProbeError("captured sample caps did not include a valid height")

    pixel_format = structure.get_string("format")
    if not pixel_format:
        raise ProbeError("captured sample caps did not include a pixel format")

    stride: int | None = None
    stride_error: str | None = None
    video_info = GstVideo.VideoInfo.new_from_caps(caps)
    if video_info is None:
        stride_error = "GStreamer could not derive video info from caps"
    else:
        try:
            stride = int(video_info.stride[0])
        except (IndexError, TypeError, ValueError) as err:
            stride = None
            stride_error = f"could not read first video stride: {err}"

    return VideoInfo(
        width=width,
        height=height,
        pixel_format=pixel_format,
        stride=stride,
        stride_error=stride_error,
    )


def build_document(args: argparse.Namespace, sample: Gst.Sample) -> CaptureDocument:
    buffer = sample.get_buffer()
    if buffer is None:
        raise ProbeError("captured sample did not include a buffer")
    frame_bytes = buffer.get_size()
    if frame_bytes <= 0:
        raise ProbeError("captured sample buffer was empty")

    caps = sample.get_caps()
    if caps is None:
        raise ProbeError("captured sample did not include caps")
    video_info = parse_video_info(caps)

    return {
        "pipewire_target_object": args.pipewire_target_object,
        "camera_name": args.camera_name,
        "frame_bytes": frame_bytes,
        "width": video_info.width,
        "height": video_info.height,
        "pixel_format": video_info.pixel_format,
        "caps": caps.to_string(),
        "stride": video_info.stride,
        "stride_error": video_info.stride_error,
    }


def capture_document(
    args: argparse.Namespace,
    pipeline_builder: Callable[[str], tuple[Gst.Pipeline, Gst.Element]],
) -> CaptureDocument:
    pipeline, sink = pipeline_builder(args.pipewire_target_object)
    try:
        start_pipeline(pipeline)
        sample = pull_sample(pipeline, sink)
        return build_document(args, sample)
    finally:
        pipeline.set_state(Gst.State.NULL)


def capture_with_supported_formats(args: argparse.Namespace) -> CaptureDocument:
    errors: list[str] = []
    for name, pipeline_builder in (
        ("mjpeg", build_mjpeg_pipeline),
        ("yuy2", build_yuy2_pipeline),
    ):
        try:
            return capture_document(args, pipeline_builder)
        except ProbeError as err:
            errors.append(f"{name}: {err}")

    raise ProbeError("could not capture a PipeWire frame; " + "; ".join(errors))


def main() -> None:
    try:
        args = parse_args()
        Gst.init(None)
        require_pipewiresrc()
        print(json.dumps(capture_with_supported_formats(args), sort_keys=True))
    except ProbeError as err:
        print(err, file=sys.stderr)
        raise SystemExit(1) from err


if __name__ == "__main__":
    main()
