# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for the Python camera-service API."""

import asyncio
import inspect
import multiprocessing
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import cairn
import grpc
import pytest
from cairn import (
    Camera,
    CameraService,
    FrameRate,
    Resolution,
    StreamConfiguration,
    StreamFormat,
    StreamFormatFilter,
)
from generated import camera_service_pb2 as camera_proto
from grpc_health.v1 import health_pb2


class MockCameraService:
    def __init__(self, response_kind: str, requests: Any) -> None:
        self.response_kind = response_kind
        self.requests = requests

    def list_cameras(
        self, _request: camera_proto.ListRequest, _context: grpc.ServicerContext
    ) -> camera_proto.ListCamerasResponse:
        return camera_proto.ListCamerasResponse(
            cameras=[camera_proto.Camera(id=7, name="front")]
        )

    def get_stream_configurations(
        self,
        request: camera_proto.StreamConfigurationRequest,
        _context: grpc.ServicerContext,
    ) -> camera_proto.StreamConfigurationResponse:
        self.requests.put(request.SerializeToString())
        if self.response_kind == "empty":
            return camera_proto.StreamConfigurationResponse()
        if self.response_kind == "missing-format":
            return camera_proto.StreamConfigurationResponse(
                configurations=[
                    camera_proto.StreamConfiguration(target="52", camera_id=7)
                ]
            )
        return camera_proto.StreamConfigurationResponse(
            configurations=[
                camera_proto.StreamConfiguration(
                    target="52",
                    camera_id=7,
                    format=camera_proto.StreamFormat(
                        resolution=camera_proto.Resolution(width=1920, height=1080),
                        pixel_format="RGB",
                        frame_rate=camera_proto.FrameRate(numerator=30, denominator=1),
                    ),
                )
            ]
        )


def run_mock_camera_service(
    response_kind: str, ready: Any, requests: Any, stop: Any
) -> None:
    service = MockCameraService(response_kind, requests)
    executor = ThreadPoolExecutor(max_workers=1)
    server = grpc.server(executor)
    server.add_generic_rpc_handlers(
        (
            grpc.method_handlers_generic_handler(
                "camera.pipewire.v1.CameraService",
                {
                    "ListCameras": grpc.unary_unary_rpc_method_handler(
                        service.list_cameras,
                        request_deserializer=camera_proto.ListRequest.FromString,
                        response_serializer=camera_proto.ListCamerasResponse.SerializeToString,
                    ),
                    "get_stream_configurations": grpc.unary_unary_rpc_method_handler(
                        service.get_stream_configurations,
                        request_deserializer=camera_proto.StreamConfigurationRequest.FromString,
                        response_serializer=camera_proto.StreamConfigurationResponse.SerializeToString,
                    ),
                },
            ),
        )
    )
    health_response = health_pb2.HealthCheckResponse(
        status=health_pb2.HealthCheckResponse.SERVING
    )
    server.add_generic_rpc_handlers(
        (
            grpc.method_handlers_generic_handler(
                "grpc.health.v1.Health",
                {
                    "Watch": grpc.unary_stream_rpc_method_handler(
                        lambda _request, _context: iter([health_response]),
                        response_serializer=health_pb2.HealthCheckResponse.SerializeToString,
                    )
                },
            ),
        )
    )
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    ready.put(port)
    stop.wait()
    server.stop(0).wait()
    executor.shutdown(wait=True)


@pytest.fixture
def camera_service(
    request: pytest.FixtureRequest,
) -> Generator[tuple[str, Any]]:
    response_kind = getattr(request, "param", "valid")
    context = multiprocessing.get_context("spawn")
    ready = context.Queue()
    requests = context.Queue()
    stop = context.Event()
    process = context.Process(
        target=run_mock_camera_service,
        args=(response_kind, ready, requests, stop),
    )
    process.start()

    try:
        port = ready.get(timeout=10)
        yield f"http://127.0.0.1:{port}", requests
    finally:
        stop.set()
        process.join(timeout=10)
        if process.is_alive():
            process.kill()
            process.join()


def camera_from_service(endpoint: str) -> Camera:
    service = CameraService(endpoint)
    cameras = service.list_cameras()

    assert len(cameras) == 1
    assert not hasattr(cameras[0], "supported_formats")
    return cameras[0]


def test_stream_filter_defaults_leave_all_constraints_unset() -> None:
    filter = StreamFormatFilter()
    assert filter.resolution is None
    assert filter.pixel_format is None
    assert filter.frame_rate is None


def test_stream_filter_preserves_dimensions_and_exact_frame_rate() -> None:
    filter = StreamFormatFilter(
        resolution=Resolution(640, 480),
        pixel_format="RGB",
        frame_rate=FrameRate(30000, 1001),
    )
    assert (filter.resolution.width, filter.resolution.height) == (640, 480)
    assert filter.pixel_format == "RGB"
    assert (filter.frame_rate.numerator, filter.frame_rate.denominator) == (30000, 1001)


def test_stream_filter_requires_typed_constraints() -> None:
    with pytest.raises(TypeError):
        StreamFormatFilter(resolution=(640, 480))
    with pytest.raises(TypeError):
        StreamFormatFilter(frame_rate=30)


