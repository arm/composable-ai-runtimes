# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Package a Cairn service contract as a tar archive."""

from __future__ import annotations

import argparse
import sys
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

import grpc_tools
from google.protobuf.descriptor_pb2 import FileDescriptorSet
from grpc_tools import protoc
from helpers import (
    EXIT_FAILURE,
    EXIT_SUCCESS,
    REPO_ROOT,
    reference_error,
    referenced_contract_files,
    service_metadata,
)


def resolve_proto_sources(entry_points: list[Path]) -> dict[str, Path]:
    if not entry_points:
        return {}

    # Resolve repository contracts from the checked-out release revision.
    roots = sorted((REPO_ROOT / "services").glob("*/proto"))
    # Include standard protobuf imports such as google/protobuf/timestamp.proto.
    roots.append(Path(grpc_tools.__file__).parent / "_proto")
    with TemporaryDirectory() as temporary:
        descriptor_path = Path(temporary) / "contracts.pb"
        return_code = protoc.main(
            [
                "protoc",
                *(f"--proto_path={root}" for root in roots),
                f"--descriptor_set_out={descriptor_path}",
                "--include_imports",
                *(str(path) for path in entry_points),
            ]
        )
        if return_code:
            raise ValueError("cannot resolve service protobuf contracts and their imports")
        descriptors = FileDescriptorSet.FromString(descriptor_path.read_bytes())

    sources: dict[str, Path] = {}
    for descriptor in descriptors.file:
        name = descriptor.name
        matches = [root for root in roots if (root / name).is_file()]
        if len(matches) != 1:
            raise ValueError(
                f"{name}: expected one protobuf source, found {len(matches)}"
            )
        root = matches[0]
        if error := reference_error(root, name):
            raise ValueError(error)
        sources[f"proto/{name}"] = root / name
    return sources


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

    sources: dict[str, Path] = {}
    for file in files:
        if error := reference_error(service_dir, file):
            print(error, file=sys.stderr)
            return EXIT_FAILURE
        sources[file] = service_dir / file

    try:
        sources.update(
            resolve_proto_sources(
                [source for source in sources.values() if source.suffix == ".proto"]
            )
        )
    except ValueError as error:
        print(error, file=sys.stderr)
        return EXIT_FAILURE

    args.output_tar.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(args.output_tar, "w") as tar:
        for file, source in sorted(sources.items()):
            add_tar_file(tar, source, file)

    print("\n".join(sorted(sources)))
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
