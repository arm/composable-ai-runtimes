#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Union, cast

JsonValue = Union[
    None, bool, int, float, str, list["JsonValue"], dict[str, "JsonValue"]
]
JsonObject = dict[str, JsonValue]

DEFAULT_ALIAS = "@cairn-codex"
TRUSTED_AUTHOR_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
JIRA_KEY_RE = re.compile(r"\bDEML-\d+\b", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
MAX_TEXT_CHARS = 8_000
MAX_COMMENT_CHARS = 2_000
MAX_CHANGED_FILES = 250


@dataclass(frozen=True)
class AgentCommand:
    mode: Literal["review", "ask"]
    request: str


@dataclass(frozen=True)
class PullRequestContext:
    number: int
    title: str
    body: str
    html_url: str
    author: str
    base_ref: str
    base_sha: str
    head_ref: str
    head_sha: str


@dataclass(frozen=True)
class ChangedFile:
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int


@dataclass(frozen=True)
class JiraIssue:
    key: str
    summary: str
    status: str
    issue_type: str
    labels: tuple[str, ...]
    components: tuple[str, ...]
    description: str


class GitHubClient:
    def __init__(self, *, api_url: str, repository: str, token: str) -> None:
        self._api_url = api_url.rstrip("/")
        self._repository = repository
        self._token = token

    def request_json(self, path: str) -> JsonValue:
        request = urllib.request.Request(
            f"{self._api_url}{path}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "cairn-codex-pr-agent",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return cast(JsonValue, json.loads(response.read().decode("utf-8")))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"GitHub API request failed ({exc.code}) for {path}: {details}"
            ) from exc

    @property
    def repository(self) -> str:
        return self._repository


def as_mapping(value: JsonValue) -> JsonObject:
    return value if isinstance(value, dict) else {}


def as_sequence(value: JsonValue) -> list[JsonValue]:
    return value if isinstance(value, list) else []


def string_value(value: JsonValue) -> str:
    return value if isinstance(value, str) else ""


def int_value(value: JsonValue) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def nested_string(mapping: JsonObject, *keys: str) -> str:
    current: JsonValue = mapping
    for key in keys:
        current = as_mapping(current).get(key)
    return string_value(current)


def clean_untrusted_text(value: str, *, limit: int = MAX_TEXT_CHARS) -> str:
    cleaned = HTML_COMMENT_RE.sub("", value).strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit].rstrip()}\n\n[truncated]"


def markdown_fence(value: str) -> str:
    safe_value = value.replace("```", "'''")
    return f"```text\n{safe_value}\n```"


def parse_agent_command(comment_body: str, alias: str = DEFAULT_ALIAS) -> AgentCommand | None:
    alias_match = re.search(re.escape(alias), comment_body, flags=re.IGNORECASE)
    if alias_match is None:
        return None

    tail = comment_body[alias_match.end() :].strip()
    tail = tail.lstrip(":,- \t").strip()
    if not tail:
        return None

    verb, _, remainder = tail.partition(" ")
    normalized_verb = verb.rstrip(":,").lower()
    remainder = remainder.strip()

    if normalized_verb == "review":
        return AgentCommand(mode="review", request=remainder)
    if normalized_verb == "ask":
        if not remainder:
            return None
        return AgentCommand(mode="ask", request=remainder)

    return AgentCommand(mode="ask", request=tail)


def extract_jira_key(*texts: str) -> str | None:
    for text in texts:
        match = JIRA_KEY_RE.search(text)
        if match is not None:
            return match.group(0).upper()
    return None


def read_event(path: Path) -> JsonObject:
    with path.open(encoding="utf-8") as event_file:
        return as_mapping(cast(JsonValue, json.load(event_file)))


def fetch_pull_request(client: GitHubClient, number: int) -> PullRequestContext:
    payload = as_mapping(
        client.request_json(f"/repos/{client.repository}/pulls/{number}")
    )
    head = as_mapping(payload.get("head"))
    base = as_mapping(payload.get("base"))
    user = as_mapping(payload.get("user"))

    return PullRequestContext(
        number=number,
        title=string_value(payload.get("title")),
        body=string_value(payload.get("body")),
        html_url=string_value(payload.get("html_url")),
        author=string_value(user.get("login")),
        base_ref=string_value(base.get("ref")),
        base_sha=string_value(base.get("sha")),
        head_ref=string_value(head.get("ref")),
        head_sha=string_value(head.get("sha")),
    )


