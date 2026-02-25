# Concordia gRPC Service

## Start The Server

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
concordia \
  --host 0.0.0.0 \
  --port 50052 \
  --model-dir /path/to/concordia-models
```

## Run Example Clients

### TTS Example

```bash
python scripts/grpc_client_tts_example.py \
  --host 127.0.0.1 \
  --port 50052 \
  --variant kokoro \
  --out output.wav
```

### YOLO Example

```bash
python scripts/grpc_client_yolo_example.py \
  --host 127.0.0.1 \
  --port 50052 \
  --image /path/to/image.jpg
```
