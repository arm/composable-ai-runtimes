<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

# arm-composable-ai-runtimes

Rust client library for [Composable AI Runtimes (Cairn)](https://github.com/arm/composable-ai-runtimes).
Cairn provides runtime services for edge and physical AI applications on Arm Linux
devices. Use this crate to discover cameras, deploy inference workflows through consistent Rust APIs. Its camera, perception, and messaging services reduce the boilerplate needed to discover cameras, run inference workflows, and receive detection events.

The library is imported as `cairn` and groups its APIs by service:

- `cairn::camera_service`: discover cameras and available stream configurations.
- `cairn::perception_service`: validate and deploy inference workflows, manage
  sessions, and decode perception results.
- `cairn::notification_service`: subscribe to event notifications over Redis.

## License

Licensed under [Apache-2.0](https://github.com/arm/composable-ai-runtimes/blob/main/LICENSE).
