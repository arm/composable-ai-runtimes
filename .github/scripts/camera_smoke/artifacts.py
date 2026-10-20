# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from camera_smoke.commands import CommandResult


def write_text_artifact(results_dir: Path, name: str, content: str) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / name).write_text(content, encoding="utf-8")


def write_command_transcript(
    results_dir: Path, name: str, result: CommandResult
) -> None:
    body = (
        f"$ {' '.join(result.args)}\n"
        f"exit_code={result.returncode}\n\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}\n"
    )
    write_text_artifact(results_dir, name, body)
