# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[3] / "scripts/docker/fetch_opk_package.sh"
PACKAGE_URL = "https://example.com/releases/opk-package.tar.gz"

pytestmark = pytest.mark.unit


def fetch_environment(tmp_path: Path, content: bytes) -> dict[str, str]:
    tools = tmp_path / "tools"
    tools.mkdir()
    source = tmp_path / "source.tar.gz"
    source.write_bytes(content)
    curl = tools / "curl"
    curl.write_text(
        """#!/bin/sh
set -eu
for arg in "$@"; do
    case "$arg" in --user|-u|--netrc*) exit 3 ;; esac
done
while [ "$#" -gt 0 ]; do
    if [ "$1" = "--output" ]; then
        cp "$FETCH_TEST_SOURCE" "$2"
        exit 0
    fi
    shift
done
exit 2
""",
        encoding="utf-8",
    )
    curl.chmod(0o755)
    return {
        "FETCH_TEST_SOURCE": str(source),
        "PATH": f"{tools}:{os.environ['PATH']}",
    }


def test_downloads_verifies_and_moves_package_into_place(tmp_path: Path) -> None:
    content = b"verified package"
    checksum = hashlib.sha256(content).hexdigest()
    destination = tmp_path / "output" / "opk-package.tar.gz"

    subprocess.run(
        [SCRIPT, PACKAGE_URL, checksum, destination],
        check=True,
        capture_output=True,
        env=fetch_environment(tmp_path, content),
        text=True,
    )

    assert destination.read_bytes() == content
    assert not list(destination.parent.glob("*.partial.*"))


def test_checksum_failure_preserves_existing_destination(tmp_path: Path) -> None:
    destination = tmp_path / "output" / "opk-package.tar.gz"
    destination.parent.mkdir()
    destination.write_bytes(b"existing package")

    completed = subprocess.run(
        [SCRIPT, PACKAGE_URL, "0" * 64, destination],
        check=False,
        capture_output=True,
        env=fetch_environment(tmp_path, b"unexpected package"),
        text=True,
    )

    assert completed.returncode == 1
    assert "checksum mismatch" in completed.stderr
    assert destination.read_bytes() == b"existing package"
    assert not list(destination.parent.glob("*.partial.*"))


def test_rejects_non_https_url_before_download(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            SCRIPT,
            "http://example.com/package.tar.gz",
            "0" * 64,
            tmp_path / "package.tar.gz",
        ],
        check=False,
        capture_output=True,
        env=fetch_environment(tmp_path, b"package"),
        text=True,
    )

    assert completed.returncode == 2
    assert "must use HTTPS" in completed.stderr
