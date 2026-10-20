<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

# Composable AI Runtimes

Composable AI Runtimes (Cairn) provides containerized runtime services for edge and
physical AI applications on Arm Linux devices. It lets you compose AI workflows
through consistent Rust and Python APIs. Its camera, perception, and messaging
services reduce the boilerplate needed to discover cameras, run inference
workflows, and receive detection events.

Cairn includes:

- [Camera Service](./services/camera/README.md): Discovers cameras and makes their streams available.
- [Messaging Service](./services/messaging/README.md): Lets services and applications publish and subscribe to messaging.
- [Perception Service](./services/perception/README.md): Deploys and runs inference workflows on camera streams.
- [Client libraries](./lib/README.md): Rust and Python APIs for interacting with Cairn services.

## Table of contents

- [Getting started](#getting-started)
- [Cairn bundles and versioning](#cairn-bundles-and-versioning)
- [Network security](#network-security)
- [License and contributions](#license-and-contributions)

## Getting started

### Compatibility

Cairn is designed to be hardware agnostic across Arm Linux devices. The table
below lists the configurations validated so far; other devices and operating
systems have not been validated.

| Component          | Validated configuration         |
| ------------------ | ------------------------------- |
| Device             | Raspberry Pi 5                  |
| Operating system   | Raspberry Pi OS 64-bit (Trixie) |
| Container Runtime  | Docker, Podman                  |
| Container platform | Linux ARM64                     |
| CSI camera         | Raspberry Pi Camera Module 3    |
| USB webcam         | UVC (USB Video Class) webcam    |

### Prerequisites

- [Docker](https://docs.docker.com/get-started/get-docker/) installed and running
  on both your development machine and target device.
- [Topo](https://github.com/arm/topo#installation) installed on your development machine.

### Run an example

We recommend starting with the
[object detection example](https://github.com/Arm-Examples/cairn-perception-object-detection/blob/main/README.md)
before moving to build an application.

### Build an application

Use the [Rust or Python client libraries](./lib/README.md) to build applications
that act on inference results from runtime services.

## Cairn bundles and versioning

[Cairn bundles](https://github.com/arm/cairn-sdk/releases) are compatible
immutable versions of components tested together. Cairn is made of discrete
components including user libraries, services and product documentation, each
with its own release cycle and [Semantic Versioning](https://semver.org/).

## Network security

Cairn uses [host networking](./services/camera/compose.yaml) to detect camera
connections. These settings can expose service APIs to other devices on the
network, so use a firewall to prevent unwanted access.

## License and contributions

Cairn is licensed under [Apache-2.0](./LICENSE). We are not accepting external
contributions at this time. See [SECURITY.md](./SECURITY.md) to report security
vulnerabilities.

Container images have attached source and license reports. Use ORAS to discover
the reports associated with an image index digest, then download a report using
its digest:

```sh
oras discover --artifact-type application/vnd.cairn.dependency-sources \
  REGISTRY/IMAGE@sha256:IMAGE_DIGEST
oras pull --output ./source-links REGISTRY/IMAGE@sha256:REPORT_DIGEST
```

New service releases attach an SBOM ZIP containing the image SBOMs, a Rust
dependency SBOM for Rust services, and the SBOM disclaimer:

```sh
oras discover --artifact-type application/vnd.cairn.sbom-bundle \
  REGISTRY/IMAGE@sha256:IMAGE_DIGEST
oras pull --output ./sbom REGISTRY/IMAGE@sha256:BUNDLE_DIGEST
unzip ./sbom/sbom.zip -d ./sbom
```

Older releases attach individual SBOMs using the `application/spdx+json` type.
