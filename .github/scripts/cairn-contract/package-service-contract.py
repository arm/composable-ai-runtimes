# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Package a Cairn service contract as a tar archive."""

from __future__ import annotations

import argparse
import sys
import tarfile
from pathlib import Path

from helpers import (
    EXIT_FAILURE,
    EXIT_SUCCESS,
    REPO_ROOT,
    reference_error,
    referenced_contract_files,
    service_metadata,
)


def add_tar_file(tar: tarfile.TarFile, source: Path, name: str) -> None:
    info = tar.gettarinfo(str(source), name)
    info.mtime = 0
    with source.open("rb") as file:
        tar.addfile(info, file)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("service")
    parser.add_argument("output_tar", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    service_dir = REPO_ROOT / "services" / args.service
    files = ["compose.yaml", *referenced_contract_files(service_metadata(args.service))]

    sources = []
    for file in files:
        if error := reference_error(service_dir, file):
            print(error, file=sys.stderr)
            return EXIT_FAILURE
        sources.append((file, service_dir / file))

    args.output_tar.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(args.output_tar, "w") as tar:
        for file, source in sources:
            add_tar_file(tar, source, file)

    print("\n".join(files))
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
