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
    InstanceSegmentationMasks,
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
    SemanticSegmentationMasks,
    TrackTraces,
    TurnDetections,
    UnexpectedProducerError,
    UnknownPayload,
    UnsupportedPayloadSchemaVersionError,
    UnsupportedProducerVersionError,
    VoiceActivityDetections,
)

# Serialized with open_perception_kit 0.1.3.
PACKET = bytes.fromhex(
    "18000000464c5744000000000c00140010000c00080004000c00000010000000"
    "540000005c000000700000004000000038306262653835376131643363363064"
    "3963353335633266343761333035623862393030623665613436346338316438"
    "373937346563333937396531303166330000000005000000302e312e33000000"
    "130000006f70656e5f70657263657074696f6e5f6b697400010000000c000000"
    "0800140008000400080000001000000013ab813c53adb7070000000070000000"
    "14000000424445540c00080000000000000004000c0000000400000001000000"
    "1400000000000e0014000000040008000c0010000e000000240000000000603f"
    "030000000400000003000000636172000c001400040008000c0010000c000000"
    "000028410000a2410000f64100002242"
)
ALL_PAYLOAD_TYPES_PACKET = bytes.fromhex(
    "18000000464c5744000000000c00140010000c00080004000c00000010000000"
    "540000005c000000700000004000000038306262653835376131643363363064"
    "3963353335633266343761333035623862393030623665613436346338316438"
    "373937346563333937396531303166330000000005000000302e312e33000000"
    "130000006f70656e5f70657263657074696f6e5f6b6974000d0000008c030000"
    "580300002c03000000030000d4020000a80200007c0200005002000024020000"
    "a0010000ec0000007000000004000000b0fcffff1000000086d99cac4007f830"
    "0000000050000000140000005455524e0c00080000000000000004000c000000"
    "04000000010000001400000000000e001c000000180017000c0004000e000000"
    "00040000000000000002000000000000000000010000403f18fdffff10000000"
    "18324769622fb365000000006000000014000000564143540c00080000000000"
    "000004000c000000040000000100000018000000140028000000240023000000"
    "180010000800070014000000000000010048e801000000000000000000000000"
    "0002000000000000000000010000603f90fdffff100000006322450f2c2bb62b"
    "0000000098000000140000004953474d0c00080000000000000004000c000000"
    "04000000010000001400000000000e001400000010000c00080004000e000000"
    "1c0000000000403f030000002c0000000c0010000c000000080004000c000000"
    "0000803f000000400000803f0c00140010000c00080004000c00000010000000"
    "14000000010000000200000002000000000300000500000075696e7438000000"
    "40feffff10000000adf7eeb65e7a3d160000000068000000140000005353474d"
    "0c00080000000000000004000c00000004000000010000000c00000008000800"
    "0000040008000000100000000c00140010000c00080004000c00000010000000"
    "14000000010000000200000002000000000300000500000075696e7438000000"
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
SDK_VERSION = b"0.1.3"
SCHEMA_DIGEST = b"80bbe857a1d3c60d9c535c2f47a305b8b900b6ea464c81d87974ec3979e101f3"
BOX_DETECTIONS_ID = 556_103_652_012_567_315
UNKNOWN_PACKET = bytes.fromhex(
    "18000000464c5744000000000c00140010000c00080004000c00000010000000"
    "540000005c000000700000004000000038306262653835376131643363363064"
    "3963353335633266343761333035623862393030623665613436346338316438"
    "373937346563333937396531303166330000000005000000302e312e33000000"
    "130000006f70656e5f70657263657074696f6e5f6b697400010000000c000000"
    "0800100008000400080000000c00000001000000000000000900000075736572"
    "2d626c6f62000000"
)
UNSUPPORTED_SCHEMA_PACKET = bytes.fromhex(
    "18000000464c5744000000000c00140010000c00080004000c00000010000000"
    "540000005c000000700000004000000038306262653835376131643363363064"
    "3963353335633266343761333035623862393030623665613436346338316438"
    "373937346563333937396531303166330000000005000000302e312e33000000"
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
        pytest.param(12, TurnDetections, id="TurnDetections"),
        pytest.param(11, VoiceActivityDetections, id="VoiceActivityDetections"),
        pytest.param(10, InstanceSegmentationMasks, id="InstanceSegmentationMasks"),
        pytest.param(9, SemanticSegmentationMasks, id="SemanticSegmentationMasks"),
    ),
)
def test_decode_returns_expected_python_payload_type(
    entry_index: int,
    payload_type: type[PerceptionPayload],
) -> None:
    result = PerceptionResult.decode(ALL_PAYLOAD_TYPES_PACKET)

    assert isinstance(result.entries, tuple)
    assert len(result.entries) == 13
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
    assert error.received_sdk_version in ("9.9.9", "0.1.3")
    assert error.received_schema_digest


def test_decode_requires_bytes() -> None:
    with pytest.raises(TypeError):
        PerceptionResult.decode(bytearray(PACKET))  # type: ignore[arg-type]


def test_decode_preserves_new_segmentation_and_audio_fields() -> None:
    result = PerceptionResult.decode(ALL_PAYLOAD_TYPES_PACKET)
    semantic, instance, voice, turn = result.entries[9:]
    assert isinstance(semantic, SemanticSegmentationMasks)
    assert semantic.masks[0].bitmap.pixels == b"\x00\x03"
    assert isinstance(instance, InstanceSegmentationMasks)
    mask = instance.masks[0]
    assert (mask.class_id, mask.confidence, mask.bounding_box.width) == (3, 0.75, 2)
    assert mask.bitmap.pixels == b"\x00\x03"
    assert isinstance(voice, VoiceActivityDetections)
    speech = voice.detections[0]
    assert (speech.speech_probability, speech.speech_active) == (0.875, True)
    assert (speech.window_start_sample, speech.window_end_sample) == (0, 512)
    assert (speech.window_start_timestamp_ns, speech.window_end_timestamp_ns) == (
        0,
        32000000,
    )
    assert speech.discontinuity
    assert isinstance(turn, TurnDetections)
    assessment = turn.detections[0]
    assert (assessment.turn_probability, assessment.turn_complete) == (0.75, True)
    assert (assessment.window_start_sample, assessment.window_end_sample) == (512, 1024)
    assert assessment.window_start_timestamp_ns is None
    assert assessment.window_end_timestamp_ns is None
    assert not assessment.discontinuity


def test_decode_rejects_previous_sdk_version() -> None:
    packet = replace_once(PACKET, SDK_VERSION, b"0.1.1")
    with pytest.raises(UnsupportedProducerVersionError):
        PerceptionResult.decode(packet)
