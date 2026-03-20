from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Any, Self, cast

import redis.asyncio as redis_asyncio
from redis.asyncio.client import PubSub, Redis

logger = logging.getLogger(__name__)

type NotificationHandler = Callable[[str, Any], None | Awaitable[None]]


class NotificationClient:
    """Minimal async notification subscriber backed by Redis Pub/Sub."""

    def __init__(self, uri: str | None = None) -> None:
        self._uri = uri or "redis://localhost:6379/0"
        self._handlers: dict[str, NotificationHandler] = {}
        self._redis: Redis | None = None
        self._pubsub: PubSub | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._closed = False

    async def subscribe(self, channel: str, handler: NotificationHandler) -> None:
        self._require_open()
        await self._ensure_connected()
        self._handlers[channel] = handler
        pubsub = self._pubsub
        if pubsub is None:
            raise RuntimeError("PubSub was not initialized.")
        await pubsub.subscribe(channel)
        self._start_listener()

    async def unsubscribe(self, channel: str) -> None:
        self._handlers.pop(channel, None)
        if self._pubsub is not None:
            await self._pubsub.unsubscribe(channel)

    async def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        if self._listener_task is not None:
            self._listener_task.cancel()
            await asyncio.gather(self._listener_task, return_exceptions=True)

        if self._pubsub is not None:
            await self._pubsub.aclose()
            self._pubsub = None

        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def __aenter__(self) -> Self:
        self._require_open()
        await self._ensure_connected()
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def _ensure_connected(self) -> None:
        if self._pubsub is not None:
            return

        self._redis = cast(
            "Redis",
            redis_asyncio.from_url(
                self._uri,
                decode_responses=True,
                encoding="utf-8",
            ),
        )
        self._pubsub = self._redis.pubsub()

    def _start_listener(self) -> None:
        if self._listener_task is None or self._listener_task.done():
            self._listener_task = asyncio.create_task(
                self._listen(),
                name="cairn-notification-listener",
            )

    async def _listen(self) -> None:
        pubsub = self._pubsub
        if pubsub is None:
            raise RuntimeError("PubSub was not initialized.")

        while not self._closed:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0,
            )
            if message is None:
                continue

            channel = message.get("channel")
            if not isinstance(channel, str):
                continue

            handler = self._handlers.get(channel)
            if handler is None:
                continue

            try:
                result = handler(channel, message.get("data"))
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("Notification handler failed for %s.", channel)

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("NotificationClient is closed.")
