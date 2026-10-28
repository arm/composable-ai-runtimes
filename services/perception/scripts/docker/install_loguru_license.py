# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Register Loguru's omitted upstream license for installed-package scanners."""

import base64
import csv
import hashlib
import sys
from importlib.metadata import distribution
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: install_loguru_license.py LICENSE_FILE")

    package = distribution("loguru")
    if package.version != "0.7.3":
        raise SystemExit("Loguru version changed; review its license before building")

    license_path = "loguru-0.7.3.dist-info/LICENSE"
    installed_license = Path(str(package.locate_file(license_path)))
    license_bytes = Path(sys.argv[1]).read_bytes()
    digest = (
        base64.urlsafe_b64encode(hashlib.sha256(license_bytes).digest())
        .decode("ascii")
        .rstrip("=")
    )

    with installed_license.open("xb") as license_file:
        license_file.write(license_bytes)
    with installed_license.with_name("RECORD").open(
        "a", encoding="utf-8", newline=""
    ) as record:
        csv.writer(record).writerow(
            [license_path, f"sha256={digest}", len(license_bytes)]
        )


if __name__ == "__main__":
    main()
