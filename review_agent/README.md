# AI Code Review Agent

Reviews a pull request on **TFS / Azure DevOps Server** or **GitHub** (github.com and
GitHub Enterprise Server) against (a) its linked user story — a TFS work item or a GitHub
issue — and (b) the team's shared code-review checklists — spreadsheets and Word documents,
read from a working copy of the checklist repository — then posts structured feedback back
onto the pull request. Defects that span files (a signature changed and a caller not
updated) are reported as cross-file issues.

> **On GitHub?** `docs/github-setup.md` covers the tokens, the two secrets, the ~19-line
> caller workflow that onboards a repository, and local runs.

**A reviewer aid, not a merge gate.** It reasons over diff text and cannot verify runtime
behaviour, so a human always decides the merge. Defaults are preview mode and
non-blocking.

> **New here?** Work through the
> [end-to-end walkthrough](../specs/002-pr-review-walkthrough/walkthrough.md) — it
> creates a sample pull request with known defects and runs the agent against it, with
> every artifact supplied ready-made. About 30 minutes.

## What it finds

The headline case is a **false coverage claim**: the PR description says an acceptance
criterion is covered, and the diff does not implement it. Everything else is supporting
detail:

| Finding | Comments inline? | Blocks (only with `FAIL_ON_CONTRADICTION=true`) |
|---|---|---|
| False coverage claim | yes, if identified and located | yes |
| `possible_contradiction` | yes, if identified and located | yes |
| `code_issue` severity `high` | yes, if located | yes |
| `code_issue` medium / low | yes, if located | no |
| Cross-file issue `high` | yes, if located; always listed in the summary | yes |
| Cross-file issue medium / low | yes, if located; always listed in the summary | no |
| Checklist violation | yes, if identified and located | no |
| `appears_addressed` | no | no |
| `not_addressed` | **never** | **never** |

**Two conditions, not one.** A finding is posted inline only if it has a stable identity
*and* anchors to a changed line (`output_layer.build_inline_comments`). A finding with no
identity goes to the summary even when its line resolves, because a comment that cannot be
recognised on the next run would be re-posted forever.

`not_addressed` is neutral by design. A pull request routinely implements only part of a
story; treating that as a defect would make the agent noise on most pull requests.

## Quick start

```bash
python -m pip install -r review_agent/requirements.txt
cp review_agent/.env.example .env               # then fill it in
python -m review_agent --local --dry-run --pr ID   # prints, posts nothing
python -m review_agent --local --post --pr ID      # posts to the pull request
```

Run from the **repository root** — `.env` is read from the current working directory.

`.env` must stay out of git. It is in `.gitignore`; keep it there.

## CLI

```
python -m review_agent [--dry-run | --post] [--pr ID] [--local] [--quiet] [--log-llm] [--help] [--version]
```

| Flag | Effect |
|---|---|
| `--dry-run` | Print the feedback, post nothing. Overrides `DRY_RUN`. |
| `--post` | Post to the pull request. Overrides `DRY_RUN`. |
| `--pr ID` | Override `TFS_PR_ID` (or `GH_PR_NUMBER` on GitHub) for one run. |
| `--local` | Review with this working copy instead of the fetched agent source. |
| `--quiet` | Suppress the phase log. |
| `--log-llm` | Write every prompt and response to a log file for this run. Overrides `LLM_LOG`. |

No flag takes a credential, so none can leak into shell history or a process list.

### Three entry points, and which one to use

| Command | What reviews | Says which copy ran? |
|---|---|---|
| `python -m review_agent` | Clones `TFS_REPO_CODE_REVIEW_CodeReviewAgent` and re-executes the review inside the clone — the default, so a pipeline review always reflects committed logic | yes |
| `python -m review_agent --local` | This working copy. **Use this for a manual run** | yes |
| `python review_agent/main.py` | This working copy, with no provenance line at all | **no** |

`python -m review_agent.run` is the child's entry point; the bootstrap invokes it inside the
clone and you do not normally type it.

## Configuration

Precedence: **pipeline variable → `.env` → default.** A validation build therefore needs
no `.env` on the agent.

### Platform (feature 007)

| Variable | Default | Meaning |
|---|---|---|
| `PLATFORM` | `tfs` | `tfs` or `github`. Only the chosen platform's settings are required |
| `STORY_SOURCE` | the platform's own | `tfs` (work items), `github-issues` (issues the PR closes), or `none` (checklist-only, said so) |

