# Contract: Verification Run

**Feature**: [../spec.md](../spec.md) | **Satisfies**: FR-034, FR-035, FR-036, FR-037, SC-010

Clarification Q1 put the live run in scope. This is that run as a protocol rather than an intention: what is performed, in what order, what evidence is captured, what is redacted, and what is torn down.

The run is not a demonstration of the walkthrough. It is the thing that makes the walkthrough's expected results observations rather than predictions, which is the only reason anyone should trust them.

## Gate — nothing below runs until these pass

| Gate | Check | If it fails |
|---|---|---|
| Configuration valid | `python review_agent/main.py --dry-run --pr <id>` reaches past configuration validation | Apply the `.env` corrections (feature 001, gap G5): add `LLM_PROVIDER`, correct `LLM_MODEL`. **A human applies these — this feature does not touch `.env`** |
| Full variable set present | The same command names no missing variable | Add what it names, then **run it again** — validation happens in rounds, not all at once. Several checks are gated on `LLM_PROVIDER` being valid (`config.py:369-376`), so they stay invisible until it is set |
| Posting rights | `TFS_PAT_FOR_PR` present, with Code (read & write) on the sample repository | The posting and repeat stages cannot run; the feature cannot be completed (FR-034) |
| Suite still green | `python -m pytest tests -q` → 401 passing | Stop. Something outside this feature broke; this feature changes no code |

The first gate is the one that stops most attempts. `config.py:361` requires `LLM_PROVIDER` and `.env` does not set it, so the agent cannot start as shipped.

## Stages

Performed in order. Each stage's evidence is captured before the next begins — a stage that is not captured did not happen, as far as the document is concerned.

### 1. Setup

Create the work item, the branch, the commit, the pull request, and the link, following the walkthrough's own sections 4–6.

**This is also a test of those sections.** Any point where the author has to decide something the document does not specify is a defect in the document, recorded and fixed before the run continues (SC-002).

Captured: nothing yet. Noted: every point where the document was insufficient.

### 2. Preview

```
python review_agent/main.py --dry-run --pr <sample-pr-id>
```

Captured:

- Full console output
- Observed exit status
- Which findings appeared, their kind, and whether each was rendered inline or summary-only

This output is the **source of every entry** in the expected-results reference (FR-035).

### 3. Post

```
python review_agent/main.py --post --pr <sample-pr-id>
```

Captured:

- Full console output and exit status
- The number of inline comments on the pull request, and the file and line each landed on
- That exactly one summary comment exists

### 4. Repeat

The same posting command again, against the unchanged pull request.

Captured:

- That the comment count is unchanged
- How the console reported the repeat findings — the wording the walkthrough will tell readers to look for

### 5. Line-drift repeat *(optional, recorded either way)*

Push a whitespace-only commit that shifts line numbers, then post again.

Captured: whether comments are still not duplicated. Fingerprints exclude the line number (`fingerprint(kind, path, text)`, feature 001 gap G4), so they should not be — but if this stage is skipped, the walkthrough says it was untested rather than implying it passed.

### 6. Teardown

Performed as part of the run (FR-037), so the teardown steps are confirmed rather than assumed.

- Abandon the pull request — **never complete it**
- Delete the sample branch
- Remove or retire the sample work item
- Remove any local artifact containing copied source

Captured: whether each step worked as the document describes, and anything the document missed.

## Evidence handling

### Redaction — required, before any captured output reaches the document

| Redact | To |
|---|---|
| Base URL, collection | a visibly distinguishable placeholder |
| Project name | placeholder |
| Repository name | placeholder |
| Pull request id | placeholder |
| Work item id | placeholder |
| Account and display names | placeholder |

Tokens should never be present — `config.emit` redacts every registered secret on the way out (`config.py:247` registers `TFS_PAT`, `TFS_PAT_FOR_PR`, `LLM_API_KEY`). **The scan does not rely on that.** It runs over the finished document regardless, because the cost of being wrong once is a credential committed to a repository, and no test in this project catches that.

This is the single most likely defect in this feature, and it arrives by copy-paste rather than by reasoning.

### Fidelity rules

| Rule | Requirement |
|---|---|
| Record what happened, not what was expected | FR-036 |
| A finding the run did not produce may not be listed as `observed` | FR-035 |
| A stage not performed is stated as not performed | FR-035 |
| Provider wording varies; record which findings appeared, not the exact sentences | expected-results contract |

**If a planted fault produces no finding**: the sample is redesigned and the run repeated. It is not written up as though the finding had appeared, and it is not quietly dropped from the fault list — a fault that the agent does not catch is worth knowing about, and if it stays in the sample it is listed with availability `expected-absent` and the reason.

## Completion

The run is complete when:

- [ ] Every stage performed, or explicitly recorded as not performed
- [ ] Every expected-results entry traces to captured output
- [ ] Every document insufficiency found during setup is fixed
- [ ] Redaction scan passed over the finished document
- [ ] Teardown verified — sample repository back to its prior state, no local artifact left
- [ ] `verified_on` and `verified_against` recorded in the walkthrough (FR-033)
- [ ] `python -m pytest tests -q` still reports 401 passing

The last one is worth stating even though this feature writes no code: it is how a stray edit under `review_agent/` gets caught before it is attributed to something else.
