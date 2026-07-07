#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

from common import safe_repo_path
from history import append_history
from run_task import run_task


def discover_tasks() -> list[str]:
    tasks_dir = safe_repo_path("usability/tasks")
    return [str(path.relative_to(path.parents[2])) for path in sorted(tasks_dir.glob("*.yaml"))]


def _github_actions_escape(message: str) -> str:
    return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def print_task_result(result: dict, result_path: Path) -> None:
    task_id = result["task_id"]
    status = result["status"]
    duration = result.get("duration_seconds")
    print(f"{task_id}: {status} ({duration}s)", flush=True)

    for setup in result.get("setup", []):
        print(
            f"  setup: {setup['name']} exited {setup['exit_code']}",
            flush=True,
        )

    verification = result.get("verification")
    if verification:
        print(
            f"  verification: {verification['command']} exited {verification['exit_code']}",
            flush=True,
        )

    if result.get("error"):
        error = str(result["error"])
        print(f"  error: {error}", file=sys.stderr, flush=True)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            annotation = _github_actions_escape(f"{task_id}: {error}")
            print(f"::error title=AI usability task failed::{annotation}", flush=True)

    print(f"  result: {result_path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="usability/results")
    parser.add_argument("--history", default="usability/history/history.json")
    parser.add_argument("--max-turns", type=int, default=12)
    args = parser.parse_args()

    results_dir = safe_repo_path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    task_paths = discover_tasks()
    task_results = []
    exit_code = 0

    for task_path in task_paths:
        result_path = results_dir / (Path(task_path).stem + ".json")
        print(f"Running usability task: {task_path}", flush=True)
        status, result = run_task(task_path, str(result_path.relative_to(results_dir.parent.parent)), args.max_turns)
        result["github_run_id"] = os.environ.get("GITHUB_RUN_ID")
        result["github_sha"] = os.environ.get("GITHUB_SHA")
        task_results.append(result)
        print_task_result(result, result_path)
        if status != 0:
            exit_code = 1

    append_history(args.history, task_results)

    framework_result = {
        "task_count": len(task_results),
        "failed_task_count": sum(1 for result in task_results if result["status"] != "passed"),
        "tasks": task_results,
    }
    (results_dir / "framework.json").write_text(
        json.dumps(framework_result, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"AI usability summary: {framework_result['task_count']} tasks, "
        f"{framework_result['failed_task_count']} failed",
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
