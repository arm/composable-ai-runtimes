# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


def run_command(*args: str, cwd: Path) -> CommandResult:
    try:
        result = subprocess.run(
            list(args),
            cwd=cwd,
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as err:
        return CommandResult(
            args=list(args),
            returncode=127,
            stdout="",
            stderr=str(err),
        )
    return CommandResult(
        args=list(args),
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )
