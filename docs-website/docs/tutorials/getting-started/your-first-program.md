---
sidebar_position: 2
---

# Your First Program

:::warning Placeholder Tutorial
The code below is example-only and uses placeholder API names.  
This page will be updated with real repository code as soon as the production demo is available.
:::

```python title="capture.py"
from cairn import Camera

# Create a Camera instance
camera = Camera()

# Capture an image
image = camera.capture()
# Display the captured image
image.show()
```
