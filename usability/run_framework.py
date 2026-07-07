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


def _count(result: dict, key: str) -> int:
    value = result.get(key)
    return len(value) if isinstance(value, list) else 0


def _print_text_block(label: str, value: str) -> None:
    text = value.strip()
    if not text:
        return
    print(f"  {label}:", flush=True)
    for line in text.splitlines():
        print(f"    {line}", flush=True)


def print_task_metrics(result: dict) -> None:
    if "total_tokens" not in result and "tool_calls" not in result:
        print("  metrics: unavailable; task failed before agent metrics were recorded", flush=True)
        return

    print("  metrics:", flush=True)
    print(
        "    tokens: "
        f"prompt={result.get('prompt_tokens', 0)}, "
        f"completion={result.get('completion_tokens', 0)}, "
        f"total={result.get('total_tokens', 0)}",
        flush=True,
    )
    print(
        "    activity: "
        f"tool_calls={result.get('tool_calls', 0)}, "
        f"files_read={_count(result, 'files_read')} "
        f"({_count(result, 'unique_files_read')} unique), "
        f"commands_run={_count(result, 'commands_run')}, "
        f"writes_made={_count(result, 'writes_made')}",
        flush=True,
    )

    output_file = result.get("output_file")
    if output_file:
        print(f"    output_file={output_file}", flush=True)
    expected_output_file = result.get("expected_output_file")
    if expected_output_file and expected_output_file != output_file:
        print(f"    expected_output_file={expected_output_file}", flush=True)

    tool_history = result.get("tool_history", [])
    if isinstance(tool_history, list) and tool_history:
        tools = [str(item.get("tool", "unknown")) for item in tool_history[:12]]
        suffix = " ..." if len(tool_history) > len(tools) else ""
        print(f"    tools={', '.join(tools)}{suffix}", flush=True)


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
        _print_text_block("verification stdout", verification.get("stdout", ""))
        _print_text_block("verification stderr", verification.get("stderr", ""))

    print_task_metrics(result)

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
    total_tokens = sum(int(result.get("total_tokens", 0) or 0) for result in task_results)
    total_tool_calls = sum(int(result.get("tool_calls", 0) or 0) for result in task_results)
    print(
        f"AI usability summary: {framework_result['task_count']} tasks, "
        f"{framework_result['failed_task_count']} failed, "
        f"{total_tokens} tokens, {total_tool_calls} tool calls",
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
