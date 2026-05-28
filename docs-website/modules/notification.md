---
id: notification
title: Notification Module
sidebar_position: 3
---

*Looking for endpoint contracts and schemas? See the [API Reference](/api).*

:::tip Why this module is useful
You can respond to events across all modules.
:::

:::info Want to have a try?
Check out the [Your First Program tutorial](/tutorials/getting-started/your-first-program) for an event driven starting point.
:::

## About the Notification Module

The Notification module delivers transient notifications between Cairn modules and user applications. It is designed for lightweight event-driven workflows that decouple producers and consumers.

## Key Capabilities

- [Module Event Subscription](#module-event-subscription)
- [Subscription Lifecycle](#subscription-lifecycle)

### Module Event Subscription

The Notification module enables your application to subscribe to lifecycle and system events emitted by other modules, such as camera connection events or inference completion notifications, allowing you to build reactive event-driven applications without tight coupling between components.

```python
import asyncio
from notification_client import NotificationClient

async def on_camera_connected(channel: str, data: str):
    print(f"[{channel}] {data}")

async def main():
    client = NotificationClient()
    client.subscribe("camera.connected", on_camera_connected)

    try:
        await asyncio.sleep(999999)
    finally:
        client.unsubscribe("camera.connected")

asyncio.run(main())
```
:::

### Subscription Lifecycle

Subscriptions are async-only. Register one handler per channel with `subscribe(channel, handler)`, and remove it with `unsubscribe(channel)` when your application shuts down or no longer needs the notification stream.
