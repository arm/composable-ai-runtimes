# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Link PipeWire, Eigen, and verified sources for bundled wheel components."""

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import NotRequired, TypedDict
from urllib.request import urlopen


class SourceRecord(TypedDict):
    project: str
    revision: str
    source_url: str
    license: NotRequired[str]


def wheel_sources(image: str) -> list[SourceRecord]:
    document = json.loads(subprocess.check_output(
        ["docker", "run", "--rm", "--network", "none", "--read-only",
         "--entrypoint", "cat", image, "/usr/share/cairn/sbom/wheel-sbom.spdx.json"],
        text=True,
    ))
    return [
        {
            "project": package["name"],
            "revision": package["versionInfo"],
            "source_url": package["downloadLocation"],
            "license": package["licenseDeclared"],
        }
        for package in document["packages"]
        if package["downloadLocation"] != "NOASSERTION"
    ]


def image_provenance(image: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--entrypoint",
            "python",
            image,
            "-c",
            (
                "from pathlib import Path\n"
                "paths = list(Path('/opt/opk/lib/opk').glob('libonnxruntime.so.*.provenance.json'))\n"
                "if len(paths) != 1:\n"
                "    raise RuntimeError('Expected one packaged ONNX Runtime provenance file')\n"
                "print(paths[0].read_text())\n"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"Cannot read ONNX Runtime provenance from {image}: {result.stderr}"
        )
    return result.stdout


def eigen_source(provenance: str) -> tuple[str, str]:
    version = json.loads(provenance)["library"].removeprefix("libonnxruntime.so.")
    port = (
        "https://raw.githubusercontent.com/microsoft/onnxruntime/"
        f"v{version}/cmake/vcpkg-ports/eigen3"
    )
    url = f"{port}/portfile.cmake"
    with urlopen(url, timeout=30) as response:
        recipe = response.read().decode("utf-8")
    revisions = re.findall(r"^\s*REF\s+([0-9a-f]{40})\s*$", recipe, re.MULTILINE)
    if len(revisions) != 1:
        raise ValueError(f"Expected one pinned Eigen revision in {url}")
    with urlopen(f"{port}/vcpkg.json", timeout=30) as response:
        license_name = json.load(response).get("license") or ""
    return revisions[0], license_name


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Locally loaded service image to inspect")
    parser.add_argument(
        "--output", type=Path, required=True, help="JSON source records"
    )
    args = parser.parse_args()
    try:
        pipewire_revision = subprocess.check_output(
            ["docker", "run", "--rm", "--network", "none", "--read-only",
             "--entrypoint", "cat", args.image, "/usr/share/doc/pipewire/source-revision"],
            text=True,
        ).strip()
        if not re.fullmatch(r"[0-9a-f]{40}", pipewire_revision):
            raise ValueError("Expected one full PipeWire source commit")
        provenance = image_provenance(args.image)
        revision, license_name = eigen_source(provenance)
        args.output.write_text(
            json.dumps(
                [
                    {
                        "project": "Eigen",
                        "revision": revision,
                        "license": license_name,
                        "source_url": f"https://gitlab.com/libeigen/eigen/-/archive/{revision}/eigen-{revision}.tar.gz",
                    },
                    {
                        "project": "PipeWire",
                        "revision": pipewire_revision,
                        "source_url": f"https://gitlab.freedesktop.org/pipewire/pipewire/-/archive/{pipewire_revision}/pipewire-{pipewire_revision}.tar.gz",
                    },
                    *wheel_sources(args.image),
                ]
            )
            + "\n"
        )
    except (OSError, KeyError, TypeError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Cannot resolve perception source links: {error}\n")


if __name__ == "__main__":
    main()
