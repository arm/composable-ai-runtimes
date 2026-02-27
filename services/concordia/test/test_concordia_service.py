
import sys
from pathlib import Path
import grpc
import pytest

PROTO_DIR = Path(__file__).parent.parent / "src" / "inference" / "proto"
sys.path.insert(0, str(PROTO_DIR))

import concordia_pb2 as pb2
import concordia_pb2_grpc as pb2_grpc

channel = grpc.insecure_channel("localhost:50052")

def test_obj_detection_reply():
    stub = pb2_grpc.InferenceServiceStub(channel)
    with open("test/sample.jpg", "rb") as f:
        image_bytes = f.read()
    request = pb2.RunBrickRequest(
        brick=pb2.BrickSpec(
            type=pb2.BRICK_TYPE_OBJECT_DETECTION,
            brick_variant="yolo",
        ),
        image=pb2.ImageInput(image_bytes=image_bytes)
    )
    try:
        response = stub.RunBrick(request, timeout=5)
    except grpc._channel._InactiveRpcError as e:
        if "connect" in str(e) or "UNAVAILABLE" in str(e):
            pytest.skip("gRPC server unavailable or not running on localhost:50052")
        else:
            pytest.fail(f"No response from server: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error: {e}")
    assert response is not None, "No response from server"
    assert response.WhichOneof("output") is not None, "No output in response"

def test_tts_reply():
    stub = pb2_grpc.InferenceServiceStub(channel)
    request = pb2.RunBrickRequest(
        brick=pb2.BrickSpec(
            type=pb2.BRICK_TYPE_TTS,
            brick_variant="kokoro",
        ),
        text=pb2.TextInput(text="Hello from Cairn SDK!"),
    )
    try:
        response = stub.RunBrick(request, timeout=5)
    except grpc._channel._InactiveRpcError as e:
        if "connect" in str(e) or "UNAVAILABLE" in str(e):
            pytest.skip("gRPC server unavailable or not running on localhost:50052")
        else:
            pytest.fail(f"No response from server: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error: {e}")
    assert response is not None, "No response from server"
    assert response.WhichOneof("output") is not None, "No output in response"
