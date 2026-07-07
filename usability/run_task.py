#!/usr/bin/env python3
import argparse
import json
import time

from ai_agent import run_agent
from common import MODEL, load_task, rel_path, run_shell, safe_repo_path


def run_task(task_path: str, result_path: str, max_turns: int) -> tuple[int, dict]:
    started = time.time()
    task = load_task(task_path)
    criteria = task["success_criteria"]
    result_file = safe_repo_path(result_path)
    result_file.parent.mkdir(parents=True, exist_ok=True)
    output_path = safe_repo_path(criteria["file_exists"])

    result = {
        "task_id": task["id"],
        "task_version": task["version"],
        "configured_model": MODEL,
        "status": "failed",
        "setup": [],
        "tool_history": [],
    }

    try:
        for step in task.get("setup", []):
            completed = run_shell(step["run"])
            result["setup"].append(
                {
                    "name": step["name"],
                    "command": step["run"],
                    "exit_code": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                }
            )
            if completed.returncode != 0:
                raise RuntimeError(f"setup failed: {step['name']}")

        agent = run_agent(task["prompt"], max_turns)
        result.update(
            {
                "model": MODEL,
                "prompt_tokens": agent.prompt_tokens,
                "completion_tokens": agent.completion_tokens,
                "total_tokens": agent.total_tokens,
                "files_used": agent.files_used,
                "unique_files_used": sorted(set(agent.files_used)),
                "commands_run": agent.commands_run,
                "writes_made": agent.writes_made,
                "tool_calls": agent.tool_calls,
                "tool_history": agent.tool_history,
                "expected_output_file": rel_path(output_path),
            }
        )
        if not output_path.exists():
            raise RuntimeError(
                f"expected output file was not written: {rel_path(output_path)}"
            )

        verification = run_shell(
            task["verification"]["command"],
            timeout=task["verification"].get("timeout_seconds"),
        )
        actual_stdout = verification.stdout.strip()

        result.update(
            {
                "output_file": rel_path(output_path),
                "verification": {
                    "command": task["verification"]["command"],
                    "exit_code": verification.returncode,
                    "stdout": verification.stdout,
                    "stderr": verification.stderr,
                },
            }
        )

        if not agent.finished:
            raise RuntimeError("agent did not call finish")
        if verification.returncode != criteria.get("exit_code", 0):
            raise RuntimeError("verification command failed")
        if actual_stdout != criteria["stdout_exact"]:
            raise RuntimeError(
                f"stdout mismatch: expected {criteria['stdout_exact']!r}, got {actual_stdout!r}"
            )

        result["status"] = "passed"
        return 0, result
    except Exception as exc:
        result["error"] = str(exc)
        return 1, result
    finally:
        result["duration_seconds"] = round(time.time() - started, 3)
        result_file.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    parser.add_argument("--result", default="usability/results/latest.json")
    parser.add_argument("--max-turns", type=int, default=12)
    args = parser.parse_args()
    status, _ = run_task(args.task, args.result, args.max_turns)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
