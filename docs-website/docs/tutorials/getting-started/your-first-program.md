---
sidebar_position: 2
---

# Your First Program

```python title="capture.py"
from cairn import CameraService

camera_service = CameraService()
camera_metadata = camera_service.list_camera_metadata()

camera = camera_service.open(camera_metadata[0])
frame = camera.get_latest_frame()

process(frame)
```
