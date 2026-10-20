# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Pytest services smoke probe for a local Topo deployment."""

from __future__ import annotations

import json
import os
import platform
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from camera_smoke.artifacts import write_command_transcript, write_text_artifact
from camera_smoke.commands import run_command
from camera_smoke.time import get_utc_now

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE = os.environ.get("TOPO_SMOKE_ENGINE", "docker")
if ENGINE not in ("docker", "podman"):
    raise ValueError("TOPO_SMOKE_ENGINE must be docker or podman")
TEST_RESULTS_DIR = REPO_ROOT / "test-results" / f"services-topo-{ENGINE}-smoke"


JsonObject = dict[str, object]


def build_initial_metadata() -> JsonObject:
    metadata: JsonObject = {
        "engine": ENGINE,
        "started_at": get_utc_now(),
        "runner_name": os.environ.get("RUNNER_NAME"),
        "runner_os": os.environ.get("RUNNER_OS"),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "result": "started",
    }
    return metadata


@pytest.fixture(scope="module")
def metadata() -> Iterator[JsonObject]:
    metadata = build_initial_metadata()
    try:
        yield metadata
    finally:
        metadata["finished_at"] = get_utc_now()
        write_text_artifact(
            TEST_RESULTS_DIR,
            "metadata.json",
            json.dumps(metadata, indent=2, sort_keys=True),
        )


def run_topo_deploy(metadata: JsonObject) -> None:
    args = ["topo", "deploy"]
    if ENGINE == "podman":
        args.extend(["--engine", ENGINE])
    args.extend(["--target", "localhost"])
    result = run_command(*args, cwd=REPO_ROOT)
    metadata["topo_deploy_exit_code"] = result.returncode
    if result.returncode != 0:
        metadata["result"] = "topo_deploy_failed"
        write_command_transcript(TEST_RESULTS_DIR, "topo-deploy.txt", result)
    assert result.returncode == 0, "topo deploy failed. See topo-deploy.txt."


def test_services_topo(metadata: JsonObject) -> None:
    run_topo_deploy(metadata)
    metadata["result"] = "passed"
