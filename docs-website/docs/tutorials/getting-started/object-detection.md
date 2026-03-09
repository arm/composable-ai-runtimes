---
sidebar_position: 5
---

# Object Detection

:::warning Placeholder Tutorial
The code below is example-only and uses placeholder API names.  
This page will be updated with real repository code as soon as the production demo is available.
:::

## Example code (placeholder)

```python
from cairn import CairnClient

client = CairnClient()
client.connect()

# Placeholder stream, model, and event schema
for frame in client.camera.subscribe_frames(source="front-camera"):
    detections = client.inference.detect_objects(
        model="yolo-edge",
        image=frame.bytes,
    )
    client.messaging.publish(
        channel="vision.detections",
        payload={
            "camera_id": frame.camera_id,
            "frame_id": frame.frame_id,
            "detections": [d.to_dict() for d in detections],
        },
    )
```
