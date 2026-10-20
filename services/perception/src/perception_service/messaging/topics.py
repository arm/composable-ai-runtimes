# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from typing import Literal

SessionTopic = Literal["results", "events"]


def session_topic(session_id: str, topic: SessionTopic) -> str:
    return f"cairn.perception.sessions.{session_id}.{topic}"
