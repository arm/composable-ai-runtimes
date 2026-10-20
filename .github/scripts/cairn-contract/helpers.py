# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Shared Cairn service contract script helpers."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
EXIT_SUCCESS = 0
EXIT_FAILURE = 1


def service_metadata(service: str) -> dict:
    service_dir = REPO_ROOT / "services" / service
    manifest = yaml.safe_load(
        (service_dir / "compose.yaml").read_text(encoding="utf-8")
    )
    return manifest["services"][f"{service}-service"]["x-cairn"]


def referenced_contract_files(metadata: dict) -> list[str]:
    references = set(metadata["api"]["grpc"].get("contracts", []))
    for topic in metadata.get("messaging", {}).get("publishes", []):
        for event in topic["events"]:
            if schema := event.get("schema"):
                references.add(schema)
    return sorted(references)


def reference_error(service_dir: Path, reference: str) -> str | None:
    path = PurePosixPath(reference)
    if path.is_absolute() or ".." in path.parts:
        return f"{reference}: contract file reference must stay inside service directory"

    resolved = (service_dir / Path(*path.parts)).resolve()
    try:
        resolved.relative_to(service_dir.resolve())
    except ValueError:
        return f"{reference}: contract file reference escapes service directory"

    if not resolved.is_file():
        return f"{reference}: referenced contract file is missing"

    return None
