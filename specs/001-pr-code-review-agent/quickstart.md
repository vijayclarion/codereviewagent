# Quickstart: PR Code Review Agent (Local Mode)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-15

> **Part 1 is superseded — kept for history.** The three corrections it asks for were
> applied and gap G5 is closed: `.env` now carries `LLM_PROVIDER`, a model identifier that
> exists, and a working key. The current setup path is
> [`specs/004-agent-docs-runbook/guide.md`](../004-agent-docs-runbook/guide.md), which also
> carries what this document could not know — the second token `--post` requires, the
> working-directory precondition, and the API version this collection needs. Part 2 is
> unaffected.

Two audiences. Part 1 gets an operator running against a real pull request. Part 2 is the US4 sample runbook satisfying FR-025 and FR-026.

> **Read this first.** The agent **cannot start as currently configured** — `.env` is missing `LLM_PROVIDER`, which `config.py` requires, and `LLM_MODEL` names a model that does not exist. Part 1 step 2 fixes both. Until then every run fails with `configuration is incomplete or invalid`.

---

## Part 1 — Operator setup

### 1. Install

```bash
python -m pip install -r review_agent/requirements.txt
python -m pip install -r review_agent/requirements-dev.txt   # to run the tests
```

Python 3.13 is present on this machine; the code needs no version-specific features.

### 2. Fix the configuration (G5 — required)

`.env` already exists and holds live credentials. **Do not regenerate it** — apply these three corrections by hand.

| Change | From | To | Why |
|---|---|---|---|
| **Add** `LLM_PROVIDER` | *(absent)* | `claude` | `config.load_config` requires it unconditionally. Without it the agent never reaches the provider. |
| **Correct** `LLM_MODEL` | `claude-sonnet-4-6` | `claude-sonnet-5` | Not a current model identifier. The adapter passes it straight through and a 404 surfaces as "no such model or endpoint" — a misleading cause. |
| **Add** `TFS_PR_ID` | *(absent)* | the PR to review | Or pass `--pr ID` per run. |

Current Claude model identifiers: `claude-opus-5`, `claude-sonnet-5`, `claude-fable-5-1`, `claude-haiku-4-5-20251001`. Use `claude-sonnet-5` for the default balance; `claude-opus-5` where review quality matters more than throughput.

The variables already present and correct: `TFS_BASE_URL`, `TFS_PROJECT`, `TFS_PAT`, `TFS_PAT_FOR_PR`, `TFS_REPO_CODE_SAMPLE`, `TFS_REPO_CODE_REVIEW_CodeReviewChecklistT`, `TFS_REPO_CODE_REVIEW_CodeReviewAgent`, `LLM_API_KEY`.

**`.env` is gitignored. Keep it that way.** It holds two PATs and a provider key.

### 3. Verify before spending a provider call

```bash
python -m pytest tests -q          # expect 409 passing, no network
python review_agent/main.py --help
```

### 4. Preview a real review

```bash
python review_agent/main.py --dry-run --pr 42
```

Preview is the default at every level, so this cannot write to the pull request — the run never constructs a client holding the posting credential.

### 5. Post

```bash
python review_agent/main.py --post --pr 42
```

Requires `TFS_PAT_FOR_PR` with **Code (read & write)**.

### Reading the exit code

| Code | Meaning | Do |
|---|---|---|
| `0` | Reviewed | Read the findings |
| `1` | Blocking findings, with `FAIL_ON_CONTRADICTION=true` | Read the findings |
| `2` | Setup failure | Change a setting — it will never work until you do |
| `3` | Degraded manual run | Nothing is broken here; try again |

### When it does not work

| Symptom | Cause | Fix |
|---|---|---|
| `configuration is incomplete or invalid: LLM_PROVIDER is required` | Step 2 not applied | Add `LLM_PROVIDER=claude` |
| `the AI provider has no such model or endpoint (HTTP 404)` | Stale `LLM_MODEL` | Set `claude-sonnet-5` |
| `SSLCertVerificationError` | Private CA not in `certifi` | `pip install truststore`, or set `REQUESTS_CA_BUNDLE` |
| `authentication failed … sign-in page` | Bad or expired PAT | Reissue it |
| `api-version 6.0 rejected` | Older TFS | `TFS_API_VERSION=5.0`, then `4.1` |
| `not permitted to write …` | PAT lacks write scope | Grant **Code (read & write)** |
| `checklist source unavailable`, review continues | **Expected until G1 lands** | See below |
| Ran fine, no comment appeared | Preview mode | Use `--post` |

**About that checklist warning**: until G1 is implemented the agent looks for `*.md` on branch `main`, while your checklist repository holds `.xlsx` and `.docx`. It will find nothing and report a degraded, checklist-free review. The reader for those formats exists and is tested — it is simply not wired in yet (research R1).

---

## Part 2 — Sample runbook

**Moved.** The sample runbook now lives in feature 002 as a complete worked example,
with the sample code, work item text and pull request description supplied verbatim
rather than described:

> **[Walkthrough: Create a Pull Request and Run the Review Agent](../002-pr-review-walkthrough/walkthrough.md)**

The sketch that used to sit here told you what *kind* of faults to plant without
saying which ones, so no two operators produced the same demonstration and nobody
could tell a broken agent from a badly-built sample. The walkthrough supplies the
artifacts and states what each one should produce.

**Part 1 above remains the authority on operator setup** — the walkthrough defers to
it rather than restating it.

Two corrections, if you are working from a copy of the old Part 2:

- It told you to confirm a run report under `.review-reports/`. **Nothing writes one**
  (gap G2), so that check could never pass.
- The exit-code table in Part 1 lists `3` for a degraded manual run. `EXIT_DEGRADED`
  is defined but never returned (`errors.py:26`, `main.py:343-346`); a degraded review
  exits `0`.

---

## What a reviewer should expect

The agent is **a reviewer aid, not a merge gate**. It reasons over diff text and cannot verify runtime behaviour, so a human always decides the merge. Defaults are preview mode and never blocking.

Its headline value is the **false coverage claim**: the description says a criterion is covered and the diff does not implement it. Everything else is supporting detail.

`not_addressed` is deliberately silent. A pull request routinely implements only part of a story; flagging that would make the agent noise on almost every review, and the one thing a review tool cannot recover from is being ignored.
