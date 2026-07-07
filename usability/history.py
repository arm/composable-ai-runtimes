import json
from datetime import UTC, datetime

from common import safe_repo_path


def append_history(path: str, entries: list[dict]) -> None:
    history_path = safe_repo_path(path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    if history_path.exists():
        history = json.loads(history_path.read_text(encoding="utf-8"))
    else:
        history = []

    timestamp = datetime.now(UTC).isoformat()
    for entry in entries:
        history.append(
            {
                "timestamp": timestamp,
                "github_run_id": entry.get("github_run_id"),
                "github_sha": entry.get("github_sha"),
                **entry,
            }
        )

    history_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
