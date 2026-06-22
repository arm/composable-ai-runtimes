from __future__ import annotations

import re


CAMERA_STARTUP_FAILURE_PATTERN = re.compile(
    r"missing runtime directory|"
    r"PipeWire .*timed out|"
    r"PipeWire .*timeout|"
    r"panic|panicked|"
    r"segmentation fault|"
    r"service process .*exit|"
    r"exited with",
    re.IGNORECASE,
)
