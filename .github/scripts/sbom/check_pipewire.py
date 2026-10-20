# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Check static PipeWire inventories against committed Dockerfile defaults.

Release builds must use these pins; build-argument overrides need separate review.
"""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote


def check_pipewire_inventory(service_directory: Path) -> None:
    dockerfile_text = (service_directory / "Dockerfile").read_text()
    build_pins = dict(
        re.findall(
            r"^ARG (PIPEWIRE_VERSION|PIPEWIRE_COMMIT)=(\S+)$",
            dockerfile_text,
            re.MULTILINE,
        )
    )
    expected_version = build_pins["PIPEWIRE_VERSION"]
    expected_commit = build_pins["PIPEWIRE_COMMIT"]

    if not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        raise ValueError("Expected a full PipeWire source commit")

    inventory_path = service_directory / "licenses/pipewire.cdx.json"
    inventory = json.loads(inventory_path.read_text())

    if inventory["bomFormat"] != "CycloneDX" or inventory["specVersion"] != "1.6":
        raise ValueError("Expected a CycloneDX 1.6 PipeWire inventory")

    (pipewire_component,) = inventory["components"]
    upstream_url = "https://gitlab.freedesktop.org/pipewire/pipewire"
    expected_package_url = (
        f"pkg:generic/pipewire@{expected_version}"
        f"?vcs_url=git+{upstream_url}.git@{expected_commit}"
    )
    expected_source_reference = {
        "type": "distribution",
        "url": f"{upstream_url}/-/archive/{expected_commit}/pipewire-{expected_commit}.tar.gz",
    }

    if (
        pipewire_component["name"] != "pipewire"
        or pipewire_component["version"] != expected_version
        or not isinstance(pipewire_component["purl"], str)
        or unquote(pipewire_component["purl"]) != expected_package_url
        or expected_source_reference not in pipewire_component["externalReferences"]
    ):
        raise ValueError("PipeWire pins changed: review licenses/pipewire.cdx.json")

    if pipewire_component["licenses"] != [{"license": {"id": "MIT"}}]:
        raise ValueError("Review the PipeWire inventory's license scope")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("services", type=Path, nargs="+", help="Service directories to check")
    args = parser.parse_args()

    for service_directory in args.services:
        try:
            check_pipewire_inventory(service_directory)
        except (OSError, ValueError, KeyError, TypeError) as error:
            parser.error(f"{service_directory}: {error}")


if __name__ == "__main__":
    main()