def fetch_changed_files(client: GitHubClient, number: int) -> tuple[ChangedFile, ...]:
    files: list[ChangedFile] = []
    page = 1
    while len(files) < MAX_CHANGED_FILES:
        payload = client.request_json(
            f"/repos/{client.repository}/pulls/{number}/files?per_page=100&page={page}"
        )
        page_items = as_sequence(payload)
        if not page_items:
            break
        for item in page_items:
            file_payload = as_mapping(item)
            files.append(
                ChangedFile(
                    filename=string_value(file_payload.get("filename")),
                    status=string_value(file_payload.get("status")),
                    additions=int_value(file_payload.get("additions")),
                    deletions=int_value(file_payload.get("deletions")),
                    changes=int_value(file_payload.get("changes")),
                )
            )
            if len(files) >= MAX_CHANGED_FILES:
                break
        if len(page_items) < 100:
            break
        page += 1
    return tuple(files)


def collect_jira_text(value: JsonValue, pieces: list[str]) -> None:
    if isinstance(value, str):
        pieces.append(value)
        return
    if isinstance(value, list):
        for item in value:
            collect_jira_text(item, pieces)
        return
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str):
            pieces.append(text)
        for key in ("content", "children"):
            collect_jira_text(value.get(key), pieces)


def jira_description_to_text(value: JsonValue) -> str:
    pieces: list[str] = []
    collect_jira_text(value, pieces)
    return clean_untrusted_text(" ".join(piece.strip() for piece in pieces if piece.strip()))


