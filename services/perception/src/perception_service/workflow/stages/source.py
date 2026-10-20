# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from typing import ClassVar

from loguru import logger

from cairn.perception.v1.perception_pb2 import (
    RESOLVED_STAGE_ROLE_SOURCE,
    StreamConfiguration,
    ResolvedStage,
    ValidationIssue,
)
from perception_service.gstreamer.values import (
    MAX_GSTREAMER_INT,
    MAX_VIDEOCONVERT_DIMENSION,
    contains_nul,
    is_valid_positive_gstreamer_int,
    serialize_gstreamer_string,
)
from perception_service.workflow.issues import ValidationCode, validation_error
from perception_service.workflow.stage import StageConstructionError, StageDefinition
from perception_service.workflow.stages.source_conversion import (
    CameraFormatConversionFactory,
)

_PIPEWIRE_STREAM_PROPERTIES = (
    "props,"
    "media.class=(string)Stream/Input/Video,"
    "node.dont-fallback=(boolean)true,"
    "node.dont-reconnect=(boolean)true,"
    "node.linger=(boolean)false,"
    "state.restore-target=(boolean)false"
)


def build_pipewire_source_fragment(pipewire_target: str) -> str:
    return (
        "pipewiresrc "
        "do-timestamp=true "
        f"target-object={serialize_gstreamer_string(pipewire_target)} "
        "stream-properties="
        f"{serialize_gstreamer_string(_PIPEWIRE_STREAM_PROPERTIES)}"
    )


class CameraSourceDefinition(StageDefinition):
    static_id: ClassVar[str] = "source:camera"
    name = "pipewire_source"
    role = RESOLVED_STAGE_ROLE_SOURCE

    def __init__(self, source_definition: StreamConfiguration):
        self._source_definition = source_definition

    def validate(self) -> tuple[bool, list[ValidationIssue]]:
        source = self._source_definition
        issues: list[ValidationIssue] = []

        if not source.target.strip():
            issues.append(
                validation_error(
                    ValidationCode.PIPEWIRE_TARGET_REQUIRED,
                    "PipeWire target is required",
                    "source.camera.target",
                    self.static_id,
                )
            )
        elif contains_nul(source.target):
            issues.append(
                validation_error(
                    ValidationCode.PIPEWIRE_TARGET_INVALID,
                    "PipeWire target must not contain NUL characters",
                    "source.camera.target",
                    self.static_id,
                )
            )

        for field_name, value in (
            ("width", source.format.resolution.width),
            ("height", source.format.resolution.height),
        ):
            if not is_valid_positive_gstreamer_int(
                value,
                maximum=MAX_VIDEOCONVERT_DIMENSION,
            ):
                issues.append(
                    validation_error(
                        ValidationCode.CAMERA_DIMENSION_INVALID,
                        f"camera {field_name} must be between 1 and "
                        f"{MAX_VIDEOCONVERT_DIMENSION}",
                        f"source.camera.format.resolution.{field_name}",
                        self.static_id,
                    )
                )

        for field_name, value in (
            ("numerator", source.format.frame_rate.numerator),
            ("denominator", source.format.frame_rate.denominator),
        ):
            if not is_valid_positive_gstreamer_int(value):
                issues.append(
                    validation_error(
                        ValidationCode.CAMERA_FRAME_RATE_INVALID,
                        f"camera frame-rate {field_name} must be between 1 and "
                        f"{MAX_GSTREAMER_INT}",
                        f"source.camera.format.frame_rate.{field_name}",
                        self.static_id,
                    )
                )

        format_issue = self._validate_pixel_format()
        if format_issue is not None:
            issues.append(format_issue)

        return not issues, issues

    def _validate_pixel_format(self) -> ValidationIssue | None:
        pixel_format = self._source_definition.format.pixel_format
        if not pixel_format:
            return validation_error(
                ValidationCode.CAMERA_FORMAT_REQUIRED,
                "camera pixel format is required",
                "source.camera.format.pixel_format",
                self.static_id,
            )

        conversion = CameraFormatConversionFactory.find(pixel_format)
        if conversion is not None:
            return None

        if CameraFormatConversionFactory.is_known_unsupported(pixel_format):
            return validation_error(
                ValidationCode.UNSUPPORTED_CAMERA_FORMAT,
                f"camera pixel format {pixel_format!r} is not supported",
                "source.camera.format.pixel_format",
                self.static_id,
            )

        return validation_error(
            ValidationCode.UNKNOWN_CAMERA_FORMAT,
            f"camera pixel format {pixel_format!r} is not recognized by GStreamer",
            "source.camera.format.pixel_format",
            self.static_id,
        )

    def construct(self) -> tuple[str, ...]:
        source = self._source_definition
        conversion = CameraFormatConversionFactory.find(source.format.pixel_format)
        if conversion is None:
            message = (
                "camera pixel format is required"
                if not source.format.pixel_format
                else f"camera pixel format {source.format.pixel_format!r} is not supported"
            )
            raise StageConstructionError(
                message,
                field_path="source.camera.format.pixel_format",
                stage_id=self.static_id,
            )

        try:
            source_fragment = build_pipewire_source_fragment(source.target)
        except ValueError as error:
            raise StageConstructionError(
                "could not serialize PipeWire target",
                field_path="source.camera.target",
                stage_id=self.static_id,
            ) from error

        if not CameraFormatConversionFactory.is_explicitly_supported(
            source.format.pixel_format
        ):
            logger.info(
                "Camera source {} format {} has no dedicated conversion; using "
                "generic raw-to-BGRA conversion",
                source.target,
                source.format.pixel_format,
            )

        logger.debug(
            "Constructing PipeWire source {} at {}x{}, {}/{} FPS, format {}",
            source.target,
            source.format.resolution.width,
            source.format.resolution.height,
            source.format.frame_rate.numerator,
            source.format.frame_rate.denominator,
            source.format.pixel_format,
        )
        return (source_fragment, *conversion(source))

    def to_resolved_stage(self) -> ResolvedStage:
        return ResolvedStage(
            id=self.static_id,
            name=self.name,
            role=self.role,
            controllable=self.controllable,
        )
