# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import pytest
from cairn import perception
from cairn.perception import (
    BoxDetections,
    Classifications,
    ExternalPayload,
    FrameContext,
    IncompatibleProducerSchemaError,
    InvalidEnvelopeError,
    MalformedKnownPayload,
    MalformedProducerIdentityError,
    MissingProducerIdentityError,
    ObjectEmbeddings,
    ObjectTracks,
    PerceptionPayload,
    PerceptionResult,
    PerceptionResultError,
    PerformanceOverlay,
    PoseEstimations,
    ProducerIdentityError,
    SegmentationMasks,
    TrackTraces,
    UnexpectedProducerError,
    UnknownPayload,
    UnsupportedPayloadSchemaVersionError,
    UnsupportedProducerVersionError,
)

# Serialized with open_perception_kit 0.1.1.
PACKET = bytes.fromhex(
    "18000000464c5744000000000c001400040008000c0010000c0000007c000000"
    "6000000050000000040000004000000031623139343138643861306433343033"
    "3861336339393839356661393361313134306332356166393130663662633633"
    "633065313139373865313263323837360000000005000000302e312e31000000"
    "130000006f70656e5f70657263657074696f6e5f6b697400010000000c000000"
    "0800140008000400080000001000000013ab813c53adb7070000000070000000"
    "14000000424445540c00080000000000000004000c0000000400000001000000"
    "1400000000000e0014000000040008000c0010000e000000240000000000603f"
    "030000000400000003000000636172000c001400040008000c0010000c000000"
    "000028410000a2410000f64100002242"
)
ALL_PAYLOAD_TYPES_PACKET = bytes.fromhex(
    "18000000464c5744000000000c001400040008000c0010000c0000007c000000"
    "6000000050000000040000004000000031623139343138643861306433343033"
    "3861336339393839356661393361313134306332356166393130663662633633"
    "633065313139373865313263323837360000000005000000302e312e31000000"
    "130000006f70656e5f70657263657074696f6e5f6b697400090000006c010000"
    "380100000c010000e0000000b4000000880000005c0000003000000004000000"
    "c0feffff1000000005b542ddd94b4e0300000000100000000c00000054524345"
    "0400040004000000e8feffff100000008f624def0a8ebd1b0000000010000000"
    "0c00000053474d53040004000400000010ffffff10000000c938a0470ed17e7e"
    "00000000100000000c000000504f5345040004000400000038ffffff10000000"
    "0c7dd21263678b6b00000000100000000c000000504552460400040004000000"
    "60ffffff10000000e0a0bc0d451d162900000000100000000c00000054524b53"
    "040004000400000088ffffff100000005d53811b0528e3520000000010000000"
    "0c000000454d42450400040004000000b0ffffff100000003c7bcf96140eaa1c"
    "00000000100000000c000000464354580400040004000000d8ffffff10000000"
    "8f3cfc33d4d0962700000000100000000c000000434c53460400040004000000"
    "0800140008000400080000001000000013ab813c53adb7070000000010000000"
    "0c000000424445540400040004000000"
)
SDK_NAME = b"open_perception_kit"
SDK_VERSION = b"0.1.1"
SCHEMA_DIGEST = b"1b19418d8a0d34038a3c99895fa93a1140c25af910f6bc63c0e11978e12c2876"
BOX_DETECTIONS_ID = 556_103_652_012_567_315
UNKNOWN_PACKET = bytes.fromhex(
    "18000000464c5744000000000c001400040008000c0010000c0000007c000000"
    "6000000050000000040000004000000031623139343138643861306433343033"
    "3861336339393839356661393361313134306332356166393130663662633633"
    "633065313139373865313263323837360000000005000000302e312e31000000"
    "130000006f70656e5f70657263657074696f6e5f6b697400010000000c000000"
    "0800100008000400080000000c00000001000000000000000900000075736572"
    "2d626c6f62000000"
)
UNSUPPORTED_SCHEMA_PACKET = bytes.fromhex(
    "18000000464c5744000000000c001400040008000c0010000c0000007c000000"
    "6000000050000000040000004000000031623139343138643861306433343033"
    "3861336339393839356661393361313134306332356166393130663662633633"
    "633065313139373865313263323837360000000005000000302e312e31000000"
    "130000006f70656e5f70657263657074696f6e5f6b697400010000000c000000"
    "0800140008000400080000001000000013ab813c53adb7070000000018000000"
    "100000004244455408000800040006000800000002000700"
)
EXTERNAL_PAYLOAD_ID = 15_173_348_289_903_558_460
EXTERNAL_PACKET = UNKNOWN_PACKET.replace(
    (1).to_bytes(8, "little"),
    EXTERNAL_PAYLOAD_ID.to_bytes(8, "little"),
    1,
)


