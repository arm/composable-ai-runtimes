# Cairn SDK

*A comprehensive development kit built for developers and agents to rapidly develop edge AI applications with containerisation in mind.*

## AI usability dashboard

The committed run history lives at `usability/history/history.json`.
A static GitHub Pages dashboard reads that file from `usability/site/index.html` and plots per-task:
- duration
- files used
- total tokens


Cairn SDK currently provides the following modules to simplify your development journey:

• 📷 [Camera](./services/camera/README.md)

• 📡 [Messaging](./services/messaging/README.md)

• 🧠 [Inference](./services/concordia/README.md)

• 🧩 [Core library (Rust/Python)](./lib/README.md)

• 📚 [Documentation](./docs-website/README.md)

Developer setup is available through VS Code Dev Containers for the camera service, Concordia service, and SDK library; see [`.devcontainer/README.md`](./.devcontainer/README.md).

⚠️ This project is in a proof of concept stage and not production-ready.

## Getting started

Cairn SDK is fully integrated with [topo](https://github.com/arm/topo) to help make setup and deployment as seamless as possible. To spin up a quick demo, follow one of our [examples](#examples) below or [create your own](#create-your-own-using-ai)

### Examples

#### Concordia Inference

[Run YOLO via Concordia](https://github.com/Arm-Debug/cairn-sdk-concordia/tree/activity-monitor) on your cameras video feed and visualise the output.

```bash
topo clone cairn_activity_monitor git:https://github.com/Arm-Debug/cairn-sdk-concordia.git#activity-monitor
cd cairn_activity_monitor
topo extend compose.yaml git:https://github.com/Arm-Debug/cairn-sdk.git#concordia-topo
topo deploy --target `input_target_device_here`
```

#### Vision Experience Kit

[Run a multi-model zero copy model suite](https://github.com/Arm-Debug/cairn-sdk-xpk-vision-kit.git) on your device, toggle models during runtime and visualise outputs/latency.

```bash
topo clone cairn_xpk_demo git:https://github.com/Arm-Debug/cairn-sdk-xpk-vision-kit.git
cd cairn_xpk_demo
git submodule update --init --recursive
topo extend compose.yaml git:https://github.com/Arm-Debug/cairn-sdk.git\#migrate-xpk-work
```

### Create your own using AI

Take the prompt below and run it using codex or any other LLM!

```bash
"Clone the https://github.com/Arm-Debug/cairn-sdk repository, and build a user application that utilises the various modules that are documented in docs-website/docs/ and defined in services/. Build the application on top of the user-application base and accompanying python lib and deploy it using the 'topo' tool to a a defined ssh target once defined. Ask your user if you cannot find 'topo'. Prefer a demo which shows a visual output via Web endpoints."
```
