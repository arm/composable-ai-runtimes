# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Print the Cairn service contract version."""

from __future__ import annotations

import argparse

from helpers import service_metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("service")
    return parser.parse_args()


def main() -> None:
    print(service_metadata(parse_args().service)["service_version"])


if __name__ == "__main__":
    main()
