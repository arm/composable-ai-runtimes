// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

//! Cairn-owned Perception result types and decoding.

use open_perception_kit::fb::open_perception_kit::metadata as opk;
use open_perception_kit::{EntryRef, NativePayload, ProducerIdentityStatus};

pub use crate::result_model::{
    AudioFrameContext, BitmapData, BoundingBox, BoxDetection, BoxDetections, Classification,
    ClassificationCandidate, Classifications, FrameContext, LayerInfo, ObjectEmbedding,
    ObjectEmbeddings, ObjectMetadata, ObjectTrack, ObjectTracks, PerformanceOverlay,
    PersonPresence, Point2d, PoseEstimation, PoseEstimations, ProducerInfo, SegmentationMask,
    SegmentationMasks, TrackTrace, TrackTraces, VideoFrameContext,
};

/// A decoded result from a Perception session's results topic.
#[derive(Debug)]
pub struct PerceptionResult {
    entries: Vec<PerceptionPayload>,
}

impl PerceptionResult {
    /// Returns payload entries in their original packet order.
    pub fn entries(&self) -> &[PerceptionPayload] {
        &self.entries
    }

    /// Consumes the result and returns its payload entries in packet order.
    pub fn into_entries(self) -> Vec<PerceptionPayload> {
        self.entries
    }

    /// Decodes one raw FLWD result packet with the published OPK Rust SDK.
    ///
    /// # Errors
    ///
    /// Returns a structured error containing the original packet when the
    /// envelope, producer identity, or schema version is invalid.
    pub fn decode(packet: &[u8]) -> Result<Self, PerceptionResultError> {
        let envelope = open_perception_kit::Envelope::decode(packet.to_vec()).map_err(|error| {
            PerceptionResultError::InvalidEnvelope {
                detail: error.to_string(),
                packet: error.into_bytes(),
            }
        })?;
        let context = DecodedEnvelopeContext::from_envelope(packet, &envelope);

        match envelope.producer_identity() {
            ProducerIdentityStatus::ExactMatch => {}
            ProducerIdentityStatus::Missing => {
                return Err(PerceptionResultError::MissingProducerIdentity { context });
            }
            ProducerIdentityStatus::Malformed => {
                return Err(PerceptionResultError::MalformedProducerIdentity { context });
            }
            ProducerIdentityStatus::SdkNameMismatch => {
                return Err(PerceptionResultError::UnexpectedProducer { context });
            }
            ProducerIdentityStatus::SdkVersionMismatch => {
                return Err(PerceptionResultError::UnsupportedProducerVersion { context });
            }
            ProducerIdentityStatus::SchemaSetMismatch => {
                return Err(PerceptionResultError::IncompatibleProducerSchema { context });
            }
        }

        // Keep one iterator per known payload type so restoring envelope order advances
        // each type once instead of repeating OPK's linear lookup for every entry.
        let mut payloads = KnownPayloadIterators::new(&envelope);
        let entries = envelope
            .entries()
            .map(|entry| match entry {
                EntryRef::Known { type_name } => {
                    next_typed_payload(type_name, &mut payloads, &context)
                }
                EntryRef::External { key, bytes } => {
                    Ok(PerceptionPayload::External(ExternalPayload {
                        id: key.value(),
                        bytes: bytes.to_vec(),
                    }))
                }
                EntryRef::Unknown { id, bytes } => Ok(PerceptionPayload::Unknown(UnknownPayload {
                    id,
                    bytes: bytes.to_vec(),
                })),
                EntryRef::MalformedKnown {
                    id,
                    expected_type,
                    bytes,
                    error,
                } => Ok(PerceptionPayload::MalformedKnown(MalformedKnownPayload {
                    id,
                    expected_type: expected_type.to_owned(),
                    bytes: bytes.to_vec(),
                    detail: error.to_string(),
                })),
            })
            .collect::<Result<Vec<_>, _>>()?;

        Ok(Self { entries })
    }
}