def replace_once(packet: bytes, old: bytes, new: bytes) -> bytes:
    assert len(old) == len(new)
    assert packet.count(old) == 1
    return packet.replace(old, new, 1)


def clear_string(packet: bytes, value: bytes) -> bytes:
    mutable = bytearray(packet)
    offset = mutable.index(value)
    mutable[offset - 4 : offset + 1] = b"\0" * 5
    return bytes(mutable)


def test_result_error_hierarchy_is_exposed_by_perception_module() -> None:
    assert issubclass(PerceptionResultError, ValueError)

    error_types = {PerceptionResultError}
    pending = [PerceptionResultError]
    while pending:
        error_type = pending.pop()
        subclasses = error_type.__subclasses__()
        error_types.update(subclasses)
        pending.extend(subclasses)

    for error_type in error_types:
        assert error_type.__module__ == "cairn.perception"
        assert getattr(perception, error_type.__name__) is error_type


@pytest.mark.parametrize(
    ("entry_index", "payload_type"),
    (
        pytest.param(0, BoxDetections, id="box-detections"),
        pytest.param(1, Classifications, id="classifications"),
        pytest.param(2, FrameContext, id="frame-context"),
        pytest.param(3, ObjectEmbeddings, id="object-embeddings"),
        pytest.param(4, ObjectTracks, id="object-tracks"),
        pytest.param(5, PerformanceOverlay, id="performance-overlay"),
        pytest.param(6, PoseEstimations, id="pose-estimations"),
        pytest.param(7, SegmentationMasks, id="segmentation-masks"),
        pytest.param(8, TrackTraces, id="track-traces"),
    ),
)
def test_decode_returns_expected_python_payload_type(
    entry_index: int,
    payload_type: type[PerceptionPayload],
) -> None:
    result = PerceptionResult.decode(ALL_PAYLOAD_TYPES_PACKET)

    assert isinstance(result.entries, tuple)
    assert len(result.entries) == 9
    payload = result.entries[entry_index]
    assert type(payload) is payload_type
    assert isinstance(payload, PerceptionPayload)
    assert payload.__class__.__module__ == "cairn.perception"


def test_decode_maps_box_detection_fields() -> None:
    result = PerceptionResult.decode(PACKET)

    payload = result.entries[0]
    assert isinstance(payload, BoxDetections)
    assert (payload.schema_major, payload.schema_minor) == (1, 0)
    assert payload.detections is not None
    assert len(payload.detections) == 1
    detection = payload.detections[0]
    assert detection.class_id == 3
    assert detection.text == "car"
    assert detection.confidence == pytest.approx(0.875)
    assert detection.bounding_box is not None
    box = detection.bounding_box
    assert (box.x, box.y, box.width, box.height) == pytest.approx(
        (10.5, 20.25, 30.75, 40.5)
    )


def test_decode_raises_dedicated_invalid_envelope_error() -> None:
    packet = b"not-an-envelope"

    with pytest.raises(InvalidEnvelopeError) as caught:
        PerceptionResult.decode(packet)

    error = caught.value
    assert isinstance(error, PerceptionResultError)
    assert error.packet == packet
    assert "invalid Perception result envelope" in str(error)


