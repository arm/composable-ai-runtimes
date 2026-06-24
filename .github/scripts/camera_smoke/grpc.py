from __future__ import annotations

import json
import re
from typing import TypedDict

from camera_smoke.commands import CommandResult


GRPC_CONNECTION_PATTERN = re.compile(
    r"failed to connect:|transport error|connection refused|tcp connect error|"
    r"error trying to connect|connect error|failed to dial target host|"
    r"context deadline exceeded|connection reset by peer|broken pipe",
    re.IGNORECASE,
)
PIPEWIRE_DISCOVERY_PATTERN = re.compile(
    r"Unavailable|UNAVAILABLE|Code:\s*Unavailable|code = Unavailable|PipeWire|"
    r"WirePlumber|snapshot|runtime directory",
    re.IGNORECASE | re.DOTALL,
)
RETRYABLE_DISCOVERY_RESULTS = {
    "grpc_connection_failed",
    "pipewire_discovery_failed",
}
COMMAND_OUTPUT_SUMMARY_LIMIT = 1000


class CameraJson(TypedDict):
    name: str


class ListCamerasJson(TypedDict):
    cameras: list[CameraJson]


def classify_grpcurl_failure(result: CommandResult) -> str:
    output = f"{result.stdout}\n{result.stderr}"
    if GRPC_CONNECTION_PATTERN.search(output):
        return "grpc_connection_failed"
    if PIPEWIRE_DISCOVERY_PATTERN.search(output):
        return "pipewire_discovery_failed"
    return "grpcurl_failed"


def summarize_command_output(result: CommandResult) -> str:
    output = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}".strip()
    if len(output) <= COMMAND_OUTPUT_SUMMARY_LIMIT:
        return output
    return f"{output[:COMMAND_OUTPUT_SUMMARY_LIMIT]}...<truncated>"


def parse_camera(value: object) -> CameraJson:
    if not isinstance(value, dict):
        raise AssertionError("list-cameras response included a non-object camera")

    name = value.get("name")
    if not isinstance(name, str):
        raise AssertionError("list-cameras response included a non-string camera name")

    return {"name": name}


def parse_camera_output(stdout: str) -> ListCamerasJson:
    try:
        document = json.loads(stdout)
    except json.JSONDecodeError as err:
        raise AssertionError(f"grpcurl did not emit valid JSON: {err}") from err
    if not isinstance(document, dict):
        raise AssertionError("grpcurl JSON output is not an object.")

    cameras = document.get("cameras", [])
    if not isinstance(cameras, list):
        raise AssertionError("list-cameras response did not include a cameras list")

    return {"cameras": [parse_camera(camera) for camera in cameras]}


def validate_camera_names(
    document: ListCamerasJson, expected_name_pattern: str | None
) -> tuple[bool, str]:
    cameras = document["cameras"]
    if not cameras:
        return False, "list-cameras response did not include any cameras"

    names: list[str] = []
    for camera in cameras:
        name = camera["name"]
        if not name.strip():
            return False, "list-cameras response included an empty camera name"
        names.append(name)

    if expected_name_pattern:
        pattern = re.compile(expected_name_pattern)
        if not any(pattern.search(name) for name in names):
            return False, "no camera name matched expected pattern"

    return True, "camera names matched expectations"
