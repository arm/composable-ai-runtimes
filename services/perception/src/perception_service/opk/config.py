# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from urllib.parse import urlparse

DEFAULT_OPK_COMM_HOST = "127.0.0.1"
DEFAULT_OPK_COMM_PORT = 7001


@dataclass(frozen=True)
class OpkCommEndpoint:
    host: str = DEFAULT_OPK_COMM_HOST
    port: int = DEFAULT_OPK_COMM_PORT

    def __post_init__(self) -> None:
        message = "opkcomm endpoint must contain a valid host and port"
        try:
            endpoint = urlparse(f"ws://{self.host}:{self.port}")
            port = endpoint.port
        except ValueError as error:
            raise ValueError(message) from error

        if endpoint.hostname != self.host.lower() or port != self.port or port == 0:
            raise ValueError(message)
