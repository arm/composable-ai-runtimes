# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Validate Cairn service metadata in Compose manifests."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from helpers import (
    EXIT_FAILURE,
    EXIT_SUCCESS,
    REPO_ROOT,
    reference_error,
    referenced_contract_files,
)
from jsonschema import Draft202012Validator

DEFAULT_SCHEMA = REPO_ROOT / "docs" / "spec" / "schema" / "compose.cairn.schema.yaml"


def has_cairn_metadata(manifest_path: Path) -> bool:
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    services = manifest.get("services", {}) if isinstance(manifest, dict) else {}
    return any(
        isinstance(service, dict) and "x-cairn" in service
        for service in services.values()
    )


def discover_manifests() -> list[Path]:
    return [
        manifest_path
        for manifest_path in sorted((REPO_ROOT / "services").glob("*/compose.yaml"))
        if has_cairn_metadata(manifest_path)
    ]


def validate_referenced_files(manifest_path: Path, manifest: dict) -> list[str]:
    errors = []
    for service_name, service in manifest["services"].items():
        for reference in referenced_contract_files(service["x-cairn"]):
            if error := reference_error(manifest_path.parent, reference):
                errors.append(f"services.{service_name}.x-cairn: {error}")
    return errors


def main() -> int:
    manifests = discover_manifests()
    if not manifests:
        print("no Cairn service Compose files found", file=sys.stderr)
        return EXIT_FAILURE

    schema = yaml.safe_load(DEFAULT_SCHEMA.read_text(encoding="utf-8"))
    schema["allOf"] = [{"$ref": "#/$defs/cairn_manifest_overlay"}]
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    has_validation_errors = False
    for manifest_path in manifests:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        schema_errors = sorted(
            validator.iter_errors(manifest), key=lambda error: error.path
        )
        reference_errors = (
            [] if schema_errors else validate_referenced_files(manifest_path, manifest)
        )
        if schema_errors or reference_errors:
            has_validation_errors = True
            print(f"{manifest_path}: invalid", file=sys.stderr)
            for error in schema_errors:
                path = ".".join(str(part) for part in error.absolute_path) or "<root>"
                print(f"  {path}: {error.message}", file=sys.stderr)
            for error in reference_errors:
                print(f"  {error}", file=sys.stderr)
        else:
            print(f"{manifest_path}: ok")

    return EXIT_FAILURE if has_validation_errors else EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