/// A decoded or preserved entry in a Perception result packet.
#[derive(Debug)]
pub enum PerceptionPayload {
    /// Object detector output.
    BoxDetections(BoxDetections),
    /// Classification output.
    Classifications(Classifications),
    /// Video or audio frame metadata.
    FrameContext(FrameContext),
    /// Object embedding output.
    ObjectEmbeddings(ObjectEmbeddings),
    /// Object tracker output.
    ObjectTracks(ObjectTracks),
    /// Human-readable performance lines.
    PerformanceOverlay(PerformanceOverlay),
    /// Pose estimation output.
    PoseEstimations(PoseEstimations),
    /// Segmentation output.
    SegmentationMasks(SegmentationMasks),
    /// Object track traces.
    TrackTraces(TrackTraces),
    /// Application-defined opaque data using an OPK external key.
    External(ExternalPayload),
    /// An unrecognized payload retained losslessly.
    Unknown(UnknownPayload),
    /// A recognized payload whose body could not be decoded, retained losslessly.
    MalformedKnown(MalformedKnownPayload),
}

/// Application-defined opaque payload using OPK's reserved external-ID range.
#[derive(Debug)]
pub struct ExternalPayload {
    /// Numeric external key from the wire envelope.
    pub id: u64,
    /// Unmodified payload bytes.
    pub bytes: Vec<u8>,
}

/// Raw payload data whose identifier is not owned by the installed OPK SDK.
#[derive(Debug)]
pub struct UnknownPayload {
    /// Numeric payload identifier from the wire envelope.
    pub id: u64,
    /// Unmodified payload bytes.
    pub bytes: Vec<u8>,
}

/// Raw data and diagnostics for a malformed recognized payload.
#[derive(Debug)]
pub struct MalformedKnownPayload {
    /// Numeric payload identifier from the packet.
    pub id: u64,
    /// Schema type registered for the identifier.
    pub expected_type: String,
    /// Unmodified payload bytes.
    pub bytes: Vec<u8>,
    /// Diagnostic from the registered payload decoder.
    pub detail: String,
}

/// Packet and producer metadata from a successfully decoded result envelope.
#[derive(Debug, Clone)]
pub struct DecodedEnvelopeContext {
    packet: Vec<u8>,
    received_sdk_name: String,
    received_sdk_version: String,
    received_schema_digest: String,
}

impl DecodedEnvelopeContext {
    fn from_envelope(packet: &[u8], envelope: &open_perception_kit::Envelope) -> Self {
        Self {
            packet: packet.to_vec(),
            received_sdk_name: envelope.producer_sdk_name().to_owned(),
            received_sdk_version: envelope.producer_sdk_version().to_owned(),
            received_schema_digest: envelope.producer_schema_set_sha256().to_owned(),
        }
    }

    /// Returns the exact packet supplied to the decoder.
    pub fn packet(&self) -> &[u8] {
        &self.packet
    }

    /// Returns the producer SDK name recorded in the decoded envelope.
    pub fn received_sdk_name(&self) -> &str {
        &self.received_sdk_name
    }

    /// Returns the producer SDK version recorded in the decoded envelope.
    pub fn received_sdk_version(&self) -> &str {
        &self.received_sdk_version
    }

    /// Returns the producer schema digest recorded in the decoded envelope.
    pub fn received_schema_digest(&self) -> &str {
        &self.received_schema_digest
    }
}

/// Error returned when a Perception result packet cannot be decoded safely.
#[derive(Debug)]
pub enum PerceptionResultError {
    /// The packet is not a valid FLWD envelope.
    InvalidEnvelope {
        /// Diagnostic from the FLWD envelope decoder.
        detail: String,
        /// Exact packet supplied to the decoder.
        packet: Vec<u8>,
    },
    /// Required producer identity fields are absent.
    MissingProducerIdentity {
        /// Packet and producer metadata available at the point of failure.
        context: DecodedEnvelopeContext,
    },
    /// A producer identity field has invalid syntax.
    MalformedProducerIdentity {
        /// Packet and producer metadata available at the point of failure.
        context: DecodedEnvelopeContext,
    },
    /// The packet was produced by another SDK.
    UnexpectedProducer {
        /// Packet and producer metadata available at the point of failure.
        context: DecodedEnvelopeContext,
    },
    /// The packet was produced by an unsupported SDK version.
    UnsupportedProducerVersion {
        /// Packet and producer metadata available at the point of failure.
        context: DecodedEnvelopeContext,
    },
    /// The packet's schema digest differs from the installed SDK.
    IncompatibleProducerSchema {
        /// Packet and producer metadata available at the point of failure.
        context: DecodedEnvelopeContext,
    },
    /// A known payload uses an unsupported schema major version.
    UnsupportedPayloadSchemaVersion {
        /// Registered payload schema type.
        payload_type: String,
        /// Received schema major version.
        schema_major: u16,
        /// Received schema minor version.
        schema_minor: u16,
        /// Schema major version accepted by Cairn.
        supported_schema_major: u16,
        /// Packet and producer metadata available at the point of failure.
        context: DecodedEnvelopeContext,
    },
}

