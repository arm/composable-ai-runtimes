# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Check installed Python license/notice files, not license completeness."""

import csv
import io
import re
import shutil
import subprocess
import sys
from importlib.metadata import Distribution, PackagePath, distributions
from pathlib import Path


def readable(path: Path) -> bool:
    try:
        return path.is_file() and bool(path.read_bytes().strip())
    except OSError:
        return False


def apt_owns_distribution(dist: Distribution) -> bool:
    if (dist.read_text("INSTALLER") or "").strip() in {"pip", "uv"}:
        return False
    # Debian metadata may have no RECORD; PathDistribution has no public metadata path.
    metadata_path = getattr(dist, "_path", None)
    if not isinstance(metadata_path, Path) or shutil.which("dpkg-query") is None:
        return False
    result = subprocess.run(
        ["dpkg-query", "-S", str(metadata_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(f"Cannot determine APT ownership: {result.stderr.strip()}")
    return result.returncode == 0


def declared_license_records(
    dist: Distribution, records: list[PackagePath]
) -> tuple[set[PackagePath], list[str]]:
    license_notice_records: set[PackagePath] = set()
    errors: list[str] = []
    metadata_version = tuple(map(int, dist.metadata["Metadata-Version"].split(".")))
    for filename in dist.metadata.get_all("License-File", []):
        # Older setuptools records source paths but installs licenses flat.
        if metadata_version < (2, 4):
            filename = Path(filename).name
        matches = {
            file
            for file in records
            if any(
                str(file).endswith(f"{prefix}/{filename}")
                for prefix in (".dist-info/licenses", ".dist-info", ".egg-info")
            )
        }
        if not matches:
            errors.append(f"declared License-File not recorded: {filename}")
        license_notice_records.update(matches)
    return license_notice_records, errors


def fallback_license_paths(dist: Distribution, name: str) -> set[Path]:
    if name == "pycairo" and dist.version == "1.29.0":
        # This release puts its notice in the header; Debian supplies the texts.
        return {
            Path(dist.locate_file("cairo/include/py3cairo.h")),
            Path("/usr/share/common-licenses/LGPL-2.1"),
            Path("/usr/share/common-licenses/MPL-1.1"),
        }
    return {Path(f"/usr/share/licenses/cairn/python/{name}-{dist.version}/LICENSE")}


def check_distribution(dist: Distribution) -> list[str]:
    name = re.sub(r"[-_.]+", "-", dist.metadata["Name"]).lower()
    record = dist.read_text("RECORD")
    if record is not None:
        # Distribution.files filters out missing paths on Python 3.13.
        records = [PackagePath(row[0]) for row in csv.reader(io.StringIO(record)) if row]
    else:
        records = list(dist.files or [])
    if not records:
        return [
            (
                f"{name}=={dist.version}: no installed-file inventory available; "
                "cannot validate package notices"
            )
        ]
    license_notice_records, errors = declared_license_records(dist, records)
    license_notice_records.update(
        file
        for file in records
        if file.name.upper().startswith(
            ("LICENSE", "LICENCE", "COPYING", "NOTICE", "COPYRIGHT", "AUTHORS")
        )
    )
    paths = {Path(dist.locate_file(file)) for file in license_notice_records}
    if not dist.metadata.get_all("License-File", []) and not any(
        file.name.upper().startswith(("LICENSE", "LICENCE", "COPYING"))
        for file in license_notice_records
    ):
        paths.update(fallback_license_paths(dist, name))
    for path in sorted(paths):
        if not readable(path):
            errors.append(f"missing, empty, or unreadable license/notice: {path}")
    return [f"{name}=={dist.version}: {error}" for error in errors]


def main() -> int:
    installed = sorted(distributions(), key=lambda dist: dist.metadata["Name"].lower())
    try:
        packages = [dist for dist in installed if not apt_owns_distribution(dist)]
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    errors = [error for dist in packages for error in check_distribution(dist)]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(
        f"Python distributions checked: {len(packages)} ({sys.executable}); "
        f"{len(installed) - len(packages)} managed by APT."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
