<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

# Licensing and SBOM contributor guide

Use this guide when changing dependencies, packaging, or copied third-party
assets. It explains where Cairn's licensing material is shipped and where to
find the checks needed for a change.

License notices record third-party terms and attribution. A software bill of
materials (SBOM) lists components in a release; source reports point to their
source locations. These serve different purposes: an SBOM or source link does
not replace the component's license notices.

## Where to find release material

| Artifact | Licensing material and release workflow |
| --- | --- |
| [Service images](../.github/workflows/publish-service-images.yml) | Licenses and notices inside the image; SBOM and source reports attached to its registry digest. |
| [Python wheels](../.github/workflows/publish-python-packages.yml) | Licenses, Rust dependency notices, and an SBOM inside the wheel. |
| [Rust crates](../.github/workflows/publish-rust-crate.yml) | License files in each crate; an SBOM and its disclaimer in the umbrella `cairn` crate. |
| Documentation assets | Attribution and license files alongside copied assets. |

## When making a change

Review the material your change adds or alters in the shipped artifact,
including bundled native libraries and copied files. A development dependency
list alone does not describe everything shipped.

- Check affected upstream licenses and preserve their notices and attribution.
- For Rust dependencies or build selections, follow the
  [Rust notice review procedure](../.github/scripts/rust-notices/README.md).
- After Rust version, dependency, or build-selection changes, run
  `.github/scripts/sbom/generate-rust.sh` from the repository root and commit
  `lib/crates/cairn/bom.json`. Use `--check` to verify freshness without rewriting
  it. Requires `jq`, the pinned Rust toolchain, and `cargo-sbom` 0.10.0
  (`cd lib && cargo install cargo-sbom --version 0.10.0 --locked`).
- For packaging or publication changes, use the linked release workflow to
  identify affected inventory and source-report inputs and validate the result.
  Automated scans can miss bundled or source-built components.

Describe the affected artifacts, checks performed, and any remaining coverage
gaps in the PR. Unchanged dependencies do not need a new exhaustive audit.