impl PerceptionResultError {
    /// Returns the decoded-envelope context when envelope decoding succeeded.
    pub fn decoded_envelope_context(&self) -> Option<&DecodedEnvelopeContext> {
        match self {
            Self::InvalidEnvelope { .. } => None,
            Self::MissingProducerIdentity { context }
            | Self::MalformedProducerIdentity { context }
            | Self::UnexpectedProducer { context }
            | Self::UnsupportedProducerVersion { context }
            | Self::IncompatibleProducerSchema { context }
            | Self::UnsupportedPayloadSchemaVersion { context, .. } => Some(context),
        }
    }

    /// Returns the exact packet supplied to the decoder.
    pub fn packet(&self) -> &[u8] {
        match self {
            Self::InvalidEnvelope { packet, .. } => packet,
            _ => self
                .decoded_envelope_context()
                .expect("non-envelope errors must carry decoded-envelope context")
                .packet(),
        }
    }
}

impl std::fmt::Display for PerceptionResultError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::InvalidEnvelope { detail, .. } => {
                write!(formatter, "invalid Perception result envelope: {detail}")
            }
            Self::MissingProducerIdentity { .. } => {
                formatter.write_str("Perception result producer identity is missing")
            }
            Self::MalformedProducerIdentity { context } => write!(
                formatter,
                "malformed Perception result producer identity: sdk={:?} version={:?}",
                Some(context.received_sdk_name()),
                Some(context.received_sdk_version())
            ),
            Self::UnexpectedProducer { context } => write!(
                formatter,
                "unexpected Perception result producer {:?}; expected {:?}",
                Some(context.received_sdk_name()),
                open_perception_kit::OPEN_PERCEPTION_KIT_NAME
            ),
            Self::UnsupportedProducerVersion { context } => write!(
                formatter,
                "unsupported Perception producer version {:?}; expected {:?}",
                Some(context.received_sdk_version()),
                open_perception_kit::OPEN_PERCEPTION_KIT_VERSION
            ),
            Self::IncompatibleProducerSchema { .. } => {
                formatter.write_str("incompatible Perception producer schema")
            }
            Self::UnsupportedPayloadSchemaVersion {
                payload_type,
                schema_major,
                schema_minor,
                supported_schema_major,
                ..
            } => write!(
                formatter,
                "unsupported {payload_type} schema version {schema_major}.{schema_minor}; supported major is {supported_schema_major}"
            ),
        }
    }
}

impl std::error::Error for PerceptionResultError {}

const SUPPORTED_PAYLOAD_SCHEMA_MAJOR: u16 = 1;

struct KnownPayloadIterators<'a> {
    box_detections: open_perception_kit::PayloadIter<'a, opk::BoxDetectionsT>,
    classifications: open_perception_kit::PayloadIter<'a, opk::ClassificationsT>,
    frame_contexts: open_perception_kit::PayloadIter<'a, opk::FrameContextT>,
    object_embeddings: open_perception_kit::PayloadIter<'a, opk::ObjectEmbeddingsT>,
    object_tracks: open_perception_kit::PayloadIter<'a, opk::ObjectTracksT>,
    performance_overlays: open_perception_kit::PayloadIter<'a, opk::PerformanceOverlayT>,
    pose_estimations: open_perception_kit::PayloadIter<'a, opk::PoseEstimationsT>,
    segmentation_masks: open_perception_kit::PayloadIter<'a, opk::SegmentationMasksT>,
    track_traces: open_perception_kit::PayloadIter<'a, opk::TrackTracesT>,
}

