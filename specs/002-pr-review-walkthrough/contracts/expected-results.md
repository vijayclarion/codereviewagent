# Contract: Expected Results

**Feature**: [../spec.md](../spec.md) | **Appears in**: walkthrough section 8, "What you should see"

This is what turns a run from *performable* into *verifiable*. Without it the reader sees output and has no way to judge it.

It is also where Principle VII — no silent outcome — is most easily broken in prose. A finding listed without an availability state reads as "you will see this". When the reader does not see it, they conclude the agent is broken. The `availability` column exists to make that impossible.

## Entry format

One row per deliberate fault, plus one row per finding the verification run produced that was not planted.

| Column | Values | Rule |
|---|---|---|
| **Fault** | label | Matches a fault id in walkthrough section 5 |
| **Traces to** | criterion or rule | FR-010, SC-004. Never blank — a finding with no source is not verifiable |
| **Finding kind** | `false-coverage` \| `coverage` \| `checklist` \| `code` | As the agent classifies it |
| **Severity** | `high` \| `medium` \| `low` \| `n/a` | `n/a` for every kind except `code` |
| **Placement** | `inline` \| `summary-only` \| `either` | Per the routing table below |
| **Availability** | `observed` \| `expected-absent` \| `varies` | See states below |
| **Note** | text | Required when availability is not `observed` |

## Availability states

| State | Means | Required note |
|---|---|---|
| `observed` | Seen in the verification run. The reader should see it too | — |
| `expected-absent` | The agent cannot produce this today. Not a failure | **The reason.** For checklist findings: the corpus is `.xlsx`/`.docx` while discovery defaults to `*.md` on `main` (`config.py:434-435`), so nothing is found and the run continues with `outcome="degraded"` (`main.py:153`) |
| `varies` | Produced by provider judgement; may differ in wording or placement between runs | **What is stable and what is not.** Typically: the finding appears, its exact wording does not |

**Rule**: `expected-absent` may not be used for a finding the verification run actually produced, and `observed` may not be used for one it did not (FR-035). The second is the failure mode that matters — it is how a prediction gets written up as an observation.

## Placement — routing is by locatability, not severity

The single most important thing this contract fixes. The spec was written expecting a configurable severity threshold. **The agent has none.**

`build_inline_comments` (`review_agent/output_layer.py:87-137`) routes every finding through `route()`, which calls `_locate` (`:72-85`). A finding goes inline when its reported file matches a file in the reviewed diff *and* its line maps into that diff. Otherwise it goes to the summary. Severity picks a header string (`:134`) and decides `has_blocking_findings` (`models.py:472`). It does not affect placement.

| Kind | Routed with | Placement | Why |
|---|---|---|---|
| `false-coverage` | the claim's file and line | `either` | The provider supplies these; they may be empty |
| `coverage` / `possible_contradiction` | `""`, `0` | **always `summary-only`** | Hard-coded at `output_layer.py:126` — cannot locate |
| `coverage` / `not_addressed` | — | **never appears** | Skipped at `:117`: *"not_addressed never comments (FR-016)"* |
| `checklist` | the violation's file and line | `either` | `expected-absent` today |
| `code` | the issue's file and line | `either` | Severity is in the header only |

**Consequence for the sample**: `possible_contradiction` is the only kind guaranteed summary-only, so it is what satisfies amended FR-011. A low-severity `code_issue` would land inline whenever the provider supplies a resolvable line — intermittently, which is worse than never, because it teaches the reader to distrust the checkpoint.

## Exit status

The walkthrough states the expected status and what the others mean (FR-023).

| Status | Meaning | Expected here? |
|---|---|---|
| `0` | Review completed — **including a degraded run** | **Yes.** With the checklist source unavailable, a degraded run is the likely outcome and it still exits `0` |
| `1` | Blocking findings, only with `FAIL_ON_CONTRADICTION=true` | Only if the operator set that flag. The sample's false coverage claim would trigger it (`models.py:472`) |
| `2` | Setup failure — nothing works until a setting changes | No. If seen, go to the symptom reference |

**`3` must not be documented.** `EXIT_DEGRADED = 3` exists at `errors.py:26` and no path returns it; `main()` catches `DegradedReview` and returns `EXIT_OK` (`main.py:343-346`). Feature 001's `contracts/cli.md` and `quickstart.md` both document `3` for a degraded manual run. Both are wrong today, and a reader told to expect `3` on the run most likely to be degraded would conclude the agent had failed.

## Minimum content

The reference is incomplete unless it covers:

- The unimplemented criterion claimed as covered → `false-coverage`, placement `either`, availability from the run.
- The contradicted criterion → `coverage`/`possible_contradiction`, placement `summary-only`, availability from the run.
- Checklist findings → `expected-absent`, with the reason. Listing these matters: it is how the reader learns what the agent *will* do once gap G1 closes, and why it does not yet.
- Exactly one summary comment, whatever the findings (FR-025).
- The repeat run adding nothing, because findings are fingerprinted by kind, path and text rather than by line (FR-024).

## What the reader is told about variability

Stated once, plainly, near the top of the section: the findings come from a provider's judgement, so wording will differ between runs and between models. What is stable is **which** findings appear and **where** they are placed. The reader checks for the finding, not for the sentence.

Without this, the first reader whose output reads differently concludes the walkthrough is stale.
