from __future__ import annotations


def print_log_group(title: str, log: str) -> None:
    print(f"::group::{title}")
    try:
        print(log, end="")
    finally:
        print("::endgroup::")
