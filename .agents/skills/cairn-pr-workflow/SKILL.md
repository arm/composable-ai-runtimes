---
name: cairn-pr-workflow
description: Mandatory for preparing, reviewing, committing, staging, pushing, or opening Cairn SDK branches and pull requests, including commit history, draft PRs, local validation checkpoints, and PR-readiness work.
---
<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

# Cairn PR Workflow

Follow these requirements for all Cairn SDK branch, commit, and pull-request work. This skill does not grant remote mutation authority.

## Safety

- Treat commit, push, PR creation, PR update, comment, and history-rewrite actions as separate permissions.
- An initial push or draft PR does not authorize later pushes. Keep subsequent changes local unless the user asks to update the remote.
- Stage only explicitly requested paths or hunks, report staged and unstaged state, and do not commit or push without separate permission.
- Never post or reply to PR comments unless explicitly requested. Return draft text, comment links, and short fixing commit hashes instead.

## Commits

- Use concise conventional-commit subjects and the repository's required sign-off.
- Keep commits atomic: each commit should do one thing. Keep a genuinely small change in one commit; for larger work, plan a few coherent reviewer-facing commits without targeting an arbitrary count.
- Keep implementation with its tests and required generated artifacts in the same commit. Put unrelated refactors, docs, or tooling in separate commits.
- Keep focused review fixes in separate commits so each comment's resolution remains traceable.

## PR title and description

- Follow `.github/PULL_REQUEST_TEMPLATE.md`. Use a concise conventional-commit title that describes the change; put the relevant issue or ticket reference in the template's ticket field, not the title.
- Keep `Background, Change and Impact` light and reviewer-focused: why, what, notable impact, compatibility, and deliberate non-goals.
- Do not repeat the commit list, implementation diary, routine CI output, or obvious diff details.
- `Steps to Validate the Change` MUST stay short: at most three brief, change-specific steps a reviewer can follow, with expected outcomes. For example: `Run <pipeline command> with <sample input>, stop it, and confirm that it exits without errors.` Replace placeholders with commands and inputs relevant to the change.
- If no manual validation is needed, say so explicitly rather than leaving the section empty. Do not add technical filler, command inventories, routine test/lint results, or invented validation.
- Report detailed validation results and unrelated environment blockers in the user handoff, not this section. Include a limitation here only when it requires reviewer action, in one short bullet within the same limit.
- Before creating or updating a PR, you MUST check its body against these requirements and remove excess validation detail.
- Agents may check checklist items when supported by evidence and authorized to create or update the PR body. The author remains responsible for the checklist.

## Draft and readiness

- Create PRs as drafts. Leave marking a PR ready for review to the author.
- Before recommending readiness, confirm intended test suites are collected and run in CI rather than unexpectedly filtered or skipped.
- Update documentation and READMEs only when explicitly requested. Otherwise, report relevant gaps and suggest updates without editing them.
- Do not poll CI after creating or updating a PR.

## Checklist verification

Before recommending that the author mark a PR ready for review, verify every
item against the current change. Report incomplete or uncertain items as
blockers and leave the readiness transition to the author.

Use the checklist in `.github/PULL_REQUEST_TEMPLATE.md` rather than a separate
list. Verify required coverage and passing tests, successful manual checks, and
documentation that matches the change under the applicable instructions, or
establish why an item is not applicable. Do not add or run tests or expand
documentation scope solely to check a box. An unavailable required environment
is a blocker, not a reason to mark an item not applicable.

- **Independent agent review:** Minor documentation-only changes may be exempt;
  record the reason when marking review not applicable. All PRs with larger
  changes require review by an independent agent or sub-agent. The implementing
  agent's self-review does not count. Retain the review result in the task handoff,
  address blocking findings, and obtain another review of substantive changes made
  afterward. If required review is unavailable, leave the item unchecked and keep
  the PR in draft.
- **Licensing:** Check whether dependencies, third-party assets, packaging, or
  publication changed. If affected, verify the required notices, SBOMs, and
  source records using `docs/licensing-guide.md`; otherwise mark not applicable.

Check conditional items only when supported by completion evidence or a genuine
not-applicable determination. Never treat skipped required work as not applicable.
Do not mark the independent-review item complete merely because review was
requested or scheduled. Report outstanding items without changing PR metadata
unless that update is authorized.

## Output

Report the branch/worktree and base, commit plan or created commits, staged versus unstaged state, local versus remote divergence, validation performed, draft PR state, excluded changes, and residual risks.
