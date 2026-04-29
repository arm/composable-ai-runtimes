# hadolint ignore=DL3007
FROM edge-ai-tooling--sdk-docker-registry.artifactory.arm.com/concordiaai-base:latest

WORKDIR /app

ENV UV_NO_DEV=1
ENV PYTHONPATH=/app/src/inference/proto:/app/src

COPY ./src /app/src
COPY ./pyproject.toml ./pyproject.toml

RUN /opt/venv/bin/python -m pip install --no-cache-dir uv==0.5.31 \
    && uv sync --active

CMD ["/opt/venv/bin/python", "-m", "inference.main", "--host", "0.0.0.0", "--port", "50052", "--model-dir", "/models"]
