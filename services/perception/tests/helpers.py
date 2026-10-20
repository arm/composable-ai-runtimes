# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path

from perception_service.workflow.model_package import create_model_validator


MODEL_VALIDATOR = create_model_validator(None)


def create_model(model_path: Path) -> Path:
    model_path.mkdir(parents=True)
    (model_path / "model.bin").write_bytes(b"model")
    (model_path / "model.json").write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "name": model_path.name,
                "modelFile": "model.bin",
                "dynamicOutput": True,
                "inputTensors": [
                    {
                        "shape": [1, 3, 16, 16],
                        "dataKind": "ImageRgbChw",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (model_path / "opchain.json").write_text(
        json.dumps(
            {
                "version": "1.0.1",
                "name": model_path.name,
                "description": f"Test package for {model_path.name}",
                "ops": [
                    {
                        "id": "opk-onnx-ops/Inference",
                        "attributes": {"modelDescriptor": "model.json"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return model_path