impl<'a> KnownPayloadIterators<'a> {
    fn new(envelope: &'a open_perception_kit::Envelope) -> Self {
        Self {
            box_detections: envelope
                .for_each(open_perception_kit::payload::<opk::BoxDetectionsT>()),
            classifications: envelope
                .for_each(open_perception_kit::payload::<opk::ClassificationsT>()),
            frame_contexts: envelope.for_each(open_perception_kit::payload::<opk::FrameContextT>()),
            object_embeddings: envelope
                .for_each(open_perception_kit::payload::<opk::ObjectEmbeddingsT>()),
            object_tracks: envelope.for_each(open_perception_kit::payload::<opk::ObjectTracksT>()),
            performance_overlays: envelope
                .for_each(open_perception_kit::payload::<opk::PerformanceOverlayT>()),
            pose_estimations: envelope
                .for_each(open_perception_kit::payload::<opk::PoseEstimationsT>()),
            segmentation_masks: envelope
                .for_each(open_perception_kit::payload::<opk::SegmentationMasksT>()),
            track_traces: envelope.for_each(open_perception_kit::payload::<opk::TrackTracesT>()),
        }
    }
}

fn next_typed_payload(
    type_name: &str,
    payloads: &mut KnownPayloadIterators<'_>,
    context: &DecodedEnvelopeContext,
) -> Result<PerceptionPayload, PerceptionResultError> {
    Ok(match type_name {
        opk::BoxDetectionsT::NAME => PerceptionPayload::BoxDetections(
            next_validated_payload(&mut payloads.box_detections, context, |payload| {
                (payload.schema_major, payload.schema_minor)
            })?
            .into(),
        ),
        opk::ClassificationsT::NAME => PerceptionPayload::Classifications(
            next_validated_payload(&mut payloads.classifications, context, |payload| {
                (payload.schema_major, payload.schema_minor)
            })?
            .into(),
        ),
        opk::FrameContextT::NAME => PerceptionPayload::FrameContext(
            next_validated_payload(&mut payloads.frame_contexts, context, |payload| {
                (payload.schema_major, payload.schema_minor)
            })?
            .into(),
        ),
        opk::ObjectEmbeddingsT::NAME => PerceptionPayload::ObjectEmbeddings(
            next_validated_payload(&mut payloads.object_embeddings, context, |payload| {
                (payload.schema_major, payload.schema_minor)
            })?
            .into(),
        ),
        opk::ObjectTracksT::NAME => PerceptionPayload::ObjectTracks(
            next_validated_payload(&mut payloads.object_tracks, context, |payload| {
                (payload.schema_major, payload.schema_minor)
            })?
            .into(),
        ),
        opk::PerformanceOverlayT::NAME => PerceptionPayload::PerformanceOverlay(
            next_validated_payload(&mut payloads.performance_overlays, context, |payload| {
                (payload.schema_major, payload.schema_minor)
            })?
            .into(),
        ),
        opk::PoseEstimationsT::NAME => PerceptionPayload::PoseEstimations(
            next_validated_payload(&mut payloads.pose_estimations, context, |payload| {
                (payload.schema_major, payload.schema_minor)
            })?
            .into(),
        ),
        opk::SegmentationMasksT::NAME => PerceptionPayload::SegmentationMasks(
            next_validated_payload(&mut payloads.segmentation_masks, context, |payload| {
                (payload.schema_major, payload.schema_minor)
            })?
            .into(),
        ),
        opk::TrackTracesT::NAME => PerceptionPayload::TrackTraces(
            next_validated_payload(&mut payloads.track_traces, context, |payload| {
                (payload.schema_major, payload.schema_minor)
            })?
            .into(),
        ),
        _ => unreachable!("OPK reported an unknown entry as known: {type_name}"),
    })
}

fn next_validated_payload<T: NativePayload + Clone>(
    payloads: &mut open_perception_kit::PayloadIter<'_, T>,
    context: &DecodedEnvelopeContext,
    schema_version: impl FnOnce(&T) -> (u16, u16),
) -> Result<T, PerceptionResultError> {
    let payload = payloads
        .next()
        .expect("known envelope entry must remain selectable");
    let (schema_major, schema_minor) = schema_version(payload);
    validate_schema(T::NAME, schema_major, schema_minor, context)?;
    Ok(payload.clone())
}

fn validate_schema(
    payload_type: &'static str,
    schema_major: u16,
    schema_minor: u16,
    context: &DecodedEnvelopeContext,
) -> Result<(), PerceptionResultError> {
    if schema_major == SUPPORTED_PAYLOAD_SCHEMA_MAJOR {
        return Ok(());
    }
    Err(PerceptionResultError::UnsupportedPayloadSchemaVersion {
        payload_type: payload_type.to_owned(),
        schema_major,
        schema_minor,
        supported_schema_major: SUPPORTED_PAYLOAD_SCHEMA_MAJOR,
        context: context.clone(),
    })
}
