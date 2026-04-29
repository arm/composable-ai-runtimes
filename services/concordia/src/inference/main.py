from concurrent import futures
from pathlib import Path
from typing import Any, Callable, Optional
import argparse

import grpc
import compute_flow_py as cfpy
from compute_flow_py.bricks import variants
from .proto import concordia_pb2 as pb2  # noqa: E402
from .proto import concordia_pb2_grpc as pb2_grpc  # noqa: E402
from . import brick_config


class InferenceService(pb2_grpc.InferenceServiceServicer):
    _BRICKS = [
        (pb2.BRICK_TYPE_TTS, "kokoro", lambda: cfpy.brick.tts(variants.TTS.KOKORO)),
        (pb2.BRICK_TYPE_TTS, "kittentts", lambda: cfpy.brick.tts(variants.TTS.KITTENTTS)),
        (
            pb2.BRICK_TYPE_OBJECT_DETECTION,
            "yolo",
            lambda: cfpy.brick.object_detection(variants.OBJECT_DETECTION.YOLO),
        ),
    ]
    _BRICK_VARIANTS = {(t, v): f for (t, v, f) in _BRICKS}

    def __init__(self, manifest_dir: Path) -> None:
        self._manifest_dir = manifest_dir
        self._brick_cache = {}

    def ListBricks(
        self, request: pb2.ListBricksRequest, context: grpc.ServicerContext
    ) -> pb2.ListBricksResponse:  # noqa: N802
        return pb2.ListBricksResponse(
            bricks=[
                pb2.BrickSpec(type=brick_type, brick_variant=variant)
                for (brick_type, variant, _factory) in self._BRICKS
            ]
        )


    def get_brick_entry(
        self, brick_type, variant, context
    ) -> Optional[Callable[[], Any]]:
        entry = self._BRICK_VARIANTS.get((brick_type, variant))
        if entry is None:
            if any(key[0] == brick_type for key in self._BRICK_VARIANTS):
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "unsupported variant")
            else:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "unsupported brick type")
            return None
        return entry

    def get_manifest_path(self, context: grpc.ServicerContext, variant: str) -> Path:
        variant_dir = self._manifest_dir / variant
        if not variant_dir.exists():
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"manifest dir not found: {variant_dir}",
            )
        manifest_candidates = sorted(
            p for p in variant_dir.glob("*manifest*.json") if p.is_file()
        )
        if not manifest_candidates:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"no manifest json found in: {variant_dir}",
            )
        if len(manifest_candidates) > 1:
            manifest_names = ", ".join(p.name for p in manifest_candidates)
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                "multiple manifest json files found in: "
                f"{variant_dir} ({manifest_names})",
            )
        return manifest_candidates[0]

    def RunBrick(
        self, request: pb2.RunBrickRequest, context: grpc.ServicerContext
    ) -> Optional[pb2.RunBrickResponse]:  # noqa: N802
        brick_type, variant = self._parse_request(request, context)

        cache_key = (brick_type, variant)
        if cache_key in self._brick_cache:
            brick = self._brick_cache[cache_key]
        else:
            brick_factory = self.get_brick_entry(brick_type, variant, context)
            if brick_factory is None:
                return
            manifest_path = self.get_manifest_path(context, variant)
            brick = self._setup_brick(brick_factory, manifest_path, brick_type, variant)
            self._brick_cache[cache_key] = brick

        if brick_type == pb2.BRICK_TYPE_OBJECT_DETECTION:
            return self._run_object_detection(brick, request, context)
        if brick_type == pb2.BRICK_TYPE_TTS:
            return self._run_tts(brick, request, context)
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "unsupported brick type")

    @staticmethod
    def _parse_request(
        request: pb2.RunBrickRequest, context: grpc.ServicerContext
    ) -> tuple[int, str]:
        brick_type = request.brick.type
        variant = request.brick.brick_variant.strip()
        if not variant:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "variant is required")
        return brick_type, variant

    def _setup_brick(
        self,
        brick_factory: Callable[[], Any],
        manifest_path: Path,
        brick_type: int,
        variant: str,
    ) -> tuple[Any, Any]:
        manifest = cfpy.load_manifest_from_json(str(manifest_path))
        brick_config.configure_accelerators(manifest, brick_type, variant)
        brick = brick_factory()
        brick.setup(manifest, True)
        return brick

    def _run_object_detection(
        self,
        brick: Any,
        request: pb2.RunBrickRequest,
        context: grpc.ServicerContext,
    ) -> pb2.RunBrickResponse:
        if not request.HasField("image"):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "image input is required")
        input = cfpy.TensorDict()
        input["img"] = brick_config.image_bytes_to_npy(request.image.image_bytes)
        output = brick.run(input)
        detections = brick_config.to_detections(output)
        return pb2.RunBrickResponse(
            detections=pb2.ObjDetectionOutput(detections=detections)
        )

    def _run_tts(
        self,
        brick: Any,
        request: pb2.RunBrickRequest,
        context: grpc.ServicerContext,
    ) -> pb2.RunBrickResponse:
        if not request.HasField("text"):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "text input is required")
        input = cfpy.TensorDict()
        input["text_prompt"] = request.text.text
        output = brick.run(input)
        left = brick_config.to_float_list(output["left_channel"])
        right = brick_config.to_float_list(output["right_channel"])
        return pb2.RunBrickResponse(
            audio=pb2.AudioOutput(
                left_channel=left,
                right_channel=right,
            )
        )


def serve(host: str, port: int, model_dir: Path) -> None:
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=8),
    )
    pb2_grpc.add_InferenceServiceServicer_to_server(
        InferenceService(model_dir), server
    )

    address = f"{host}:{port}"
    server.add_insecure_port(address)
    server.start()
    print(f"Concordia gRPC server listening on {address}", flush=True)
    server.wait_for_termination()


def main() -> None:
    parser = argparse.ArgumentParser(description="Concordia inference service")
    parser.add_argument(
        "--model-dir",
        required=True,
        help="Base directory containing models and manifests",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=50052, help="Port to bind")

    args = parser.parse_args()
    serve(args.host, args.port, Path(args.model_dir).expanduser().resolve())


if __name__ == "__main__":
    main()
