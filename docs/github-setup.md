# GitHub Setup

How to run the AI code review on GitHub (github.com or GitHub Enterprise Server): the tokens
and what each may do, the secrets to add, onboarding a repository, running it from your own
machine, and what the common failures mean.

TFS / Azure DevOps Server is unchanged; its runbook is `specs/004-agent-docs-runbook/guide.md`.
The whole flow, both platforms, is drawn in `docs/review-flow.puml`.

## 1. How it fits together

```text
your repository                          vijayclarion/codereviewagent
.github/workflows/ai-review.yml   --->   .github/workflows/code-review.yml   (reusable)
  on: pull_request                         checks out the agent, installs it, runs
  ~19 lines, two secrets                   python -m review_agent --local
                                                    |
                                                    v
                                 reads the PR, its linked issues, the checklist repo;
                                 asks the model; posts ONE review + ONE summary comment
```

The agent is central. A repository opts in with one small caller file. It never copies the
agent.

## 2. Tokens and permissions

| Token | Where it comes from | Used for | Permissions it needs |
|---|---|---|---|
| `GITHUB_TOKEN` (`github.token`) | GitHub, automatically, per job | reading the PR and its issues; posting the summary and the review | exactly the job's `permissions:` block: `contents: read`, `pull-requests: write`, `issues: write` |
| `AI_REVIEW_BOT_TOKEN` (secret) | a fine-grained PAT you create | cloning the **checklist** repository, and nothing else | **Contents: read** on the checklist repository only. Optional while that repository is public |
| `AI_REVIEW_LLM_API_KEY` (secret) | your model provider | calling the model | the provider's API access |

Why reads and posts use `GITHUB_TOKEN`: because then the `permissions:` block *is* the agent's
whole authority on your repository, and you can read that authority in the caller file.
`GITHUB_TOKEN` cannot read another private repository, which is the only reason a second
token exists.

## 3. Secrets to add

In **each repository that is reviewed**: *Settings → Secrets and variables → Actions → New
repository secret*.

| Name | Value | Required |
|---|---|---|
| `AI_REVIEW_LLM_API_KEY` | the model provider's API key | yes |
| `AI_REVIEW_BOT_TOKEN` | the fine-grained PAT from section 2 | only when the checklist repository is private |

Nothing else. The agent never sets a secret, and never prints one. Every token is registered
for redaction, and every posted comment is redacted before it is sent.

## 4. Onboarding a repository

Add `.github/workflows/ai-review.yml`:

```yaml
name: AI code review
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
permissions:
  contents: read
  pull-requests: write
  issues: write
jobs:
  review:
    uses: vijayclarion/codereviewagent/.github/workflows/code-review.yml@master
    with:
      model: claude-sonnet-5
      checklist_repo: vijayclarion/codereviewchecklist
      dry_run: false
    secrets:
      llm_api_key: ${{ secrets.AI_REVIEW_LLM_API_KEY }}
      review_bot_token: ${{ secrets.AI_REVIEW_BOT_TOKEN }}
```

Then add the secrets from section 3. That is the whole onboarding.

**Why the caller states its own `permissions:`.** A called workflow can only *narrow* the token
its caller grants, never widen it. Without this block, a repository whose default token is
read-only gives the agent no write access, and posting fails with HTTP 403.

**`dry_run` defaults to `true`.** Leave it out and every run prints the review in the job log
and posts nothing. That is a sensible first week. Set `dry_run: false` to post.

### Inputs

| Input | Default | Meaning |
|---|---|---|
| `model` | — (required) | the model identifier; not a secret |
| `checklist_repo` | — (required) | `owner/name` of the checklist repository (`.xlsx` / `.docx` rules) |
| `llm_provider` | `claude` | `claude`, `openai`, `azure`, `ollama` |
| `story_source` | `github-issues` | `github-issues` or `none` |
| `dry_run` | `true` | print only, post nothing |
| `llm_log` | `false` | upload the prompt/response log as an artifact (see section 6) |
| `fail_on_contradiction` | `false` | fail the job on a possible contradiction, a false coverage claim, or a high-severity finding |
| `agent_ref` | `master` | the agent version to run. Keep it equal to the ref after `@` in `uses:` |
| `agent_repository` | `vijayclarion/codereviewagent` | where the agent lives |

### What the workflow guarantees

- **Never `pull_request_target`.** Fork code never runs with your secrets.
- **Draft and fork pull requests are skipped**, and a `skipped` job says why. Marking a draft
  "ready for review" runs the review (`ready_for_review`).
- **A newer commit cancels the older review** of the same pull request (`concurrency`).
- **Exit codes pass through**: 0 (reviewed or degraded, green), 1 (blocking findings with
  `fail_on_contradiction`, red), 2 (setup failure, red).

### Writing stories as issues

The sample repository has an issue template `.github/ISSUE_TEMPLATE/user-story.md`. What the
agent reads:

