<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

# Cairn Glossary

This glossary defines shared terminology used across Cairn specifications. It
is descriptive and does not introduce conformance requirements.

## Cairn System

A deployed set of Cairn Services and user applications that communicate to provide functionality.

## Cairn Service

An OCI-compliant container image that conforms to the [Cairn Service
Extensibility Specification](service-extensibility.md).

## Cairn Service Identifier

A stable name used to reference a Cairn Service in manifests and tooling. It
uses a provider-owned namespace and remains unchanged across deployments and
releases, as defined by the [Cairn Service Extensibility
Specification](service-extensibility.md#identifiers-and-versioning).

## Cairn Event Identifier

A unique identifier used to reference an event in messaging contracts. Like a
Cairn Service Identifier, it uses a provider-owned namespace and remains
unchanged across deployments and releases.

## Cairn Core Service

A Cairn Service that provides functionality for use by other Cairn Services.

## Cairn Solution Service

A Cairn Service that provides a workflow for use by a user application.

## Cairn Manifest

A Compose-based document that declares the metadata, interfaces,
communication, dependencies, and operational contract for a Cairn Service.

## Cairn Library

The client library used by user applications to interact with Cairn Services.

## Cairn Service Contract

The manifest and referenced schemas that describe how consumers discover,
connect to, and use a Cairn Service.

## Required Dependency

A dependency that must be available for a Cairn Service to operate correctly.

## Optional Dependency

A dependency that enables additional functionality but is not required for a
Cairn Service to operate.

## Public API

A documented interface or contract that a Cairn Service exposes for use outside its service boundary.

## User application

Application code that uses one or more Cairn Services to deliver a user workflow.
