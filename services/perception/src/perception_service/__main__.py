# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from contextlib import ExitStack

from loguru import logger
from perception_service import service as grpc_service
from perception_service.cli import parse_args
from perception_service.gstreamer.glib_dispatcher import GLibTaskDispatcher
from perception_service.gstreamer.runtime import MAX_PIPELINES, GStreamerRuntime
from perception_service.logging import configure_logging
from perception_service.messaging.lifecycle import LifecyclePublisher
from perception_service.messaging.result_publisher import (
    RedisEventPublisher,
    RedisResultPublisher,
    ResultStats,
)
from perception_service.opk.config import OpkCommEndpoint
from perception_service.opk.endpoint_pool import OpkCommEndpointPool
from perception_service.opk.result_router import OpkResultRouter
from perception_service.pipeline_manager import PipelineManager
from perception_service.pipeline_store import PipelineStore
from perception_service.workflow.model_package import create_model_validator
from perception_service.workflow.model_registry import ModelRegistry
from perception_service.workflow.stage import StageDependencies
from perception_service.workflow.stages.registry import create_stage_factory
from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry


def log_publication_stats(stats: ResultStats) -> None:
    logger.info("Perception publication statistics: {}", stats.snapshot())


def main() -> None:
    configure_logging()
    args = parse_args()

    model_paths = tuple(args.model_path or ())
    try:
        model_registry = ModelRegistry(
            model_paths,
            create_model_validator(args.model_schema_path),
        )
    except ValueError as error:
        raise SystemExit(f"Cannot load configured models: {error}") from None
    opk_comm_endpoint = OpkCommEndpoint(
        args.opk_comm_host,
        args.opk_comm_first_port,
    )
    endpoint_pool = OpkCommEndpointPool(opk_comm_endpoint, MAX_PIPELINES)
    stage_dependencies = StageDependencies(
        model_registry=model_registry,
        opk_comm_endpoint=opk_comm_endpoint,
    )
    stage_factory = create_stage_factory(stage_dependencies)
    stats = ResultStats()

    with ExitStack() as stack:
        stack.callback(log_publication_stats, stats)
        redis_client = stack.enter_context(
            Redis.from_url(
                args.redis_url,
                retry=Retry(NoBackoff(), 0),
                socket_connect_timeout=args.redis_timeout,
                socket_timeout=args.redis_timeout,
            )
        )
        result_publisher = stack.enter_context(
            RedisResultPublisher(
                redis_client.publish,
                stats,
                args.redis_queue_size,
            )
        )
        lifecycle_event_publisher = stack.enter_context(
            RedisEventPublisher(
                redis_client.publish,
                stats,
                args.redis_queue_size,
                queue_name="lifecycle",
            )
        )
        lifecycle = LifecyclePublisher(lifecycle_event_publisher)
        result_router = stack.enter_context(OpkResultRouter(result_publisher, stats))
        gstreamer_runtime = stack.enter_context(GStreamerRuntime(GLibTaskDispatcher()))
        pipeline_manager = PipelineManager(gstreamer_runtime, PipelineStore())
        service = grpc_service.PerceptionService(
            pipeline_manager, stage_factory, result_router, endpoint_pool, lifecycle
        )
        stack.callback(service.begin_shutdown)
        grpc_service.serve(service, pipeline_manager, args.host, args.port)


if __name__ == "__main__":
    main()
