# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import pytest

from perception_service.errors import ResourceExhaustedError
from perception_service.opk.config import OpkCommEndpoint
from perception_service.opk.endpoint_pool import OpkCommEndpointPool

pytestmark = pytest.mark.unit


def test_endpoint_lease_releases_unclaimed_and_retains_claimed_ports() -> None:
    pool = OpkCommEndpointPool(OpkCommEndpoint(port=7001), 1)

    with pool.reserve() as lease:
        assert lease.endpoint.port == 7001

    claimed = pool.reserve()
    claimed.claim()
    with pytest.raises(ResourceExhaustedError, match="all opkcomm result connections are in use"):
        pool.reserve()

    claimed.release()
    with pool.reserve() as reused:
        assert reused.endpoint.port == 7001
