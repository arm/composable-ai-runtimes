from __future__ import annotations

from typing import Any
import os

import numpy as np
from PIL import Image

import compute_flow_py as cfpy
from .proto import concordia_pb2 as pb2

DEFAULT_IMAGE_WIDTH = 640
DEFAULT_IMAGE_HEIGHT = 480
DEFAULT_IMAGE_CHANNELS = 3


def configure_accelerators(manifest: Any, brick_type: int, variant: str) -> None:
    num_threads = os.cpu_count() or 1
    if brick_type == pb2.BRICK_TYPE_TTS:
        manifest[variant].acc_config = cfpy.AcceleratorConfig.cpu_only(num_threads)
    elif brick_type == pb2.BRICK_TYPE_OBJECT_DETECTION and variant == "yolo":
        manifest["yolo"].acc_config = cfpy.AcceleratorConfig.cpu_only(num_threads)


def to_float_list(values: Any) -> list[float]:
    if hasattr(values, "tolist"):
        values = values.tolist()
    flat: list[float] = []
    for v in values:
        if isinstance(v, (list, tuple)):
            flat.extend(float(x) for x in v)
        else:
            flat.append(float(v))
    return flat


def image_bytes_to_npy(image_bytes: bytes, input_size=(640, 640)) -> np.ndarray:
    expected_len = DEFAULT_IMAGE_WIDTH * DEFAULT_IMAGE_HEIGHT * DEFAULT_IMAGE_CHANNELS
    if len(image_bytes) != expected_len:
        raise ValueError(
            "image_bytes must contain raw packed RGB pixels for "
            f"{DEFAULT_IMAGE_WIDTH}x{DEFAULT_IMAGE_HEIGHT} input "
            f"({expected_len} bytes)"
        )

    img_np = np.frombuffer(image_bytes, dtype=np.uint8).reshape(
        DEFAULT_IMAGE_HEIGHT,
        DEFAULT_IMAGE_WIDTH,
        DEFAULT_IMAGE_CHANNELS,
    )
    img = Image.fromarray(img_np, mode="RGB")
    img = img.resize(input_size, Image.BILINEAR)
    img_np = np.asarray(img).astype(np.float32)
    img_np /= 255.0
    img_np = np.transpose(img_np, (2, 0, 1))
    img_np = np.expand_dims(img_np, axis=0)
    return img_np


def to_detections(output: Any) -> list[pb2.Detection]:
    boxes = np.asarray(output["box"], dtype=np.float32)
    class_ids = np.asarray(output["id"]).astype(int).flatten()
    scores = np.asarray(output["score"], dtype=np.float32).flatten()
    class_names = output["name"]

    if boxes.size == 0:
        return []

    if boxes.ndim == 1 and boxes.size == 4:
        boxes = boxes.reshape(1, 4)

    if boxes.max() > 1.01:
        boxes = boxes / 640.0

    detections: list[pb2.Detection] = []
    for i in range(boxes.shape[0]):
        name_row = class_names[i] if i < len(class_names) else []
        if isinstance(name_row, (bytes, bytearray)):
            name_bytes = bytes(name_row)
        else:
            name_bytes = bytes(np.asarray(name_row).tolist())
        class_name = name_bytes.split(b"\x00", 1)[0].decode("utf-8", errors="replace")

        detections.append(
            pb2.Detection(
                box=[float(x) for x in boxes[i].tolist()],
                class_id=int(class_ids[i]) if i < len(class_ids) else -1,
                score=float(scores[i]) if i < len(scores) else 0.0,
                class_name=class_name,
            )
        )
    return detections
