---
name: review-docs
description: Review repository documentation against the current implementation, commands, examples, APIs, and limitations, then report pedantic findings with file references instead of performing routine branch documentation updates.
---
<!---
SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
SPDX-License-Identifier: Apache-2.0
--->

This skill performs a pedantic documentation audit against the current repository state.

## Trigger

Use this skill when:
- the user asks for a documentation review or audit
- the user wants to know whether the docs accurately describe the implementation
- you are checking documentation quality on a stable branch, especially `main`
- you need findings and risks before deciding what documentation to edit

## Goal

- Find mismatches between documentation and the codebase
- Be precise about wording that overstates support, hides limitations, or describes outdated behavior
- Separate user-facing documentation issues from developer-facing documentation issues
- Recommend targeted fixes, rewrites, or removals before editing anything broad

## Documentation surfaces

- `docs/**`: repository-wide guidance, plans, and reference documentation
- `README.md` files: developer and operator documentation
- code comments in touched or reviewed areas: developer context only, and only when the comment is still justified

Review each document in the context it serves. User docs should explain the current SDK behavior clearly. READMEs should describe current developer and operator workflows. Code comments should be sparse and accurate.

## Review scope

1. Start from the user request:
   - focused audit of a subsystem, path, or recent change
   - broad repository audit when no narrower scope is given
2. Read the relevant implementation before judging the docs.
3. Compare documentation against:
   - code and public APIs
   - compose files and operational commands
   - examples, tutorials, and sample code
   - maturity statements, limitations, and caveats
4. Be alert for stale content such as:
   - renamed services, modules, paths, or commands
   - removed or partial features documented as complete
   - examples that no longer run as written
   - duplicated sections that disagree
   - TODO or aspirational wording presented as current behavior

## Review rules

- Findings come first.
- Order findings by severity.
- Include file references for both the problematic documentation and the supporting implementation where useful.
- Be pedantic about factual accuracy, but distinguish hard mismatches from style or clarity improvements.
- Do not perform broad documentation edits unless the user explicitly asks after the review.
- If a document is mostly obsolete, recommend rewrite or removal rather than incremental patching.

## Verification

- Confirm claims against the current tree rather than assumptions.
- When a command, API name, path, or example is called out as wrong, identify what the repository currently shows instead.
- State explicitly when hardware-dependent or environment-specific behavior could not be validated.

## Output contract

- Provide findings first, ordered by severity with file references.
- Follow with brief coverage notes, open questions, and recommended fixes or removals.
- State explicitly if no documentation issues were found in the reviewed scope.
