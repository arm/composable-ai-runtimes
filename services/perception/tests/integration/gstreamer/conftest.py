# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0


from collections.abc import Iterator

import pytest
from loguru import logger


@pytest.fixture
def log_messages() -> Iterator[list[str]]:
    messages: list[str] = []
    sink_id = logger.add(lambda message: messages.append(message.record["message"]))
    try:
        yield messages
    finally:
        logger.remove(sink_id)
