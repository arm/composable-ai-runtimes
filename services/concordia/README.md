# Concordia Inference Service

## Overview

Concordia is a gRPC-based inference service for running object detection and text-to-speech models.
In the current Cairn SDK proof of concept (PoC), it provides the initial inference workflow used to validate model execution and client integration patterns.

## Requirements

- Python 3.12
- [pip](https://pip.pypa.io/en/stable/)
- [virtualenv](https://virtualenv.pypa.io/en/latest/)
- Docker (optional, for containerized deployment)

For containerised Concordia development, use the `.devcontainer/concordia` Dev Container; it runs `uv sync --active --extra dev` during post-create setup.

## Installation

### Local Setup

```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Install the package in editable mode
pip install -e .
```

### Docker Compose

Ensure your `compose.yaml` mounts the models and source code.  
Start the local server using:

```bash
docker compose up
```

## Usage

### Example to test gRPC Client

```bash
pip install .[dev]

pytest test/test_concordia_service.py
```

## Development

- Install dev dependencies:
  ```bash
  pip install .[dev]
  ```
- Regenerate protobuf files as needed.

## Troubleshooting

- Ensure `/models` contains the required manifest and model files. Download them from [https://gitlab.geo.arm.com/artificial-intelligence/gen-ai/compute_flow](https://gitlab.geo.arm.com/artificial-intelligence/gen-ai/compute_flow) (see `bricks` diectory).
- Replace model files if corrupted.
- Check Docker logs for errors:
  ```bash
  docker compose logs concordia
  ```
- Use `localhost:50052` as the client target if running locally.

## Building the Base Image

The base image is hosted in artifactory as edge-ai-tooling--sdk-docker-registry.artifactory.arm.com/concordiaai-base:latest. It is currently built by hand and then uploaded. If you would like to rebuild this image, you can do so from the [compute_flow repository](https://gitlab.geo.arm.com/artificial-intelligence/gen-ai/compute_flow) by following the README in `.docker`. If you would also like to include the models into the base image instead of mounting them, you can adjust the base image Dockerfile to copy the models across into the image. Currently the base image has been bundled with the required models.
