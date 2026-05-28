---
id: inference
title: Concordia Inference Module
sidebar_position: 4
---

*Looking for endpoint contracts and schemas? See the [API Reference](/api).*

:::tip Why this module is useful
You can run AI inference in your application without building and operating your own model-serving pipeline.
:::

## About the Concordia Inference Module

The Concordia Inference Module gives you access to simple on-device inference via Concordia AI Bricks. Concordia AI Bricks are pre-packaged AI model functions that perform specific inference tasks, such as object detection or text-to-speech. By using the Concordia Inference Module, you can easily link together a series of AI Brick invocations to build complex inference workflows without the complexity of setting up a full inference stack.

## Key Capabilities

- [AI Bricks](#brick-execution)
- [Runtime Configuration](#runtime-configuration)

### Brick Execution

The current API supports an object detection and text-to-speech Concordia Brick. With Brick type, variant, and model input provided as parameters.

```python
from pathlib import Path

from cairn import ConcordiaService

endpoint = "http://127.0.0.1:50051"
inference = ConcordiaService(endpoint)

image_path = Path("friends.jpg")

detection_result = inference.run_brick(
    brick_type="OBJECT_DETECTION",
    brick_variant="YOLO",
    options={"image_bytes": image_path.read_bytes()},
)

detections = detection_result["detections"]
num_persons = len([d for d in detections if d["class_name"] == "person"])
print(f"Number of persons detected: {num_persons}")

audio_result = inference.run_brick(
    brick_type="TEXT_TO_SPEECH",
    brick_variant="KOKORO",
    options={"text": "Hello, world!"},
)

left_channel = audio_result["left_channel"]
right_channel = audio_result["right_channel"]
```


### Runtime Configuration

Select from different AI Brick variants to adjust the model used and other parameters at runtime, allowing you to optimize your calls for different performance and accuracy needs without changing your application code. In the current API this is done with the `brick_variant` argument, for example `YOLO` for object detection or `KOKORO` for text-to-speech.
