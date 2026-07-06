# Codex PR Agent

The `Codex PR Agent` workflow lets trusted reviewers ask Codex for a focused,
read-only pass on a pull request by commenting with the repository alias:

```text
@cairn-codex review
@cairn-codex ask does this satisfy DEML-1234?
@cairn-codex does this update the docs that changed behavior requires?
```

The alias is parsed as comment text by GitHub Actions. It only behaves as a
normal GitHub mention if a matching GitHub user, bot, app, or team exists.

## Behavior

- Runs only on PR comments from `OWNER`, `MEMBER`, or `COLLABORATOR` authors.
- Can also be run manually from the Actions UI with `workflow_dispatch` after
  the workflow exists on the default branch.
- Reads the PR title, body, branch name, changed-file list, and first `DEML-####`
  Jira key it can find.
- Fetches Jira issue context when Jira secrets are configured.
- Checks out the PR merge ref with Git credentials disabled.
- Runs `openai/codex-action@v1` in read-only sandbox mode.
- Posts one PR comment with the Codex result.

`review` mode reports only P0/P1 findings. `ask` mode answers the reviewer
question directly. The first version does not push commits or submit formal
GitHub review decisions.

## Required Secrets

Configure these repository secrets before enabling the workflow:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`, for example the Arm OpenAI proxy provider URL for the
  region/account used by the generated key
- `JIRA_BASE_URL`, for example `https://jira.arm.com`
- `JIRA_USER`
- `JIRA_API_TOKEN`

If the Jira secrets are missing or Jira cannot be reached, the workflow still
runs and tells Codex that Jira context was unavailable.

## Local Validation

Validate the helper script with:

```bash
python3 -m unittest discover .github/scripts/tests
```

Run the normal repository validation before merging workflow changes:

```bash
prek validate-config
prek run --all-files --stage pre-push
```

## Demo Notes

GitHub runs `issue_comment` and `workflow_dispatch` workflows only when the
workflow file exists on the default branch. That means commenting
`@cairn-codex review` or using **Run workflow** may not work for a brand-new
workflow that exists only on a feature branch.

For a pre-merge team demo, use one of these temporary paths:

- Add a branch-only `pull_request` or `push` demo trigger and remove it before
  merging.
- Merge a minimal bootstrap workflow first, then demo the comment trigger in a
  follow-up PR.

After the workflow exists on the default branch, open the workflow in the
Actions UI, choose **Run workflow**, enter the PR number, and use a command such
as:

```text
@cairn-codex review
```
