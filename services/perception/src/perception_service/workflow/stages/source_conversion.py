# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Callable, Mapping
from typing import ClassVar

import gi

from cairn.perception.v1.perception_pb2 import StreamConfiguration
from perception_service.gstreamer.values import contains_nul

gi.require_version("GstVideo", "1.0")
from gi.repository import GstVideo  # noqa: E402


type CameraFormatConversion = Callable[[StreamConfiguration], tuple[str, ...]]


def raw_to_bgra(source_configuration: StreamConfiguration) -> tuple[str, ...]:
    return (
        _raw_caps(source_configuration, source_configuration.format.pixel_format),
        "videoconvert",
        _raw_caps(source_configuration, "BGRA"),
    )


def bgra_passthrough(source_configuration: StreamConfiguration) -> tuple[str, ...]:
    return (_raw_caps(source_configuration, "BGRA"),)


def _raw_caps(source_configuration: StreamConfiguration, pixel_format: str) -> str:
    fields = ["video/x-raw", f"format={pixel_format}"]
    fields.extend(
        (
            f"width={source_configuration.format.resolution.width}",
            f"height={source_configuration.format.resolution.height}",
            f"framerate={source_configuration.format.frame_rate.numerator}/"
            f"{source_configuration.format.frame_rate.denominator}",
        )
    )
    return ",".join(fields)


class CameraFormatConversionFactory:
    _format_conversions: ClassVar[Mapping[str, CameraFormatConversion]] = {
        "GRAY8": raw_to_bgra,
        "RGB": raw_to_bgra,
        "YUY2": raw_to_bgra,
        "BGRA": bgra_passthrough,
    }
    _unsupported_formats: ClassVar[frozenset[str]] = frozenset(
        {"DMA_DRM", "ENCODED", "M420", "MJPEG", "MJPG", "Mjpg"}
    )

    @classmethod
    def find(cls, pixel_format: str) -> CameraFormatConversion | None:
        if (
            not pixel_format
            or contains_nul(pixel_format)
            or pixel_format in cls._unsupported_formats
        ):
            return None

        conversion = cls._format_conversions.get(pixel_format)
        if conversion is not None:
            return conversion
        if (
            GstVideo.VideoFormat.from_string(pixel_format)
            != GstVideo.VideoFormat.UNKNOWN
        ):
            return raw_to_bgra
        return None

    @classmethod
    def is_explicitly_supported(cls, pixel_format: str) -> bool:
        return pixel_format in cls._format_conversions

    @classmethod
    def is_known_unsupported(cls, pixel_format: str) -> bool:
        return pixel_format in cls._unsupported_formats
