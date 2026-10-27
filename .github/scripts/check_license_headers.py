# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Validate license headers in tracked Cairn files."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path, PurePosixPath

COPYRIGHT_OWNER = (
    "Arm Limited and/or its affiliates <open-source-office@arm.com>"
)
LICENSE_IDENTIFIER = "Apache-2.0"
COPYRIGHT_RE = re.compile(
    rf"SPDX-FileCopyrightText: Copyright "
    rf"(?P<start_year>\d{{4}})(?:-(?P<end_year>\d{{4}}))? "
    rf"{re.escape(COPYRIGHT_OWNER)}"
)

EXCLUDED_PATHS = frozenset(
    {
        PurePosixPath(".python-version"),
        PurePosixPath("LICENSE"),
        PurePosixPath("lib/crates/cairn/SBOM-DISCLAIMER.txt"),
        PurePosixPath("lib/python/cairn/__init__.pyi"),
        PurePosixPath("lib/python/cairn/py.typed"),
        # The sample image retains its upstream license unchanged.
        PurePosixPath("services/perception/tests/e2e/pipewire_source/sample_input.jpg.LICENSE"),
    }
)
EXCLUDED_SUFFIXES = frozenset(
    {
        ".gif",
        ".ico",
        ".jpeg",
        ".jpg",
        ".json",
        ".lock",
        ".png",
    }
)
GENERATED_FILE_SUFFIXES = ("_pb2.py", "_pb2.pyi", "_pb2_grpc.py")
HASH_COMMENT_SUFFIXES = frozenset(
    {
        ".Dockerfile",
        ".conf",
        ".dockerignore",
        ".env",
        ".gitignore",
        ".py",
        ".pyi",
        ".sh",
        ".txt",
        ".toml",
        ".yaml",
        ".yml",
    }
)
HASH_COMMENT_NAMES = frozenset(
    {".dockerignore", ".gitattributes", ".gitignore", "CODEOWNERS", "Dockerfile"}
)
SLASH_COMMENT_SUFFIXES = frozenset({".go", ".proto", ".rs"})


class HeaderStyle(Enum):
    """Comment syntax used by a license header."""

    CSS = "css"
    HASH = "hash"
    HANDLEBARS = "handlebars"
    JINJA = "jinja"
    MARKDOWN = "markdown"
    RST = "rst"
    SLASH = "slash"


@dataclass(frozen=True)
class Violation:
    """A license-header validation failure."""

    path: PurePosixPath
    message: str


def is_excluded(path: PurePosixPath) -> bool:
    """Return whether a tracked file intentionally has no inline header."""

    if (
        path in EXCLUDED_PATHS
        or path.name in {"LICENSE", "THIRD-PARTY-DISCLAIMER.txt", "go.sum"}
        or path.suffix in EXCLUDED_SUFFIXES
    ):
        return True
    if "generated" in path.parts:
        return True
    return path.name.endswith(GENERATED_FILE_SUFFIXES)


def header_style(path: PurePosixPath) -> HeaderStyle | None:
    """Return the required comment style, or None for an unknown format."""

    if path.suffix in {".html", ".md"}:
        return HeaderStyle.MARKDOWN
    if path.suffix == ".j2":
        return HeaderStyle.JINJA
    if path.suffix == ".hbs":
        return HeaderStyle.HANDLEBARS
    if path.suffix == ".css":
        return HeaderStyle.CSS
    if path.suffix == ".rst":
        return HeaderStyle.RST
    if path.suffix in SLASH_COMMENT_SUFFIXES or path.name == "go.mod":
        return HeaderStyle.SLASH
    if path.suffix in HASH_COMMENT_SUFFIXES or path.name in HASH_COMMENT_NAMES:
        return HeaderStyle.HASH
    return None


def _has_misplaced_shebang(lines: list[str], style: HeaderStyle) -> bool:
    """Return whether a hash-commented file has a shebang after its first line."""

    return (
        style is HeaderStyle.HASH
        and bool(lines)
        and not lines[0].startswith("#!")
        and any(line.startswith("#!") for line in lines)
    )


def _header_start(path: PurePosixPath, lines: list[str], style: HeaderStyle) -> int:
    if style is HeaderStyle.HASH and lines and lines[0].startswith("#!"):
        return 1
    if (
        style is HeaderStyle.HASH
        and lines
        and (path.name == "Dockerfile" or path.suffix == ".Dockerfile")
        and lines[0].startswith("# syntax=")
    ):
        return 1
    if style is HeaderStyle.MARKDOWN and lines and lines[0] == "---":
        try:
            return lines.index("---", 1) + 1
        except ValueError:
            return 0
    return 0


