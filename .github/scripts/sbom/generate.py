# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Generate and check service image SBOMs before uploading the image."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def image_platforms(layout: Path, image_digest: str) -> list[str]:
    result = subprocess.run(
        ["oras", "manifest", "fetch", "--oci-layout", f"{layout}@{image_digest}"],
        check=True,
        capture_output=True,
        text=True,
    )
    index = json.loads(result.stdout)
    platforms: list[str] = []
    for manifest in index["manifests"]:
        if manifest.get("annotations", {}).get("vnd.docker.reference.type") == (
            "attestation-manifest"
        ):
            continue
        platform = manifest["platform"]
        architecture = platform["architecture"]
        if (
            platform["os"] != "linux"
            or architecture not in ("arm64", "amd64")
            or architecture in platforms
        ):
            raise ValueError(
                "Expected one Linux image per supported architecture (arm64 or amd64)"
            )
        platforms.append(architecture)
    if not platforms:
        raise ValueError("Image index contains no platform images")
    return platforms


def add_disclaimer(sbom_path: Path, disclaimer: str) -> None:
    document = json.loads(sbom_path.read_text(encoding="utf-8"))
    if (
        document.get("spdxVersion") != "SPDX-2.3"
        or document.get("SPDXID") != "SPDXRef-DOCUMENT"
    ):
        raise ValueError(f"{sbom_path}: expected an SPDX 2.3 document")
    comment = document.get("comment")
    if comment is None:
        comment = ""
    if not isinstance(comment, str):
        raise TypeError(f"{sbom_path}: expected a string comment")
    document["comment"] = f"{comment}\n\n{disclaimer}" if comment else disclaimer
    sbom_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def generate_sbom(layout: Path, architecture: str, disclaimer: str) -> None:
    sbom_path = layout / f"sbom-{architecture}.spdx.json"
    subprocess.run(
        [
            "syft",
            "scan",
            f"oci-dir:{layout}",
            "--platform",
            f"linux/{architecture}",
            "--select-catalogers",
            "+sbom-cataloger",
            "-o",
            f"spdx-json={sbom_path}",
        ],
        check=True,
        env={
            **os.environ,
            "SYFT_CHECK_FOR_APP_UPDATE": "false",
            "SYFT_GOLANG_SEARCH_REMOTE_LICENSES": "true",
        },
    )
    add_disclaimer(sbom_path, disclaimer)


def attach_sbom_bundle(
    layout: Path, image_digest: str, platforms: list[str], disclaimer: str,
    rust_sbom: Path | None,
) -> None:
    if rust_sbom is not None:
        document = json.loads(rust_sbom.read_text())
        targets = [
            prop["value"] for prop in document["metadata"]["properties"]
            if prop["name"] == "cdx:rustc:sbom:target:triple"
        ]
        if document.get("bomFormat") != "CycloneDX" or len(targets) != 1:
            raise ValueError("Expected a CycloneDX Rust SBOM with one target triple")
        architecture = {"aarch64": "arm64", "x86_64": "amd64"}.get(targets[0].split("-")[0])
        if "-linux-" not in targets[0] or platforms != [architecture]:
            raise ValueError("Rust SBOM target must match the image's single Linux platform")
    with ZipFile(layout / "sbom.zip", "w", compression=ZIP_DEFLATED) as bundle:
        for architecture in platforms:
            name = f"sbom-{architecture}.spdx.json"
            bundle.write(layout / name, name)
        if rust_sbom is not None:
            bundle.write(rust_sbom, "rust.cyclonedx.json")
        bundle.writestr("SBOM-DISCLAIMER.txt", disclaimer)
    subprocess.run(
        [
            "oras",
            "attach",
            "--oci-layout",
            "--artifact-type",
            "application/vnd.cairn.sbom-bundle",
            f"{layout}@{image_digest}",
            "sbom.zip:application/zip",
        ],
        cwd=layout,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("layout", type=Path)
    parser.add_argument("image_digest")
    parser.add_argument("disclaimer", type=Path)
    parser.add_argument("--rust-sbom", type=Path, help="Target-specific cargo-cyclonedx JSON")
    args = parser.parse_args()
    try:
        disclaimer = args.disclaimer.read_bytes().decode("utf-8")
        if not disclaimer.strip():
            raise ValueError("SBOM disclaimer is empty")
        layout = args.layout.resolve()
        platforms = image_platforms(layout, args.image_digest)
        for architecture in platforms:
            generate_sbom(layout, architecture, disclaimer)
        attach_sbom_bundle(layout, args.image_digest, platforms, disclaimer, args.rust_sbom)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.CalledProcessError,
    ) as error:
        detail = (
            error.stderr
            if isinstance(error, subprocess.CalledProcessError)
            else str(error)
        )
        print(f"SBOM generation failed: {detail or error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
