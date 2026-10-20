// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

use open_perception_kit::fb::open_perception_kit::metadata as opk;
use open_perception_kit::{Envelope, NativePayload, external_key, external_payload};

use super::{
    PerceptionPayload, PerceptionResult, PerceptionResultError,
    result::{BoundingBox, BoxDetection, BoxDetections, ClassificationCandidate, ObjectMetadata},
};

const BOX_DETECTIONS_ID: u64 = 556_103_652_012_567_315;

fn replace_once(bytes: &mut [u8], from: &[u8], to: &[u8]) {
    assert_eq!(from.len(), to.len());
    let offset = bytes
        .windows(from.len())
        .position(|window| window == from)
        .expect("test packet should contain replacement target");
    bytes[offset..offset + to.len()].copy_from_slice(to);
}

fn clear_string(bytes: &mut [u8], value: &[u8]) {
    let offset = bytes
        .windows(value.len())
        .position(|window| window == value)
        .expect("test packet should contain string");
    bytes[offset - std::mem::size_of::<u32>()..=offset].fill(0);
}

#[test]
fn decode_preserves_known_payload_order() {
    let first = opk::BoxDetectionsT::default();
    let mut second = opk::BoxDetectionsT::default();
    second.schema_minor = 1;

    let mut envelope = Envelope::new();
    envelope.add(first);
    envelope.add(opk::ClassificationsT::default());
    envelope.add(second);
    let result = PerceptionResult::decode(&envelope.serialize()).expect("packet should decode");

    assert_eq!(result.entries().len(), 3);
    assert!(matches!(
        result.entries()[0],
        PerceptionPayload::BoxDetections(BoxDetections {
            schema_minor: 0,
            ..
        })
    ));
    assert!(matches!(
        result.entries()[1],
        PerceptionPayload::Classifications(_)
    ));
    assert!(matches!(
        result.entries()[2],
        PerceptionPayload::BoxDetections(BoxDetections {
            schema_minor: 1,
            ..
        })
    ));
}

#[test]
fn decode_maps_nested_metadata_to_cairn_types() {
    let mut layer = opk::LayerInfoT::default();
    layer.model = Some("detector-a".to_owned());
    let mut detection = opk::BoxDetectionT::default();
    detection.class_id = 3;
    detection.text = Some("car".to_owned());
    let mut first = opk::BoxDetectionsT::default();
    first.layer = Some(Box::new(layer));
    first.detections = Some(vec![detection]);

    let mut envelope = Envelope::new();
    envelope.add(first);
    let result = PerceptionResult::decode(&envelope.serialize()).expect("packet should decode");

    let PerceptionPayload::BoxDetections(BoxDetections {
        layer: Some(layer),
        detections: Some(detections),
        ..
    }) = &result.entries()[0]
    else {
        panic!("first entry should be Cairn-owned box detections");
    };
    assert_eq!(layer.model.as_deref(), Some("detector-a"));
    assert_eq!(detections[0].class_id, 3);
    assert_eq!(detections[0].text.as_deref(), Some("car"));
}

#[test]
fn box_detection_mapping_preserves_nested_metadata() {
    let mut object = opk::ObjectMetaT::default();
    object.creation_ts_ns = 42;
    let mut bounding_box = opk::BoundingBoxT::default();
    bounding_box.width = 30.75;
    bounding_box.height = 40.5;
    let mut detection = opk::BoxDetectionT::default();
    detection.object = Some(Box::new(object));
    detection.box_ = Some(Box::new(bounding_box));

    let mapped = BoxDetection::from(detection);

    assert!(matches!(
        mapped.object,
        Some(ObjectMetadata {
            creation_timestamp_ns: 42,
            ..
        })
    ));
    assert!(matches!(
        mapped.bounding_box,
        Some(BoundingBox { width, height, .. })
            if width == 30.75 && height == 40.5
    ));
}

#[test]
fn classification_candidate_mapping_preserves_renamed_fields() {
    let mut candidate = opk::ClassificationCandidateT::default();
    candidate.w = 12.5;
    candidate.h = 8.25;

    let mapped = ClassificationCandidate::from(candidate);
    assert_eq!(mapped.width, 12.5);
    assert_eq!(mapped.height, 8.25);
}

