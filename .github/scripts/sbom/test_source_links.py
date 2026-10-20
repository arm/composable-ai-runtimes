# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import json
import sys
from pathlib import Path

import pytest
import source_links as report_generator


def test_supplement_joins_package_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    sbom = tmp_path / "sbom.json"
    sbom.write_text(json.dumps({"packages": [
        {
            "name": "example", "versionInfo": "1.0", "licenseDeclared": "MIT",
            "externalRefs": [{"referenceType": "purl", "referenceLocator": purl}],
        }
        for purl in ("pkg:deb/debian/example@1.0", "pkg:pypi/example@1.0")
    ]}))
    supplement = tmp_path / "supplement.json"
    supplement.write_text(json.dumps([
        {"project": "native", "revision": "abc", "source_url": "https://example.org/native", "license": "BSD-3-Clause"},
        {"project": "unspecified", "revision": "def", "source_url": "https://example.org/unspecified"},
        {"project": "blank", "revision": "ghi", "source_url": "https://example.org/blank", "license": " "},
    ]))
    monkeypatch.setattr(report_generator, "apt_source_links", lambda *args: [("APT", "https://example.org/apt")])
    monkeypatch.setattr(report_generator, "python_source_links", lambda *args: [("PyPI", "https://example.org/python")])
    output = tmp_path / "report.md"
    args = ["source_links.py", "--image", "image@sha256:example", "--apt-container", "apt", "--output", str(output), str(sbom)]
    monkeypatch.setattr(sys, "argv", args)
    report_generator.main()
    package_report = output.read_text()
    assert "https://example.org/apt" in package_report
    assert "https://example.org/python" in package_report

    monkeypatch.setattr(sys, "argv", args + ["--supplement", str(supplement)])
    report_generator.main()
    report = output.read_text()
    assert report.startswith(package_report)
    assert "image@sha256:example" in report
    assert report.count("| Ecosystem |") == 1
    rows = [line for line in report.splitlines() if line.startswith("| Native |")]
    assert len(rows) == 3
    assert "BSD-3-Clause" in rows[0] and "https://example.org/native" in rows[0]
    assert all("NOASSERTION" in row for row in rows[1:])


def test_empty_supplement_fails_before_writing_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    supplement = tmp_path / "supplement.json"
    supplement.write_text("[]")
    output = tmp_path / "report.md"
    monkeypatch.setattr(sys, "argv", [
        "source_links.py", "--image", "test", "--apt-container", "apt",
        "--output", str(output), "--supplement", str(supplement), "unused.json",
    ])
    with pytest.raises(SystemExit) as error:
        report_generator.main()
    assert error.value.code == 2
    assert not output.exists()
