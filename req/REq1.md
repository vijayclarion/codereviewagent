# Context

## Repositories
Repository URLs and credentials are in `.env`. Read values from there.
NEVER print, log, echo, or commit any token or secret value. Refer to variables by NAME only.

| Variable | Repository | Purpose |
|---|---|---|
| GIT_REPO_CODE_REVIEW_CodeReviewAgent | Code Review Agent | The central agent you will modify. Currently TFS / Azure DevOps Server only. |
| GIT_REPO_CODE_SAMPLE | Code Sample | Application repo used to test the agent end-to-end on real PRs. |
| GIT_REPO_CODE_REVIEW_CodeReviewChecklist | Checklist | Organization checklists in .xlsx and .docx, used as review rules. |

## What the agent does today
For one pull request it fetches the PR and its linked user stories, reads the
checklist documents into citable rules, computes a unified diff, sends
story + checklist + diff to an LLM, validates the JSON response, and posts inline
comments plus a summary on the PR (DRY_RUN=true by default only prints).

## Before writing any code
1. Read `CLAUDE.md`, `review_agent/README.md`, `docs/developer-guide.md`, `specs/`, and `tests/`.
2. Note the existing principles and keep them:
   - Single-responsibility boundaries: only `tfs_client.py` speaks TFS REST, only
     `llm_adapter.py` speaks provider APIs, only `source_fetch.py` runs git, only
     `config.py` reads the environment. These are enforced by
     `tests/contract/test_import_boundaries.py`.
   - Secret redaction on all output and logs.
   - Exit codes: 0 = ok or degraded, 1 = blocking findings, 2 = setup failure.
   - DRY_RUN defaults to true.
3. Follow the repo's Spec Kit process: create `specs/007-github-and-cross-file/` with
   spec, plan, and tasks before implementing.
4. Summarize your understanding and plan, then proceed.

# Tasks

## T1. Support both TFS and GitHub (platform abstraction)
- Define a `PlatformClient` protocol with the operations the pipeline needs:
  get PR, list changed files, get file content at a commit, get head/base commits,
  list prior agent comments, post inline comments, create/update summary comment.
- Keep `tfs_client.py` as the TFS implementation (no behaviour change).
- Add `github_client.py` as the GitHub implementation (REST + GraphQL where needed):
  - Base commit = merge-base from the compare API; head = PR head SHA.
  - Post all inline comments as ONE review (`POST /pulls/{n}/reviews`, `event: COMMENT`).
  - Summary = one issue comment, updated in place on re-runs (dedupe via the
    existing `ai-review:` marker).
  - Support github.com and GitHub Enterprise Server via `GH_API_URL`.
- Select the platform with `PLATFORM=tfs|github` in config.
- Update import-boundary tests: only `github_client.py` may call the GitHub API.

Acceptance: the existing TFS test suite passes unchanged; an equivalent GitHub test
suite passes using fakes; a dry run against a real PR works on both platforms.

## T2. User stories from GitHub Issues
- Add a story source selected by `STORY_SOURCE=tfs|github-issues|none`.
- Find linked issues from GraphQL `closingIssuesReferences` AND from
  `Closes|Fixes|Resolves #N` in the PR body (deduplicated).
- Parse acceptance criteria from an `## Acceptance criteria` section of the issue body
  (checkbox list or bullet list). Map into the existing `WorkItem` model.
- Add an issue template `.github/ISSUE_TEMPLATE/user-story.md` to GIT_REPO_CODE_SAMPLE
  with Description and Acceptance criteria sections.

Acceptance: a PR linked to an issue gets per-criterion verdicts
(appears_addressed / not_addressed / possible_contradiction), same as TFS.

## T3. Cross-file and integration review
Problem: diffs are split into chunks of `LLM_MAX_CHUNK_LINES`, and each LLM call sees
only its own files, so cross-file problems are missed.
Implement, in this order:
1. Token-based chunk budget (`LLM_MAX_PROMPT_TOKENS`, default 120000) instead of
   line count, so most PRs are reviewed in a single call.
2. PR outline in every chunk: all changed files, change type, line counts, which
   part reviews them, and added/removed declarations (class, interface, method
   signatures) extracted from the diff without an LLM call.
3. Dependency-aware chunking: keep files that reference each other (shared type
   names, interface/implementation, same base name, source + test) in the same chunk.
4. Oversized single files: split on hunk boundaries and prepend a file skeleton
   (class, fields, method signatures) to each part.
5. Final synthesis pass (one extra LLM call when there was more than one chunk):
   input = merged findings + chunk change notes + PR outline + acceptance criteria;
   output = one coherent summary, final criterion verdicts, and `cross_file_issues`.
