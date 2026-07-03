from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar


P = ParamSpec("P")
T = TypeVar("T")
TimeoutAttempt = Callable[P, T | None]
TimeoutFallback = Callable[[], T | None]


def with_timeout(
    timeout_seconds: float,
    *,
    interval_seconds: float = 1.0,
    on_timeout: TimeoutFallback | None = None,
) -> Callable[[TimeoutAttempt], TimeoutAttempt]:
    def decorator(func: TimeoutAttempt) -> TimeoutAttempt:
        @wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> T | None:
            deadline = time.monotonic() + timeout_seconds

            while time.monotonic() < deadline:
                result = func(*args, **kwargs)
                if result is not None:
                    return result
                if interval_seconds > 0:
                    time.sleep(interval_seconds)

            if on_timeout is not None:
                return on_timeout()
            return None

        return wrapped

    return decorator