def test_stream_configuration_constructor_preserves_fields() -> None:
    target = "opaque/pipewire:target"
    camera_id = 7
    format = StreamFormat(
        resolution=Resolution(1920, 1080),
        pixel_format="NV12",
        frame_rate=FrameRate(30000, 1001),
    )

    configuration = StreamConfiguration(target, camera_id, format)

    assert configuration.target == target
    assert configuration.camera_id == camera_id
    assert configuration.format.pixel_format == format.pixel_format
    assert configuration.format.resolution.width == format.resolution.width
    assert configuration.format.resolution.height == format.resolution.height
    assert configuration.format.frame_rate.numerator == format.frame_rate.numerator
    assert configuration.format.frame_rate.denominator == format.frame_rate.denominator


def test_stream_configuration_api_is_exported() -> None:
    assert not hasattr(Camera, "supported_formats")
    assert callable(CameraService.get_stream_configurations)
    assert StreamConfiguration.__module__ == "cairn"
    assert StreamFormat.__module__ == "cairn"


def test_camera_types_are_exported_from_package() -> None:
    expected = {
        "Camera",
        "FrameRate",
        "Resolution",
        "StreamConfiguration",
        "StreamFormat",
        "StreamFormatFilter",
    }

    assert expected <= set(cairn.__all__)
    assert cairn.Camera is Camera
    assert cairn.FrameRate is FrameRate
    assert cairn.Resolution is Resolution
    assert cairn.StreamConfiguration is StreamConfiguration
    assert cairn.StreamFormat is StreamFormat
    assert cairn.StreamFormatFilter is StreamFormatFilter


def test_get_stream_configurations_exposes_filter_arguments() -> None:
    signature = inspect.signature(Camera.get_stream_configurations)

    assert list(signature.parameters) == [
        "self",
        "resolution",
        "pixel_format",
        "frame_rate",
    ]
    assert signature.parameters["resolution"].default is None
    assert signature.parameters["pixel_format"].default is None
    assert signature.parameters["frame_rate"].default is None


def test_stream_configuration_requires_all_fields() -> None:
    with pytest.raises(TypeError):
        StreamConfiguration()  # type: ignore[call-arg]


@pytest.mark.parametrize("entry_point", ["camera", "service"])
def test_get_stream_configurations_forwards_filters_and_converts_response(
    camera_service: tuple[str, Any], entry_point: str,
) -> None:
    endpoint, requests = camera_service
    if entry_point == "camera":
        camera = camera_from_service(endpoint)
        async def discover() -> list[StreamConfiguration]:
            result = camera.get_stream_configurations(
                resolution=(1920, 1080),
                pixel_format="RGB",
                frame_rate=(30, 1),
            )
            assert inspect.isawaitable(result)
            return await asyncio.wait_for(result, timeout=5)

        configurations = asyncio.run(discover())
    else:
        service = CameraService(endpoint)
        configurations = service.get_stream_configurations(
            7,
            StreamFormatFilter(
                resolution=Resolution(1920, 1080),
                pixel_format="RGB",
                frame_rate=FrameRate(30, 1),
            ),
        )
    request = camera_proto.StreamConfigurationRequest.FromString(
        requests.get(timeout=1)
    )

    assert request.camera_id == 7
    assert request.format.resolution == camera_proto.Resolution(width=1920, height=1080)
    assert request.format.pixel_format == "RGB"
    assert request.format.frame_rate == camera_proto.FrameRate(
        numerator=30, denominator=1
    )

    assert isinstance(configurations, list)
    assert len(configurations) == 1
    configuration = configurations[0]
    assert isinstance(configuration, StreamConfiguration)
    assert configuration.target == "52"
    assert configuration.camera_id == 7
    assert isinstance(configuration.format, StreamFormat)
    assert isinstance(configuration.format.resolution, Resolution)
    assert configuration.format.resolution.width == 1920
    assert configuration.format.resolution.height == 1080
    assert configuration.format.pixel_format == "RGB"
    assert isinstance(configuration.format.frame_rate, FrameRate)
    assert configuration.format.frame_rate.numerator == 30
    assert configuration.format.frame_rate.denominator == 1


@pytest.mark.parametrize("camera_service", ["empty"], indirect=True)
def test_get_stream_configurations_returns_empty_list(
    camera_service: tuple[str, Any],
) -> None:
    endpoint, _requests = camera_service
    camera = camera_from_service(endpoint)
    service = CameraService(endpoint)

    async def discover() -> list[StreamConfiguration]:
        return await asyncio.wait_for(camera.get_stream_configurations(), timeout=5)

    assert asyncio.run(discover()) == []
    assert service.get_stream_configurations(7) == []


@pytest.mark.parametrize("camera_service", ["missing-format"], indirect=True)
def test_get_stream_configurations_rejects_missing_format(
    camera_service: tuple[str, Any],
) -> None:
    endpoint, _requests = camera_service
    camera = camera_from_service(endpoint)

    async def discover() -> list[StreamConfiguration]:
        return await asyncio.wait_for(camera.get_stream_configurations(), timeout=5)

    with pytest.raises(RuntimeError, match="missing its format"):
        asyncio.run(discover())
    service = CameraService(endpoint)
    with pytest.raises(RuntimeError, match="missing its format"):
        service.get_stream_configurations(7)
