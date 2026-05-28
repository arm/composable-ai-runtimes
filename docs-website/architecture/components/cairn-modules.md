---
id: cairn-modules
title: Cairn Modules
sidebar_position: 1
---

## What are Cairn Modules?

Cairn modules are the runtime building blocks of Cairn SDK. Each module provides a focused capability area (e.g. camera management, AI inference, or cross module messaging). Each module runs within a container and exposes stable interfaces to applications through the Cairn library and APIs.

## Purpose

- Provide clear, pre-packaged capabilities for common edge application needs.
- Separate concerns into clear runtime boundaries.
- Provide composability and flexibility in how capabilities are combined and extended.
- Keep user application integration points stable and consistent as internal implementations evolve.

## Contract model

Each Cairn module is expected to maintain explicit contracts:

- **API contracts**: request/response and streaming semantics exposed over documented interfaces.
- **Event contracts**: stable event names and payload shapes for module-driven notifications.
- **Operational contracts**: predictable startup behavior, health/failure signaling, and actionable logs.

When these contracts change, corresponding documentation and compatibility expectations should be updated together.

For more on modules, see [Modules](/modules/overview).