def _expected_header_pattern(style: HeaderStyle) -> tuple[re.Pattern[str], ...]:
    copyright_pattern = COPYRIGHT_RE.pattern
    license_identifier = re.escape(LICENSE_IDENTIFIER)
    if style is HeaderStyle.HASH:
        return (
            re.compile(rf"# {copyright_pattern}"),
            re.compile(rf"# SPDX-License-Identifier: {license_identifier}"),
        )
    if style is HeaderStyle.SLASH:
        return (
            re.compile(rf"// {copyright_pattern}"),
            re.compile(rf"// SPDX-License-Identifier: {license_identifier}"),
        )
    if style is HeaderStyle.CSS:
        return (
            re.compile(r"/\*"),
            re.compile(rf" \* {copyright_pattern}"),
            re.compile(rf" \* SPDX-License-Identifier: {license_identifier}"),
            re.compile(r" \*/"),
        )
    if style is HeaderStyle.RST:
        return (
            re.compile(rf"\.\. {copyright_pattern}"),
            re.compile(rf"\.\. SPDX-License-Identifier: {license_identifier}"),
        )
    if style is HeaderStyle.HANDLEBARS:
        return (
            re.compile(r"\{\{!--"),
            re.compile(copyright_pattern),
            re.compile(rf"SPDX-License-Identifier: {license_identifier}"),
            re.compile(r"--\}\}"),
        )
    if style is HeaderStyle.JINJA:
        return (
            re.compile(r"\{#"),
            re.compile(copyright_pattern),
            re.compile(rf"SPDX-License-Identifier: {license_identifier}"),
            re.compile(r"-?#\}"),
        )
    return (
        re.compile(r"<!---"),
        re.compile(copyright_pattern),
        re.compile(rf"SPDX-License-Identifier: {license_identifier}"),
        re.compile(r"--->"),
    )


def _is_valid_copyright_year_range(copyright_match: re.Match[str]) -> bool:
    """Return whether a copyright year or range is ordered and not in the future."""

    start_year = int(copyright_match.group("start_year"))
    end_year_text = copyright_match.group("end_year")
    end_year = int(end_year_text) if end_year_text is not None else start_year
    current_year = datetime.now(tz=UTC).year
    return start_year <= end_year <= current_year


def _license_identifier_count(lines: list[str], style: HeaderStyle) -> int:
    if style is HeaderStyle.HASH:
        return sum(line.startswith("# SPDX-License-Identifier:") for line in lines)
    if style is HeaderStyle.SLASH:
        return sum(line.startswith("// SPDX-License-Identifier:") for line in lines)
    if style is HeaderStyle.CSS:
        return sum(
            line.startswith(" * SPDX-License-Identifier:") for line in lines
        )
    if style is HeaderStyle.RST:
        return sum(line.startswith(".. SPDX-License-Identifier:") for line in lines)

    count = 0
    fence: str | None = None
    for line in lines:
        stripped = line.lstrip()
        marker = stripped[:3]
        if fence is None and marker in {"```", "~~~"}:
            fence = marker
            continue
        if fence == marker:
            fence = None
            continue
        if fence is None and line.startswith("SPDX-License-Identifier:"):
            count += 1
    return count


def validate_content(path: PurePosixPath, content: str) -> list[Violation]:
    """Validate the header of an eligible tracked file."""

    style = header_style(path)
    if style is None:
        return [
            Violation(
                path,
                "unsupported tracked file type; classify it as header-bearing or excluded",
            )
        ]

    lines = content.splitlines()
    if _has_misplaced_shebang(lines, style):
        return [Violation(path, "missing, malformed, or incorrectly placed SPDX header")]
    start = _header_start(path, lines, style)
    patterns = _expected_header_pattern(style)
    candidate = lines[start : start + len(patterns)]
    if len(candidate) != len(patterns) or any(
        pattern.fullmatch(line) is None
        for pattern, line in zip(patterns, candidate, strict=True)
    ):
        return [Violation(path, "missing, malformed, or incorrectly placed SPDX header")]

    copyright_match = next(
        (
            match
            for line in candidate
            if (match := COPYRIGHT_RE.search(line)) is not None
        ),
        None,
    )
    if copyright_match is None:
        return [Violation(path, "malformed SPDX copyright line")]

    if not _is_valid_copyright_year_range(copyright_match):
        return [Violation(path, "copyright year or range is invalid")]

    header_end = start + len(patterns)
    if header_end < len(lines) and lines[header_end] != "":
        return [Violation(path, "SPDX header must be followed by a blank line")]

    if _license_identifier_count(lines, style) != 1:
        return [Violation(path, "file must contain exactly one SPDX license identifier")]

    return []


def tracked_files(repo_root: Path) -> list[PurePosixPath]:
    """Return tracked files according to Git."""

    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    return [
        PurePosixPath(raw_path.decode("utf-8"))
        for raw_path in result.stdout.split(b"\0")
        if raw_path
    ]


def validate_repository(repo_root: Path) -> list[Violation]:
    """Validate all tracked files in a repository."""

    violations: list[Violation] = []
    for relative_path in tracked_files(repo_root):
        if is_excluded(relative_path):
            continue
        file_path = repo_root / relative_path
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            violations.append(Violation(relative_path, f"cannot read as UTF-8: {error}"))
            continue
        violations.extend(validate_content(relative_path, content))
    return violations


def repository_root() -> Path:
    """Resolve the current Git repository root."""

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip())


def main() -> int:
    """Run repository license-header validation."""

    try:
        violations = validate_repository(repository_root())
    except subprocess.CalledProcessError as error:
        print(f"license header check could not inspect Git files: {error}", file=sys.stderr)
        return 2

    for violation in violations:
        print(f"{violation.path}: {violation.message}", file=sys.stderr)
    if violations:
        print(f"license header check failed: {len(violations)} violation(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
