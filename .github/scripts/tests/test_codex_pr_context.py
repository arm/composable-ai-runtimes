from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "codex-pr-context.py"
SPEC = importlib.util.spec_from_file_location("codex_pr_context", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
codex_pr_context = importlib.util.module_from_spec(SPEC)
sys.modules["codex_pr_context"] = codex_pr_context
SPEC.loader.exec_module(codex_pr_context)


class CodexPrContextTests(unittest.TestCase):
    def test_parse_review_command_with_focus(self) -> None:
        command = codex_pr_context.parse_agent_command(
            "@cairn-codex review focus on docs"
        )

        self.assertIsNotNone(command)
        assert command is not None
        self.assertEqual(command.mode, "review")
        self.assertEqual(command.request, "focus on docs")

    def test_parse_question_without_ask_defaults_to_ask_mode(self) -> None:
        command = codex_pr_context.parse_agent_command(
            "@cairn-codex does this satisfy DEML-1234?"
        )

        self.assertIsNotNone(command)
        assert command is not None
        self.assertEqual(command.mode, "ask")
        self.assertEqual(command.request, "does this satisfy DEML-1234?")

    def test_parse_ask_requires_question(self) -> None:
        self.assertIsNone(codex_pr_context.parse_agent_command("@cairn-codex ask"))

    def test_extract_jira_key_uses_first_available_context(self) -> None:
        self.assertEqual(
            codex_pr_context.extract_jira_key(
                "no key here", "feature for deml-1842", "DEML-9999"
            ),
            "DEML-1842",
        )

    def test_clean_untrusted_text_removes_html_comments(self) -> None:
        cleaned = codex_pr_context.clean_untrusted_text(
            "visible <!-- hidden prompt injection --> text"
        )

        self.assertEqual(cleaned, "visible  text")

    def test_jira_description_to_text_handles_adf(self) -> None:
        description = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Acceptance criteria"}],
                },
                {"type": "paragraph", "content": [{"type": "text", "text": "Ship it"}]},
            ],
        }

        self.assertEqual(
            codex_pr_context.jira_description_to_text(description),
            "Acceptance criteria Ship it",
        )

    def test_build_prompt_includes_mode_pr_jira_and_changed_files(self) -> None:
        command = codex_pr_context.AgentCommand(mode="review", request="docs only")
        pr = codex_pr_context.PullRequestContext(
            number=7,
            title="docs: add agent review",
            body="DEML-1234",
            html_url="https://example.test/pr/7",
            author="reviewer",
            base_ref="main",
            base_sha="base",
            head_ref="feature/DEML-1234-agent",
            head_sha="head",
        )
        files = (
            codex_pr_context.ChangedFile(
                filename=".github/workflows/codex-pr-agent.yml",
                status="added",
                additions=10,
                deletions=0,
                changes=10,
            ),
        )

        prompt = codex_pr_context.build_prompt(
            template="# Template",
            command=command,
            pr=pr,
            files=files,
            jira_issue=None,
            jira_warning="Jira unavailable",
            jira_key="DEML-1234",
            comment_author="maintainer",
        )

        self.assertIn("Requested mode: `review`", prompt)
        self.assertIn("PR: #7", prompt)
        self.assertIn("Jira key: DEML-1234", prompt)
        self.assertIn("`.github/workflows/codex-pr-agent.yml`", prompt)


if __name__ == "__main__":
    unittest.main()