- the issues the PR closes, from GitHub's own record and from `Closes #N` / `Fixes #N` /
  `Resolves #N` in the PR description (any case, deduplicated, this repository only);
- in each issue, the section under a heading **Acceptance criteria** (any level), as a
  checkbox or bullet list, one criterion per item, up to the next heading.

Each criterion gets a verdict: *appears addressed*, *not addressed* (neutral, no comment) or
*possible contradiction*. An issue without that section is still used, and the summary says
its criteria came from the description.

## 5. Running it from your own machine

From the agent repository, with a `.env` (gitignored, never committed):

```ini
PLATFORM=github
GH_REPOSITORY=vijayclarion/codereviewsample
GH_CHECKLIST_REPO=vijayclarion/codereviewchecklist
GIT_REPO_TOKEN=<fine-grained PAT: Contents, Issues, Pull requests (read)>
LLM_PROVIDER=claude
LLM_MODEL=claude-sonnet-5
LLM_API_KEY=<key>
```

```bash
python -m review_agent --local --pr 12                 # preview: prints, posts nothing
python -m review_agent --local --pr 12 --log-llm       # ... and writes .llm-logs/
GH_TOKEN_FOR_PR=<token with PRs + Issues write> python -m review_agent --local --pr 12 --post
```

`GIT_REPO_TOKEN` is accepted as the read token (so are `GH_TOKEN` and `GITHUB_TOKEN`).
Posting needs a **separate** token in `GH_TOKEN_FOR_PR`. A preview never constructs a client
holding it.

GitHub Enterprise Server: also set `GH_API_URL=https://<host>/api/v3`. The git host and the
GraphQL endpoint (`https://<host>/api/graphql`) are derived from it.

Every setting: `review_agent/README.md`.

### Cost and the token budget

- Each review's console output ends with `llm usage: input N · output M · cost X USD`, using
  the provider's own counts. Set `LLM_PRICE_INPUT_PER_MTOK` and `LLM_PRICE_OUTPUT_PER_MTOK`
  (price per million tokens) for the cost; without them the line says "cost not estimated".
- `LLM_MAX_PROMPT_TOKENS` (default 120,000) is the budget for one call. With the real
  checklist corpus, about 98,000 tokens (~290,000 characters) of diff fit in one call
  (measured, `specs/007-github-and-cross-file/validation.md`). Beyond that the PR is split.
  Every part sees an outline of the whole PR, and one extra **synthesis** call looks for
  defects that span files.

## 6. The prompt/response log contains source code

`llm_log: true` uploads `.llm-logs/` as the artifact `llm-log-pr-<number>`, kept **3 days**.
It holds every prompt (the whole reviewed diff, the checklist, the story) and every raw
response, with token counts per call. Secrets are redacted, but **source code is not**.
Anyone who can read the repository's Actions artifacts can read it. Turn it on to investigate
a review, then turn it off.

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Job never starts on a PR | caller missing, or the PR is a draft / from a fork | check the `skipped` job's message; mark ready for review |
| `GH_REPOSITORY must be owner/name` | a bare repository name | use `owner/name` |
| `authentication failed ... (HTTP 401) -> check GH_TOKEN` | token expired or wrong | renew it; locally check `GIT_REPO_TOKEN` / `GH_TOKEN` |
| `not permitted to write to ... (HTTP 403)` | the caller has no `permissions:` block, or an organization policy forbids write tokens | add the block from section 4; ask an org admin |
| `not found: .../pulls/N (HTTP 404) -> check GH_REPOSITORY and GH_PR_NUMBER` | wrong repository or number, or the token cannot see a private repository | check both, and the token's repository access |
| `could not obtain owner/checklists at ...` | the checklist repository is private and `AI_REVIEW_BOT_TOKEN` is missing or lacks Contents: read | add or fix the secret |
| Summary says "GitHub refused the inline anchor" | GitHub rejected the review (HTTP 422) because an anchor was outside its diff | nothing is lost: the findings are listed in a review comment instead. Report it if it repeats |
| `Story: not assessed - the credential cannot read work items (HTTP 403 ...)` | the token lacks Issues: read | grant it; the checklist half still ran |
| `Story source: #8 is a pull request, not an issue` | "Closes #8" names a PR | link the issue instead |
| `llm usage: ... partial — 2 of 3 calls reported usage` | one send failed and was retried before it reported anything | expected after a timeout; the totals cover what was reported |
| `Synthesis did not complete: ...` | the extra cross-file call failed or returned bad JSON | the per-part findings are complete; re-run to retry the synthesis |
| Second run posted nothing new | expected: findings already posted are recognised by their `ai-review:` markers | — |
| TFS: every call returns 404 | `TFS_API_VERSION` defaults to 6.0 | set `TFS_API_VERSION=5.0` on this server |
