<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

# Camera Smoke Helpers

This package contains shared Python helpers for the camera smoke tests under
`.github/scripts`.

## Hotplug Helper

The board-farm notification hotplug test unbinds and rebinds a selected UVC USB
camera interface to validate Redis `connected` and `disconnected` events.

The test relies on the board farm concurrency group giving the job exclusive
access to the camera setup. During the Redis subscription window, the only
matching hotplug event expected is the single intentional unbind or rebind action
performed by the test, so the assertions match events by `event_type`.

Hotplug is intentionally routed through a narrow privileged helper instead of
granting the workflow broad sudo access. By default, the helper path is:

```text
/usr/local/sbin/cairn-camera-hotplug
```

Override the helper path with `CAMERA_BOARDFARM_HOTPLUG_HELPER` when testing a
runner with a non-default installation.

The test invokes the helper with non-interactive sudo:

```text
sudo -n <helper> bind|unbind <usb-interface-id>
```

Runner provisioning must allow the GitHub Actions runner user to run that helper
without a password, and only for the helper contract above. Update the runner
sudoers entry and this note together if the helper path, actions, or argument
contract changes.
