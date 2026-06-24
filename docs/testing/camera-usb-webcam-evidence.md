# USB Webcam Board-Farm Evidence

This note records the evidence used to promote the board-farm Lenovo USB
webcam target in [camera-test.md](camera-test.md) to `Supported`.

## Summary

| Field | Evidence |
| --- | --- |
| Result | Passed |
| Candidate SHA | `d6368de5d7d0498cef01acde48931d25eb64d2c8` |
| Workflow | [`Camera Smoke` run 28029927449](https://github.com/Arm-Debug/cairn-sdk/actions/runs/28029927449) |
| Discovery job | [`Validate camera discovery on Pi board farm`](https://github.com/Arm-Debug/cairn-sdk/actions/runs/28029927449/job/82967530071) |
| Direct capture job | [`Validate direct PipeWire frame capture on Pi board farm`](https://github.com/Arm-Debug/cairn-sdk/actions/runs/28029927449/job/82967529722) |
| Board hardware | `Raspberry Pi 5 Model B Rev 1.1` |
| Board hostname | `devx-cairn01` |
| Board OS image | Raspberry Pi OS 64-bit `trixie` board-farm image; `/etc/os-release` reports `Debian GNU/Linux 13 (trixie)` |
| Board kernel | `6.12.75+rpt-rpi-2712` |
| Camera model | Lenovo Performance FHD Webcam (`4XC1D66055`) |
| Accepted waivers | None |

## Camera Discovery

The `camera-boardfarm-list-cameras-smoke-results` artifact from the workflow
run recorded a successful `CameraService.list_cameras` response after the
camera service started and accepted TCP connections on `127.0.0.1:50051`.

| Camera name | Supported formats |
| --- | --- |
| `Lenovo Performance Camera` | `Mjpg`, `YUY2` |
| `Lenovo Performance Camera` | `GRAY8` |

The workflow metadata reported:

- `list_cameras_exit_code`: `0`
- `list_cameras_validation_result`: `camera names matched expectations`
- `result`: `passed`

## Direct PipeWire Capture

The `camera-boardfarm-pipewire-capture-smoke-results` artifact recorded one
successful direct PipeWire frame capture from the Lenovo target. The capture
settings below are the negotiated values from that smoke run, not a fixed
camera configuration contract.

| Field | Observed value |
| --- | --- |
| Selected camera | `Lenovo Performance Camera` |
| PipeWire target object | `v4l2_input.platform-xhci-hcd.1-usb-0_1_1.0` |
| Capture result | `passed` |
| Capture exit code | `0` |
| Captured frame format | `I420` |
| Captured frame size | `640x480` |
| Captured frame rate | `30/1` |

## V4L2 And Version Collection

Read-only host checks were collected from `devx-cairn-01@10.2.3.43` after the
workflow artifact review. The host reported:

| Command | Evidence |
| --- | --- |
| `hostname` | `devx-cairn01` |
| `cat /proc/device-tree/model` | `Raspberry Pi 5 Model B Rev 1.1` |
| `cat /etc/os-release` | `PRETTY_NAME="Debian GNU/Linux 13 (trixie)"`; `DEBIAN_VERSION_FULL=13.4` |
| `uname -a` | `Linux devx-cairn01 6.12.75+rpt-rpi-2712 #1 SMP PREEMPT Debian 1:6.12.75-1+rpt1 (2026-03-11) aarch64 GNU/Linux` |
| `pipewire --version` | Compiled and linked with `libpipewire 1.4.2` |
| `wireplumber --version` | Compiled and linked with `libwireplumber 0.5.8` |
| `rpicam-hello --version` | `rpicam-apps build: v1.11.1 02-02-2026 (18:47:33)`; `libcamera build: v0.7.0+rpt20260205` |
| `v4l2-ctl --version` | `v4l2-ctl 1.30.1` |
| `lsusb` | `Bus 003 Device 002: ID 17ef:4839 Lenovo Lenovo Performance Camera` |

`v4l2-ctl --list-devices` reported the Lenovo webcam as:

```text
Lenovo Performance Camera: Leno (usb-xhci-hcd.1-1):
        /dev/video0
        /dev/video1
        /dev/video2
        /dev/video3
        /dev/media3
        /dev/media4
```

The Lenovo-related V4L2 nodes reported these supported formats:

| Device | Supported formats observed |
| --- | --- |
| `/dev/video0` | `MJPG`, including `1920x1080` at 30 FPS; `YUYV`/YUY2 |
| `/dev/video2` | `GREY` at `640x480` 30 FPS |

The V4L2 collection confirms the expected FHD `1920x1080` MJPEG 30 FPS mode
and YUYV/YUY2 video coding for the board-farm Lenovo USB webcam target.