#[test]
fn decode_exposes_all_nine_result_families() {
    let mut envelope = Envelope::new();
    envelope.add(opk::BoxDetectionsT::default());
    envelope.add(opk::ClassificationsT::default());
    envelope.add(opk::FrameContextT::default());
    envelope.add(opk::ObjectEmbeddingsT::default());
    envelope.add(opk::ObjectTracksT::default());
    envelope.add(opk::PerformanceOverlayT::default());
    envelope.add(opk::PoseEstimationsT::default());
    envelope.add(opk::SegmentationMasksT::default());
    envelope.add(opk::TrackTracesT::default());

    let result = PerceptionResult::decode(&envelope.serialize()).expect("packet should decode");

    assert!(matches!(
        result.entries()[0],
        PerceptionPayload::BoxDetections(_)
    ));
    assert!(matches!(
        result.entries()[1],
        PerceptionPayload::Classifications(_)
    ));
    assert!(matches!(
        result.entries()[2],
        PerceptionPayload::FrameContext(_)
    ));
    assert!(matches!(
        result.entries()[3],
        PerceptionPayload::ObjectEmbeddings(_)
    ));
    assert!(matches!(
        result.entries()[4],
        PerceptionPayload::ObjectTracks(_)
    ));
    assert!(matches!(
        result.entries()[5],
        PerceptionPayload::PerformanceOverlay(_)
    ));
    assert!(matches!(
        result.entries()[6],
        PerceptionPayload::PoseEstimations(_)
    ));
    assert!(matches!(
        result.entries()[7],
        PerceptionPayload::SegmentationMasks(_)
    ));
    assert!(matches!(
        result.entries()[8],
        PerceptionPayload::TrackTraces(_)
    ));
}

#[test]
fn decode_returns_typed_identity_errors_with_exact_packet() {
    let external = external_key("com.arm.cairn.test.external");
    let mut envelope = Envelope::new();
    envelope.add(external_payload(external, b"user-blob".to_vec()));
    let exact = envelope.serialize();

    type IdentityErrorMatcher = fn(&PerceptionResultError) -> bool;
    let mut cases: Vec<(Vec<u8>, IdentityErrorMatcher)> = Vec::new();
    let mut missing = exact.clone();
    clear_string(
        &mut missing,
        open_perception_kit::OPEN_PERCEPTION_KIT_NAME.as_bytes(),
    );
    cases.push((missing, |error| {
        matches!(error, PerceptionResultError::MissingProducerIdentity { .. })
    }));
    let mut malformed = exact.clone();
    replace_once(
        &mut malformed,
        open_perception_kit::OPEN_PERCEPTION_KIT_NAME.as_bytes(),
        b"Open_perception_kit",
    );
    cases.push((malformed, |error| {
        matches!(
            error,
            PerceptionResultError::MalformedProducerIdentity { .. }
        )
    }));
    let mut unexpected = exact.clone();
    replace_once(
        &mut unexpected,
        open_perception_kit::OPEN_PERCEPTION_KIT_NAME.as_bytes(),
        b"open_perception_kix",
    );
    cases.push((unexpected, |error| {
        matches!(error, PerceptionResultError::UnexpectedProducer { .. })
    }));
    let mut version = exact.clone();
    replace_once(
        &mut version,
        open_perception_kit::OPEN_PERCEPTION_KIT_VERSION.as_bytes(),
        b"9.9.9",
    );
    cases.push((version, |error| {
        matches!(
            error,
            PerceptionResultError::UnsupportedProducerVersion { .. }
        )
    }));
    let mut schema = exact;
    replace_once(
        &mut schema,
        open_perception_kit::SCHEMA_SET_SHA256.as_bytes(),
        b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    );
    cases.push((schema, |error| {
        matches!(
            error,
            PerceptionResultError::IncompatibleProducerSchema { .. }
        )
    }));

    for (packet, matches_expected_variant) in cases {
        let error = PerceptionResult::decode(&packet).expect_err("identity mismatch should fail");
        assert_eq!(error.packet(), packet);
        assert!(matches_expected_variant(&error));
        let context = error
            .decoded_envelope_context()
            .expect("identity errors must retain decoded-envelope context");
        assert_eq!(context.packet(), packet);
    }
}

#[test]
fn decode_preserves_external_payload_bytes() {
    let external = external_key("com.arm.cairn.test.external");
    let mut envelope = Envelope::new();
    envelope.add(external_payload(external, b"external".to_vec()));
    let packet = envelope.serialize();

    let result = PerceptionResult::decode(&packet).expect("packet should decode");

    assert!(matches!(
        &result.entries()[0],
        PerceptionPayload::External(payload)
            if payload.id == external.value() && payload.bytes == b"external"
    ));
}

#[test]
fn decode_preserves_unknown_payload_bytes() {
    let unknown_source = external_key("com.arm.cairn.test.unknown");
    let mut envelope = Envelope::new();
    envelope.add(external_payload(unknown_source, b"unknown".to_vec()));
    let mut packet = envelope.serialize();
    replace_once(
        &mut packet,
        &unknown_source.value().to_le_bytes(),
        &1_u64.to_le_bytes(),
    );

    let result = PerceptionResult::decode(&packet).expect("packet should decode");

    assert!(matches!(
        &result.entries()[0],
        PerceptionPayload::Unknown(payload) if payload.id == 1 && payload.bytes == b"unknown"
    ));
}

