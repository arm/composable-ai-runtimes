---
sidebar_position: 2
---

# Getting Started

This tutorial is the main starting point for building your own Cairn SDK application.

It uses the [`cairn-sdk-getting-started`](https://github.com/Arm-Debug/cairn-sdk-getting-started) project, which gives you a minimal user application with an intentionally simple `app/app.py` entry point for you to add your own code.

After completing this tutorial you will know how to:

- Setup, build and extend a Cairn-enabled application
- Deploy a Cairn-enabled application to a real device using `topo`

## Before you begin

You will need:

- [`topo`](https://github.com/arm/topo) installed and available on your machine
- an SSH target for the device you want to deploy to
- access to the [Cairn SDK repository](https://github.com/Arm-Debug/cairn-sdk) and the [getting-started](https://github.com/Arm-Debug/cairn-sdk-getting-started) repository

## 1. Clone the Getting Started project

Start from the dedicated getting-started repository:

```bash
topo clone cairn_getting_started git:https://github.com/Arm-Debug/cairn-sdk-getting-started.git
cd cairn_getting_started
```

## 2. Extend it with Cairn SDK services

The getting-started project is intentionally minimal. You add the Cairn SDK service stack by extending its `compose.yaml` with the Cairn SDK:

```bash
topo extend compose.yaml git:https://github.com/Arm-Debug/cairn-sdk.git#concordia-topo
```

At this point you will have a simple application container and the Cairn services it depends on.


## 3. Start with a simple application shape

Use a very small first program that proves your application can talk to the Cairn SDK clients and shows exactly where to add your own application logic and how to integrate with the SDK APIs.

```python title="app/app.py"
from cairn_sdk import CameraService, ConcordiaService


def main():
    camera_service = CameraService()
    inference_service = ConcordiaService()

    cameras = camera_service.list_camera_metadata()
    print(f"Discovered {len(cameras)} camera(s)")

    if not cameras:
        raise RuntimeError("No cameras found")
    # Add your application logic here.
    # For example:
    # - open a camera
    # - read a frame
    # - send it to Concordia
    # - handle the result


if __name__ == "__main__":
    main()
```

## 4. Deploy to your device

Once you are happy with your application code, deploy it with `topo`:

```bash
topo deploy --target <ssh_target>
```

and to see if its running run:

```bash
docker -H ssh://user@host compose ps -a
```

Replace `<ssh_target>` with the SSH target for your device.

### Cleaning Up

To clean up your deployment you can run:

```bash
topo stop --target <ssh_target>
```

## Next steps

After you have a basic application running, try one of the more complete example repositories:

### Concordia example project

[`cairn-sdk-concordia`](https://github.com/Arm-Debug/cairn-sdk-concordia) shows a more focused inference-led flow using Concordia.

### Vision Experience Kit

[`cairn-sdk-xpk-vision-kit`](https://github.com/Arm-Debug/cairn-sdk-xpk-vision-kit) is a broader vision demo with multiple models and runtime interaction.

## See also

- [Object Detection](/tutorials/getting-started/object-detection)
- [Modules Overview](/modules/overview)
- [API Reference](/api)
