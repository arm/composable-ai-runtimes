# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from jsonschema import Draft202012Validator

from cairn.messaging.v1.messaging_pb2 import CairnEvent
from perception_service.messaging.lifecycle import (
    LifecyclePublisher,
    SessionState,
    StageState,
)
from perception_service.messaging.result_publisher import RedisEventPublisher

pytestmark = pytest.mark.unit


def published_events(publisher: MagicMock) -> list[CairnEvent]:
    return [call.args[0] for call in publisher.submit.call_args_list]


def test_lifecycle_event_format() -> None:
    redis_publisher = MagicMock(spec=RedisEventPublisher)
    lifecycle = LifecyclePublisher(redis_publisher)
    topic = lifecycle.start_session("session-a", ["objects"], enabled=True)

    lifecycle.publish_stage("session-a", "objects", StageState.DISABLED)

    starting, disabled = published_events(redis_publisher)
    schema = json.loads(
        (
            Path(__file__).parents[2] / "schemas/perception-lifecycle-event.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    starting_payload = json.loads(starting.payload)
    disabled_payload = json.loads(disabled.payload)
    validator.validate(starting_payload)
    validator.validate(disabled_payload)

    assert starting.origin == "cairn.perception-service"
    assert starting.event_type == "cairn.perception.session.starting"
    assert starting.topic == topic
    assert starting_payload == {
        "session_id": "session-a",
        "state": "starting",
    }
    assert disabled.event_type == "cairn.perception.stage.disabled"
    assert topic == "cairn.perception.sessions.session-a.events"
    assert disabled.topic == "cairn.perception.sessions.session-a.events"
    assert disabled_payload == {
        "session_id": "session-a",
        "stage_id": "objects",
        "state": "disabled",
    }
    assert starting.HasField("timestamp")
    assert disabled.HasField("timestamp")


def test_sessions_and_stages_are_isolated() -> None:
    redis_publisher = MagicMock(spec=RedisEventPublisher)
    lifecycle = LifecyclePublisher(redis_publisher)
    lifecycle.start_session("session-a", ["objects"], enabled=True)
    lifecycle.start_session("session-b", ["poses"], enabled=True)

    lifecycle.publish_session("session-a", SessionState.RUNNING)
    lifecycle.publish_stage("session-a", "poses", StageState.DISABLED)
    lifecycle.publish_session("session-b", SessionState.FAILED, "poses")

    events = published_events(redis_publisher)
    assert [event.topic for event in events] == [
        "cairn.perception.sessions.session-a.events",
        "cairn.perception.sessions.session-b.events",
        "cairn.perception.sessions.session-a.events",
        "cairn.perception.sessions.session-b.events",
    ]
    assert events[-1].event_type == "cairn.perception.session.failed"
    assert json.loads(events[-1].payload)["stage_id"] == "poses"


def test_finished_and_disabled_sessions_are_noops() -> None:
    redis_publisher = MagicMock(spec=RedisEventPublisher)
    lifecycle = LifecyclePublisher(redis_publisher)
    disabled_topic = lifecycle.start_session("disabled", ["objects"], enabled=False)
    active_topic = lifecycle.start_session("active", ["objects"], enabled=True)
    redis_publisher.reset_mock()

    lifecycle.publish_session("disabled", SessionState.RUNNING)
    lifecycle.publish_session("active", SessionState.STOPPED)
    lifecycle.publish_session("active", SessionState.RUNNING)
    lifecycle.publish_session("active", SessionState.FAILED)

    assert disabled_topic == ""
    events = published_events(redis_publisher)
    assert [event.event_type for event in events] == [
        "cairn.perception.session.stopped"
    ]
    assert active_topic == "cairn.perception.sessions.active.events"
