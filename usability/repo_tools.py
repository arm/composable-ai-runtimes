import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from common import ROOT, rel_path, run_shell, safe_repo_path

EXCLUDED_DIRS = {".git", "target", ".venv", "node_modules", "__pycache__"}
MAX_TOOL_OUTPUT = 12000
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List repository files under a path.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "default": "."}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file from the repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer", "default": 1},
                    "max_lines": {"type": "integer", "default": 200},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command in the repository root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout_seconds": {"type": "integer", "default": 20},
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write a file in the repository. Use only for the requested output file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Finish the task after the output file has been written.",
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
                "additionalProperties": False,
            },
        },
    },
]


@dataclass
class ToolExecutor:
    required_output_file: str | None = None
    files_used: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    writes_made: list[str] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: int = 0
    finished: bool = False

    def __post_init__(self) -> None:
        if self.required_output_file is not None:
            self.required_output_file = rel_path(safe_repo_path(self.required_output_file))

    @property
    def required_output_written(self) -> bool:
        return (
            self.required_output_file is None
            or self.required_output_file in self.writes_made
        )

    def execute(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        name = tool_call["function"]["name"]
        arguments = json.loads(tool_call["function"].get("arguments", "{}"))
        handler = getattr(self, name, None)
        result = handler(arguments) if handler else {"error": f"unknown tool: {name}"}

        self.tool_calls += 1
        self.history.append({"tool": name, "arguments": arguments, "result": result})
        return result

    def list_files(self, arguments: dict[str, Any]) -> dict[str, Any]:
        base = safe_repo_path(arguments.get("path", "."))
        if not base.exists():
            return {"error": "path does not exist"}
        if base.is_file():
            used = rel_path(base)
            self.files_used.append(used)
            return {"path": used, "files": [used]}

        files: list[str] = []
        for current_root, dirs, names in os.walk(base):
            dirs[:] = [d for d in sorted(dirs) if d not in EXCLUDED_DIRS]
            root_path = Path(current_root)
            for name in sorted(names):
                full = root_path / name
                rel = full.relative_to(ROOT)
                if any(part in EXCLUDED_DIRS for part in rel.parts):
                    continue
                files.append(str(rel))
        self.files_used.extend(files)
        return {"path": rel_path(base), "files": files}

    def read_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = safe_repo_path(arguments["path"])
        start_line = max(1, int(arguments.get("start_line", 1)))
        max_lines = max(1, int(arguments.get("max_lines", 200)))
        lines = path.read_text(encoding="utf-8").splitlines()
        start = start_line - 1
        end = start + max_lines
        self.files_used.append(rel_path(path))
        return {
            "path": rel_path(path),
            "start_line": start_line,
            "end_line": min(len(lines), end),
            "content": "\n".join(lines[start:end]),
        }

    def run_command(self, arguments: dict[str, Any]) -> dict[str, Any]:
        command = arguments["command"]
        self.commands_run.append(command)
        completed = run_shell(command, timeout=int(arguments.get("timeout_seconds", 20)))
        return {
            "command": command,
            "exit_code": completed.returncode,
            "stdout": self._truncate(completed.stdout),
            "stderr": self._truncate(completed.stderr),
        }

    def write_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = safe_repo_path(arguments["path"])
        target = rel_path(path)
        if (
            self.required_output_file is not None
            and target != self.required_output_file
        ):
            return {
                "error": (
                    "write_file rejected: expected path "
                    f"{self.required_output_file}, got {target}"
                )
            }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(arguments["content"], encoding="utf-8")
        self.writes_made.append(target)
        return {"path": target, "bytes_written": len(arguments["content"].encode("utf-8"))}

    def finish(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self.required_output_written:
            return {
                "error": (
                    "finish rejected: call write_file for "
                    f"{self.required_output_file} before finish"
                )
            }
        self.finished = True
        return {"summary": arguments["summary"]}

    @staticmethod
    def _truncate(text: str) -> str:
        if len(text) <= MAX_TOOL_OUTPUT:
            return text
        return text[:MAX_TOOL_OUTPUT] + "\n...[truncated]..."
