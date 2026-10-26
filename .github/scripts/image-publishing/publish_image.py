# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Mount unchanged upstream layers and publish without their payloads."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def publish_image(
    *, oci_layout_dir: Path, image_digest: str, destination_repository: str, existing_layer_digests: list[str]
) -> None:
    oci_layout_dir = oci_layout_dir.resolve()
    excluded_paths = {
        oci_layout_dir / "blobs" / digest.replace(":", "/", 1)
        for digest in existing_layer_digests
    }

    def omit_existing_layers(directory: str, names: list[str]) -> set[str]:
        return {name for name in names if Path(directory) / name in excluded_paths}

    # Withhold existing payloads so ORAS cannot upload them if the destination changes.
    with tempfile.TemporaryDirectory(prefix="publish-", dir=oci_layout_dir.parent) as temporary:
        upload_layout = Path(temporary) / "image"
        shutil.copytree(oci_layout_dir, upload_layout, copy_function=os.link, ignore=omit_existing_layers)
        subprocess.run(
            ["oras", "cp", "--recursive", "--from-oci-layout",
             f"{upload_layout}@{image_digest}", f"{destination_repository}@{image_digest}"],
            check=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oci-layout-dir", type=Path, required=True, help="Exported OCI image layout directory")
    parser.add_argument("--destination-repository", required=True, help="Registry/repository, without tag or digest")
    parser.add_argument("--layer-source-metadata", type=Path, required=True, help="Image digest and build inputs extracted from Buildx metadata")
    args = parser.parse_args()
    try:
        result = subprocess.run(
            ["go", "run", "-mod=readonly", ".",
             "--layer-source-metadata", str(args.layer_source_metadata.resolve()),
             "--oci-layout-dir", str(args.oci_layout_dir.resolve()),
             "--destination-repository", args.destination_repository],
            cwd=Path(__file__).resolve().with_name("existing-layer-mounting"),
            stdout=subprocess.PIPE, text=True, check=True,
        )
        existing_layer_info = json.loads(result.stdout)
        publish_image(
            oci_layout_dir=args.oci_layout_dir, image_digest=existing_layer_info["image_digest"],
            destination_repository=args.destination_repository, existing_layer_digests=existing_layer_info["existing_layer_digests"],
        )
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        detail = error.stderr if isinstance(error, subprocess.CalledProcessError) and error.stderr else str(error)
        print(f"Image publication failed: {detail}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
