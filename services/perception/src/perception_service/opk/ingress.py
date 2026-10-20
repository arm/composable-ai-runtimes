# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterable
from types import TracebackType
from typing import Any, Self

from loguru import logger
from perception_service.opk.config import (
    DEFAULT_OPK_COMM_HOST,
    DEFAULT_OPK_COMM_PORT,
)
from websockets.exceptions import WebSocketException
from websockets.sync.client import ClientConnection, connect

DEFAULT_MAX_RECORD_BYTES = 1024 * 1024
MAX_RECONNECT_DELAY_SECONDS = 30.0

RecordHandler = Callable[[dict[str, Any]], None]
DropHandler = Callable[[], None]


def consume_messages(
    messages: Iterable[str | bytes],
    on_record: RecordHandler,
    on_drop: DropHandler | None = None,
) -> None:
    drop = on_drop or (lambda: None)
    for message in messages:
        try:
            record = json.loads(message)
        except (ValueError, RecursionError) as error:
            logger.warning("Dropping malformed OPK result record: {}", error)
            drop()
            continue

        if not isinstance(record, dict):
            logger.warning("Dropping OPK result record that is not a JSON object")
            drop()
            continue

        try:
            on_record(record)
        except Exception:
            logger.exception(
                "OPK result handler failed; continuing with the next record"
            )


class OpkIngress:
    def __init__(
        self,
        on_record: RecordHandler,
        host: str = DEFAULT_OPK_COMM_HOST,
        port: int = DEFAULT_OPK_COMM_PORT,
        max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
        reconnect_delay_seconds: float = 1.0,
        on_drop: DropHandler | None = None,
    ) -> None:
        if max_record_bytes < 1:
            raise ValueError("max_record_bytes must be positive")
        self._on_record = on_record
        self._host = host
        self._port = port
        self._max_record_bytes = max_record_bytes
        self._reconnect_delay_seconds = reconnect_delay_seconds
        self._on_drop = on_drop
        self._stop = threading.Event()
        self._connection_lock = threading.Lock()
        self._connection: ClientConnection | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="opk-ingress", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._connection_lock:
            if self._connection is not None:
                self._connection.close()
        if self._thread is not None:
            self._thread.join()
            self._thread = None

    def _run(self) -> None:
        uri = f"ws://{self._host}:{self._port}/ws"
        reconnect_delay = self._reconnect_delay_seconds
        while not self._stop.is_set():
            try:
                with connect(
                    uri,
                    open_timeout=1,
                    close_timeout=1,
                    max_size=self._max_record_bytes,
                    proxy=None,
                ) as connection:
                    with self._connection_lock:
                        if self._stop.is_set():
                            return
                        self._connection = connection
                    reconnect_delay = self._reconnect_delay_seconds
                    logger.info("Connected to OPK result stream at {}", uri)
                    consume_messages(connection, self._on_record, self._on_drop)
            except (OSError, TimeoutError, WebSocketException) as error:
                if not self._stop.is_set():
                    logger.warning("OPK result stream failed: {}", error)
            finally:
                with self._connection_lock:
                    self._connection = None

            if not self._stop.is_set():
                logger.info(
                    "OPK result stream disconnected; reconnecting in {} seconds",
                    reconnect_delay,
                )
                self._stop.wait(reconnect_delay)
                reconnect_delay = min(
                    reconnect_delay * 2, MAX_RECONNECT_DELAY_SECONDS
                )

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()
