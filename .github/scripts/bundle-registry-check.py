# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Read-only availability checks for the artifacts selected by an SDK bundle."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Iterator
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urldefrag, urljoin, urlsplit

import requests
import yaml
from jsonschema import SchemaError, ValidationError, validate
from packaging.utils import InvalidWheelFilename, parse_wheel_filename

DOCKER_HUB_REGISTRY = "docker.io"


class RegistryError(Exception):
    """A registry check could not establish artifact availability."""


def registry_request(
    url: str,
    *,
    method: str = "GET",
    auth: tuple[str, str] | None = None,
    headers: dict[str, str] | None = None,
    missing_ok: bool = False,
) -> requests.Response | None:
    try:
        response = requests.request(
            method,
            url,
            auth=auth,
            headers=headers,
            timeout=30,
            allow_redirects=True,
        )
    except requests.RequestException as error:
        # Exception bodies can contain credentials or signed redirect URLs.
        raise RegistryError(
            f"{url}: {type(error).__name__}; cannot verify registry availability"
        ) from error

    match response.status_code:
        case 200:
            return response
        case 404 if missing_ok:
            return None
        case 401 | 403:
            raise RegistryError(
                f"{url}: HTTP {response.status_code}; check registry credentials, "
                "permissions, and network access"
            )
        case status:
            raise RegistryError(
                f"{url}: unexpected HTTP {status}; "
                "cannot verify registry availability"
            )


def require_artifact(
    url: str,
    *,
    auth: tuple[str, str] | None = None,
) -> None:
    if registry_request(url, method="HEAD", auth=auth, missing_ok=True) is None:
        raise RegistryError(f"{url}: HTTP 404; artifact is not published")


class WheelLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if (
            tag == "a"
            and "data-yanked" not in attributes
            and (href := attributes.get("href"))
        ):
            self.links.append(href)


def check_rust_version(version: str) -> None:
    """Check the parent crate through crates.io's public download endpoint."""
    # https://doc.rust-lang.org/cargo/reference/registry-index.html#index-configuration
    url = f"https://crates.io/api/v1/crates/arm-cairn/{version}/download"
    require_artifact(url)


def extract_arm64_wheel_urls(index: str, html: str, version: str) -> Iterator[str]:
    """Yield non-yanked Cairn ARM64 wheel URLs for the requested version."""
    parser = WheelLinks()
    parser.feed(html)
    for link in parser.links:
        url = urldefrag(urljoin(index, link))[0]
        filename = unquote(urlsplit(url).path.rsplit("/", 1)[-1])
        try:
            name, wheel_version, _, tags = parse_wheel_filename(filename)
        except InvalidWheelFilename as error:
            print(f"Skipping registry entry {filename!r}: {error}")
            continue
        if (
            name == "arm-cairn"
            and str(wheel_version) == version
            and any(tag.platform.endswith("_aarch64") for tag in tags)
        ):
            yield url


def check_python_version(version: str) -> None:
    """Check a non-yanked ARM64 wheel on public PyPI."""
    index = "https://pypi.org/simple/arm-cairn/"
    response = registry_request(
        index, headers={"Accept": "text/html"}, missing_ok=True
    )
    if response is None:
        raise RegistryError(f"{index}: HTTP 404; Python package is not published")
    errors = []
    for url in extract_arm64_wheel_urls(index, response.text, version):
        if registry_request(url, method="HEAD", missing_ok=True) is not None:
            return
        errors.append(f"{url}: HTTP 404; wheel file is not published")
    detail = (
        "; ".join(errors)
        if errors
        else "no non-yanked ARM64 wheel for this exact version"
    )
    raise RegistryError(f"{index}: {detail}")


