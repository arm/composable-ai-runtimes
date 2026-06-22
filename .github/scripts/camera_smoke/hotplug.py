from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from camera_smoke.commands import CommandResult, run_command


HOTPLUG_HELPER_ENV = "CAMERA_BOARDFARM_HOTPLUG_HELPER"
DEFAULT_HOTPLUG_HELPER = "/usr/local/sbin/cairn-camera-hotplug"
SYS_VIDEO4LINUX_DIR = Path("/sys/class/video4linux")
USB_REBIND_TIMEOUT_SECONDS = 15

CommandTranscriptWriter = Callable[[str, CommandResult], None]


@dataclass(frozen=True)
class UsbCameraTarget:
    device_path: Path
    physical_device_id: str
    interface_id: str
    interface_path: Path
    driver_path: Path


@dataclass(frozen=True)
class UsbCameraCleanupResult:
    status: Literal["already_bound", "rebound", "failed"]
    error: str = ""


class HotplugError(Exception):
    """Raised for expected USB hotplug failures."""


def _wait_for_condition(timeout_seconds: float, predicate: Callable[[], bool]) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return bool(predicate())


def is_usb_camera_bound(target: UsbCameraTarget) -> bool:
    driver_link = target.interface_path / "driver"
    try:
        return driver_link.resolve(strict=True) == target.driver_path
    except FileNotFoundError:
        return False


def _get_video_device_paths_for_usb_interface(
    target: UsbCameraTarget,
    *,
    sys_video4linux_dir: Path = SYS_VIDEO4LINUX_DIR,
) -> list[Path]:
    if not sys_video4linux_dir.exists():
        return []

    device_paths: list[Path] = []
    for video_sysfs_path in sorted(sys_video4linux_dir.glob("video*")):
        if not video_sysfs_path.name[5:].isdecimal():
            continue
        try:
            interface_path = (video_sysfs_path / "device").resolve(strict=True)
        except FileNotFoundError:
            continue
        if interface_path == target.interface_path:
            device_paths.append(Path("/dev") / video_sysfs_path.name)
    return device_paths


def _get_hotplug_helper_path() -> str:
    configured_helper = os.environ.get(HOTPLUG_HELPER_ENV, "").strip()
    return configured_helper if configured_helper else DEFAULT_HOTPLUG_HELPER


def _build_hotplug_helper_command(action: str, target: UsbCameraTarget) -> list[str]:
    if action not in {"bind", "unbind"}:
        raise ValueError(f"unsupported hotplug action: {action}")

    return [
        "sudo",
        "-n",
        _get_hotplug_helper_path(),
        action,
        target.interface_id,
    ]


def _run_usb_hotplug_action(
    action: str,
    target: UsbCameraTarget,
    *,
    cwd: Path,
    write_command_transcript: CommandTranscriptWriter | None = None,
) -> CommandResult:
    transcript_name = f"hotplug-{action}.txt"
    result = run_command(*_build_hotplug_helper_command(action, target), cwd=cwd)
    if result.returncode != 0:
        if write_command_transcript is not None:
            write_command_transcript(transcript_name, result)
        raise HotplugError(
            f"privileged hotplug helper failed to {action} {target.interface_id}; "
            f"see {transcript_name}"
        )
    return result


def unbind_usb_camera(
    target: UsbCameraTarget,
    *,
    cwd: Path,
    write_command_transcript: CommandTranscriptWriter | None = None,
) -> None:
    result = _run_usb_hotplug_action(
        "unbind",
        target,
        cwd=cwd,
        write_command_transcript=write_command_transcript,
    )

    if not _wait_for_condition(
        USB_REBIND_TIMEOUT_SECONDS,
        lambda: not is_usb_camera_bound(target),
    ):
        if write_command_transcript is not None:
            write_command_transcript("hotplug-unbind.txt", result)
        raise HotplugError(
            f"timed out waiting for {target.interface_id} to unbind from uvcvideo; "
            "see hotplug-unbind.txt"
        )


def bind_usb_camera(
    target: UsbCameraTarget,
    *,
    cwd: Path,
    write_command_transcript: CommandTranscriptWriter | None = None,
) -> None:
    result = _run_usb_hotplug_action(
        "bind",
        target,
        cwd=cwd,
        write_command_transcript=write_command_transcript,
    )

    if not _wait_for_condition(
        USB_REBIND_TIMEOUT_SECONDS,
        lambda: is_usb_camera_bound(target),
    ):
        if write_command_transcript is not None:
            write_command_transcript("hotplug-bind.txt", result)
        raise HotplugError(
            f"timed out waiting for {target.interface_id} to bind to uvcvideo; "
            "see hotplug-bind.txt"
        )

    if not _wait_for_condition(
        USB_REBIND_TIMEOUT_SECONDS,
        lambda: bool(_get_video_device_paths_for_usb_interface(target)),
    ):
        if write_command_transcript is not None:
            write_command_transcript("hotplug-bind.txt", result)
        raise HotplugError(
            f"timed out waiting for {target.interface_id} to expose /dev/video nodes; "
            "see hotplug-bind.txt"
        )


def ensure_usb_camera_bound(
    target: UsbCameraTarget,
    *,
    cwd: Path,
    write_command_transcript: CommandTranscriptWriter | None = None,
) -> UsbCameraCleanupResult:
    try:
        if is_usb_camera_bound(target):
            return UsbCameraCleanupResult(status="already_bound")
        bind_usb_camera(
            target,
            cwd=cwd,
            write_command_transcript=write_command_transcript,
        )
        return UsbCameraCleanupResult(status="rebound")
    except Exception as exc:
        return UsbCameraCleanupResult(
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
        )
