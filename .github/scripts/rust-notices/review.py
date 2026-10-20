# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Review Rust dependencies and notices shipped in wheels or service images."""

import argparse
import hashlib
import json
import shlex
from pathlib import Path

import tomllib
from common import (
    NOTICE_INPUTS,
    ROOT,
    changed_files,
    file_hashes,
    update_snapshot,
)

SNAPSHOTS_SUBDIR = Path(".github/scripts/rust-notices/reviewed")
NOTICES_SUBDIR = Path("notices/rust")
WHEEL_INPUT_FILES = (
    "Cargo.toml",
    "Cargo.lock",
    ".cargo/config.toml",
    "rust-toolchain.toml",
)


def cargo_args(root: Path, manifest_path: Path) -> list[str]:
    if manifest_path.name == "Cargo.toml":
        package = tomllib.loads(manifest_path.read_text())["package"]
        try:
            target = package["metadata"]["cairn"]["rust-notices"]["target"]
        except KeyError as error:
            raise ValueError(
                f"Set package.metadata.cairn.rust-notices.target in {manifest_path} to match the image build."
            ) from error
        return ["--manifest-path", str(manifest_path), "--target", target]
    maturin = tomllib.loads(manifest_path.read_text())["tool"]["maturin"]
    features: list[str] = []
    if maturin.get("features"):
        features.extend(["--features", " ".join(maturin["features"])])
    for flag in ("all-features", "no-default-features"):
        if maturin.get(flag):
            features.append(f"--{flag}")
    # Wheel arguments are hashed; keep their paths repository-relative for portability.
    return [
        "--manifest-path",
        str(manifest_path.parent.relative_to(root) / maturin["manifest-path"]),
        "--target",
        maturin.get("target", "aarch64-unknown-linux-gnu"),
        *features,
    ]


def input_hashes(root: Path, manifest_path: Path) -> dict[str, str]:
    artifact_dir = manifest_path.parent
    input_paths = [root / name for name in NOTICE_INPUTS]
    if manifest_path.name == "Cargo.toml":
        input_paths.extend((artifact_dir / "Cargo.toml", artifact_dir / "Cargo.lock"))
        input_paths.extend((artifact_dir / ".cargo").glob("config*"))
        return file_hashes(root, input_paths)
    input_paths.extend(artifact_dir / name for name in WHEEL_INPUT_FILES)
    input_paths.extend((artifact_dir / "crates").glob("*/Cargo.toml"))
    inputs = file_hashes(root, input_paths)
    inputs[f"{manifest_path.relative_to(root).as_posix()}:build-selection"] = hashlib.sha256(
        json.dumps(cargo_args(root, manifest_path)).encode()
    ).hexdigest()
    return inputs


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "manifest", type=Path,
        help="Wheel pyproject.toml or service Cargo.toml, relative to the repository root",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--cargo-args",
        action="store_true",
        help="Print the selected artifact's notice-generation arguments",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="Also check generated notice bundles",
    )
    mode.add_argument(
        "--update-snapshot",
        action="store_true",
        help="Update one snapshot after upstream review and notice generation",
    )
    args = parser.parse_args(argv)
    if args.manifest.name not in {"pyproject.toml", "Cargo.toml"}:
        parser.error("Manifest must be named pyproject.toml or Cargo.toml")
    try:
        manifest_path = (root / args.manifest).resolve()
        relative_manifest_path = manifest_path.relative_to(root)
        artifact_dir = manifest_path.parent
        notice_args = cargo_args(root, manifest_path)
        if args.cargo_args:
            print("\n".join(notice_args))
            return 0
        inputs = input_hashes(root, manifest_path)
        snapshots_dir = root / SNAPSHOTS_SUBDIR
        snapshot_path = snapshots_dir / f"{relative_manifest_path.parent.as_posix()}.json"
        notices_dir = artifact_dir / NOTICES_SUBDIR
        if args.update_snapshot:
            update_snapshot(snapshot_path, inputs, notices_dir)
            print(
                f"Updated {relative_manifest_path} snapshot. Upstream review and code-owner approval are still required."
            )
            return 0
        if not snapshot_path.is_file():
            changes = [f"No reviewed baseline: {snapshot_path}"]
        else:
            changes = changed_files(snapshot_path, inputs, notices_dir if args.check else None)
        if changes:
            print(f"{relative_manifest_path} Rust license review required:\n" + "\n".join(changes))
            print(
                f"Review changes against upstream and regenerate {relative_manifest_path} notices, then run:\n"
                f"uv run --no-project python .github/scripts/rust-notices/review.py {shlex.quote(str(relative_manifest_path))} --update-snapshot\n"
                "Commit the updated snapshot for code-owner approval. This does not prove license completeness."
            )
            return 1
    except (OSError, ValueError, KeyError) as error:
        print(f"{args.manifest} Rust license review failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