def fetch_oci_manifest(
    reference: str, *, auth: tuple[str, str] | None = None, descriptor: bool = False
) -> str:
    """Fetch an OCI manifest or its descriptor as JSON through ORAS."""
    command = ["oras", "manifest", "fetch"]
    if descriptor:
        command.append("--descriptor")
    password = None
    if auth is not None:
        username, password = auth
        command.extend(["--username", username, "--password-stdin"])
    command.append(reference)

    try:
        result = subprocess.run(
            command,
            input=password,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except FileNotFoundError as error:
        raise RegistryError(
            "ORAS is required to verify OCI service artifacts"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise RegistryError(
            f"{reference}: ORAS timed out while fetching the manifest"
        ) from error
    except subprocess.CalledProcessError as error:
        raise RegistryError(
            f"{reference}: ORAS could not fetch the manifest; "
            "check the artifact reference, registry credentials, permissions, "
            "and network access"
        ) from error
    return result.stdout


def check_service_version(
    component: str,
    version: str,
    repository: str,
    *,
    auth: tuple[str, str] | None = None,
) -> str:
    """Check the versioned contract and return its verified image reference."""
    contract_tag = f"service-{version}"
    contract_reference = f"{repository}:{contract_tag}"
    manifest_json = fetch_oci_manifest(contract_reference, auth=auth)
    try:
        manifest = json.loads(manifest_json)
    except json.JSONDecodeError as error:
        raise RegistryError(
            f"{contract_reference}: contract manifest is not valid JSON"
        ) from error

    subject = manifest.get("subject") if isinstance(manifest, dict) else None
    digest = subject.get("digest") if isinstance(subject, dict) else None
    if not isinstance(digest, str) or not re.fullmatch(
        r"[a-z0-9]+(?:[+._-][a-z0-9]+)*:[A-Za-z0-9=_-]+", digest
    ):
        raise RegistryError(
            f"{contract_reference}: contract manifest has no valid image subject digest"
        )
    print(f"Verified {component} {version}: contract tag {contract_tag}")

    image_reference = f"{repository}@{digest}"
    fetch_oci_manifest(image_reference, auth=auth, descriptor=True)
    print(f"Verified {component} {version}: image {image_reference}")
    return image_reference


def check_dockerhub_version(
    component: str,
    version: str,
    namespace: str,
    *,
    auth: tuple[str, str] | None = None,
) -> str:
    """Check a service in Docker Hub, optionally using a username and access token."""
    if not namespace:
        raise RegistryError("--registry-namespace is required for service components")
    repository = f"{DOCKER_HUB_REGISTRY}/{namespace}/arm-cairn-{component}-service"
    return check_service_version(
        component,
        version,
        repository,
        auth=auth,
    )


def check_versions_for_component(
    components: dict[str, str], registry_namespace: str
) -> tuple[list[str], dict[str, str]]:
    errors = []
    service_images = {}
    for component, version in components.items():
        label = f"{component} {version}"
        try:
            match component:
                case "rust":
                    check_rust_version(version)
                    print(f"Verified {label}: arm-cairn")
                case "python":
                    check_python_version(version)
                    print(f"Verified {label}: ARM64 wheel")
                case "camera" | "messaging" | "perception":
                    image_reference = check_dockerhub_version(
                        component, version, registry_namespace
                    )
                    repository = image_reference.split("@", 1)[0]
                    service_images[f"{repository}:service-{version}"] = image_reference
                case _:
                    raise RegistryError("Unknown component")
        except RegistryError as error:
            errors.append(f"{label}: {error}")
    return errors, service_images


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Rust crates are checked on public crates.io without credentials. "
            "Python wheels are checked on public PyPI without credentials. "
            "Service images are read from public Docker Hub repositories using ORAS."
        ),
    )
    parser.add_argument("config", type=Path)
    parser.add_argument("--tag", required=True)
    parser.add_argument(
        "--registry-namespace",
        default="",
        help="Docker Hub namespace (required for services)",
    )
    parser.add_argument(
        "--service-images-output",
        type=Path,
        help="Write verified contract-to-image references as JSON after validation",
    )
    args = parser.parse_args()
    try:
        schema_path = (
            Path(__file__).resolve().parents[1]
            / "workflows/release-config/bundle-config.schema.yaml"
        )
        schema = yaml.safe_load(schema_path.read_text())
        bundle = yaml.safe_load(args.config.read_text())
        validate(instance=bundle, schema=schema)
        if args.tag != f"cairn/v{bundle['version']}":
            raise ValueError("The tag does not match the bundle version")
        errors, service_images = check_versions_for_component(
            bundle["components"],
            args.registry_namespace,
        )
        if errors:
            parser.exit(
                1, "".join(f"Bundle registry check failed: {error}\n" for error in errors)
            )
        if args.service_images_output is not None:
            args.service_images_output.write_text(json.dumps(service_images) + "\n")
    except (
        TypeError,
        ValueError,
        KeyError,
        OSError,
        yaml.YAMLError,
        SchemaError,
        ValidationError,
    ) as error:
        parser.exit(1, f"Bundle validation failed: {error}\n")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
