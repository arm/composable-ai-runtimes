---
id: inference
title: Concordia Inference Module
sidebar_position: 4
---

*Looking for endpoint contracts and schemas? See the [API Reference](/api).*

:::tip Why this module is useful
You can run AI inference in your application without building and operating your own model-serving pipeline.
:::

:::info Want to have a try?
Check out the [Sound-to-Text tutorial](/tutorials/getting-started/sound-to-text) for an example of how to use Concordia for inference.
:::

## About the Concordia Inference Module

The Concordia Inference Module gives you access to simple on-device inference via Concordia AI Bricks. Concordia AI Bricks are pre-packaged AI model functions that perform specific inference tasks, such as object detection or the conversion of speech-to-text. By using the Concordia Inference Module, you can easily link together a series of AI Brick invocations to build complex inference workflows without the complexity of setting up a full inference stack.

## Key Capabilities

- [AI Bricks](#brick-execution)
- [Runtime Configuration](#runtime-configuration)

### Brick Execution

Run simple AI inference tasks by passing input data to Concordia AI Bricks and receiving structured outputs.

:::warning Placeholder Code
The code below is example-only and uses an indicative API only.
This page will be updated with real repository code as soon as the production demo is available.
```python
from cairn import concordia

annotated_image = concordia.run_brick(
    brick_name="object-detection",
    input_data={"image": image_bytes},
)

text_result = concordia.run_brick(
    brick_name="sound-to-text",
    input_data={"audio": audio_bytes},
)
```
:::



### Runtime Configuration

Select from different AI Brick variants to adjust the model used and other parameters at runtime, allowing you to optimize your calls for different performance and accuracy needs without changing your application code.
