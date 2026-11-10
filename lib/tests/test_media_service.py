# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for the Python media-service API."""

import asyncio
import inspect
import multiprocessing
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from multiprocessing.queues import Queue
from typing import Any

import cairn
import grpc
import pytest
from cairn import (
    Camera,
    FrameRate,
    MediaService,
    Resolution,
    StreamConfiguration,
    StreamFormat,
    StreamFormatFilter,
)
from generated import media_service_pb2 as camera_proto
from grpc_health.v1 import health_pb2


class MockMediaService:
    def __init__(self, response_kind: str, requests: Any) -> None:
        self.response_kind = response_kind
        self.requests = requests

    def list_cameras(
        self, _request: camera_proto.ListRequest, context: grpc.ServicerContext
    ) -> camera_proto.ListCamerasResponse:
        cameras = [camera_proto.Camera(id=7, name="front")]
        if self.response_kind == "unavailable-cameras":
            context.abort(grpc.StatusCode.UNAVAILABLE, "PipeWire unavailable")
        elif self.response_kind == "no-cameras":
            cameras = []
        return camera_proto.ListCamerasResponse(cameras=cameras)

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


def run_mock_media_service(
    response_kind: str, ready: Any, requests: Any, stop: Any
) -> None:
    service = MockMediaService(response_kind, requests)
    executor = ThreadPoolExecutor(max_workers=1)
    server = grpc.server(executor)
    server.add_generic_rpc_handlers(
        (
            grpc.method_handlers_generic_handler(
                "media.pipewire.v1.MediaService",
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
def media_service(
    request: pytest.FixtureRequest,
) -> Generator[tuple[str, Any]]:
    response_kind = getattr(request, "param", "valid")
    context = multiprocessing.get_context("spawn")
    ready = context.Queue()
    requests = context.Queue()
    stop = context.Event()
    process = context.Process(
        target=run_mock_media_service,
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


async def camera_from_service(endpoint: str) -> Camera:
    service = await MediaService.connect(endpoint)
    cameras = service.list_cameras()

    assert len(cameras) == 1
    assert not hasattr(cameras[0], "supported_formats")
    return cameras[0]


@pytest.mark.parametrize("camera_id", [None, 7])
def test_get_camera_returns_camera_with_configuration_discovery(
    media_service: tuple[str, "Queue[bytes]"],
    camera_id: int | None,
) -> None:
    endpoint, requests = media_service

    async def discover() -> None:
        service = await MediaService.connect(endpoint)
        camera = await service.get_camera(camera_id=camera_id)
        assert isinstance(camera, Camera)
        assert (camera.id, camera.name) == (7, "front")
        configurations = await camera.get_stream_configurations()
        assert configurations[0].camera_id == 7

    asyncio.run(asyncio.wait_for(discover(), timeout=5))
    request = camera_proto.StreamConfigurationRequest.FromString(requests.get(timeout=1))
    assert request.camera_id == 7


@pytest.mark.parametrize("media_service", ["no-cameras"], indirect=True)
def test_get_camera_returns_none_when_no_cameras_are_available(
    media_service: tuple[str, "Queue[bytes]"],
) -> None:
    async def discover() -> None:
        service = await MediaService.connect(media_service[0])
        assert await service.get_camera() is None
        assert await service.get_camera(camera_id=None) is None

    asyncio.run(asyncio.wait_for(discover(), timeout=5))


@pytest.mark.parametrize(
    "media_service, camera_id, error_type, message",
    [
        ("valid", 123, LookupError, "camera 123 was not found"),
        ("no-cameras", 123, LookupError, "camera 123 was not found"),
        ("unavailable-cameras", 123, RuntimeError, "PipeWire unavailable"),
        ("unavailable-cameras", None, RuntimeError, "PipeWire unavailable"),
    ],
    indirect=["media_service"],
)
def test_get_camera_reports_lookup_and_service_errors(
    media_service: tuple[str, "Queue[bytes]"],
    camera_id: int | None,
    error_type: type[Exception],
    message: str,
) -> None:
    async def discover() -> None:
        service = await MediaService.connect(media_service[0])
        with pytest.raises(error_type, match=message):
            await service.get_camera(camera_id=camera_id)

    asyncio.run(asyncio.wait_for(discover(), timeout=5))


def test_direct_construction_is_not_supported() -> None:
    with pytest.raises(TypeError):
        MediaService()


def test_connect_rejects_invalid_endpoint() -> None:
    async def connect() -> None:
        with pytest.raises(RuntimeError, match="health watch"):
            await MediaService.connect("http://[::1")

    asyncio.run(connect())


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
    assert callable(MediaService.get_stream_configurations)
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
    media_service: tuple[str, Any], entry_point: str,
) -> None:
    endpoint, requests = media_service

    async def discover() -> list[StreamConfiguration]:
        if entry_point == "camera":
            camera = await camera_from_service(endpoint)
            result = camera.get_stream_configurations(
                resolution=(1920, 1080),
                pixel_format="RGB",
                frame_rate=(30, 1),
            )
            assert inspect.isawaitable(result)
            return await asyncio.wait_for(result, timeout=5)

        service = await MediaService.connect(endpoint)
        return service.get_stream_configurations(
            7,
            StreamFormatFilter(
                resolution=Resolution(1920, 1080),
                pixel_format="RGB",
                frame_rate=FrameRate(30, 1),
            ),
        )

    configurations = asyncio.run(discover())
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


@pytest.mark.parametrize("media_service", ["empty"], indirect=True)
def test_get_stream_configurations_returns_empty_list(
    media_service: tuple[str, Any],
) -> None:
    endpoint, _requests = media_service

    async def discover() -> None:
        camera = await camera_from_service(endpoint)
        service = await MediaService.connect(endpoint)
        assert await asyncio.wait_for(camera.get_stream_configurations(), timeout=5) == []
        assert service.get_stream_configurations(7) == []

    asyncio.run(discover())


@pytest.mark.parametrize("media_service", ["missing-format"], indirect=True)
def test_get_stream_configurations_rejects_missing_format(
    media_service: tuple[str, Any],
) -> None:
    endpoint, _requests = media_service

    async def discover() -> None:
        camera = await camera_from_service(endpoint)
        with pytest.raises(RuntimeError, match="missing its format"):
            await asyncio.wait_for(camera.get_stream_configurations(), timeout=5)
        service = await MediaService.connect(endpoint)
        with pytest.raises(RuntimeError, match="missing its format"):
            service.get_stream_configurations(7)

    asyncio.run(discover())
