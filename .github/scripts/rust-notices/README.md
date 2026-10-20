<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

# Rust notices and review

This directory contains the shared notice-generation settings and per-artifact
review tooling for the Python wheel and Rust service images.

See [Licensing and SBOM contributor guide](../../../docs/licensing-guide.md) for contributor guidance.

From the repository root, check the affected artifact. For example, for the wheel:

```bash
uv run --no-project python .github/scripts/rust-notices/review.py lib/pyproject.toml
```

For a service image, replace `lib/pyproject.toml` with
`services/camera/Cargo.toml` or `services/messaging/Cargo.toml` in each command.

If review is required:

1. Review the affected dependencies' licenses and attribution against upstream.
   Update `about.toml` in this directory if needed.
2. Regenerate the notices using the toolchain setup and "Generate Rust notices"
   step in the [wheel workflow](../../workflows/publish-python-packages.yml) or
   [service image workflow](../../workflows/publish-service-images.yml).
3. Update the snapshot, then check the generated bundle in a separate command:

   ```bash
   uv run --no-project python .github/scripts/rust-notices/review.py lib/pyproject.toml --update-snapshot
   uv run --no-project python .github/scripts/rust-notices/review.py lib/pyproject.toml --check
   ```

4. Commit the artifact's snapshot under `reviewed/` and any notice configuration
   changes for code-owner approval. Generated notice directories stay ignored.

Do not update a snapshot merely to clear CI. Snapshot updates and generated
notices do not replace upstream review or code-owner approval.
