# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Compare build inputs and generated notices with their reviewed file hashes."""

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NOTICE_INPUTS = (
    ".github/scripts/rust-notices/about.toml",
    ".github/scripts/rust-notices/about.hbs",
    ".github/scripts/rust-notices/toolchain.env",
)


def file_hashes(root: Path, paths: Iterable[Path]) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    }


def notice_hashes(directory: Path) -> dict[str, str]:
    for required in ("THIRD_PARTY_NOTICES.txt", "COPYRIGHT-library.html"):
        if not (directory / required).is_file():
            raise ValueError(
                f"Generate notices in {directory} before checking or recording them."
            )
    return file_hashes(
        directory, (path for path in directory.rglob("*") if path.is_file())
    )


def update_snapshot(snapshot_path: Path, inputs: dict[str, str], notices: Path) -> None:
    snapshot = {"inputs": inputs, "notices": notice_hashes(notices)}
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")


def changed_files(
    record: Path, inputs: dict[str, str], notices: Path | None = None
) -> list[str]:
    reviewed = json.loads(record.read_text())
    actual = {"inputs": inputs}
    if notices is not None:
        actual["notices"] = notice_hashes(notices)
    changes = []
    for scope, hashes in actual.items():
        expected = reviewed[scope]
        for name in sorted(expected.keys() | hashes.keys()):
            if expected.get(name) != hashes.get(name):
                changes.append(f"{scope}: {name}")
    return changes
