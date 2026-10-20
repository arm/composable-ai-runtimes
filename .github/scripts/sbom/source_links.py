# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""List apt and Python source links with an optional service-owned supplement."""

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import NamedTuple
from urllib.parse import parse_qs, quote, unquote, urlsplit
from urllib.request import urlopen

PYPI_SOURCE_LOOKUP_IGNORES: set[str] = {"open-perception-kit"}


class SourceReference(NamedTuple):
    project: str
    revision: str
    source_url: str
    license: str | None = None


def snapshot_source_links(project: str, version: str) -> list[tuple[str, str]]:
    name, release = quote(project, safe=""), quote(version, safe="")
    url = f"https://snapshot.debian.org/mr/package/{name}/{release}/srcfiles"
    try:
        with urlopen(url, timeout=60) as response:
            files = json.load(response)["result"]
    except OSError as error:
        raise RuntimeError(f"Cannot resolve {project}={version}: {url}") from error
    if not files:
        raise RuntimeError(f"No source files for {project}={version}")
    return [
        ("Debian Snapshot", f"https://snapshot.debian.org/package/{name}/{release}/")
    ]


def apt_source_links(container: str, project: str, version: str) -> list[tuple[str, str]]:
    result = subprocess.run(
        [
            "docker",
            "exec",
            container,
            "apt-get",
            "source",
            "--print-uris",
            "--only-source",
            f"{project}={version}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        if any(
            message in result.stderr
            for message in ("Can not find version", "Unable to find a source package")
        ):
            return snapshot_source_links(project, version)
        raise RuntimeError(f"APT failed for {project}={version}: {result.stderr}")

    links = []
    for line in result.stdout.splitlines():
        if line.startswith("'"):
            url, filename, *_ = shlex.split(line)
            links.append((filename, url))
    if not links:
        raise RuntimeError(f"APT returned no source links for {project}={version}")
    return links


def apt_source_project(
    purl: str, package_name: str, package_version: str
) -> tuple[str, str]:
    upstream = parse_qs(urlsplit(purl).query).get("upstream", [package_name])[0]
    project, separator, version = upstream.partition("@")
    if not separator:
        version = package_version
    return project, version


def python_source_project(purl: str) -> tuple[str, str]:
    parsed = urlsplit(purl)
    if "vcs_url" in parse_qs(parsed.query, keep_blank_values=True):
        raise RuntimeError(
            f"Python package records a VCS source; provide source handling for that origin "
            f"instead of looking it up on PyPI: {purl}"
        )
    project, _, version = parsed.path.removeprefix("pypi/").rpartition("@")
    project, version = unquote(project), unquote(version)
    if not project or not version:
        raise RuntimeError(f"Python package lacks an exact name/version: {purl}")
    return project, version


def python_source_links(project: str, version: str) -> list[tuple[str, str]]:
    name, release = quote(project, safe=""), quote(version, safe="")
    url = f"https://pypi.org/pypi/{name}/{release}/json"
    try:
        with urlopen(url, timeout=60) as response:
            files = json.load(response)["urls"]
    except OSError as error:
        raise RuntimeError(
            f"Cannot resolve Python {project}={version}: {url}"
        ) from error
    links = [
        (file["filename"], file["url"])
        for file in files
        if file["packagetype"] == "sdist"
    ]
    if not links:
        raise RuntimeError(f"No source distribution for Python {project}={version}")
    return links


def collect_source_projects(sboms: list[Path]) -> dict[tuple[str, str, str], set[str]]:
    projects: dict[tuple[str, str, str], set[str]] = {}
    for path in sboms:
        for package in json.loads(path.read_text())["packages"]:
            for ref in package.get("externalRefs", []):
                if ref["referenceType"] != "purl":
                    continue
                purl = ref["referenceLocator"]
                if purl.startswith("pkg:pypi/"):
                    ecosystem = "PyPI"
                    project, version = python_source_project(purl)
                elif purl.startswith("pkg:deb/debian/"):
                    ecosystem = "APT"
                    project, version = apt_source_project(
                        purl, package["name"], package["versionInfo"]
                    )
                else:
                    continue
                break
            else:
                # No supported package URL was found.
                continue
            if ecosystem == "PyPI" and project in PYPI_SOURCE_LOOKUP_IGNORES:
                continue
            licenses = {
                package[field]
                for field in ("licenseDeclared", "licenseConcluded")
                if package.get(field) not in (None, "", "NOASSERTION", "NONE")
            }
            projects.setdefault((ecosystem, project, version), set()).update(
                licenses or {"NOASSERTION"}
            )
    return projects


def build_report(
    image: str,
    container: str,
    projects: dict[tuple[str, str, str], set[str]],
    supplement: list[SourceReference],
) -> str:
    lines = [
        "# Dependency source links",
        "",
        f"Image: `{image}`",
        "",
        (
            "APT and PyPI entries from the supplied SBOMs are grouped by ecosystem/source project/version. "
            "Native entries come from service source resolvers. Licenses are reported as supplied by the SBOM or resolver; "
            "missing or blank licenses are shown as NOASSERTION. These are not reviewed conclusions. Base-image packages are included."
        ),
        "",
        (
            "APT source links include descriptors and source/packaging archives. "
            "Historical Debian versions link to their exact Snapshot page. "
            "Python links point to PyPI source distributions for the exact version. No source archives are downloaded."
        ),
        "",
        "| Ecosystem | Project | Source version | Reported licenses | Source files |",
        "| --- | --- | --- | --- | --- |",
    ]
    rows: list[list[str]] = []
    for (ecosystem, project, version), licenses in sorted(projects.items()):
        sources = (
            python_source_links(project, version)
            if ecosystem == "PyPI"
            else apt_source_links(container, project, version)
        )
        links = " · ".join(f"[{name}]({url})" for name, url in sources)
        rows.append([ecosystem, project, version, "; ".join(sorted(licenses)), links])
    for source in supplement:
        rows.append(
            [
                "Native", source.project, source.revision,
                (source.license or "").strip() or "NOASSERTION",
                f"[Source archive]({source.source_url})",
            ]
        )
    for cells in rows:
        lines.append(
            "| "
            + " | ".join(cell.replace("|", "\\|").replace("\n", " ") for cell in cells)
            + " |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument(
        "--apt-container",
        required=True,
        help="Running container with deb-src configured and apt indexes updated",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--supplement",
        type=Path,
        help="JSON array of source records with project, revision, source_url, and optional license fields",
    )
    parser.add_argument("sboms", type=Path, nargs="+")
    args = parser.parse_args()

    supplement: list[SourceReference] = []
    if args.supplement:
        supplement = [
            SourceReference(**record)
            for record in json.loads(args.supplement.read_text())
        ]
        if not supplement:
            parser.error(f"Source supplement is empty: {args.supplement}")
    projects = collect_source_projects(args.sboms)
    if not projects and not supplement:
        parser.error("No apt or Python source projects found in the SBOMs")
    report = build_report(args.image, args.apt_container, projects, supplement)
    args.output.write_text(report)
    print(f"Wrote {args.output}: {len(projects) + len(supplement)} source projects/versions")


if __name__ == "__main__":
    main()