### GitHub (`PLATFORM=github`)

| Variable | Default | Meaning |
|---|---|---|
| `GH_REPOSITORY` (alias `GITHUB_REPOSITORY`) | — | **Required.** `owner/name` |
| `GH_PR_NUMBER` | — | **Required** (or `--pr`) |
| `GH_TOKEN` (aliases `GITHUB_TOKEN`, `GIT_REPO_TOKEN`) | — | **Required.** Read token: Pull requests, Issues, Contents (read) |
| `GH_TOKEN_FOR_PR` | — | **Required to post.** Pull requests and Issues (write). A preview never builds a client holding it |
| `GH_API_URL` (alias `GITHUB_API_URL`) | `https://api.github.com` | GitHub Enterprise Server: `https://<host>/api/v3` |
| `GH_CHECKLIST_REPO` | the checklist settings below | `owner/name` of the checklist repository |
| `GH_CHECKLIST_TOKEN` | `GH_TOKEN` | Contents (read) on the checklist repository |
| `GH_AGENT_REPO` | — | `owner/name` of the agent, for the default (fetching) entry point. Not needed with `--local` |

### Always required on TFS

| Variable | Pipeline equivalent |
|---|---|
| `TFS_BASE_URL` | `System.TeamFoundationCollectionUri` |
| `TFS_PROJECT` | `System.TeamProject` |
| `TFS_REPO_CODE_SAMPLE` (alias: `TFS_REPO`) | `Build.Repository.Name` |
| `TFS_PR_ID` | `System.PullRequest.PullRequestId` |
| `LLM_PROVIDER` | `claude` \| `openai` \| `azure` \| `ollama` |
| `LLM_MODEL` | — |

### Authentication — one to read, a second to post

| Variable | Use |
|---|---|
| `SYSTEM_ACCESSTOKEN` | Pipeline runs → Bearer. **Preferred.** Needs "Allow scripts to access the OAuth token". |
| `TFS_PAT` | Manual runs → Basic. Needs **Code (read)**, plus **Work Items (read)** to judge story coverage. |
| `TFS_PAT_FOR_PR` | **Required to post.** Needs **Code (write)**. Without it, `--post` fails with `TFS_PAT_FOR_PR is required to post (omit --post for a dry run)` — a preview needs only the read credential. |

Exactly one of the first two supplies the read credential. `TFS_PAT_FOR_PR` is separate and
additional; it may hold the same PAT as `TFS_PAT` if that token has write scope.

A token without **Work Items (read)** does not fail the run — the story half is lost, the
summary says so, and the checklist review continues.

An **empty** `SYSTEM_ACCESSTOKEN` counts as absent — that is exactly what a job without
the OAuth-token setting exports, and treating it as present produces a baffling redirect
instead of a clear message.

### Optional

| Variable | Default | Meaning |
|---|---|---|
| `TFS_API_VERSION` | `6.0` | Try `5.0`, then `4.1`, on an older server. On the collection this project runs against, `6.0` returns 404 on every endpoint — **set `5.0`** |
| `TFS_REPO_CODE_REVIEW_CodeReviewAgent` | — | The agent's own repository, cloned by the default entry point. Not needed with `--local` |
| `CHECKLIST_MAX_CHARS` | `60000` | Budget for checklist rule text; lowest-ranked rules are dropped above it, and the count is reported |
| `TFS_REPO_CODE_REVIEW_CodeReviewChecklist` | — | **The checklist repository.** Three older names are still accepted: `...ChecklistT`, `CHECKLIST_REPO`, and the `_git/{name}` segment of `CHECKLIST_REPO_URL` |
| `CHECKLIST_PATH` | `/` | Read recursively from here |
| `CHECKLIST_FILE_PATTERN` | `*.xlsx,*.docx` | Comma-separated, matched against the filename. Set `*.md` for the plain-text path |
| `CHECKLIST_BRANCH` | the repository's own default | Set it only if you need a branch other than the default |
| `DRY_RUN` | `true` | `true` prints, `false` posts |
| `FAIL_ON_CONTRADICTION` | `false` | `true` → exit 1 on a blocking finding |
| `REVIEW_EXCLUDE_PATTERNS` | built-in | Globs never sent to the provider |
| `REVIEW_EXCLUDE_MODE` | `extend` | `extend` or `replace` the built-in list |
| `REVIEW_MAX_FILES` | `40` | Review bound |
| `REVIEW_MAX_DIFF_LINES` | `3000` | Review bound |
| `LLM_MAX_PROMPT_TOKENS` | `120000` | Budget for one call, whole prompt, estimated at 3 characters per token. A PR under it is one call; above it, it is split with an outline in every part and one extra synthesis call |
| `LLM_MAX_OUTPUT_TOKENS` | `8192` | The model's output limit (sent to Claude). Must be under half the prompt budget |
| `LLM_MAX_CHUNK_LINES` | unset | **Changed by 007**: was a 1200-line default; now an optional extra cap on changed lines per call |
| `LLM_PRICE_INPUT_PER_MTOK` / `LLM_PRICE_OUTPUT_PER_MTOK` | unset | Price per million tokens. With both set, every run prints its estimated cost |
| `LLM_PRICE_CURRENCY` | `USD` | Label for that cost |
| `LLM_LOG` | `false` | Write every prompt and response to a file. **Off by default** — see Security |
| `LLM_LOG_DIR` | `.llm-logs` | Where those files go. A relative path resolves against the directory you ran from, not the fetched clone |
| `LLM_LOG_KEEP` | `10` | How many of the agent's own logs survive. Older ones are deleted at the start of each run |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Review completed **or degraded**. The normal outcome, findings or not. |
| `1` | Blocking findings — only with `FAIL_ON_CONTRADICTION=true`. |
| `2` | Setup failure: configuration, credential, unreachable PR, or no permission to post. |

