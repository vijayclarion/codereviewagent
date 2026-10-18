# Phase 0 Research: Complete Worked Example

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-15

Eight items, all closed. Six were answerable from the repository; R1, R6 and R7 were settled by inspecting the live environment, and R4 and R8 by performing the verification run.

Two were added during implementation:

- **R7** — a first attempt misdiagnosed an unsupported API version as rejected credentials. Kept as its own item because a reader of the walkthrough can make the same mistake just as easily.
- **R8** — the repeat run duplicates inline comments. A genuine defect that no amount of further reading would have found, and the clearest argument for clarification Q1 having put the live run in scope.

---

## R1 — What language are the example files written in?

**Status**: **Resolved by inspection, 2026-09-15. Python.**

Observed in `TFS_REPO_CODE_SAMPLE` on its default branch (`refs/heads/master`), 102 files:

| Extension | Count |
|---|---|
| `.md` | 45 (markup — excluded by the rule) |
| **`.py`** | **26** |
| `.ps1` | 8 |
| `.json` | 7 |
| `.yml` | 6 |
| `.sh` | 4 |
| `.cs` | 3 |

Python holds the plurality of source files by a wide margin, so step 2 of the rule
applies — not the fallback. The example files in `example-files/` are Python and
match the repository natively.

**Correction to an earlier draft of this item.** A previous attempt concluded the
sample repository was unreachable because "both access tokens are rejected". **That was
wrong.** The tokens are valid. Two unrelated things produced that false diagnosis:

1. The probe omitted an `Accept: application/json` header, so the server returned its
   HTML "Page not found" page instead of an API response — which reads like a 404 on a
   valid path.
2. `TFS_API_VERSION` defaults to `6.0` (`config.py:425`) and **this server rejects
   `6.0`** with a 404. Versions `5.0` and below all return `200`.

Nothing was wrong with the credentials. See R7.

**Decision rule**, retained for a future implementer:

## R2 — Which findings can today's agent produce, and which of them anchor to a line?

**Status**: Resolved from the repository.

**Decision**: The sample is designed around four finding types, of which only three are reachable today.

| Finding type | Produced from | Anchors to a line? | Reachable today? |
|---|---|---|---|
| `false_coverage_claims` | PR description claims a criterion is covered; diff does not implement it | **Sometimes** — routed with the claim's own `file`/`line`, which the provider supplies and may leave empty | Yes |
| `coverage` entries, status `possible_contradiction` | Linked work item's acceptance criteria versus the diff | **Never** — routed with `path=""` | Yes |
| `coverage` entries, status `not_addressed` | Same | **Never comments at all** — skipped before routing | Yes, but silent by design |
| `checklist_violations` | Checklist corpus | Sometimes | **No** — corpus yields nothing (G1) |
| `code_issues` | Diff, severity `high`/`medium`/`low` | Sometimes | Yes |

**Evidence**: `review_agent/output_layer.py:87-137` — `build_inline_comments` iterates these four collections and calls `route()`. `route()` calls `_locate` (`:72-85`), which returns a path and line only when the reported file matches a file in `reviewable.reviewed` *and* the line maps into the diff; otherwise the finding goes to `summary_only`. The `possible_contradiction` branch at `:126` passes `""` and `0` as file and line, so it cannot ever locate. `not_addressed` is `continue`d at `:117` with the comment *"not_addressed never comments (FR-016)"*.

**Rationale for recording this at all**: the spec assumes a severity threshold decides inline versus summary. It does not exist. This table is what replaces it, and it is what makes the sample designable.

**Consequence**: `possible_contradiction` is the only finding type *guaranteed* summary-only. The sample uses it to satisfy amended FR-011 rather than relying on a low-severity nit, which would land inline or not depending on whether the provider happened to supply a resolvable line.

**Alternatives considered**: Using a `code_issue` with severity `low` — rejected, severity does not affect routing, so it would land inline whenever the provider supplies a line, and the checkpoint would fail intermittently. Intermittent is worse than absent: it teaches the reader to distrust the document.