def fetch_jira_issue(
    *,
    key: str,
    base_url: str,
    user: str,
    token: str,
) -> tuple[JiraIssue | None, str | None]:
    if not base_url or not user or not token:
        return None, "Jira credentials are not configured for this workflow run."

    credentials = base64.b64encode(f"{user}:{token}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/rest/api/2/issue/{key}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {credentials}",
            "User-Agent": "cairn-codex-pr-agent",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = as_mapping(cast(JsonValue, json.loads(response.read().decode("utf-8"))))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        return None, f"Jira request failed ({exc.code}) for {key}: {details}"
    except urllib.error.URLError as exc:
        return None, f"Jira request failed for {key}: {exc.reason}"

    fields = as_mapping(payload.get("fields"))
    raw_labels = (string_value(item) for item in as_sequence(fields.get("labels")))
    labels = tuple(label for label in raw_labels if label)
    components = tuple(
        nested_string(as_mapping(item), "name")
        for item in as_sequence(fields.get("components"))
        if nested_string(as_mapping(item), "name")
    )

    return (
        JiraIssue(
            key=key,
            summary=string_value(fields.get("summary")),
            status=nested_string(fields, "status", "name"),
            issue_type=nested_string(fields, "issuetype", "name"),
            labels=labels,
            components=components,
            description=jira_description_to_text(fields.get("description")),
        ),
        None,
    )


def changed_files_markdown(files: tuple[ChangedFile, ...]) -> str:
    if not files:
        return "- No changed files were returned by the GitHub API."

    lines = [
        f"- {file.status or 'unknown'} `{file.filename}` "
        f"(+{file.additions}/-{file.deletions}, {file.changes} changes)"
        for file in files
    ]
    if len(files) >= MAX_CHANGED_FILES:
        lines.append(f"- Changed file list truncated at {MAX_CHANGED_FILES} files.")
    return "\n".join(lines)


def jira_markdown(issue: JiraIssue | None, warning: str | None, key: str | None) -> str:
    if issue is None:
        key_line = key or "No DEML Jira key found."
        warning_line = warning or "Jira issue details were not fetched."
        return f"Jira key: {key_line}\n\nJira context warning: {warning_line}"

    labels = ", ".join(issue.labels) if issue.labels else "none"
    components = ", ".join(issue.components) if issue.components else "none"
    description = issue.description or "No Jira description returned."
    return "\n".join(
        [
            f"Jira key: {issue.key}",
            f"Summary: {issue.summary}",
            f"Status: {issue.status}",
            f"Issue type: {issue.issue_type}",
            f"Labels: {labels}",
            f"Components: {components}",
            "",
            "Description:",
            markdown_fence(description),
        ]
    )


def build_prompt(
    *,
    template: str,
    command: AgentCommand,
    pr: PullRequestContext,
    files: tuple[ChangedFile, ...],
    jira_issue: JiraIssue | None,
    jira_warning: str | None,
    jira_key: str | None,
    comment_author: str,
) -> str:
    request = command.request or "No additional focus was provided."
    return "\n\n".join(
        [
            template.strip(),
            "## Runtime Context",
            f"Requested mode: `{command.mode}`",
            f"Reviewer comment request from `{comment_author}`:",
            markdown_fence(clean_untrusted_text(request, limit=MAX_COMMENT_CHARS)),
            "## Pull Request",
            "\n".join(
                [
                    f"PR: #{pr.number}",
                    f"URL: {pr.html_url}",
                    f"Author: {pr.author}",
                    f"Title: {pr.title}",
                    f"Base: {pr.base_ref} ({pr.base_sha})",
                    f"Head: {pr.head_ref} ({pr.head_sha})",
                    "",
                    "PR body:",
                    markdown_fence(clean_untrusted_text(pr.body or "No PR body provided.")),
                ]
            ),
            "## Jira Context",
            jira_markdown(jira_issue, jira_warning, jira_key),
            "## Changed Files",
            changed_files_markdown(files),
            "## Local Review Hints",
            "\n".join(
                [
                    "- Inspect the checked-out PR merge ref and use `git diff` or "
                    "file reads as needed.",
                    "- Keep this workflow separate from existing lint, compose, "
                    "camera smoke, and contract workflows.",
                    "- Treat documentation reconciliation as required when behavior, "
                    "commands, APIs, or workflows changed.",
                ]
            ),
        ]
    )


def write_github_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as output_file:
        output_file.write(f"{name}<<__CODEX_PR_AGENT__\n{value}\n__CODEX_PR_AGENT__\n")


def mark_skipped(reason: str) -> None:
    write_github_output("should_run", "false")
    write_github_output("skip_reason", reason)
    print(reason)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Codex PR-agent prompt.")
    parser.add_argument("--event-path", default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--alias", default=os.environ.get("CODEX_AGENT_ALIAS", DEFAULT_ALIAS))
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--comment-body")
    parser.add_argument("--comment-author", default=os.environ.get("GITHUB_ACTOR", ""))
    parser.add_argument("--author-association")
    parser.add_argument(
        "--prompt-template",
        default=str(Path(__file__).resolve().parents[1] / "codex/prompts/pr-agent.md"),
    )
    parser.add_argument(
        "--github-api-url",
        default=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
    )
    parser.add_argument("--github-repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN", ""))
    parser.add_argument("--jira-base-url", default=os.environ.get("JIRA_BASE_URL", ""))
    parser.add_argument("--jira-user", default=os.environ.get("JIRA_USER", ""))
    parser.add_argument("--jira-token", default=os.environ.get("JIRA_API_TOKEN", ""))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.pr_number is not None:
        number = args.pr_number
        comment_body = args.comment_body or f"{args.alias} review"
        comment_author = args.comment_author
        author_association = (args.author_association or "OWNER").upper()
    else:
        if not args.event_path:
            mark_skipped("GITHUB_EVENT_PATH is not set.")
            return

        event = read_event(Path(args.event_path))
        issue = as_mapping(event.get("issue"))
        if not as_mapping(issue.get("pull_request")):
            mark_skipped("Comment is not on a pull request.")
            return

        comment = as_mapping(event.get("comment"))
        comment_body = string_value(comment.get("body"))
        comment_author = string_value(as_mapping(comment.get("user")).get("login"))
        author_association = string_value(comment.get("author_association")).upper()
        number = int_value(issue.get("number"))

    command = parse_agent_command(comment_body, alias=args.alias)
    if command is None:
        mark_skipped(f"Comment does not contain a supported {args.alias} command.")
        return

    if author_association not in TRUSTED_AUTHOR_ASSOCIATIONS:
        mark_skipped(f"Comment author association is not trusted: {author_association}")
        return

    if not args.github_repository or not args.github_token:
        raise RuntimeError("GITHUB_REPOSITORY and GITHUB_TOKEN are required.")

    if number == 0:
        raise RuntimeError("Could not determine pull request number from event payload.")

    client = GitHubClient(
        api_url=args.github_api_url,
        repository=args.github_repository,
        token=args.github_token,
    )
    pr = fetch_pull_request(client, number)
    files = fetch_changed_files(client, number)
    jira_key = extract_jira_key(comment_body, pr.title, pr.body, pr.head_ref)
    jira_issue: JiraIssue | None = None
    jira_warning: str | None = None
    if jira_key is not None:
        jira_issue, jira_warning = fetch_jira_issue(
            key=jira_key,
            base_url=args.jira_base_url,
            user=args.jira_user,
            token=args.jira_token,
        )
    else:
        jira_warning = (
            "No DEML Jira key was found in the comment, PR title, PR body, "
            "or branch name."
        )

    template = Path(args.prompt_template).read_text(encoding="utf-8")
    prompt = build_prompt(
        template=template,
        command=command,
        pr=pr,
        files=files,
        jira_issue=jira_issue,
        jira_warning=jira_warning,
        jira_key=jira_key,
        comment_author=comment_author,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(prompt, encoding="utf-8")

    write_github_output("should_run", "true")
    write_github_output("mode", command.mode)
    write_github_output("jira_key", jira_key or "")
    write_github_output("prompt_path", str(output_path))
    print(f"Prepared Codex {command.mode} prompt for PR #{pr.number}.")


if __name__ == "__main__":
    main()
