---
title: cairn_sdk.notification Module
description: Async notification client helpers for the Cairn SDK.
sidebar_position: 2
---

## Attributes

- `logger`: Module logger for notification client events and failures.
- `NotificationHandler`: `Callable[[str, Any], None | Awaitable[None]]`

## Classes

- [`NotificationClient`](#notificationclient)

## NotificationClient

Minimal async notification subscriber backed by Redis Pub/Sub.

### `NotificationClient(uri: str | None = None)`

Create a notification client. If `uri` is not provided, the client uses `redis://localhost:6379/0`.

### `subscribe(channel: str, handler: NotificationHandler) -> None`

Subscribe to a channel and register the handler that should run when a message arrives.

This method is asynchronous.

### `unsubscribe(channel: str) -> None`

Remove the subscription for a channel.

This method is asynchronous.

### `close() -> None`

Close the client and release any open Redis resources.

This method is asynchronous.