---

## R3 — What is the complete prerequisite set?

**Status**: Resolved from the repository.

**Decision**: The walkthrough's prerequisite section lists every variable `load_config` requires, not the subset 001's quickstart names.

Required unconditionally (`review_agent/config.py:313-395`):

| Variable | Note |
|---|---|
| `TFS_BASE_URL` | alias `SYSTEM_TEAMFOUNDATIONCOLLECTIONURI` |
| `TFS_PROJECT` | alias `SYSTEM_TEAMPROJECT` |
| `TFS_REPO_CODE_SAMPLE` | alias `TFS_REPO` |
| `TFS_PR_ID` | or `--pr ID` per run |
| `TFS_PAT` | read credential |
| `LLM_PROVIDER` | **missing from `.env` today — the agent cannot start** (G5) |
| `LLM_MODEL` | **names a non-existent model today** (G5) |
| `LLM_API_KEY` | required unless the provider is keyless (`ollama`) |
| `TFS_REPO_CODE_REVIEW_CodeReviewAgent` | required unless `--local` is passed |
| `TFS_PAT_FOR_PR` | required only to post; omitting it makes `--post` a setup failure |

Conditionally required:

| Variable | Required when |
|---|---|
| `LLM_BASE_URL` | `LLM_PROVIDER` is `azure` or `ollama` only (`config.py:107`, `BASE_URL_REQUIRED`). **Not required for `claude`** |

**Correction, 2026-09-15**: an earlier draft of this item listed `LLM_BASE_URL` as unconditionally required and called its absence from 001's quickstart an omission. That was wrong — `config.py:374-376` gates it on the provider, and for a `claude` setup it is not needed. 001's quickstart was right. Recorded rather than quietly deleted, because the walkthrough's prerequisite section is built from this table and the error would have propagated into it.

**Observed state of `.env`** (checked 2026-09-15, without printing values): `LLM_PROVIDER` absent, `TFS_PR_ID` absent, `LLM_MODEL` present but naming a model that does not exist. Everything else required for a `claude` setup is present. So gap G5's fix is exactly the two changes 001's quickstart already describes, plus `--pr` per run.

**Cheapest confirmation**: `python review_agent/main.py --dry-run --pr <id>` fails at configuration validation before contacting anything.

**But it does not report everything at once.** Observed:

```
ai-review setup failure: configuration is incomplete or invalid: LLM_PROVIDER is required
  -> set the listed values in .env or as pipeline variables
ai-review run=- phase=done outcome=setup-failure ms=19 exit=2
```

One problem, not a list — because several checks are *gated on the provider being valid* (`config.py:369-376`). Until `LLM_PROVIDER` is set, the key and base-URL checks are skipped entirely. A reader therefore hits validation in **rounds**, and the walkthrough must say so; telling them one run reports everything sets them up to think they are done after the first fix.

**Alternatives considered**: Having the walkthrough restate each variable's meaning — rejected under FR-003; 001's quickstart Part 1 owns that and stays authoritative.

---

## R4 — How does the sample produce both an anchorable and an unanchorable finding from work-item alignment alone?

**Status**: **Confirmed by the verification run, 2026-09-15. Both defects reproduced.**

Observed: `coverage=4 violations=0 issues=4 false_claims=2`, and in the rendered output —

| Planted defect | Produced | Placement |
|---|---|---|
| Criterion 4 unimplemented, claimed covered | `false_coverage_claim` + coverage `not_addressed` | summary |
| Criterion 3 implemented with the wrong message | coverage **`possible_contradiction`** + `false_coverage_claim` | **summary only, as predicted** |
| Bare `except` | `code_issue` `medium` | inline `/discount.py:50` |
| Unused import | `code_issue` `low` | **inline** `/discount.py:6` |