#[test]
fn decode_preserves_mixed_payload_order() {
    let external = external_key("com.arm.cairn.test.external");
    let unknown_source = external_key("com.arm.cairn.test.unknown");
    let mut envelope = Envelope::new();
    envelope.add(external_payload(external, Vec::new()));
    envelope.add(opk::BoxDetectionsT::default());
    envelope.add(external_payload(unknown_source, Vec::new()));
    let mut packet = envelope.serialize();
    replace_once(
        &mut packet,
        &unknown_source.value().to_le_bytes(),
        &1_u64.to_le_bytes(),
    );

    let result = PerceptionResult::decode(&packet).expect("packet should decode");

    assert!(matches!(
        result.entries()[0],
        PerceptionPayload::External(_)
    ));
    assert!(matches!(
        result.entries()[1],
        PerceptionPayload::BoxDetections(_)
    ));
    assert!(matches!(result.entries()[2], PerceptionPayload::Unknown(_)));
}

#[test]
fn decode_preserves_malformed_known_payload_and_other_entries_in_order() {
    let mut first = opk::BoxDetectionsT::default();
    first.schema_minor = 1;
    let mut second = opk::BoxDetectionsT::default();
    second.schema_minor = 2;
    let source = external_key("com.arm.cairn.test.malformed");

    let mut envelope = Envelope::new();
    envelope.add(first);
    envelope.add(external_payload(source, b"malformed".to_vec()));
    envelope.add(opk::ClassificationsT::default());
    envelope.add(second);
    let mut packet = envelope.serialize();
    replace_once(
        &mut packet,
        &source.value().to_le_bytes(),
        &BOX_DETECTIONS_ID.to_le_bytes(),
    );

    let result = PerceptionResult::decode(&packet)
        .expect("a malformed known entry should not discard valid entries");

    assert_eq!(result.entries().len(), 4);
    assert!(matches!(
        result.entries()[0],
        PerceptionPayload::BoxDetections(BoxDetections {
            schema_minor: 1,
            ..
        })
    ));
    assert!(matches!(
        &result.entries()[1],
        PerceptionPayload::MalformedKnown(payload)
            if payload.id == BOX_DETECTIONS_ID
                && payload.expected_type
                    == <opk::BoxDetectionsT as NativePayload>::NAME
                && payload.bytes == b"malformed"
                && !payload.detail.is_empty()
    ));
    assert!(matches!(
        result.entries()[2],
        PerceptionPayload::Classifications(_)
    ));
    assert!(matches!(
        result.entries()[3],
        PerceptionPayload::BoxDetections(BoxDetections {
            schema_minor: 2,
            ..
        })
    ));
}

#[test]
fn decode_validates_schema_major_for_all_nine_result_families() {
    macro_rules! assert_unsupported {
        ($payload_type:ty) => {{
            let mut payload = <$payload_type>::default();
            payload.schema_major = 2;
            payload.schema_minor = 7;
            let mut envelope = Envelope::new();
            envelope.add(payload);
            let packet = envelope.serialize();

            let error = PerceptionResult::decode(&packet)
                .expect_err("unsupported schema major should fail");
            assert_eq!(error.packet(), packet);
            assert!(matches!(
                &error,
                PerceptionResultError::UnsupportedPayloadSchemaVersion {
                    payload_type,
                    schema_major: 2,
                    schema_minor: 7,
                    supported_schema_major: 1,
                    ..
                } if payload_type == <$payload_type as NativePayload>::NAME
            ));
            let context = error
                .decoded_envelope_context()
                .expect("schema errors must retain decoded-envelope context");
            assert_eq!(context.received_sdk_name(), open_perception_kit::OPEN_PERCEPTION_KIT_NAME);
            assert_eq!(
                context.received_sdk_version(),
                open_perception_kit::OPEN_PERCEPTION_KIT_VERSION
            );
            assert_eq!(
                context.received_schema_digest(),
                open_perception_kit::SCHEMA_SET_SHA256
            );
        }};
    }

    assert_unsupported!(opk::BoxDetectionsT);
    assert_unsupported!(opk::ClassificationsT);
    assert_unsupported!(opk::FrameContextT);
    assert_unsupported!(opk::ObjectEmbeddingsT);
    assert_unsupported!(opk::ObjectTracksT);
    assert_unsupported!(opk::PerformanceOverlayT);
    assert_unsupported!(opk::PoseEstimationsT);
    assert_unsupported!(opk::SegmentationMasksT);
    assert_unsupported!(opk::TrackTracesT);
}

#[test]
fn decode_rejects_invalid_input_without_panicking_and_retains_bytes() {
    for packet in [&[][..], b"not-an-envelope", &[0; 32]] {
        let decoded = std::panic::catch_unwind(|| PerceptionResult::decode(packet));
        let error = decoded
            .expect("decode should not panic")
            .expect_err("invalid envelope should fail");

        assert_eq!(error.packet(), packet);
        assert!(matches!(
            &error,
            PerceptionResultError::InvalidEnvelope { .. }
        ));
        assert!(error.decoded_envelope_context().is_none());
    }
}
