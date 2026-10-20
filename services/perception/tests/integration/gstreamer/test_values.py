# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import gi
import pytest

gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst  # noqa: E402

from perception_service.gstreamer.values import (  # noqa: E402
    MAX_GSTREAMER_INT,
    MAX_VIDEOCONVERT_DIMENSION,
    contains_nul,
    is_valid_positive_gstreamer_int,
    serialize_gstreamer_string,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "value",
    [
        "gstreamer-test-source",
        "name with space",
        'name"quoted',
        "name\\path",
        "source ! fakesink",
    ],
)
def test_serialize_gstreamer_string_round_trips_through_parse_launch(
    value: str,
) -> None:
    pipeline = Gst.parse_launch(
        f"filesrc name=source location={serialize_gstreamer_string(value)} ! fakesink"
    )
    assert isinstance(pipeline, Gst.Pipeline)
    source = pipeline.get_by_name("source")

    assert source is not None
    assert source.get_property("location") == value


def test_contains_nul_detects_nul_character() -> None:
    assert not contains_nul("camera-source")
    assert contains_nul("camera\x00source")


def test_positive_gstreamer_integer_validation_uses_glib_boundaries() -> None:
    assert MAX_GSTREAMER_INT == GLib.MAXINT
    assert is_valid_positive_gstreamer_int(1)
    assert is_valid_positive_gstreamer_int(GLib.MAXINT)
    assert not is_valid_positive_gstreamer_int(0)
    assert not is_valid_positive_gstreamer_int(GLib.MAXINT + 1)
    assert is_valid_positive_gstreamer_int(
        MAX_VIDEOCONVERT_DIMENSION,
        maximum=MAX_VIDEOCONVERT_DIMENSION,
    )
    assert not is_valid_positive_gstreamer_int(
        MAX_VIDEOCONVERT_DIMENSION + 1,
        maximum=MAX_VIDEOCONVERT_DIMENSION,
    )