Add a `cross_file_issues` section to the JSON contract and the PR summary. Examples
to detect: changed signature with callers not updated, interface/implementation
mismatch, new dependency not registered (DI), new config key not added to config
files, model change without migration, tests not updated for changed behaviour.

Acceptance: a test PR where `ICartService` changes a signature and `CartController`
is not updated produces a cross-file finding, including when the two files land in
different chunks.

## T4. Detailed prompt/response logging
`llm_log.py` already exists (`LLM_LOG=true`). Verify and extend; do not rebuild:
- Cover every call: review chunks, retries, and the synthesis pass, on both platforms.
- Record per call: timestamp, provider, model, chunk id, prompt, raw response,
  input/output token counts from the provider response (not estimates), latency.
- Add a per-run total of tokens and estimated cost to the log and the console.
- Keep redaction of all secrets. Logging must never crash a review.
- In the GitHub workflow, expose `llm_log` as an input (default false). If enabled,
  upload the log as a short-retention artifact, and document that it contains source code.

## T5. GitHub workflow: central agent, reusable by any repo
The agent is central and will later be used by many repositories. So:
- In GIT_REPO_CODE_REVIEW_CodeReviewAgent, add a reusable workflow
  `.github/workflows/code-review.yml` (`on: workflow_call`) that checks out the
  agent, installs dependencies, and runs `python -m review_agent --local`.
  Inputs: model, story_source, checklist_repo, dry_run, llm_log, fail_on_contradiction.
  Secrets: llm_api_key, review_bot_token.
- In GIT_REPO_CODE_SAMPLE, add a thin caller workflow `.github/workflows/ai-review.yml`
  triggered on `pull_request` (opened, synchronize, reopened, ready_for_review)
  that calls the central workflow and reviews against
  GIT_REPO_CODE_REVIEW_CodeReviewChecklist.
- Permissions: least privilege (`contents: read`, `pull-requests: write`, `issues: write`).
- Skip draft PRs and fork PRs. Do NOT use `pull_request_target`.
- Use concurrency to cancel a review when a newer commit arrives.
- Onboarding another repo must take only the ~15-line caller file plus secrets.

## T6. Documentation
1. `docs/review-flow.puml`: PlantUML activity diagram of the full flow, step by step,
   with swimlanes (Developer, GitHub/TFS, Workflow, Agent, LLM). Include both platform
   branches, chunking + synthesis, retry, degraded paths, dedupe, and DRY_RUN.
   Attach notes with a concrete worked example: issue #7 "Add item to cart" with
   3 acceptance criteria → PR #12 changing 4 files → 2 chunks → findings → posted
   comments. Validate it renders (run plantuml if available).
2. `docs/code-structure.md`: repository tree, then for EVERY file: purpose,
   responsibility, main functions/classes, inputs/outputs, depends on, called by.
   Also cover tests/, specs/, and config files.
3. `docs/github-setup.md`: tokens and permissions, secrets, onboarding a new repo,
   local run steps, troubleshooting.
4. Update `README.md` and `CLAUDE.md` with the new configuration variables.

## T7. Set up the repositories
- Clone all three repositories using the URLs in `.env`.
- Commit work on a feature branch in each repo and open PRs; do not push to main.
- In GIT_REPO_CODE_SAMPLE: add the caller workflow, the issue template, one sample
  issue with acceptance criteria, and one demo PR linked to it (include one
  deliberate cross-file defect and one checklist violation for testing).
- Do not set secret values. List exactly which secrets I must add, where, and with
  which permissions.
- Ensure `.env` is in `.gitignore` in every repo and that no secret appears in git history
  of your changes.

# Constraints
- Do not break TFS. All existing tests must pass; add tests for every new module
  (unit, contract, integration with fakes).
- Do not add runtime dependencies unless essential; justify any you add.
- Keep DRY_RUN=true as the default.
- If a required credential or permission is missing, stop and tell me; do not work around it.
- LLM model and key will be configurable in .env file 

# Definition of done
- [ ] All tests pass (`pytest`), including new contract tests.
- [ ] Dry run works on a TFS PR and a GitHub PR.
- [ ] Demo PR in GIT_REPO_CODE_SAMPLE receives inline comments, a summary,
      acceptance criteria verdicts, and the deliberate cross-file defect is found.
- [ ] Re-running the review does not duplicate comments.
- [ ] LLM log shows every prompt/response with real token counts.
- [ ] docs/review-flow.puml, docs/code-structure.md, docs/github-setup.md exist and are accurate.

# Report back
At the end, give: a summary of changes per repo, PR links, test results, the list of
secrets I must configure, any assumptions you made, and known limitations.