---
id: vision
title: Vision Module (Proposed)
sidebar_position: 5
---

:::info Proposed module
This page captures the current proposal for decomposing the `amp-dev-forge` experience kit into Cairn SDK service boundaries. It is a design note, not a description of a finished runtime surface.
:::

## Why this module may be valuable

The `amp-dev-forge` repository demonstrates a strong reference implementation for media-driven vision workflows. Today, its entry points are the `amp-menu` launcher and direct GStreamer pipeline composition. A proposed Cairn Vision Module builds on that foundation by exposing those same vision capabilities through Cairn’s service model, making them easier to integrate into existing applications, easier to compose with other SDK modules, and less dependent on direct GStreamer integration at the application layer.

For Cairn SDK, this helps establish vision pipelines as a first-class feature with clearer contracts for workflows, sessions, results and events, and provides a natural integration point between the Camera Module, the Message Module and future output or preview capabilities.

## Potential benefits of a dedicated Vision Module include:
- **Service-oriented API**: A dedicated Vision Module can provide a stable, high-level API that abstracts away the complexities of GStreamer and media processing, making it easier for applications to leverage vision capabilities without needing to manage low-level details.
- **Workflow management**: The module can manage the lifecycle of vision workflows, including session management, event handling, and result delivery, providing a more coherent and application-friendly integration surface.
- **Event semantics**: By defining clear event semantics for vision-related events (e.g., workflow started, workflow stopped, source degraded), the module can help applications react appropriately to changes in vision processing state and results.
- **Integration with other modules**: The Vision Module can integrate with the Camera Module for input and the Message Module for event and result transport, providing a cohesive toolkit for media-driven applications.
- **Path to semantic events**: Over time, structured workflow results could support higher-level semantic events such as stable presence/absence signals for people or faces, as well as source and workflow state changes, making it easier for applications and other SDK modules to react to meaningful conditions.

## Cairn Integration Overview

*In this proposed model, user applications interface with the Vision Module through the Cairn Client Library, which provides a high-level API for managing vision workflows, sessions, and results. The Vision Module depends on the Camera Module for video input and the Message Module for event and result transport.*

```mermaid
flowchart LR
    App[User app.py] --> SDK[Cairn Client Library]

    subgraph Cairn[Cairn Modules]
        Camera[Camera Module]
        Vision[Vision Module]
        Bus[Message Module]
    end

    SDK --> Camera
    SDK --> Vision
    SDK <--> Bus

    Camera --> Vision
    Vision --> Bus
    Camera --> Bus
```

## Vision Module Overview

*In this proposed model, an abstraction layer inside the Vision Module compiles application-facing workflow definitions into GStreamer pipelines that execute the requested vision workloads using components from the `amp-dev-forge` experience kit. The module manages the lifecycle of these pipelines and translates their outputs into structured results and events that are emitted through the Message Module.*

```mermaid
flowchart LR
    VisionAPI[Vision Module API]
    Camera[Camera Module]
    Bus[Message Module]

    subgraph VisionService[Vision Module]
        GraphReader[Abstraction Layer]

        subgraph Gst[GStreamer]
            PipewireSrc[pipewiresrc] --> PreAmp[...] --> AmpInfer[ampinfer] --> AmpComponents[...]
            AmpComponents --> FileSink[filesink]
            AmpComponents --> AmpSink[ampsink]
            AmpComponents --> CairnSink[cairnsink]
        end

        GraphReader --> Gst
    end

    VisionAPI --> GraphReader
    Camera --> PipewireSrc
    CairnSink -- structured results --> Bus --> VisionAPI
```

## Workflow model

The public Vision Service API is workflow-oriented in this proposed model.

Applications define:

- what source is used (camera id, evaluated by the camera service)
- which analysis stages run
- how stages are connected
- what outputs are produced

This is intentionally pipeline-shaped, but is not a raw GStreamer graph. The API abstracts away GStreamer-specific concepts and focuses on the composition semantics that applications care about.

## Provisional application shape

The client SDK remains a thin shim over services in this proposed model. It does not implement workflow semantics by itself.

Conceptually, the application looks something like this:


```python
import os
import time

from cairn_sdk import CameraService
from cairn_sdk.vision_builder import Inference, Output, VisionBuilder
from cairn_sdk.vision_builder.opchains import (
    GenericImagePreprocess,
    GenericPostprocess,
    InferenceController,
    OpChain,
    OpChainInference,
)
from cairn_sdk.vision_builder.outputs import AMPSink, RTSPStreamSink
from cairn_sdk.vision_builder.presets import Ultraface


def main():
    camera = CameraService().list_camera_metadata()[0]

    pipeline = (
        VisionBuilder(
            camera=camera,
        )
        .add(Inference(name="faces", opchain=Ultraface(), active=True))
        .add(
            Inference(
                name="custom_objects",
                active=False,
                opchain=OpChain(
                    ops=[
                        InferenceController(),
                        GenericImagePreprocess(
                            inputImageTensorIndex=0,
                            inputImageSourceName="pipelineVideoFrame",
                        ),
                        OpChainInference(
                            modelDescriptor="/work/etc/models/yolo/yolo.json",
                        ),
                        GenericPostprocess(
                            parser="YoloParser",
                            normalizeOutputCoordinates=False,
                            applyNms=True,
                            confidenceThreshold=0.5,
                            iouThreshold=0.45,
                        ),
                    ]
                ),
            )
        )
        .build(
            output=Output(
                sink=AMPSink(), # or RTSPSink
                show_performance=True,
                show_detections=True,
            )
        )
    )

    pipeline.add_listener(inference="faces", callback=handle_faces)
    pipeline.add_listener(inference="custom_objects", callback=handle_custom_objects)

    pipeline.start()
    try:
        print(f"Vision session {pipeline.session_id} started")
        pipeline.enable("custom_objects")
        while True:
            time.sleep(1)
            # pipeline.disable("faces")
            # pipeline.enable("faces")
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
```

This keeps `main()` short while still showing the core VisionBuilder surface: named inferences, preview output, listeners, and runtime control.
