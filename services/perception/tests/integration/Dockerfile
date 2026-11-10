# syntax=docker/dockerfile:1
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff

FROM ${UV_IMAGE} AS uv

# hadolint ignore=DL3006
FROM production

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

HEALTHCHECK NONE

COPY --from=uv /uv /usr/local/bin/uv
# workspace is a named build context supplied by Compose additional_contexts,
# not a Dockerfile stage; DL3022 does not recognize this external context.
# hadolint ignore=DL3022
COPY --from=workspace --chown=perception-service:perception-service pyproject.toml uv.lock /workspace/
# hadolint ignore=DL3022
COPY --from=workspace --chown=perception-service:perception-service lib/pyproject.toml /workspace/lib/
COPY --chown=perception-service:perception-service pyproject.toml /workspace/services/perception/
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

RUN --mount=type=cache,target=/home/perception-service/.cache/uv,uid=10002,gid=10002 \
  uv sync --project /workspace/services/perception --package perception-service --locked --no-dev --group test --no-install-workspace

COPY --chown=perception-service:perception-service pyproject.toml ./
COPY --chown=perception-service:perception-service tests ./tests

ENTRYPOINT ["uv", "run", "--project", "/workspace/services/perception", "--package", "perception-service", "--no-sync", "pytest"]
CMD ["-m", "integration"]
