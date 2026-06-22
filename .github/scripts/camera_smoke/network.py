from __future__ import annotations

import socket


def can_connect_to_tcp(host: str, port: int, *, timeout_seconds: float = 2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False
