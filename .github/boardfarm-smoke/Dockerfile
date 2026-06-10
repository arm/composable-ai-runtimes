FROM debian:trixie-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*

CMD ["sh", "-c", "echo boardfarm dummy container ready; touch /tmp/ready; exec sleep infinity"]
