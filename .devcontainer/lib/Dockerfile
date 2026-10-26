# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

FROM docker.io/library/python:3.13.17-slim-trixie@sha256:19ed48e5e9c132082510ba9efb11bc2098d582f610374670fa30b6b17026617b AS python

FROM docker.io/library/rust:1.99.1-trixie@sha256:931c2c0531a8b143e044f0f3914dfe802f15bb3d1955f0b657e9359327ac2ffc

COPY --from=python /usr/local/ /usr/local/
