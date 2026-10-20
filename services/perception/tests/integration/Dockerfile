# syntax=docker/dockerfile:1
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.11.32@sha256:df4cae8f3a96d175e2e5f992e597550000edbe78fdc2594d5cd8de1a217f504c

FROM ${UV_IMAGE} AS uv

# hadolint ignore=DL3006
FROM production

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

HEALTHCHECK NONE

COPY --from=uv /uv /usr/local/bin/uv
COPY --chown=perception-service:perception-service pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/home/perception-service/.cache/uv,uid=10002,gid=10002 \
  uv sync --locked --no-dev --group test --no-install-project

COPY --chown=perception-service:perception-service tests ./tests

ENTRYPOINT ["uv", "run", "--no-sync", "pytest"]
CMD ["-m", "integration"]
