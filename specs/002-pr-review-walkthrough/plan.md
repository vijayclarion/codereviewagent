# Implementation Plan: Complete Worked Example — Create a Pull Request and Run the Review Agent

**Branch**: `002-pr-review-walkthrough` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-pr-review-walkthrough/spec.md`

## Summary

Deliver one document that carries an operator from an unprepared machine to review comments posted on a real pull request, with every artifact supplied ready-made, and verify it by performing it end to end against the live sample repository.

This closes **gap G7** of feature 001, which named the work exactly: *"Write the runbook; execute it once for real."* Feature 001 shipped a sketch in `quickstart.md` Part 2 that says *what kind* of faults to plant without saying which ones. This feature replaces that sketch with executable content and, per clarification Q5, leaves a pointer in its place.

**The survey changed the shape of this plan.** Reading `review_agent/` against the spec turned up three places where the spec describes the agent feature 001 intends to build rather than the agent that exists today. Clarification Q3 chose today's agent, and FR-036 forbids adjusting the document to describe intended behaviour. So those three are reconciled here, in the Reality Reconciliation table, before any writing starts. The largest: **the agent has no severity threshold** — inline versus summary-only is decided by whether a finding can be anchored to a changed line, not by how severe it is. A walkthrough written to FR-011 as literally worded would tell the reader to watch for behaviour the agent does not have.

## Technical Context

**Language/Version**: The deliverable is Markdown. The example files are source code in the sample repository's predominant language, determined by inspection per FR-009c, defaulting to Python 3.13 (the agent's own) if that repository is empty or mixed.
**Primary Dependencies**: None added. The walkthrough drives `review_agent/main.py` through its existing CLI. No change to the agent's code, its dependencies, or its tests.
**Storage**: Files in `specs/002-pr-review-walkthrough/`. No database, no new configuration.
**Testing**: The verification run (FR-034) *is* the test. No automated test is added — the example files are deliberately faulty and must stay outside anything `pytest` collects. Confirmed safe: `pytest.ini` sets `testpaths = tests`, and `tests/contract/test_import_boundaries.py:13` scans only `review_agent/`, so files under `specs/` are reached by neither.
**Target Platform**: Windows 11 local developer machine, PowerShell. The agent's commands are identical in PowerShell and bash, so the walkthrough quotes one form.
**Project Type**: Documentation deliverable with committed reference material.
**Performance Goals**: SC-001 — a first-time operator finishes within 30 minutes.
**Constraints**: FR-031 — no credential, token, real host address, or real project identifier in the document. This is the one constraint that can be violated by accident, because the verification run produces output containing real values that are tempting to paste in.
**Scale/Scope**: One document, one set of example files, one work item, one pull request, one verification run.

No NEEDS CLARIFICATION remains. Every value above is observed in the repository or fixed by a clarification answer.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is still an unfilled template — every principle is a `[PRINCIPLE_N_NAME]` placeholder. The formal gate passes vacuously, exactly as it did for feature 001.

Feature 001 reconstructed five de-facto principles from the code and its contract tests. This feature writes no code, so four of the five cannot be violated by it. The fifth can:

| Reconstructed principle | Can this feature violate it? | How it is held |
|---|---|---|
| I — One module reads the environment | No — no code written | — |
| IV — Format knowledge is isolated | No — no code written | — |
| VII — No silent outcome | **Yes, in documentation form.** A walkthrough that lists an expected finding without saying it is currently absent is exactly the silence this principle forbids | FR-026, FR-026a, SC-009; enforced by the expected-results contract |
| Nothing hard-coded | No — no code written | — |
| **Secrets never escape** | **Yes.** The verification run prints real values, and the author will be copying from that output into the document | FR-031; enforced by the pre-publication scan in Phase 2, task-level gate |

Both live risks are documentation risks, and both are addressed by contracts in Phase 1 rather than by good intentions.

**Post-Phase-1 re-check**: the design holds both. The expected-results contract requires an explicit availability state on every listed finding, so an absent finding cannot be listed silently. The verification-run contract requires the redaction scan to run against the finished document before it is considered delivered, not after.

**Unchanged recommendation from 001**: run `/speckit.constitution` to ratify the five principles in writing. Until then the contract tests hold four of them and nothing holds the fifth for documents.

## Reality Reconciliation

The spine of this plan, and the reason it is not simply "write the document".

The spec was written against feature 001's intended behaviour. Clarification Q3 chose to target the agent as it is today. These are the three places where those differ. Each row is a decision made now, so the walkthrough author is not making it alone at 2am with a live pull request open.

| # | Spec says | The agent actually does | Evidence | Resolution |
|---|---|---|---|---|
| **R1** | FR-011 — include a fault "below the inline-comment threshold", exercising inline versus summary-only | **There is no severity threshold.** `build_inline_comments` routes a finding inline if `_locate` resolves its file and line inside the reviewed diff, and to the summary otherwise. Severity only picks a header string and decides `has_blocking_findings` | `review_agent/output_layer.py:87-137`, `:72-85`; `review_agent/models.py:472` | FR-011's *intent* — exercise both routes — is satisfiable today by a finding with no anchorable location. The reliable one is a `possible_contradiction` coverage entry: it is routed with `path=""` at `output_layer.py:126`, so it can never locate and is **always** summary-only. The sample is designed around that, not around severity. **Spec amendment required** — see Spec Amendments below |
| **R2** | FR-023 — state the expected completion status. 001's `contracts/cli.md` and `quickstart.md` both document exit `3` for a degraded manual run | **Exit 3 is never returned.** `EXIT_DEGRADED = 3` is defined in `errors.py:26` and no code path returns it; `main()` catches `DegradedReview` and returns `EXIT_OK` | `review_agent/errors.py:26`; `review_agent/main.py:343-346` | The walkthrough documents `0`, `1`, `2` only, and says plainly that a degraded run also exits `0`. This matters more than it looks: with the checklist source yielding nothing, a degraded run is the *likely* outcome, and a reader told to expect `3` would conclude the agent is broken |
| **R3** | FR-021, FR-026 — expected results include checklist-derived findings; 001's Part 2 checkpoint tells the reader to confirm a run report under `.review-reports/` | **Neither exists today.** Checklist discovery defaults to `CHECKLIST_FILE_PATTERN=*.md` on `CHECKLIST_BRANCH=main` while the corpus is `.xlsx`/`.docx` (gap G1), so `checklist.available` is false and the run continues with `outcome="degraded"` at `main.py:153`. No module writes a run report (gap G2) | `review_agent/config.py:434-435`; `review_agent/main.py:153`; 001 plan G1, G2 | Checklist findings are listed as **expected-absent with the reason** (FR-026). The run-report checkpoint is **removed**, not carried forward — FR-026a forbids a checkpoint the reader cannot satisfy. This is the concrete bug that 001's Part 2 currently contains and that FR-003a's replacement fixes |

**Consequence for the sample design**: with checklist findings absent, the demonstration rests entirely on requirement alignment against the linked work item — which is what FR-026b already requires. The four finding types the agent can actually produce today are `false_coverage_claims`, `coverage` entries, `checklist_violations` (absent) and `code_issues`. The sample must therefore generate, from the work item alone, at least one anchorable finding and one unanchorable one. That is the single hardest design constraint in this feature and it drives Phase 0 research item R4.

### Spec Amendments

FR-011 is unsatisfiable as worded against today's agent. Rather than silently reinterpret it, this plan records the required amendment and `/speckit.tasks` carries it as a task:

> **FR-011 (amended)**: The sample change MUST produce at least one finding that cannot be anchored to a changed line, so that the demonstration exercises the distinction between findings posted inline and findings reported only in the summary. That finding MUST NOT depend on the checklist source. *(The agent routes by locatability, not severity; there is no configurable threshold today. When one is introduced, this requirement reverts to severity-based wording.)*

No other requirement needs amendment. FR-023 and FR-026 are satisfied by writing them to observed behaviour, which is what they already ask for.

## Project Structure

### Documentation (this feature)

```text
specs/002-pr-review-walkthrough/
├── plan.md                     # This file
├── spec.md                     # Clarified specification
├── research.md                 # Phase 0 output
├── data-model.md               # Phase 1 output
├── quickstart.md               # Phase 1 output — how to execute this plan
├── contracts/                  # Phase 1 output
│   ├── walkthrough-structure.md   # Required sections and what each must carry
│   ├── expected-results.md        # Fault → finding mapping, and availability state
│   └── verification-run.md        # The live-run protocol and the evidence it must capture
├── checklists/
│   └── requirements.md         # Spec quality checklist (complete)
├── walkthrough.md              # THE DELIVERABLE — written in the implement phase
├── example-files/              # THE DELIVERABLE — faulty sample code, copied by the reader
│   └── (language and contents fixed by research R1 and R4)
└── tasks.md                    # Phase 2 output — NOT created by /speckit.plan
```

### Files outside this feature that change

Three, all small, all required by a clarification answer:

```text
specs/001-pr-code-review-agent/quickstart.md   # Part 2 replaced by a pointer  [FR-003a, Q5]
CLAUDE.md                                      # Active feature + plan pointer [Phase 1 step 3]
review_agent/README.md                         # Link to the walkthrough       [FR-002]
```

**Structure Decision**: The walkthrough and its example files live together in the feature directory. Two reasons, both load-bearing. First, FR-009a needs the faulty code somewhere `pytest` will not collect it and no reader will mistake it for part of the agent — `specs/` satisfies both, verified above. Second, FR-009b makes the example files the single copy of that code, so document and files must move together or the reference breaks.

`review_agent/` is not touched. This feature adds no module, changes no behaviour, and must leave the 401-test suite passing untouched — if a task in this feature modifies anything under `review_agent/`, that task is out of scope.

## Phase 0: Research

See [research.md](./research.md). Six items. Four are answerable from the repository; two require reaching the live environment and are therefore scheduled as the first implementation actions rather than resolved here.

- **R1** — the sample repository's predominant language, which fixes what the example files are (FR-009c). *Requires network.*
- **R2** — which finding types today's agent can produce from a work item alone, and which of them anchor to a line. This is what makes the sample design possible or not.
- **R3** — the exact prerequisite set: every variable `config.py` requires, including the two that 001's quickstart omits.
- **R4** — how to design a sample change that yields both an anchorable finding and an unanchorable one from work-item alignment alone, given R2.
- **R5** — what the verification run must capture as evidence, and how that evidence is redacted before it reaches the document.
- **R6** — whether the sample repository already holds artifacts from earlier demonstrations, which fixes the naming scheme (FR-013). *Requires network.*

## Phase 1: Design & Contracts

- **[data-model.md](./data-model.md)** — the eight entities from the spec, given fields, validation rules, and the one state machine that matters: a finding's availability state, which is what keeps Principle VII from being violated in prose.
- **[contracts/walkthrough-structure.md](./contracts/walkthrough-structure.md)** — the document's required sections in execution order, what each must contain, and which requirement each satisfies. The acceptance surface for the deliverable.
- **[contracts/expected-results.md](./contracts/expected-results.md)** — the fault-to-finding mapping format, including the mandatory availability state that makes an absent finding visible rather than missing.
- **[contracts/verification-run.md](./contracts/verification-run.md)** — the protocol for the live run: what is performed, in what order, what evidence is captured, what is redacted, and what is torn down. FR-034 through FR-037 in executable form.
- **[quickstart.md](./quickstart.md)** — how an implementer executes this plan, including the prerequisite gate that must pass before the live run is attempted.
- **Agent context** — `CLAUDE.md` updated between its `<!-- SPECKIT START -->` markers to point at this plan.

## Sequencing

Two hard orderings, both discovered in the survey rather than assumed:

1. **The `.env` corrections (001's gap G5) block everything.** `config.py:361` requires `LLM_PROVIDER`, which `.env` does not set, so the agent cannot start. `LLM_MODEL` names a model that does not exist. Until a human applies both, no verification run is possible and no expected result can be observed. Feature 001 deliberately declined to touch `.env`; this feature does too. It becomes a prerequisite gate in the quickstart, owned by the operator.
2. **Research R1 and R6 block the example files.** The language and the naming scheme are both determined by looking at the sample repository. Writing example files before that lookup means writing them twice.

Everything else is parallel. The document's recovery section and teardown section can be drafted from the repository alone; only the expected-results section depends on the verification run.

## Complexity Tracking

No constitution violations to justify — the gate passed vacuously and the design holds the two principles this feature could plausibly break. Three scope decisions are recorded instead, because each is a place a reader might reasonably expect different work:

| Decision | Why | Alternative rejected because |
|---|---|---|
| Amend FR-011 rather than reinterpret it silently | The spec's wording is unsatisfiable against today's agent (R1). An amendment is visible; a reinterpretation is not | Quietly writing the document to locatability while the spec says severity leaves the next reader unable to tell which is authoritative — and FR-036 exists precisely to forbid that move |
| Close no gap from feature 001 (G1, G2, G3 stay open) | Clarification Q3 chose today's agent, and this feature adds no code. Closing G1 would make checklist findings appear and is unambiguously valuable — but it is 001's work, with 001's tests | Fixing G1 here would mean this feature both changes the agent and documents it, so a failed verification run could not be attributed to either. It also inverts the dependency: a documentation feature blocking on implementation work |
| Remove the run-report checkpoint from 001's Part 2 rather than carrying it forward | It cannot be satisfied — nothing writes a run report (G2). FR-026a forbids a checkpoint the reader cannot pass | Carrying it forward means the first honest reader hits a check that fails for a reason the document does not explain, and concludes the agent is broken. That is the exact failure this feature exists to prevent |

## What this plan does not do

- It does not write the walkthrough. `/speckit.tasks` then `/speckit.implement` follow.
- It does not touch `review_agent/`. No gap from feature 001 is closed here.
- It does not touch `.env`. The G5 corrections are a human-applied prerequisite, as they were in 001.
- It does not perform the verification run. That is an implementation task, gated on `.env` being fixed and on credentials being available.
- It does not decide whether your organisation permits source code to reach a third-party provider. FR-006 obliges the walkthrough to state the exposure before the reader creates anything; whether that exposure is acceptable is a policy decision outside this repository.
