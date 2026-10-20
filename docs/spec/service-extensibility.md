<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

# Cairn Service Extensibility Specification

## Status

Version: 0.1

This specification is an alpha release and may introduce breaking changes without notice.

## Table of contents

- [Introduction](#introduction)
  - [Scope](#scope)
  - [Related specifications](#related-documents)
- [Requirement language](#requirement-language)
- [Service model](#service-model)
- [Compatibility requirements](#compatibility-requirements)
  - [Identifiers and versioning](#identifiers-and-versioning)
  - [Interfaces and communication](#interfaces-and-communication)
  - [Dependencies](#dependencies)
  - [Packaging and deployment](#packaging-and-deployment)
  - [Operational behavior](#operational-behavior)

## Introduction

This specification defines a common contract for deploying, connecting, and
operating services consistently in a [Cairn system](glossary.md#cairn-system).

### Scope

A [Cairn Service](glossary.md#cairn-service) is an OCI-compliant container image that conforms to this specification. This specification covers packaging, identity, interfaces, communication, dependencies, and operational behavior.

Extension of the [Cairn Library](glossary.md#cairn-library) is outside the
scope of this specification.

### Related documents

- The [Cairn Glossary](glossary.md) defines terminology shared across Cairn
  specifications without introducing conformance requirements.
- The [Cairn Compose manifest schema](schema/compose.cairn.schema.yaml)
  defines the manifest used by Cairn tooling.
- The [Cairn Messaging Envelope](event-envelope.md) defines the common
  structure of events published through the Cairn Messaging Service.

## Requirement language

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are
used as defined by
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and
[RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) when they appear in capitals.

## Service model

A [**Cairn Service**](glossary.md#cairn-service) **MUST** conform to this
specification.

Cairn Services are classified as either
[Cairn Core Services](glossary.md#cairn-core-service) or
[Cairn Solution Services](glossary.md#cairn-solution-service).

At this time, the Core classification is assigned by Cairn maintainers and
**MUST NOT** be declared by third-party service authors.

## Compatibility requirements

### Identifiers and versioning

A Cairn Service identifier is a stable name used to reference a service in manifests and tooling. It **MUST** use a provider-owned namespace and **MUST** remain unchanged across deployments and releases. Changing the identifier creates a new Cairn Service rather than a new version of the existing service. The "cairn." namespace is reserved for Cairn-owned services and **MUST NOT** be used unless the service has been reviewed and accepted as Cairn-owned.

This specification and the
[Cairn Compose manifest schema](schema/compose.cairn.schema.yaml) are versioned
independently as `spec/v<major>.<minor>` and
`service-manifest-schema/v<major>.<minor>`.

Cairn Compose manifests declare the schema version they use in
`x-cairn.format_version`.

### Interfaces and communication

A Cairn Service **MUST** expose a documented gRPC interface defined using
protobuf.

Each event published through the Cairn Messaging Service **MUST** conform to the
[Cairn Messaging Envelope Specification](event-envelope.md).

Each event payload **MUST** conform to the payload format and schema declared
for its topic in the manifest.

### Dependencies

A Cairn Service **MUST** declare each dependency in the
[manifest](glossary.md#cairn-manifest), using the dependency’s stable Cairn
Service identifier, as either
[required](glossary.md#required-dependency) for operation or
[optional](glossary.md#optional-dependency).

A Cairn Service **MAY** depend on other Cairn Core Services but **MUST NOT**
depend on Cairn Solution Services. The graph formed by required dependencies
**MUST** be acyclic.

### Packaging and deployment

A Cairn Service **MUST** be packaged as a container image that conforms to the
[OCI Image Format Specification](https://specs.opencontainers.org/image-spec/)
and supports the `linux/arm64` platform. A multi-platform image is conforming
when `linux/arm64` is one of its supported platforms.

Every Cairn Service **MUST** provide a [manifest](glossary.md#cairn-manifest)
that conforms to the
[Cairn Compose manifest schema](schema/compose.cairn.schema.yaml).

Every Cairn Service **MUST** publish a
[service contract](glossary.md#cairn-service-contract) OCI artifact containing
its manifest and referenced schemas. The artifact **MUST** be published in the
same registry repository as the service image and associated with that image
using the OCI `subject` relationship.

The service image **SHOULD** include the standard OCI `org.opencontainers.image.source` and `org.opencontainers.image.revision` annotations.

### Operational behavior

Cairn uses a common readiness signal to determine whether a Cairn Service can
participate in the system. A Cairn Service **MUST** implement
`grpc.health.v1.Health`. A health check request with an empty `service` field
**MUST** report readiness for the Cairn Service as a whole. A Cairn Service
**MAY** additionally report health for named gRPC services.

A Cairn Service **MUST** report `SERVING` only while it is initialized and its required interfaces and dependencies are available. An unavailable optional dependency **MUST NOT** prevent it from reporting `SERVING`.
An unrecoverable failure that prevents further operation **MUST** cause the
Cairn Service container to exit with a non-zero status.

A Cairn Service **MUST** tolerate restart without preservation of in-memory
state. State that must survive restart **MUST** be stored in declared persistent
storage.

Operational logs **MUST** be written to `stdout` or `stderr`.
