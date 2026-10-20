# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import pytest

from cairn.perception.v1 import perception_pb2
import perception_service.workflow.stages.source as source_module
from perception_service.gstreamer.values import (
    MAX_GSTREAMER_INT,
    MAX_VIDEOCONVERT_DIMENSION,
)
from perception_service.workflow.issues import ValidationCode
from perception_service.workflow.stage import StageConstructionError
from perception_service.workflow.stages.source import CameraSourceDefinition

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("pixel_format", ["GRAY8", "NV12", "RGB", "YUY2"])
def test_camera_source_constructs_raw_format_conversion(
    pixel_format: str,
) -> None:
    definition = CameraSourceDefinition(camera_source(pixel_format))

    assert definition.validate() == (True, [])
    assert definition.construct() == (
        pipewire_source_fragment(),
        f"video/x-raw,format={pixel_format},width=640,height=480,framerate=30/1",
        "videoconvert",
        "video/x-raw,format=BGRA,width=640,height=480,framerate=30/1",
    )


def test_camera_source_constructs_native_bgra_without_conversion() -> None:
    definition = CameraSourceDefinition(camera_source("BGRA"))

    assert definition.validate() == (True, [])
    assert definition.construct() == (
        pipewire_source_fragment(),
        "video/x-raw,format=BGRA,width=640,height=480,framerate=30/1",
    )


def test_camera_source_requires_pixel_format() -> None:
    definition = CameraSourceDefinition(camera_source(""))

    valid, issues = definition.validate()

    assert not valid
    assert len(issues) == 1
    assert issues[0].code == ValidationCode.CAMERA_FORMAT_REQUIRED
    assert issues[0].field_path == "source.camera.format.pixel_format"

    with pytest.raises(StageConstructionError, match="pixel format is required"):
        definition.construct()


@pytest.mark.parametrize(
    ("pipewire_target", "expected_code"),
    [
        ("", ValidationCode.PIPEWIRE_TARGET_REQUIRED),
        ("   ", ValidationCode.PIPEWIRE_TARGET_REQUIRED),
        ("camera\x00source", ValidationCode.PIPEWIRE_TARGET_INVALID),
    ],
)
def test_camera_source_rejects_invalid_pipewire_targets(
    pipewire_target: str,
    expected_code: ValidationCode,
) -> None:
    valid, issues = CameraSourceDefinition(
        camera_source("YUY2", pipewire_target=pipewire_target)
    ).validate()

    assert not valid
    assert [issue.code for issue in issues] == [expected_code]
    assert issues[0].field_path == "source.camera.target"


def test_camera_source_accumulates_invalid_mode_issues() -> None:
    source = camera_source(
        "H264",
        pipewire_target="",
        width=0,
        height=MAX_VIDEOCONVERT_DIMENSION + 1,
        frame_rate_numerator=0,
        frame_rate_denominator=MAX_GSTREAMER_INT + 1,
    )

    valid, issues = CameraSourceDefinition(source).validate()

    assert not valid
    assert [issue.code for issue in issues] == [
        ValidationCode.PIPEWIRE_TARGET_REQUIRED,
        ValidationCode.CAMERA_DIMENSION_INVALID,
        ValidationCode.CAMERA_DIMENSION_INVALID,
        ValidationCode.CAMERA_FRAME_RATE_INVALID,
        ValidationCode.CAMERA_FRAME_RATE_INVALID,
        ValidationCode.UNKNOWN_CAMERA_FORMAT,
    ]
    assert [issue.field_path for issue in issues] == [
        "source.camera.target",
        "source.camera.format.resolution.width",
        "source.camera.format.resolution.height",
        "source.camera.format.frame_rate.numerator",
        "source.camera.format.frame_rate.denominator",
        "source.camera.format.pixel_format",
    ]


@pytest.mark.parametrize("missing", ["format", "resolution", "frame_rate"])
def test_camera_source_rejects_missing_nested_configuration(missing: str) -> None:
    source = camera_source("NV12")
    if missing == "format":
        source.ClearField(missing)
    else:
        source.format.ClearField(missing)

    valid, issues = CameraSourceDefinition(source).validate()

    assert not valid
    expected_paths = {
        "resolution": [
            "source.camera.format.resolution.width",
            "source.camera.format.resolution.height",
        ],
        "frame_rate": [
            "source.camera.format.frame_rate.numerator",
            "source.camera.format.frame_rate.denominator",
        ],
    }
    assert [issue.field_path for issue in issues] == (
        expected_paths["resolution"]
        + expected_paths["frame_rate"]
        + ["source.camera.format.pixel_format"]
        if missing == "format"
        else expected_paths[missing]
    )


