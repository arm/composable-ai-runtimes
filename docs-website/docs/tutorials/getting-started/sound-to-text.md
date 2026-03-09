---
sidebar_position: 4
---

# Sound-to-Text

:::warning Placeholder Tutorial
The code below is example-only and uses placeholder API names.  
This page will be updated with real repository code as soon as the production demo is available.
:::

## Example code (placeholder)

```python
from cairn import CairnClient

client = CairnClient()
client.connect()

# Placeholder channel and method names
for chunk in microphone_stream():
    result = client.inference.transcribe_audio(
        model="whisper-small",
        audio_bytes=chunk,
        language="en",
    )
    client.messaging.publish(
        channel="transcription.events",
        payload={
            "text": result.text,
            "confidence": result.confidence,
            "timestamp": result.timestamp,
        },
    )
```
