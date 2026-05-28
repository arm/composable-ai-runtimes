---
sidebar_position: 5
---

# Object Detection

This tutorial illustrates how to use the Concordia Service in an object detection workflow.

## Example code

```python
from pathlib import Path

from cairn import ConcordiaService

endpoint = "http://127.0.0.1:50051"
inference = ConcordiaService(endpoint)

image_path = Path("friends.jpg")

result = inference.run_brick(
    brick_type="OBJECT_DETECTION",
    brick_variant="YOLO",
    options={"image_bytes": image_path.read_bytes()},
)

for detection in result["detections"]:
    class_name = detection["class_name"]
    score = detection["score"]
    box = detection["box"]
    print(f"{class_name}: {score:.2f} at {box}")
```

`result["detections"]` contains a list of detection objects. Each detection includes:

- `class_name`: the detected label, for example `person`
- `score`: the model confidence for that detection
- `box`: normalized bounding box coordinates in `[x1, y1, x2, y2]` format
