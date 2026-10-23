# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

ARG PYTHON_IMAGE=docker.io/library/python:3.13.17-slim-trixie@sha256:19ed48e5e9c132082510ba9efb11bc2098d582f610374670fa30b6b17026617b
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff
ARG PIPEWIRE_VERSION=1.6.9
ARG PIPEWIRE_COMMIT=8fa27cabdc6c0c1350c69c026af5850ef0af1e26

FROM ${PYTHON_IMAGE} AS package-repositories

FROM ghcr.io/grpc-ecosystem/grpc-health-probe:v0.4.51@sha256:cc4ff9327e602119103bedef448eec26f8ba02bce5c81107cb3685c360c4a6c0 AS grpc-health-probe

FROM ${UV_IMAGE} AS uv

FROM package-repositories AS opk-package-acquisition

ARG DEBIAN_FRONTEND=noninteractive
ARG OPK_PACKAGE_URL=https://artifacts.tools.arm.com/open-perception-kit/v0.1.1/opk-release-artifacts/opk-0.1.1-linux-aarch64.tar.gz
ARG OPK_PACKAGE_SHA256=2bfdd529a1efef40fc6160f9f548ae9e402d1276d6b5120a5709815fba5fb73f

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    curl=8.14.1-2+deb13u7 \
  && rm -rf /var/lib/apt/lists/*

COPY --chmod=0755 scripts/docker/fetch_opk_package.sh /usr/local/bin/fetch-opk-package

RUN fetch-opk-package \
    "${OPK_PACKAGE_URL}" \
    "${OPK_PACKAGE_SHA256}" \
    /tmp/opk-package.tar.gz \
  && mkdir -p \
    /opt/opk/lib/gstreamer-1.0 \
    /opt/opk/lib/opk \
    /opt/opk/share/opk \
    /opt/opk/web \
    /tmp/opk-package \
  && tar --extract --gzip \
    --file /tmp/opk-package.tar.gz \
    --directory /tmp/opk-package \
    --strip-components 1 \
    --no-same-owner \
    --no-same-permissions \
  && cp \
    /tmp/opk-package/lib/gstreamer-1.0/libopkcomm.so \
    /tmp/opk-package/lib/gstreamer-1.0/libopkinfer.so \
    /tmp/opk-package/lib/gstreamer-1.0/libopkosd.so \
    /tmp/opk-package/lib/gstreamer-1.0/libopkperformance.so \
    /tmp/opk-package/lib/gstreamer-1.0/libopksink.so \
    /opt/opk/lib/gstreamer-1.0/ \
  && cp -a \
    /tmp/opk-package/lib/opk/libonnxruntime.so.* \
    /tmp/opk-package/lib/opk/libopk-common.so \
    /tmp/opk-package/lib/opk/opk-executorch-ops.so \
    /tmp/opk-package/lib/opk/opk-onnx-ops.so \
    /tmp/opk-package/lib/opk/opk-python-ops.so \
    /tmp/opk-package/lib/opk/opk-std-ops.so \
    /opt/opk/lib/opk/ \
  && cp -a \
    /tmp/opk-package/share/opk/licenses \
    /tmp/opk-package/share/opk/python \
    /tmp/opk-package/share/opk/schemas \
    /opt/opk/share/opk/ \
  && cp -a /tmp/opk-package/web/content /opt/opk/web/ \
  && rm -rf \
    /opt/opk/web/content/models.test.mjs \
    /tmp/opk-package \
    /tmp/opk-package.tar.gz

FROM package-repositories AS pipewire-client-build

ARG DEBIAN_FRONTEND=noninteractive
ARG PIPEWIRE_VERSION
ARG PIPEWIRE_COMMIT

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    build-essential=12.12 \
    git=1:2.47.3-0+deb13u1 \
    libcairo2-dev=1.18.4-1+b1 \
    libgirepository-2.0-dev=2.84.4-3~deb13u5 \
    libgstreamer-plugins-base1.0-dev=1.26.2-1+deb13u2 \
    libgstreamer1.0-dev=1.26.2-2 \
    meson=1.7.0-1 \
    ninja-build=1.12.1-1+b1 \
    pkg-config=1.8.1-4 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp
RUN git clone --branch "${PIPEWIRE_VERSION}" --depth 1 \
      https://gitlab.freedesktop.org/pipewire/pipewire.git pipewire-src \
  && test "$(git -C pipewire-src rev-parse HEAD)" = "${PIPEWIRE_COMMIT}" \
  && git -C pipewire-src rev-parse HEAD > pipewire-src/source-revision

WORKDIR /tmp/pipewire-src
RUN arch="$(dpkg-architecture -qDEB_HOST_MULTIARCH)" \
  && meson setup build \
      --buildtype=release \
      --prefix=/usr \
      --libdir="/usr/lib/${arch}" \
      -Dauto_features=disabled \
      -Ddbus=disabled \
      -Ddocs=disabled \
      -Dexamples=disabled \
      -Dgstreamer=enabled \
      -Dgstreamer-device-provider=disabled \
      -Dman=disabled \
      -Dpipewire-jack=disabled \
      -Dpipewire-v4l2=disabled \
      -Drlimits-install=false \
      -Dsession-managers=[] \
      -Dlibsystemd=disabled \
      -Dtests=disabled \
  && meson compile -C build \
  && meson install -C build --destdir /opt/pipewire-root --strip

# Check the source-built installation, not distro-provided PipeWire files.
RUN exceptions="$(find /opt/pipewire-root \( -name 'libspa-alsa.so*' -o -name 'libjackserver.so*' \) -print -quit)" \
  && test -z "$exceptions" \
  || { echo "Review PipeWire license exceptions: $exceptions" >&2; exit 1; }

FROM package-repositories AS runtime-base

ARG PERCEPTION_SERVICE_UID=10002
ARG PERCEPTION_SERVICE_GID=10002

RUN groupadd --system --gid "${PERCEPTION_SERVICE_GID}" perception-service \
  && useradd --system --uid "${PERCEPTION_SERVICE_UID}" --gid perception-service \
    --create-home --home-dir /home/perception-service --shell /usr/sbin/nologin perception-service \
  && mkdir -p /app /models /run/pipewire \
  && chown -R perception-service:perception-service /app /home/perception-service

WORKDIR /app

FROM pipewire-client-build AS python-dependencies

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --locked --no-dev --no-install-project

COPY scripts/docker/wheel_sbom.py scripts/docker/wheel_sbom.toml /tmp/wheel-sbom/
RUN --mount=type=cache,target=/root/.cache/uv \
    UV_PROJECT_ENVIRONMENT=/tmp/sbom-venv uv sync --locked --only-group sbom --no-install-project \
    && /tmp/sbom-venv/bin/python /tmp/wheel-sbom/wheel_sbom.py \
    /app/.venv/lib/python3.13/site-packages /app/wheel-sbom.spdx.json

FROM runtime-base AS runtime-common

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    gir1.2-gst-plugins-base-1.0=1.26.2-1+deb13u2 \
    gir1.2-gstreamer-1.0=1.26.2-2 \
    gstreamer1.0-nice=0.1.22-1 \
    gstreamer1.0-plugins-bad=1.26.2-3+deb13u3 \
    gstreamer1.0-plugins-base=1.26.2-1+deb13u2 \
    gstreamer1.0-plugins-good=1.26.2-1+deb13u2 \
    gstreamer1.0-tools=1.26.2-2 \
    libcairo2=1.18.4-1+b1 \
    libgirepository-2.0-0=2.84.4-3~deb13u5 \
    libgstreamer1.0-0=1.26.2-2 \
    libjson-glib-1.0-0=1.10.6+ds-2 \
    libsoup-3.0-0=3.6.5-3 \
    libssl3t64=3.5.7-1~deb13u3 \
    libusb-1.0-0=2:1.0.28-1 \
    python3-gst-1.0=1.26.2-1 \
  && rm -rf /var/lib/apt/lists/*

# Install the pinned PipeWire build last so APT cannot replace its SPA plugins.
COPY --from=pipewire-client-build /opt/pipewire-root/usr/lib/ /usr/lib/
COPY --from=pipewire-client-build \
  /opt/pipewire-root/usr/share/pipewire/client.conf /usr/share/pipewire/client.conf
COPY --from=pipewire-client-build \
  /tmp/pipewire-src/COPYING /tmp/pipewire-src/LICENSE \
  /tmp/pipewire-src/source-revision /usr/share/doc/pipewire/
COPY licenses/pipewire.cdx.json /usr/share/doc/pipewire/pipewire.cdx.json
RUN ldconfig

ENV GST_PLUGIN_PATH=/opt/opk/lib/gstreamer-1.0

COPY --from=opk-package-acquisition /opt/opk/ /opt/opk/

COPY --from=python-dependencies --chown=perception-service:perception-service \
  /app/.venv /app/.venv
COPY --from=python-dependencies /app/wheel-sbom.spdx.json /usr/share/cairn/sbom/wheel-sbom.spdx.json
COPY --chown=perception-service:perception-service src /app/src

COPY --from=grpc-health-probe /ko-app/grpc-health-probe /usr/local/bin/grpc_health_probe

ENV VIRTUAL_ENV=/app/.venv \
    PYTHONPATH=/app/src \
    XDG_RUNTIME_DIR=/run/pipewire

HEALTHCHECK --interval=5s --timeout=6s --start-period=15s --retries=12 \
  CMD ["grpc_health_probe", "-addr=127.0.0.1:50053"]

USER perception-service

CMD ["/app/.venv/bin/python", "-B", "-m", "perception_service", "--model-path", "/models", "--model-schema-path", "/opt/opk/share/opk/schemas/json/v1"]

FROM runtime-common AS runtime

LABEL org.opencontainers.image.licenses="Apache-2.0"

COPY LICENSE /usr/share/licenses/cairn/LICENSE
COPY THIRD-PARTY-DISCLAIMER.txt /THIRD-PARTY-DISCLAIMER.txt
COPY notices/ /usr/share/licenses/cairn/
