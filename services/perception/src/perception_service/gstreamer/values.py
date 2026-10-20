# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from typing import Final

import gi

gi.require_version("Gst", "1.0")
from gi.repository import GLib, GObject, Gst  # noqa: E402

MAX_GSTREAMER_INT: Final = GLib.MAXINT
MAX_VIDEOCONVERT_DIMENSION: Final = 32_767


def serialize_gstreamer_string(value: str) -> str:
    if not Gst.is_initialized():
        Gst.init(None)

    serialized = Gst.value_serialize(GObject.Value(GObject.TYPE_STRING, value))
    if serialized is None:
        raise ValueError("could not serialize GStreamer string")
    return serialized


def contains_nul(value: str) -> bool:
    return "\x00" in value


def is_valid_positive_gstreamer_int(
    value: int,
    *,
    maximum: int = MAX_GSTREAMER_INT,
) -> bool:
    return 0 < value <= maximum
