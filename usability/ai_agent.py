import json
import os
from dataclasses import dataclass
from typing import Any

import requests

from common import MODEL
from repo_tools import TOOL_SCHEMAS, ToolExecutor

SYSTEM_PROMPT = """You are a coding agent working in a checked-out repository.
Use the available tools to inspect the repo and create the requested file.
Prefer minimal changes.
When you are done, call finish.
"""


@dataclass
class AgentResult:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    finished: bool
    tool_history: list[dict[str, Any]]
    files_read: list[str]
    commands_run: list[str]
    writes_made: list[str]
    tool_calls: int


def run_agent(prompt: str, max_turns: int) -> AgentResult:
    executor = ToolExecutor()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt.strip()},
    ]
    usage_totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for _ in range(max_turns):
        assistant_message, usage = call_model(messages)
        for key in usage_totals:
            usage_totals[key] += usage.get(key, 0) or 0

        tool_calls = assistant_message.get("tool_calls") or []
        messages.append(assistant_message)
        if not tool_calls:
            continue

        for tool_call in tool_calls:
            result = executor.execute(tool_call)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": tool_call["function"]["name"],
                    "content": json.dumps(result),
                }
            )

        if executor.finished:
            break

    return AgentResult(
        prompt_tokens=usage_totals["prompt_tokens"],
        completion_tokens=usage_totals["completion_tokens"],
        total_tokens=usage_totals["total_tokens"],
        finished=executor.finished,
        tool_history=executor.history,
        files_read=executor.files_read,
        commands_run=executor.commands_run,
        writes_made=executor.writes_made,
        tool_calls=executor.tool_calls,
    )


def call_model(messages: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    response = requests.post(
        f"{os.environ['OPENAI_BASE_URL'].rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "temperature": 0,
            "messages": messages,
            "tools": TOOL_SCHEMAS,
            "tool_choice": "auto",
        },
        timeout=180,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["choices"][0]["message"], payload.get("usage", {})
