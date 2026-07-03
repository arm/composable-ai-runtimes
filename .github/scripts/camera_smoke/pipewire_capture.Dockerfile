FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gir1.2-gst-plugins-base-1.0 \
        gir1.2-gstreamer-1.0 \
        gstreamer1.0-pipewire \
        gstreamer1.0-plugins-base \
        gstreamer1.0-plugins-good \
        gstreamer1.0-tools \
        python3 \
        python3-gi \
        python3-gst-1.0 \
    && rm -rf /var/lib/apt/lists/*

COPY pipewire_capture_probe.py /usr/local/bin/pipewire_capture_probe.py

ENTRYPOINT ["python3", "/usr/local/bin/pipewire_capture_probe.py"]
