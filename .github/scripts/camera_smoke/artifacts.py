from __future__ import annotations

from pathlib import Path


def write_text_artifact(results_dir: Path, name: str, content: str) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / name).write_text(content, encoding="utf-8")