def test_decode_preserves_unknown_id_and_bytes() -> None:
    result = PerceptionResult.decode(UNKNOWN_PACKET)

    assert len(result.entries) == 1
    payload = result.entries[0]
    assert type(payload) is UnknownPayload
    assert isinstance(payload, PerceptionPayload)
    assert payload.id == 1
    assert payload.bytes == b"user-blob"


def test_decode_preserves_external_key_and_bytes_separately() -> None:
    result = PerceptionResult.decode(EXTERNAL_PACKET)

    assert len(result.entries) == 1
    payload = result.entries[0]
    assert type(payload) is ExternalPayload
    assert isinstance(payload, PerceptionPayload)
    assert payload.id == EXTERNAL_PAYLOAD_ID
    assert payload.bytes == b"user-blob"


def test_decode_preserves_malformed_known_payload_details() -> None:
    packet = replace_once(
        UNKNOWN_PACKET,
        (1).to_bytes(8, "little"),
        BOX_DETECTIONS_ID.to_bytes(8, "little"),
    )

    result = PerceptionResult.decode(packet)

    assert len(result.entries) == 1
    payload = result.entries[0]
    assert type(payload) is MalformedKnownPayload
    assert isinstance(payload, PerceptionPayload)
    assert payload.id == BOX_DETECTIONS_ID
    assert payload.expected_type == "open_perception_kit.metadata.BoxDetections"
    assert payload.bytes == b"user-blob"
    assert payload.detail


def test_decode_reports_unsupported_payload_schema_version() -> None:
    packet = UNSUPPORTED_SCHEMA_PACKET

    with pytest.raises(UnsupportedPayloadSchemaVersionError) as caught:
        PerceptionResult.decode(packet)

    error = caught.value
    assert error.packet == packet
    assert error.payload_type == "open_perception_kit.metadata.BoxDetections"
    assert (error.schema_major, error.schema_minor) == (2, 7)
    assert error.supported_schema_major == 1


@pytest.mark.parametrize(
    ("incompatible_packet", "error_type", "message"),
    (
        pytest.param(
            clear_string(PACKET, SDK_NAME),
            MissingProducerIdentityError,
            "producer identity is missing",
            id="missing-identity",
        ),
        pytest.param(
            replace_once(PACKET, SDK_NAME, b"Open_perception_kit"),
            MalformedProducerIdentityError,
            "malformed Perception result producer identity",
            id="malformed-identity",
        ),
        pytest.param(
            replace_once(PACKET, SDK_NAME, b"open_perception_kix"),
            UnexpectedProducerError,
            "unexpected Perception result producer",
            id="unexpected-producer",
        ),
        pytest.param(
            replace_once(PACKET, SDK_VERSION, b"9.9.9"),
            UnsupportedProducerVersionError,
            "unsupported Perception producer version",
            id="unsupported-version",
        ),
        pytest.param(
            replace_once(PACKET, SCHEMA_DIGEST, b"a" * 64),
            IncompatibleProducerSchemaError,
            "incompatible Perception producer schema",
            id="incompatible-schema",
        ),
    ),
)
def test_decode_raises_distinct_producer_errors_with_identity_fields(
    incompatible_packet: bytes,
    error_type: type[ProducerIdentityError],
    message: str,
) -> None:
    with pytest.raises(error_type) as caught:
        PerceptionResult.decode(incompatible_packet)

    error = caught.value
    assert isinstance(error, ProducerIdentityError)
    assert error.packet == incompatible_packet
    assert message in str(error)
    assert error.received_sdk_version in ("9.9.9", "0.1.1")
    assert error.received_schema_digest


def test_decode_requires_bytes() -> None:
    with pytest.raises(TypeError):
        PerceptionResult.decode(bytearray(PACKET))  # type: ignore[arg-type]
