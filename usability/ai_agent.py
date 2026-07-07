import json
import os
from dataclasses import dataclass
from typing import Any

import requests

from common import MODEL
from repo_tools import TOOL_SCHEMAS, ToolExecutor


def response_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    properties = parameters.get("properties", {})
    return {
        **parameters,
        "required": sorted(properties.keys()),
    }


OPENAI_RESPONSES_URL = "https://openai-api-proxy.geo.arm.com/api/providers/openai/v1/responses"
RESPONSE_TOOLS = [
    {
        "type": "function",
        "name": tool["function"]["name"],
        "description": tool["function"]["description"],
        "parameters": response_parameters(tool["function"]["parameters"]),
        "strict": True,
    }
    for tool in TOOL_SCHEMAS
]
SYSTEM_PROMPT = """You are a coding agent working in a checked-out repository.
Use the available tools to inspect the repo and create the requested file.
Prefer minimal changes.
Do not list or read broad parts of the repository unless the task requires it.
If the user asks for a specific output file, write that file as soon as you have
enough information. Do not spend all turns exploring.
When you are done, call finish.
"""


@dataclass
class AgentResult:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    finished: bool
    tool_history: list[dict[str, Any]]
    files_used: list[str]
    commands_run: list[str]
    writes_made: list[str]
    tool_calls: int


def run_agent(prompt: str, max_turns: int) -> AgentResult:
    executor = ToolExecutor()
    conversation: list[dict[str, Any]] = [{"role": "user", "content": prompt.strip()}]
    usage_totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for _ in range(max_turns):
        response, usage = call_model(conversation)
        for key in usage_totals:
            usage_totals[key] += usage.get(key, 0) or 0

        output_items = response.get("output", [])
        conversation.extend(output_items)
        function_calls = [item for item in output_items if item.get("type") == "function_call"]
        if not function_calls:
            continue

        for function_call in function_calls:
            result = executor.execute(
                {
                    "function": {
                        "name": function_call["name"],
                        "arguments": function_call["arguments"],
                    }
                }
            )
            conversation.append(
                {
                    "type": "function_call_output",
                    "call_id": function_call["call_id"],
                    "output": json.dumps(result),
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
        files_used=executor.files_used,
        commands_run=executor.commands_run,
        writes_made=executor.writes_made,
        tool_calls=executor.tool_calls,
    )


def call_model(input_items: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    response = requests.post(
        OPENAI_RESPONSES_URL,
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "instructions": SYSTEM_PROMPT,
            "input": input_items,
            "tools": RESPONSE_TOOLS,
            "tool_choice": "auto",
        },
        timeout=180,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"OpenAI proxy error {response.status_code}: {response.text}")
    payload = response.json()
    usage = payload.get("usage", {})
    return payload, {
        "prompt_tokens": usage.get("input_tokens", 0),
        "completion_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }
