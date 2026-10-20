# syntax=docker/dockerfile:1
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

FROM docker.io/library/debian:trixie@sha256:3352c2e13876c8a5c5873ef20870e1939e73cb9a3c1aeba5e3e72172a85ce9ed

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    gstreamer1.0-pipewire=1.4.2-1 \
    gstreamer1.0-plugins-base=1.26.2-1+deb13u2 \
    gstreamer1.0-plugins-good=1.26.2-1+deb13u2 \
    gstreamer1.0-tools=1.26.2-2 \
    pipewire=1.4.2-1 \
    wireplumber=0.5.8-2 \
  && rm -rf /var/lib/apt/lists/*

# UltraFace's sample supplies faces for the BlazeFace BYOM test.
ADD --checksum=sha256:c83c559908a902dcb69e6aaaa7ddd80eb1aec90654c59d35676c0cbf96adee67 --chmod=644 \
    https://huggingface.co/Arm/ultraface-rfb-320-onnx-raspberry/resolve/dd894b3db6ac5ac2bcff20e5cab96b40a4402855/sample_input.jpg /sample_input.jpg
COPY --chmod=644 sample_input.jpg.LICENSE /sample_input.jpg.LICENSE

ENV XDG_RUNTIME_DIR=/run/pipewire

COPY --chmod=755 entrypoint.sh /usr/local/bin/pipewire-source-entrypoint.sh

HEALTHCHECK --interval=1s --timeout=2s --start-period=10s --retries=20 \
  CMD pw-dump | grep -Fq -- "gstreamer-test-source" \
    || { echo "PipeWire source gstreamer-test-source is not visible"; exit 1; }

ENTRYPOINT ["/usr/local/bin/pipewire-source-entrypoint.sh"]
