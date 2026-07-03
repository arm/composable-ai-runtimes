#!/usr/bin/env python3
"""Pytest camera smoke probe for the board-farm Topo deployment path."""

from __future__ import annotations

import json
import os
import platform
import socket
from pathlib import Path
from typing import Iterator

import pytest

from camera_smoke.artifacts import write_command_transcript, write_text_artifact
from camera_smoke.commands import CommandResult, run_command as run_shell_command
from camera_smoke.time import get_utc_now


REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_RESULTS_DIR = REPO_ROOT / "test-results" / "camera-boardfarm-topo-smoke"
TOPO_TARGET_ENV = "CAMERA_BOARDFARM_TOPO_TARGET"


JsonObject = dict[str, object]


def run_command(*args: str) -> CommandResult:
    return run_shell_command(*args, cwd=REPO_ROOT)


def fail_with_result(metadata: JsonObject, result: str, message: str) -> None:
    metadata["result"] = result
    pytest.fail(message)


def build_initial_metadata() -> JsonObject:
    metadata: JsonObject = {
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


def remove_stale_artifacts() -> None:
    if not TEST_RESULTS_DIR.exists():
        return

    for artifact in TEST_RESULTS_DIR.iterdir():
        if artifact.is_file():
            artifact.unlink()


@pytest.fixture(scope="module")
def metadata() -> Iterator[JsonObject]:
    remove_stale_artifacts()
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


@pytest.fixture(scope="module")
def topo_cleanup(metadata: JsonObject) -> Iterator[None]:
    try:
        yield
    finally:
        target = os.environ.get(TOPO_TARGET_ENV, "").strip()
        if target:
            stop_result = run_command("topo", "stop", "--target", target)
            metadata["topo_stop_exit_code"] = stop_result.returncode
            if stop_result.returncode != 0:
                write_command_transcript(TEST_RESULTS_DIR, "topo-stop.txt", stop_result)


def require_topo_target(metadata: JsonObject) -> str:
    target = os.environ.get(TOPO_TARGET_ENV, "").strip()
    if not target:
        fail_with_result(
            metadata,
            "missing_topo_target",
            f"{TOPO_TARGET_ENV} must be set to the Topo deployment target, for example user@host.",
        )
    return target


def run_topo_deploy(metadata: JsonObject, target: str) -> None:
    result = run_command("topo", "deploy", "--no-registry", "--target", target)
    metadata["topo_deploy_exit_code"] = result.returncode
    if result.returncode != 0:
        metadata["result"] = "topo_deploy_failed"
        write_command_transcript(TEST_RESULTS_DIR, "topo-deploy.txt", result)
    assert result.returncode == 0, "topo deploy failed. See topo-deploy.txt."


def test_camera_boardfarm_topo_smoke(
    metadata: JsonObject, topo_cleanup: None
) -> None:
    target = require_topo_target(metadata)
    run_topo_deploy(metadata, target)
    metadata["result"] = "passed"
