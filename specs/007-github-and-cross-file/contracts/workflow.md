# Contract: GitHub Workflows

**Files**: `.github/workflows/code-review.yml` (agent repository, reusable),
`.github/workflows/ai-review.yml` (each consuming repository, caller)
**Research**: D17 | **Enforced by**: `tests/contract/test_workflow_contract.py` (PyYAML)

## Reusable workflow — `code-review.yml`

```yaml
on:
  workflow_call:
    inputs:
      model:                 {type: string,  required: true}
      llm_provider:          {type: string,  default: claude}
      story_source:          {type: string,  default: github-issues}
      checklist_repo:        {type: string,  required: true}     # owner/name
      dry_run:               {type: boolean, default: true}
      llm_log:               {type: boolean, default: false}
      fail_on_contradiction: {type: boolean, default: false}
      agent_repository:      {type: string,  default: vijayclarion/codereviewagent}
      agent_ref:             {type: string,  default: master}
    secrets:
      llm_api_key:      {required: true}
      review_bot_token: {required: false}
```

Job `review`:
- `if: github.event.pull_request.draft == false && github.event.pull_request.head.repo.full_name == github.repository`
- `permissions: {contents: read, pull-requests: write, issues: write}`
- `concurrency: {group: ai-review-${{ github.repository }}-${{ github.event.pull_request.number }}, cancel-in-progress: true}`
- `timeout-minutes: 15`
- Steps: checkout `agent_repository@agent_ref` (no credentials persisted) → `setup-python`
  3.12 → `pip install -r review_agent/requirements.txt` → `python -m review_agent --local`
  with the environment below → upload `.llm-logs/` when `always() && inputs.llm_log`,
  `retention-days: 3`, artifact name `llm-log-pr-<number>`.

Environment of the review step:

| Variable | Value |
|---|---|
| `PLATFORM` | `github` |
| `GH_API_URL` | `${{ github.api_url }}` (GitHub Enterprise Server works unchanged) |
| `GH_REPOSITORY` | `${{ github.repository }}` |
| `GH_PR_NUMBER` | `${{ github.event.pull_request.number }}` |
| `GH_TOKEN`, `GH_TOKEN_FOR_PR` | `${{ github.token }}` — bounded by `permissions:` |
| `GH_CHECKLIST_TOKEN` | `${{ secrets.review_bot_token || github.token }}` |
| `GH_CHECKLIST_REPO` | `${{ inputs.checklist_repo }}` |
| `STORY_SOURCE`, `LLM_PROVIDER`, `LLM_MODEL` | inputs |
| `LLM_API_KEY` | `${{ secrets.llm_api_key }}` |
| `DRY_RUN`, `LLM_LOG`, `FAIL_ON_CONTRADICTION` | inputs, as `true`/`false` |

Job `skipped`: inverse `if:`; one step that prints *"AI review skipped: draft pull request"*
or *"… pull request from a fork - secrets are not exposed to fork code"*.

Exit codes pass through: 0 green (including degraded), 1 red (blocking findings with
`fail_on_contradiction`), 2 red (setup failure).

## Caller — `ai-review.yml` (the whole onboarding, ≈ 15 lines)

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
      model: <model id>     # not a secret; the sample uses its .env LLM_MODEL value
      checklist_repo: vijayclarion/codereviewchecklist
      dry_run: false
    secrets:
      llm_api_key: ${{ secrets.AI_REVIEW_LLM_API_KEY }}
      review_bot_token: ${{ secrets.AI_REVIEW_BOT_TOKEN }}
```

A called workflow can only narrow the token permissions its caller grants, never widen them.
So the caller states the same three permissions itself. Without that block, a repository
whose default token is read-only would give the agent no write access, and posting would
fail with HTTP 403.

## Invariants the contract test asserts

1. No workflow file in either repository contains `pull_request_target`.
2. The reusable workflow's `on` is exactly `workflow_call`; `dry_run` defaults to `true`;
   `llm_log` and `fail_on_contradiction` default to `false`.
3. `permissions` is exactly the three entries above — no `write-all`, no `contents: write`.
4. The `review` job's `if` excludes drafts and forks; a `skipped` job states why.
5. `concurrency.cancel-in-progress` is `true` and the group includes the PR number.
6. The upload step has `retention-days` ≤ 7 and is conditional on `inputs.llm_log`.
7. No secret value and no `${{ secrets.* }}` appears in a `run:` script body — secrets
   reach the agent only through `env:`.
8. The caller is ≤ 20 non-blank lines and references `code-review.yml`.
