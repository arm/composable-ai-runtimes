# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import MagicMock, call, patch

import pytest

from perception_service.opk.frame_results import FRAME_RESULTS_ENCODING, FrameResultRecord
from perception_service.messaging.result_publisher import (
    RedisResultPublisher,
    ResultStats,
)
from perception_service.errors import ResourceExhaustedError
from perception_service.opk.config import OpkCommEndpoint
from perception_service.opk.endpoint_pool import OpkCommEndpointPool
from perception_service.opk.result_router import OpkResultRouter, ResultRoutingError

pytestmark = pytest.mark.unit


def record(frame_counter: int, packet: str = "QQ==") -> dict[str, object]:
    return {
        "frame_counter": frame_counter,
        "frame_results_encoding": FRAME_RESULTS_ENCODING,
        "frame_results_packet_b64": packet,
    }


def test_routes_concurrent_sessions_and_reuses_stopped_connection() -> None:
    publisher = MagicMock(spec=RedisResultPublisher)
    stats = ResultStats()
    first_ingress = MagicMock()
    second_ingress = MagicMock()

    with patch(
        "perception_service.opk.result_router.OpkIngress",
        side_effect=[first_ingress, second_ingress],
    ):
        pool = OpkCommEndpointPool(OpkCommEndpoint(port=7001), 2)
        router = OpkResultRouter(publisher, stats)
        first_lease = pool.reserve()
        second_lease = pool.reserve()
        first_lease.claim()
        second_lease.claim()
        router.start("session-a", first_lease)
        router.start("session-b", second_lease)

        router._accept_record("session-a", record(1, "QQ=="))
        router._accept_record("session-b", record(4, "Qg=="))
        router.stop("session-a")

        with pool.reserve() as reused_lease:
            assert reused_lease.endpoint == first_lease.endpoint
        router.close()

    assert (first_lease.endpoint.port, second_lease.endpoint.port) == (7001, 7002)
    assert publisher.submit.call_args_list == [
        call("session-a", FrameResultRecord(1, b"A")),
        call("session-b", FrameResultRecord(4, b"B")),
    ]
    first_ingress.stop.assert_called_once()
    second_ingress.stop.assert_called_once()


def test_invalid_records_and_frame_gaps_are_counted_per_session() -> None:
    publisher = MagicMock(spec=RedisResultPublisher)
    stats = ResultStats()

    with patch("perception_service.opk.result_router.OpkIngress"):
        pool = OpkCommEndpointPool(OpkCommEndpoint(), 1)
        router = OpkResultRouter(publisher, stats)
        lease = pool.reserve()
        lease.claim()
        router.start("session-a", lease)
        router._accept_record("session-a", record(2))
        router._accept_record("session-a", record(5))
        router._accept_record("session-a", record(6, "not-base64"))
        router.close()

    assert stats.snapshot()["source_frame_gaps"] == 2
    assert stats.snapshot()["parse_failures"] == 1


def test_start_failure_retains_endpoint_until_pipeline_cleanup() -> None:
    ingress = MagicMock()
    ingress.start.side_effect = RuntimeError("ingress failed")

    with patch("perception_service.opk.result_router.OpkIngress", return_value=ingress):
        pool = OpkCommEndpointPool(OpkCommEndpoint(), 1)
        lease = pool.reserve()
        lease.claim()
        router = OpkResultRouter(MagicMock(spec=RedisResultPublisher), ResultStats())

        with pytest.raises(
            ResultRoutingError, match="failed to start result routing"
        ) as error:
            router.start("session-a", lease)
        with pytest.raises(ResourceExhaustedError, match="all opkcomm result connections"):
            pool.reserve()

        assert isinstance(error.value.__cause__, RuntimeError)
        lease.release()