`0` covering both "reviewed fine" and "could not review" is deliberate: a provider outage
must not gate anyone's merge. What tells them apart is the summary discussion and the
phase log, not the exit code. `2` is reserved for failures that mean the review will
*never* work until someone changes a setting — which is exactly what should turn a build
red.

## Pipeline setup

`azure-pipelines.yml` at the repo root runs the agent as a validation build. On TFS a pull
request cannot trigger a pipeline from YAML, so wire it as a branch policy:

1. **Repos → Branches → `master` → Branch policies → Build Validation** → add this pipeline.
2. Enable **"Allow scripts to access the OAuth token"** on the job.
3. Grant the build service identity **Contribute to pull requests** on this repo.

Steps 2 and 3 are easy to miss and produce the same symptom: the build goes green and no
comment appears. Without them the agent reports a setup failure naming the missing
permission.

Keep `LLM_API_KEY` in a secret variable group (`ai-code-review`), never in the YAML.

### Comment status

Comments are posted as **active** threads, so they appear in the normal review flow. If
your team also enables the "all comments resolved before merge" policy, someone must
resolve them — including the summary on a clean review. That is a deliberate choice
(spec.md SC-009); leave that policy off to keep the review fully out of the merge path.

## How it works

```
config -> fetch (story, PR, changes, checklists) -> select -> prompt(s)
       -> provider -> validate -> reconcile with what is already posted
       -> print or post
```

| Module | Responsibility |
|---|---|
| `config.py` | The only module that reads the environment; secret registry and `emit` |
| `errors.py` | `SetupFailure` (exit 2) vs `DegradedReview` (exit 0) |
| `models.py` | Frozen dataclasses for every entity |
| `tfs_client.py` | **The only module that speaks TFS REST** |
| `checklist.py` | Obtain a working copy of the checklist repository; read every document in it into citable rules. Falls back to the plain-text path |
| `checklist_docs.py` | **The only module that knows what a `.xlsx` or `.docx` looks like** |
| `diff_builder.py` | Blobs → unified diff + the line map for anchoring |
| `selection.py` | Exclusion list, review bound, relevance ordering |
| `prompt_builder.py` | Assemble the prompt; chunk on file boundaries |
| `llm_adapter.py` | **The only module that knows a provider's wire format** |
| `parser.py` | Contract validation, one strict retry, false-claim derivation |
| `dedupe.py` | Fingerprints; recover prior feedback from the PR |
| `output_layer.py` | Render, print, post |
| `main.py` | CLI, orchestration, exit codes |

Three things are less obvious than they look:

- **Diffs are computed locally.** The `changes` endpoint returns change *entries*, not
  patch text, and no on-prem endpoint reliably returns unified diff across TFS versions.
  Computing it from two blobs also produces the line map that inline anchoring needs.
- **State lives on the pull request.** The agent is stateless; it recovers what it already
  said by reading its own threads back, keyed on the `ai-review:` marker in the comment
  text rather than the author id — because a manual run and a pipeline run post under
  different identities.
