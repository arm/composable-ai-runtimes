from pathlib import Path
import subprocess

import yaml

ROOT = Path(__file__).resolve().parent.parent
MODEL = "gpt-4.1"


def load_task(path: str) -> dict:
    task_path = ROOT / path
    if task_path.is_dir():
        metadata_path = task_path / "task.yaml"
        with metadata_path.open(encoding="utf-8") as handle:
            task = yaml.safe_load(handle) or {}

        prompt_name = task.get("prompt_file", "Prompt.md")
        prompt_path = task_path / prompt_name
        task["prompt"] = prompt_path.read_text(encoding="utf-8")
        return task

    with task_path.open(encoding="utf-8") as handle:
        task = yaml.safe_load(handle) or {}

    prompt_name = task.get("prompt_file")
    if prompt_name:
        prompt_path = task_path.parent / prompt_name
        task["prompt"] = prompt_path.read_text(encoding="utf-8")

    return task


def safe_repo_path(path: str) -> Path:
    resolved = (ROOT / path).resolve()
    resolved.relative_to(ROOT)
    return resolved


def rel_path(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def run_shell(command: str, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        shell=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
