<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

# Cairn Messaging Envelope Specification

## Status

Version: 0.1

This specification is an alpha release and may introduce breaking changes without notice.

## Requirement language

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are
used as defined by
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and
[RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) when they appear in capitals.

## Introduction
This specification defines a common envelope contract; all events transmitted through the messaging service must follow this structure.

## Scope
This specification defines the envelope used to pass Messaging Service events. This specification defines the structure of the envelope describing the event; it does not define the structure of the payload within the message.

## Envelope Specification
Any event transmitted through the Messaging Service must be a [protocol buffer](https://protobuf.dev/) message, that MUST contain only the following fields.

The canonical protobuf definition is available in the [Cairn Messaging Service
event envelope](../../services/messaging/proto/cairn/messaging/v1/messaging.proto).

- `timestamp`: A UTC timestamp recording the time of the creation of this event envelope. It is preserved across retries.
- `origin`: The [Cairn Service Identifier](glossary.md#cairn-service-identifier) of the service from which this event originated.
- `event_type`: The [Cairn Event Identifier](glossary.md#cairn-event-identifier) for this event.
- `topic`: The pub/sub topic that the event has been published to.
- `payload`: The payload of the event. The structure of the payload is defined by the applicable topic or event contract.

All of the above fields are required for the event envelope to be valid. The encoding senders MUST validate the alignment with the above specification before sending the event. Consumers SHOULD make the best effort at decoding, warning the user if an invalid event is received. The handling of invalid events is left at the discretion of the user.

## Ownership and Versioning
The contract is owned by and is versioned together with the Cairn Messaging Service. It must be published as a part of the OCI release bundle of the Messaging Service.

As the other release components, the Event Envelope contract is versioned according to [Semantic Versioning 2.0.0](https://semver.org/). Its compatibility with other release components is defined by the compatibility rules of Semantic Versioning.

## Unknown Events
An event is classed as unknown if the consumer does not recognize the `event_type` and has no registered decoder. In the case of an unknown event being received by the consumer, the consumer MAY handle the event in the approach most fit for that consumer.


## Example


```textproto
timestamp {
  seconds: 1735689600
}
origin: "cairn.camera-service"
event_type: "cairn.camera.connected"
topic: "camera.events"
payload: "{\"event_type\":\"connected\",\"id\":42,\"name\":\"front-door\"}"
```

The `payload` value above is shown as UTF-8 JSON bytes for readability. The
payload format is illustrative; each topic or event contract defines its own
payload structure.
