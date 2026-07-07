import json
from datetime import UTC, datetime

from common import safe_repo_path


def history_entry(timestamp: str, entry: dict) -> dict:
    files_used = sorted(set(entry.get("files_used", [])))
    return {
        "timestamp": timestamp,
        "github_run_id": entry.get("github_run_id"),
        "github_sha": entry.get("github_sha"),
        "task_id": entry.get("task_id"),
        "status": entry.get("status"),
        "model": entry.get("model") or entry.get("configured_model"),
        "prompt_tokens": entry.get("prompt_tokens", 0),
        "completion_tokens": entry.get("completion_tokens", 0),
        "total_tokens": entry.get("total_tokens", 0),
        "duration_seconds": entry.get("duration_seconds", 0),
        "tool_calls": entry.get("tool_calls", 0),
        "command_count": len(entry.get("commands_run", [])),
        "write_count": len(entry.get("writes_made", [])),
        "file_count": len(files_used),
        "files_used": files_used,
    }


def append_history(path: str, entries: list[dict]) -> None:
    history_path = safe_repo_path(path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    if history_path.exists():
        history = json.loads(history_path.read_text(encoding="utf-8"))
    else:
        history = []

    timestamp = datetime.now(UTC).isoformat()
    history.extend(history_entry(timestamp, entry) for entry in entries)
    history_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