def test_camera_source_preserves_exact_frame_rate_in_caps() -> None:
    source = camera_source(
        "NV12",
        width=1920,
        height=1080,
        frame_rate_numerator=30000,
        frame_rate_denominator=1001,
    )
    definition = CameraSourceDefinition(source)

    assert definition.validate() == (True, [])
    assert (
        definition.construct()[1]
        == "video/x-raw,format=NV12,width=1920,height=1080,framerate=30000/1001"
    )


def test_camera_source_accepts_gstreamer_integer_boundaries() -> None:
    source = camera_source(
        "YUY2",
        width=MAX_VIDEOCONVERT_DIMENSION,
        height=MAX_VIDEOCONVERT_DIMENSION,
        frame_rate_numerator=MAX_GSTREAMER_INT,
        frame_rate_denominator=MAX_GSTREAMER_INT,
    )

    assert CameraSourceDefinition(source).validate() == (True, [])


@pytest.mark.parametrize(
    ("pixel_format", "expected_code"),
    [
        ("DMA_DRM", ValidationCode.UNSUPPORTED_CAMERA_FORMAT),
        ("ENCODED", ValidationCode.UNSUPPORTED_CAMERA_FORMAT),
        ("M420", ValidationCode.UNSUPPORTED_CAMERA_FORMAT),
        ("MJPEG", ValidationCode.UNSUPPORTED_CAMERA_FORMAT),
        ("MJPG", ValidationCode.UNSUPPORTED_CAMERA_FORMAT),
        ("Mjpg", ValidationCode.UNSUPPORTED_CAMERA_FORMAT),
        ("NV12\x00suffix", ValidationCode.UNKNOWN_CAMERA_FORMAT),
        ("FUTURE_RAW_FORMAT", ValidationCode.UNKNOWN_CAMERA_FORMAT),
        ("H264", ValidationCode.UNKNOWN_CAMERA_FORMAT),
    ],
)
def test_camera_source_rejects_unavailable_formats(
    pixel_format: str,
    expected_code: ValidationCode,
) -> None:
    definition = CameraSourceDefinition(camera_source(pixel_format))

    valid, issues = definition.validate()

    assert not valid
    assert len(issues) == 1
    assert issues[0].code == expected_code
    assert issues[0].field_path == "source.camera.format.pixel_format"
    assert issues[0].stage_id == "source:camera"

    with pytest.raises(StageConstructionError):
        definition.construct()


def test_camera_source_wraps_gstreamer_serialization_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_serialization(_: str) -> str:
        raise ValueError("serialization failed")

    monkeypatch.setattr(source_module, "serialize_gstreamer_string", fail_serialization)

    with pytest.raises(StageConstructionError) as error:
        CameraSourceDefinition(camera_source("YUY2")).construct()

    assert str(error.value) == "could not serialize PipeWire target"
    assert error.value.field_path == "source.camera.target"
    assert error.value.stage_id == "source:camera"
    assert isinstance(error.value.__cause__, ValueError)


def camera_source(
    pixel_format: str,
    *,
    pipewire_target: str = "gstreamer-test-source",
    width: int = 640,
    height: int = 480,
    frame_rate_numerator: int = 30,
    frame_rate_denominator: int = 1,
) -> perception_pb2.StreamConfiguration:
    return perception_pb2.StreamConfiguration(
        target=pipewire_target,
        format=perception_pb2.StreamFormat(
            resolution=perception_pb2.Resolution(width=width, height=height),
            frame_rate=perception_pb2.FrameRate(
                numerator=frame_rate_numerator,
                denominator=frame_rate_denominator,
            ),
            pixel_format=pixel_format,
        ),
    )


def pipewire_source_fragment() -> str:
    return (
        "pipewiresrc do-timestamp=true target-object=gstreamer-test-source "
        'stream-properties="props\\,'
        "media.class\\=\\(string\\)Stream/Input/Video\\,"
        "node.dont-fallback\\=\\(boolean\\)true\\,"
        "node.dont-reconnect\\=\\(boolean\\)true\\,"
        "node.linger\\=\\(boolean\\)false\\,"
        'state.restore-target\\=\\(boolean\\)false"'
    )
