---
name: update-docs
description: Reconcile repository documentation with the current branch by comparing it to the base branch and applying accurate updates to user-facing docs, developer READMEs, and necessary code comments. Use when documentation should be updated or refreshed after feature work, before review or merge, or after iterative development has caused drift.
---
<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

Reconcile documentation against the current repository state once implementation work on a branch has stabilized, and apply the necessary changes.

## Goal

- Make documentation describe the repository as it exists now
- Compare branch changes against the correct base branch rather than only looking at the most recent commit
- Keep each document coherent as a whole; do not treat docs as append-only changelogs
- Identify stale, duplicated, speculative, or obsolete documentation and update it or recommend removal
- Do not assume missing documentation must be created immediately; treat new documentation as a user decision when no suitable existing document already covers the area
- Apply updates to existing documentation surfaces and report what changed, or explicitly state that the docs already reflect the branch accurately

## Base branch resolution

Resolve the comparison base in this order:
1. If PR context is available, use the PR base branch and calculate the merge-base against that branch
2. Otherwise, if `refs/remotes/origin/HEAD` resolves locally, use the merge-base against the remote default branch it points to
3. Otherwise, try common integration branches in this order: `origin/main`, `main`
4. Use `@{upstream}` only when it clearly points to an integration branch rather than the remote copy of the current feature branch
5. Ask the user only if none of the above exist

If a candidate merge-base is `HEAD` or otherwise yields no committed branch delta, keep falling back instead of accepting that candidate as the base.

Use the committed branch base to understand the branch delta with:
- `git diff --name-status <base>...HEAD`

Inspect local in-progress edits separately with:
- `git diff --name-status --cached`
- `git diff --name-status`

Treat the committed branch state as the primary source of truth for reconciliation. Consider staged and unstaged changes only as local context for the current task, and exclude unrelated local WIP from the documentation plan.

## Reconciliation flow

1. Identify the changed subsystem(s) from the branch diff.
2. Read the changed implementation and the relevant docs for those areas.
3. Map documentation work to the audience and documentation surfaces defined in `AGENTS.md`.
4. If no suitable documentation surface already exists for part of the change, do not assume a new document should be created immediately; ask the user whether they want that documentation added now.
5. Update, rewrite, or remove stale content so each affected document tells the right story for the branch as a whole.
6. Report relevant documentation that requires a user decision or falls outside the task scope.

## Workflow

1. Read the relevant implementation files before touching docs.
2. Read each relevant existing document fully before editing it.
3. Cross-check documentation against code, compose files, proto/API contracts, examples, and tests that changed.
4. Decide whether each relevant document needs no change, an update, a rewrite, removal, or a user decision about adding new documentation.
5. Flag stale content such as:
   - renamed services, modules, paths, or commands
   - deleted or incomplete features described as available
   - examples that no longer match the code
   - duplicated explanations that now disagree
   - speculative TODO language presented as present behavior
6. Apply in-scope updates to existing documentation. If a document is mostly obsolete, prefer a substantial rewrite or remove it when the user has clearly authorized documentation reconciliation.

## Editing rules

- Do not blindly append a new bullet or paragraph to the end of an existing document.
- Prefer rewriting a section so the document remains readable without knowledge of the branch history.
- Keep user-facing docs implementation-accurate but approachable.
- Keep README content operational and developer-centered.
- Keep code comments sparse; if one is misleading, update or delete it.
- If the best documentation outcome would require creating a brand-new document or section hierarchy that does not already exist, ask the user before introducing it.
- If stale documentation sits outside the direct branch scope but is discovered during the reconciliation, mention it explicitly. Update it only when it is necessary to keep the branch docs coherent.

## Verification

- Confirm modified commands, paths, service names, API symbols, defaults, and examples against the current tree.
- Follow the documentation validation instructions in `AGENTS.md` for every changed surface.
- Report validation that was not available locally, including external site validation when applicable.
- State explicitly when hardware-dependent or environment-specific behavior could not be validated.

## Output contract

- Summarize the documentation files updated, rewritten, or removed and why.
- List any remaining documentation work that requires a user decision or falls outside the task scope.
- Report validation performed and any validation that was not available locally.
- If the relevant docs already accurately reflect the branch changes, state that explicitly.
- If no relevant docs are found, state that explicitly and do not treat that alone as a requirement to create new documentation.