The `low`-severity finding landing inline is the clean confirmation that placement is
by locatability, not severity — the point R2 predicted and the reason FR-011 was amended.

The risk this item flagged — that provider judgement might not reproduce the findings —
did not materialise for *which* findings appear. It did materialise for **how many**:
three runs on identical input produced 4, then 5, then 4 code issues. Stable in kind,
unstable in count.

**Decision**: The sample carries two independent requirement defects, not one.

1. **An unimplemented criterion claimed as covered.** The work item has four acceptance criteria; the change implements three; the pull request description lists all four under "Covered". This produces a `false_coverage_claim` — the demonstration's headline. It anchors to a line when the provider supplies one and falls to the summary when it does not, so the walkthrough states both outcomes as acceptable and explains why (R2).
2. **An implemented criterion contradicted by the code.** One criterion states a specific behaviour; the change implements something that visibly conflicts with it — the stated message text differs, or the stated condition is inverted. This produces a `coverage` entry with status `possible_contradiction`, which is **always** summary-only (R2).

Defect 2 is what satisfies amended FR-011, and it is the one the sample must be designed around most carefully, because it is the only guaranteed summary-only finding.

**Rationale**: FR-026b requires the demonstration to remain meaningful with the checklist source yielding nothing. Two requirement defects with different routing exercise inline comments, the summary comment, the inline-versus-summary distinction, and — because both are fingerprinted by kind, path and text — the repeat run's deduplication. That is every checkpoint the walkthrough needs, from the work item alone.

**Risk, stated plainly**: both findings come from a provider's judgement, not from a deterministic rule. The provider may phrase them differently between runs, or miss one. The verification run is what converts this from a prediction into an observation, and FR-035 forbids stating any expected result the run did not produce. If defect 2 does not reproduce, the sample is redesigned — it is not written up as though it had.

**Alternatives considered**: Relying on `code_issues` for the second finding — rejected, severity does not control routing (R2), so it gives no guarantee. Waiting for G1 so checklist findings carry the demonstration — rejected by clarification Q3.

---

## R5 — What evidence does the verification run capture, and how is it redacted?

**Status**: Resolved.

**Decision**: The run captures console output and pull request state, and everything captured passes a redaction scan before any of it reaches the document.

Captured:

- The preview run's full console output — the source of every expected result (FR-035).
- The posting run's console output, plus the pull request comment count and the file and line each comment landed on.
- The repeat run's console output, plus the unchanged comment count.
- The observed exit status of each run.

Redacted before use, per FR-031: the base URL and collection name, the project name, the repository name, the pull request id, the work item id, and any account or display name. These become visibly distinguishable placeholders. **No token should appear in the first place** — `config.emit` redacts every registered secret on the way out (`SECRET_ENV_NAMES` at `config.py:247` covers `TFS_PAT`, `TFS_PAT_FOR_PR`, `LLM_API_KEY`) — but the scan does not rely on that holding, because the cost of being wrong is a leaked credential in a committed file.

**Rationale**: this is the one place this feature can violate the "secrets never escape" principle, and it violates it by copy-paste, which no test catches. Making the scan a required step of the protocol rather than a habit is the whole mitigation.

**Alternatives considered**: Pasting raw output for authenticity — rejected outright under FR-031. Paraphrasing all output rather than quoting it — rejected, it weakens FR-035's guarantee that results were observed; quoting redacted real output keeps both.

---

## R6 — Do earlier demonstration artifacts already exist in the sample repository?

**Status**: **Resolved by inspection, 2026-09-15. Nothing to collide with.**

Observed in `TFS_REPO_CODE_SAMPLE`:

- **Branches**: `master` only. It is also the default branch.
- **Pull requests**: none, in any state — `active` and `all` both return empty.

So no earlier demonstration has been run here, and teardown needs no warning about
pre-existing leftovers. The dated naming scheme still applies, because it costs nothing
and the *next* operator will not have this guarantee:

- Branch: `sample/pr-review-walkthrough-<YYYYMMDD>`
- Work item title suffix: the same date

