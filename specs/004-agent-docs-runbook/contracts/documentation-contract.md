# Contract: The Documentation Reference

**Feature**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md) | **Date**: 2026-09-16

What `guide.md` must satisfy to be done. Each clause is checkable by one person in under a
minute, without running the agent and without a reviewer's judgement about "quality".

There is no test runner for a markdown file. These clauses are the substitute, and a task
that closes without naming the clauses it satisfies has not closed.

---

## D — Document shape

| # | Clause | Check | Source |
|---|---|---|---|
| **D1** | The document opens with a scope statement naming what it covers and what `walkthrough.md`, `demo.md` and `review_agent/README.md` cover, each linked | First screen; four links; all four resolve | FR-002 |
| **D2** | Exactly four parts, in the order Run · What · Where · Flow | Headings | research D2 |
| **D3** | No content is reproduced from a document that already carries it correctly; it is linked, and the link says what is there | Spot-check any three links | FR-003 |
| **D4** | A maintenance note states what to update when a module, entry point, setting or finding kind changes | Present, and names this file's clauses | FR-029 |
| **D5** | The document is reachable from `review_agent/README.md` | One link, in the README's worked-examples or contents area | FR-001 |

---

## S — Structure part

| # | Clause | Check |
|---|---|---|
| **S1** | Every shipped file and directory appears exactly once | `git ls-files`, compare counts; zero missing (SC-010) |
| **S2** | Every module row states a single responsibility | Read for the word "and" joining two responsibilities |
| **S3** | Every invariant-carrying module names its rule and the `tests/contract/` file that enforces it | Five invariants, five test files |
| **S4** | Deliberate non-defects are named as such, with the reason | At minimum: `002/example-files/`, `003/demo-files/`, the unfilled constitution, the corrupt-document fixture |
| **S5** | The test suite is grouped by what each group proves | Five groups; every test file placed |

**S1 is the clause most likely to be quietly skipped.** The README's module table covers 14
of 20 modules, and the six it omits are exactly the ones that decide how a run starts —
`__main__`, `run`, `bootstrap`, `__init__`, `textutil`, `source_fetch`. Transcribing the
table and stopping fails this clause.

---

## F — Flow part

| # | Clause | Check |
|---|---|---|
| **F1** | Every stage names input, output, its log signal, and a `module.symbol` anchor | Per stage, four fields |
| **F2** | Every log line a straight-through run prints maps to exactly one stage, and every stage to a line | Compare against the `tests.demo.run` transcript (SC-004) |
| **F3** | All nine alternate paths are documented with condition, signal, outcome and anchor | Count nine; data-model entity 5 lists them |
| **F4** | The four entry points are distinguished, including which ones announce the copy of the logic that ran | research D6's table |
| **F5** | The three finding-identity schemes are stated, with the residual risk for code issues | `checklist_key`, `criterion_key`, `code_issue_key`; C11 |

---

## C — Capability part

| # | Clause | Check |
|---|---|---|
| **C1** | Every finding kind has a routing row: inline (under which conditions), summary, blocking | Six kinds |
| **C2** | Inline placement states **both** conditions — stable identity and an anchorable changed line | C15; the single most-repeated error in existing documents |
| **C3** | `not_addressed` reads "never", and names its contract test | `test_routing_not_addressed.py` |
| **C4** | Every exit code has meaning and an action; 3 is listed as defined-and-never-returned | C10 |
| **C5** | The limits section is present, with each numeric limit naming the setting that changes it | data-model entity 7 |
| **C6** | Open gaps are named by number (G2 no run report, G3 no severity threshold) rather than described as mysteries | Two gaps minimum |

---

## R — Runbook part

| # | Clause | Check |
|---|---|---|
| **R1** | Steps are numbered and run from a clean checkout to a confirmed posted review | Read end to end |
| **R2** | Every step has command, success signal, failure symptom and fix | No step with a success and no symptom |
| **R3** | The working-directory precondition appears in step 1 | C7 |
| **R4** | `TFS_API_VERSION=5.0` appears at the configuration step with its 404 symptom | C12, FR-019 |
| **R5** | `TFS_PAT_FOR_PR` appears at the posting step, with its exact failure message | C3, FR-019 |
| **R6** | Token scopes are stated with what degrades if each is missing — Code (read), Code (write) for posting, Work Items (read) | FR-020; the Work Items case degrades to a checklist-only review, it does not fail |
| **R7** | The install check is `python -m pytest tests` — **without** `-q` — and states `532 passed` | C2, FR-024 |
| **R8** | The no-server path names `python -m tests.demo.run` and states what it does *not* prove | C14, FR-022 |
| **R9** | The repeat-run expectation is stated, with what a wrong result would look like | FR-021, G-D |
| **R10** | The shell is named, with the PowerShell/Git Bash differences inline | D7, FR-023 |

**R5 and R7 are the two clauses that would have prevented this feature's own findings.**
Both exist because a plausible command was written and never run.

---

## V — Verification and safety

| # | Clause | Check |
|---|---|---|
| **V1** | Every actionable claim carries `module.symbol` | Sample ten; SC-006 |
| **V2** | Every actionable claim carries `[executed]`, `[read]` or `[unobserved]` | Sample ten |
| **V3** | Every `[unobserved]` names the observation that would close it | Grep the marker; each has a "closes when" |
| **V4** | A Verification Record states commit, date, environment, and the three lists | Present at the end |
| **V5** | **No real credential, token, live host, live project or repository identifier appears** | Grep for the collection host, the project name, `TFS_PAT` values, and any 40+ character opaque string. Placeholders only | 
| **V6** | Transcripts come from `tests.demo.run` or from redacted agent output | Provenance stated under each transcript |
| **V7** | The suite is 532 passing after every edit this feature makes | `python -m pytest tests` |

**V5 is a gate, not a clause.** A deliverable that fails it does not get corrected and
shipped — the commit does not happen, because a secret in git history is not removed by a
later edit. See [verification-record.md](./verification-record.md).

---

## What "done" means

`guide.md` is done when every clause above passes and the Correction Register's `applied`
column is true for each of C1-C9 and C11-C15 that this feature chose to apply, with the
corresponding edit present in `review_agent/README.md`, `CLAUDE.md` or
`specs/001-.../quickstart.md`.

C10, C12 and C14 have `applied = false` by design: the first is a correct claim recorded so
nobody "fixes" it, and the other two are correct already and merely move to where an
operator will meet them.
