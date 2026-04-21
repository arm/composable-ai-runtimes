---
name: update-docs
description: Assess repository documentation against the current branch by comparing it to the base branch, then suggest which user-facing docs, developer READMEs, and necessary code comments should be updated, rewritten, removed, or optionally added.
---

This skill assesses documentation against the current repository state once implementation work on a branch has stabilised, then produces a concrete list of suggested documentation changes.

## Trigger

Use this skill when:
- the user asks to update or refresh documentation after feature work on a branch
- the user wants docs checked against the current implementation before review or merge
- documentation may have drifted during iterative development and now needs to match the branch state

## Goal

- Make documentation describe the repository as it exists now
- Compare branch changes against the correct base branch rather than only looking at the most recent commit
- Keep each document coherent as a whole; do not treat docs as append-only changelogs
- Identify stale, duplicated, speculative, or obsolete documentation and update it or recommend removal
- Do not assume missing documentation must be created immediately; treat new documentation as a user decision when no suitable existing document already covers the area
- Produce a clear list of suggested documentation targets, or explicitly state that the docs found already reflect the branch changes accurately

## Documentation surfaces

- `docs-website/**`: user-facing SDK documentation
- `README.md` files: developer and operator documentation
- code comments in touched areas: developer context only, and only when the comment is still justified

Prefer updating `docs-website/**` for user-visible behaviour, APIs, and workflows. Prefer `README.md` files for setup, development, and operational guidance. Avoid adding new code comments unless the code would otherwise be hard to follow.

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
3. Map documentation work by audience:
   - user-facing behaviour or API changes -> `docs-website/**`
   - developer workflow or operational changes -> relevant `README.md`
   - non-obvious local implementation detail -> code comments only if necessary
4. If no suitable documentation surface already exists for part of the change, do not assume a new document should be created immediately; ask the user whether they want that documentation added now.
5. Build a list of suggested documentation actions so each affected document would tell the right story for the branch as a whole.
6. Recommend rewrite or removal for stale content instead of suggesting isolated notes be stacked onto the end of an existing document.

## Workflow

1. Read the relevant implementation files before touching docs.
2. Read the existing document fully before suggesting or editing changes to it.
3. Cross-check documentation against code, compose files, proto/API contracts, examples, and tests that changed.
4. Decide whether each relevant document needs no change, an update, a rewrite, a removal recommendation, or a user decision about adding new documentation.
5. Flag stale content such as:
   - renamed services, modules, paths, or commands
   - deleted or incomplete features described as available
   - examples that no longer match the code
   - duplicated explanations that now disagree
   - speculative TODO language presented as present behaviour
6. If a document is mostly obsolete, prefer a substantial rewrite or recommend deletion rather than preserving dead sections.

## Editing rules

- Do not blindly append a new bullet or paragraph to the end of an existing document.
- Prefer rewriting a section so the document remains readable without knowledge of the branch history.
- Keep user-facing docs implementation-accurate but approachable.
- Keep README content operational and developer-centred.
- Keep code comments sparse; if one is misleading, update or delete it.
- If the best documentation outcome would require creating a brand-new document or section hierarchy that does not already exist, ask the user before introducing it.
- If stale documentation sits outside the direct branch scope but is discovered during the reconciliation, mention it explicitly. Update it only when it is necessary to keep the branch docs coherent.

## Verification

- Confirm modified commands, paths, service names, API symbols, defaults, and examples against the current tree.
- If the task also includes applying documentation changes, run the smallest relevant validation for the docs you changed:
  - `pnpm --dir docs-website install --frozen-lockfile` when editing `docs-website/**`
  - `pnpm --dir docs-website build` when editing `docs-website/**`
  - lighter Markdown or lint sanity checks when only README/comment changes were made
- State explicitly when hardware-dependent or environment-specific behaviour could not be validated.

## Output contract

- Return a flat numeric list of suggested documentation targets.
- For each suggestion, include the document or documentation surface, the reason it is relevant to the branch, and the suggested action such as `update`, `rewrite`, `remove`, or `ask whether to add new docs`.
- If the relevant docs already accurately reflect the branch changes, state that explicitly.
- If no relevant docs are found, state that explicitly and do not treat that alone as a requirement to create new documentation.