- **Each finding kind has its own identity**, and none of them is the provider's prose,
  which is regenerated every run. A checklist violation keys on its rule identifier, a
  coverage finding on the criterion's number within its story. A code issue has no natural
  identifier, so it keys on `severity@line` — which means a code issue whose line moves is
  a new comment. The other two kinds are immune to that shift.

## Security

- Every value comes from configuration. Nothing is hard-coded (enforced by a test).
- Every secret is registered and redacted from all output; no credential reaches stdout,
  logs, the prompt, or posted feedback (enforced by a test).
- TLS verification is never disabled. `truststore` binds `requests` to the OS trust store
  so a private internal CA validates; fallback is `REQUESTS_CA_BUNDLE`.
- Files matching the exclusion list — environment files, certificates, keys, credential
  stores — are never sent to the provider, and every skipped file is named in the report.
  This is a safety net against an accidental commit, **not** secret scanning: it matches
  on path only and will not spot a credential pasted into ordinary source.
- Reviewing sends story text, checklist text, the PR description, and non-excluded diff
  text to the configured provider. Where that provider is external, that exposure is
  accepted, or configure a self-hosted one via `LLM_BASE_URL`.
- **`LLM_LOG` writes the conversation to disk.** A log holds every prompt in full — the
  pull request's whole diff, the story, and the entire checklist corpus — plus every
  response. It is off by default for that reason. Every byte still goes through the same
  redaction as console output, so no credential reaches the file (enforced by a test), but
  the *source code* in it is real. `.llm-logs/` is gitignored; point `LLM_LOG_DIR`
  somewhere tracked and that protection is gone.
- Retention deletes only files matching the agent's own log naming, non-recursively, and
  never one newer than the running process. Other files in `LLM_LOG_DIR` are left alone
  however old they are (enforced by a test).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `missing required configuration: ...` | Incomplete `.env` | Set every listed variable |
| `SSLCertVerificationError` | Private CA not trusted by `certifi` | `pip install truststore`, or set `REQUESTS_CA_BUNDLE` |
| `authentication failed ... sign-in page` | Bad/expired credential | Reissue the PAT, or enable the OAuth-token setting |
| `api-version 6.0 rejected` | Older server | `TFS_API_VERSION=5.0`, then `4.1` |
| `not permitted to write ...` | Build identity cannot comment | Grant **Contribute to pull requests** |
| Build green, no comment | Preview mode | Set `DRY_RUN=false` |
| `no checklist repository is configured` | None of the four accepted names is set | Set `TFS_REPO_CODE_REVIEW_CodeReviewChecklist` |
| `no checklist repository named X was found` | Wrong name or branch | Check the name and `CHECKLIST_BRANCH` |
| `could not be read with this credential` | The repository exists; the token cannot see it | Grant Code (read) on that repository |
| `was reached, but no file matched` | The selection is wrong, not the repository | Check `CHECKLIST_FILE_PATTERN` and `CHECKLIST_PATH` |
| Story section says coverage was not assessed | No linked work item, or the token lacks Work Items (read) | The message says which |
| Exit 2, `not found` | Wrong repo or PR id | Check `TFS_REPO` and `TFS_PR_ID` |

## Tests

```bash
python -m pip install -r review_agent/requirements-dev.txt
python -m pytest tests
```

**Without `-q`.** `pytest.ini` already sets it, so adding it again runs at `-qq` and
suppresses the summary line — the run passes and prints no count.

No live network. The contract tests are the ones worth watching — they assert no secret
reaches output, no `verify=False` exists, preview mode issues no writes, and the module
boundaries hold. `not_addressed` routing is asserted by
`tests/unit/test_routing_not_addressed.py`.

## Worked examples

- **[The full reference and manual runbook](../specs/004-agent-docs-runbook/guide.md)** —
  the general case behind this README: numbered steps from a clean checkout to a posted
  review, every file and what owns it, the review traced stage by stage with its log lines,
  and what the agent will not do. Every claim anchored, and what is unverified says so.
- **[The checklist-document demonstration](../specs/003-checklist-repo-review-demo/demo.md)** —
  `.xlsx` and `.docx` checklists, a linked story judged criterion by criterion, and a
  second run that adds nothing. Its self-contained half runs with no server:
  `python -m tests.demo.run`.
- **[The markdown walkthrough](../specs/002-pr-review-walkthrough/walkthrough.md)** —
  the plain-text checklist path, verified end to end against a real pull request on
  2026-09-15. Still valid; not replaced by the above.
