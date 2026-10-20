# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Inventory reviewed bundled code/data in perception's NumPy and grpcio wheels."""

import argparse
import hashlib
import sys
import tomllib
from datetime import UTC, datetime
from importlib.metadata import distributions
from pathlib import Path
from typing import NotRequired, TypedDict, cast
from uuid import uuid4

from license_expression import Licensing, get_spdx_licensing
from spdx_tools.spdx.model import (
    Actor,
    ActorType,
    CreationInfo,
    Document,
    ExternalPackageRef,
    ExternalPackageRefCategory,
    Package,
    PackagePurpose,
    Relationship,
    RelationshipType,
    SpdxNoAssertion,
)
from spdx_tools.spdx.writer.write_anything import write_file


class Component(TypedDict):
    name: str
    license: str
    version: NotRequired[str]
    purpose: NotRequired[str]
    license_url: NotRequired[str]
    source_url: NotRequired[str]
    source_sha256: NotRequired[str]


class Payload(TypedDict):
    path: str
    sha256: str
    components: list[Component]


class WheelPackage(TypedDict):
    name: str
    version: str
    license_file: str
    license_sha256: str
    payloads: list[Payload]


def check_hash(path: Path, expected: str) -> None:
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"{path}: changed since review; update wheel_sbom.toml after reviewing the wheel")


def validate_wheel(site_packages: Path, package: WheelPackage, installed_version: str | None) -> None:
    name, version = package['name'], package['version']
    if installed_version != version:
        raise ValueError(f"{name}: expected reviewed version {version}, got {installed_version}; review wheel_sbom.toml")
    check_hash(site_packages / package['license_file'], package['license_sha256'])
    for payload in package['payloads']:
        check_hash(site_packages / payload['path'], payload['sha256'])


def build_component_package(
    site_packages: Path,
    package: WheelPackage,
    payload: Payload,
    component: Component,
    licensing: Licensing,
) -> Package:
    name, version = package['name'], package['version']
    purl = f"pkg:generic/{name}-bundled/{component['name']}"
    if 'version' in component:
        purl += f"@{component['version']}"
    description = (
        f"Bundled in {name} {version}: {payload['path']}. "
        "Reviewed subset, not an exhaustive linked dependency inventory. "
    )
    source_info = (
        f"Containing wheel: pkg:pypi/{name}@{version}; "
        f"payload: {site_packages / payload['path']}; "
        f"payload SHA256: {payload['sha256']}; "
        f"wheel license: {site_packages / package['license_file']}."
    )
    if 'source_url' in component:
        if not component.get('version') or not component.get('source_sha256'):
            raise ValueError(f"{component['name']}: source requires a reviewed version and archive checksum")
        source_info += f" Source archive SHA256: {component['source_sha256']}."
    else:
        description += "Exact source revision is unresolved."
    return Package(
        spdx_id=f"SPDXRef-{name}-{component['name']}",
        name=f"{name}-bundled/{component['name']}",
        version=component.get('version'),
        primary_package_purpose=PackagePurpose[component.get('purpose', 'LIBRARY')],
        download_location=component.get('source_url', SpdxNoAssertion()),
        files_analyzed=False,
        copyright_text=SpdxNoAssertion(),
        license_declared=licensing.parse(component['license'], validate=True),
        license_concluded=SpdxNoAssertion(),
        license_comment=(
            f"Upstream license evidence (not exact build provenance): {component['license_url']}"
            if 'license_url' in component else None
        ),
        external_references=[ExternalPackageRef(
            ExternalPackageRefCategory.PACKAGE_MANAGER, 'purl', purl,
        )],
        description=description,
        source_info=source_info,
    )


def generate(site_packages: Path, manifest: Path, output: Path) -> None:
    packages = cast(list[WheelPackage], tomllib.loads(manifest.read_text())['packages'])
    installed = {dist.metadata['Name']: dist.version for dist in distributions(path=[str(site_packages)])}
    licensing = get_spdx_licensing()
    components: list[Package] = []
    for package in packages:
        validate_wheel(site_packages, package, installed.get(package['name']))
        components.extend(
            build_component_package(site_packages, package, payload, component, licensing)
            for payload in package['payloads']
            for component in payload['components']
        )
    document = Document(
        creation_info=CreationInfo(
            spdx_version='SPDX-2.3',
            spdx_id='SPDXRef-DOCUMENT',
            name='perception-wheel-supplement',
            document_namespace=f'https://spdx.org/spdxdocs/cairn-wheels-{uuid4()}',
            creators=[Actor(ActorType.TOOL, 'cairn-wheel-sbom')],
            created=datetime.now(UTC),
        ),
        packages=components,
        relationships=[
            Relationship('SPDXRef-DOCUMENT', RelationshipType.DESCRIBES, entry.spdx_id)
            for entry in components
        ],
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    write_file(document, str(output))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site_packages', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        generate(args.site_packages, Path(__file__).with_suffix('.toml'), args.output)
    except (OSError, ValueError) as error:
        print(f'Wheel SBOM generation failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
