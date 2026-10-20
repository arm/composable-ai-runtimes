# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Render release notes for a validated SDK bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import NotRequired, TypedDict

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError

TEMPLATE_ENVIRONMENT = Environment(
    loader=FileSystemLoader(
        Path(__file__).resolve().parents[1] / "workflows/release-config"
    ),
    undefined=StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)


class Bundle(TypedDict):
    version: str
    components: dict[str, str]
    notes: NotRequired[str]


def release_notes(
    bundle: Bundle,
    cargo_package_url: str,
    pypi_package_url: str,
    registry_namespace: str,
    *,
    service_images: dict[str, str] | None = None,
) -> str:
    """Render the selected versions and their registry locations as Markdown."""
    for component in bundle["components"]:
        if component == "rust" and not cargo_package_url:
            raise ValueError("--cargo-package-url is required for Rust components")
        if component == "python" and not pypi_package_url:
            raise ValueError("--pypi-package-url is required for Python components")
        if component not in ("rust", "python") and not registry_namespace:
            raise ValueError("--registry-namespace is required for service components")
    template = TEMPLATE_ENVIRONMENT.get_template("bundle-release-notes.md.j2")
    return template.render(
        version=bundle["version"],
        notes=bundle.get("notes", ""),
        components=bundle["components"],
        cargo_package_url=cargo_package_url,
        pypi_package_url=pypi_package_url,
        registry_namespace=registry_namespace,
        service_images=service_images if service_images is not None else {},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--cargo-package-url",
        default="",
        help="Package URL template with {version} (required for Rust)",
    )
    parser.add_argument(
        "--pypi-package-url",
        default="",
        help="Package URL template with {version} (required for Python)",
    )
    parser.add_argument(
        "--registry-namespace",
        default="",
        help="Docker Hub namespace (required for services)",
    )
    parser.add_argument(
        "--service-images",
        default="{}",
        help="JSON map of verified contract-to-image references (required for services)",
    )
    args = parser.parse_args()
    try:
        bundle: Bundle = yaml.safe_load(args.config.read_text())
        service_images = json.loads(args.service_images)
        if not isinstance(service_images, dict) or any(
            not isinstance(contract, str) or not isinstance(image, str) or not image
            for contract, image in service_images.items()
        ):
            raise ValueError("--service-images must be a JSON object of image references")
        notes = release_notes(
            bundle,
            args.cargo_package_url,
            args.pypi_package_url,
            args.registry_namespace,
            service_images=service_images,
        )
        args.output.write_text(notes)

    except (TypeError, ValueError, KeyError, OSError, yaml.YAMLError, TemplateError) as error:
        parser.exit(1, f"Release note generation failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
