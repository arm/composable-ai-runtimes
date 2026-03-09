---
id: message-bus
title: Message Bus Module
sidebar_position: 3
---

*Looking for endpoint contracts and schemas? See the [API Reference](/api).*

:::tip Why this module is useful
You can respond to events across all modules.
:::

:::info Want to have a try?
Check out the [Your First Program tutorial](/tutorials/getting-started/your-first-program) for a message-driven starting point.
:::

## About the Message Bus Module

The Message Bus Module provides pub/sub event distribution between Cairn modules and user applications. It is designed for lightweight notification workflows that decouple producers and consumers.

## Key Capabilities

- [Module Event Subscription](#module-event-subscription)

### Module Event Subscription

The Messaing module enables your application to subscribe to a plethora of lifecycle and system events emitted by other modules, such as camera connection events or inference completion notifications, allowing you to build reactive event-driven applications without tight coupling between components.

:::warning Placeholder code
```python
from cairn import messaging

def camera_connected_handler(event_data):
    print(f"Camera connected: {event_data}")

messaging.on_notification("camera_connected", callback=camera_connected_handler)
```
:::
