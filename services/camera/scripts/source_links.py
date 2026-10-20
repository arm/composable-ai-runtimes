# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Report the source-built PipeWire revision packaged with camera."""

import argparse
import json
import re
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Locally loaded service image")
    parser.add_argument("--output", type=Path, required=True, help="JSON source records")
    args = parser.parse_args()
    try:
        revision = subprocess.check_output(
            ["docker", "run", "--rm", "--network", "none", "--read-only",
             "--entrypoint", "cat", args.image, "/usr/share/doc/pipewire/source-revision"],
            text=True,
        ).strip()
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError("Expected one full PipeWire source commit")
        args.output.write_text(json.dumps([{
            "project": "PipeWire",
            "revision": revision,
            "source_url": f"https://gitlab.freedesktop.org/pipewire/pipewire/-/archive/{revision}/pipewire-{revision}.tar.gz",
        }]) + "\n")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Cannot resolve camera source links: {error}\n")


if __name__ == "__main__":
    main()
