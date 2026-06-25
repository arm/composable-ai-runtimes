from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from camera_smoke.commands import CommandResult, run_command


HOTPLUG_HELPER_ENV = "CAMERA_BOARDFARM_HOTPLUG_HELPER"
HOTPLUG_DEVICE_ENV = "CAMERA_BOARDFARM_HOTPLUG_DEVICE"
DEFAULT_HOTPLUG_HELPER = "/usr/local/sbin/cairn-camera-hotplug"
SYS_VIDEO4LINUX_DIR = Path("/sys/class/video4linux")
UVCVIDEO_DRIVER_DIR = Path("/sys/bus/usb/drivers/uvcvideo")
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


def normalize_video_device_path(value: str) -> Path:
    candidate = Path(value)
    device_name = candidate.name
    if not device_name.startswith("video") or not device_name[5:].isdecimal():
        raise HotplugError(
            f"{HOTPLUG_DEVICE_ENV} must identify a /dev/videoN device: {value!r}"
        )

    if candidate.is_absolute() and candidate.parent != Path("/dev"):
        raise HotplugError(
            f"{HOTPLUG_DEVICE_ENV} must identify a /dev/videoN device: {value!r}"
        )

    return Path("/dev") / device_name


def _read_sysfs_link(path: Path) -> Path:
    try:
        return path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise HotplugError(f"missing required sysfs path: {path}") from exc


def get_usb_camera_target(
    device_path: Path,
    *,
    sys_video4linux_dir: Path = SYS_VIDEO4LINUX_DIR,
    driver_path: Path = UVCVIDEO_DRIVER_DIR,
) -> UsbCameraTarget:
    video_sysfs_path = sys_video4linux_dir / device_path.name
    interface_path = _read_sysfs_link(video_sysfs_path / "device")
    interface_driver_path = _read_sysfs_link(interface_path / "driver")
    expected_driver_path = _read_sysfs_link(driver_path)

    if interface_driver_path != expected_driver_path:
        raise HotplugError(
            f"{device_path} is bound to {interface_driver_path}, not uvcvideo"
        )

    return UsbCameraTarget(
        device_path=device_path,
        physical_device_id=interface_path.name.split(":", maxsplit=1)[0],
        interface_id=interface_path.name,
        interface_path=interface_path,
        driver_path=expected_driver_path,
    )


def discover_uvc_camera_targets(
    *,
    sys_video4linux_dir: Path = SYS_VIDEO4LINUX_DIR,
    driver_path: Path = UVCVIDEO_DRIVER_DIR,
) -> list[UsbCameraTarget]:
    if not sys_video4linux_dir.exists():
        return []

    video_sysfs_paths = sorted(
        (
            video_sysfs_path
            for video_sysfs_path in sys_video4linux_dir.glob("video*")
            if video_sysfs_path.name[5:].isdecimal()
        ),
        key=lambda video_sysfs_path: int(video_sysfs_path.name[5:]),
    )

    targets_by_interface: dict[str, UsbCameraTarget] = {}
    for video_sysfs_path in video_sysfs_paths:
        device_path = Path("/dev") / video_sysfs_path.name
        try:
            target = get_usb_camera_target(
                device_path,
                sys_video4linux_dir=sys_video4linux_dir,
                driver_path=driver_path,
            )
        except HotplugError:
            continue
        targets_by_interface.setdefault(target.interface_id, target)

    return list(targets_by_interface.values())


def select_usb_camera_target() -> UsbCameraTarget:
    configured_device = os.environ.get(HOTPLUG_DEVICE_ENV, "").strip()
    if configured_device:
        return get_usb_camera_target(normalize_video_device_path(configured_device))

    targets = discover_uvc_camera_targets()
    if not targets:
        raise HotplugError(
            f"no uvcvideo /dev/videoN devices found; set {HOTPLUG_DEVICE_ENV}"
        )
    return targets[0]


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