**Note for the walkthrough**: the default branch is **`master`**, not `main`. The
walkthrough names the target branch by role rather than by literal name (FR — edge case
"the sample repository's default branch has moved"), which is what keeps that correct.

---

## R7 — Why did the agent appear unable to reach TFS?

**Status**: Resolved, 2026-09-15.

**Decision**: the walkthrough documents `TFS_API_VERSION` as a setting this server
**requires**, not an optional tuning knob.

**What was observed**: with `LLM_PROVIDER` set, the agent gets past configuration
(`phase=config outcome=ok auth=basic`) and then fails reaching the pull request
endpoint with HTTP 404. The credential is fine; the *API version* is not.

| `api-version` | Result |
|---|---|
| `6.0` — **the agent's default** (`config.py:425`) | **404** |
| `5.0`, `4.1`, `4.0`, `3.2`, `3.0`, `2.0`, `1.0` | `200` |

**Fix**: set `TFS_API_VERSION=5.0`.

Feature 001's quickstart already lists this symptom and this fix. What it does not
say is that this server needs it *always*, so a first-time operator meets a 404 that
reads like a wrong project or repository name. The agent's own message says
"check TFS_PROJECT, TFS_REPO, and TFS_PR_ID" — three things that were all correct —
and never mentions the API version.

**Consequence for the walkthrough**: `TFS_API_VERSION=5.0` belongs in the prerequisite
section alongside the gap G5 corrections, and this misleading 404 belongs in the
symptom reference as its own entry.

---

## R8 — Does the repeat run actually avoid duplicating comments?

**Status**: **No. Confirmed defect, 2026-09-15.** Added after the verification run.

**What was expected** (FR-024, SC-005, and feature 001's gap G4, which recorded
"no gap"): a second `--post` against an unchanged pull request adds no comments.

**What happened**:

```
phase=prior  outcome=ok  posted=5 summary=True
phase=post   outcome=ok  inline=4 suppressed=0 summary=update
```

Prior state *was* recovered. The summary *was* updated in place rather than duplicated.
But `suppressed=0` — not one inline finding was recognised as already posted, and four
duplicates were created. The pull request ended with **9 inline comments from two runs**
that should have produced 5.

**Cause**: `fingerprint(kind, path, text)` (`review_agent/parser.py:194-205`). The line
number is excluded deliberately, so identity survives line drift — that part works. But
`text` is the language model's prose, regenerated every run and never byte-identical.
Different text → different fingerprint → no match against what was posted.

The duplicates make it visible: the same bare-`except` defect was posted at lines 47, 50
and 51 across runs, described three different ways.

**Why feature 001 did not catch this**: G4 reasoned about the fingerprint's *inputs* —
correctly noting that excluding the line number satisfies FR-020 and FR-020a — without
exercising it against a live provider twice. Against a deterministic rule engine the
design works. Against a language model it does not.

**Consequence for this feature**: recorded in walkthrough section 10 as observed
behaviour, with the explicit instruction not to re-post to the same pull request. Not
papered over, and not fixed here — fixing it means changing how findings are identified,
which is feature 001's work and needs its own design decision (fingerprint the
*citation* — rule or criterion — rather than the prose).

---

## Summary of what remains unknown

| Item | Status |
|---|---|
| R1 — sample repository language | **Closed.** Python, by inspection |
| R6 — earlier demonstration artifacts | **Closed.** None exist |
| R7 — apparent unreachability | **Closed.** `api-version 6.0` unsupported; use `5.0` |
| R4 — whether both requirement defects reproduce | **Closed.** Both reproduced; counts vary, kinds do not |
| R8 — does the repeat run avoid duplicates | **Closed, and the answer is no.** Genuine defect, see above |

All eight are closed. R8 exists only because the run happened — it is the item that
would not have been found by any amount of further reading, and the reason clarification
Q1 putting the live run in scope was the right call.
