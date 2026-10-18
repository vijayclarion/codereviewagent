---

description: "Task list for 004-agent-docs-runbook"
---

# Tasks: Agent Documentation and Manual Run Runbook

**Input**: Design documents from `/specs/004-agent-docs-runbook/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: No test tasks. This feature writes no code; the suite is a **guard**, not a
deliverable — `python -m pytest tests` must report **532 passed** before the first task and
after the last (SC-009). Adding a test means you have left the feature.

**Organization**: by user story, so each part of the deliverable can be written and judged
on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallel-safe — a *different file* from every other task running with it
- **[Story]**: US1-US4, matching spec.md's priorities
- Every task names its file path and the contract clauses it closes

## Why `[P]` is rare here

The deliverable is **one file** (research D1). Two people writing different parts of
`guide.md` are editing the same file, so almost nothing inside a story phase is
parallel-safe. The genuine parallel opportunities are the read-only evidence tasks and the
corrections, which land in three different documents. This is a real constraint of the
chosen shape, not an oversight — see [Parallel Opportunities](#parallel-opportunities).

## Path Conventions

- The deliverable: `specs/004-agent-docs-runbook/guide.md`
- Corrections: `review_agent/README.md`, `CLAUDE.md`, `specs/001-pr-code-review-agent/quickstart.md`
- Scratch evidence (never committed): the session scratchpad directory
- **Forbidden**: `review_agent/*.py`, `tests/**` (quickstart's "What you may edit" table)

---

## Phase 1: Setup

**Purpose**: the baseline that every later claim is measured against.

- [X] T001 Record the verification baseline in `specs/004-agent-docs-runbook/guide.md`: run `python -m pytest tests` (**no `-q`** — C2) and `git rev-parse --short HEAD`, and open the file with a Verification Record stub carrying commit, date, platform, Python and pytest versions (data-model entity 9, clause V4)
- [X] T002 Create the four-part skeleton in `specs/004-agent-docs-runbook/guide.md` — headings in the D2 order: *Run it by hand* · *What it does and will not do* · *Where things live* · *How one review flows* — plus an appendix heading for the Correction Register (clause D2)
- [X] T003 [P] Generate the shipped-file inventory with `git ls-files` into the scratchpad as the working checklist for the structure map (clause S1, SC-010); do not commit it

**Checkpoint**: the file exists, its shape is fixed, and the number that guards the feature is written down.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: conventions and evidence that all four parts depend on.

**⚠️ No part of the deliverable may be written until this phase is complete** — a section
written before the conventions exist has to be rewritten to carry them.

- [X] T004 Write the scope statement at the top of `specs/004-agent-docs-runbook/guide.md`: audience, what this document covers, and what `specs/002-pr-review-walkthrough/walkthrough.md`, `specs/003-checklist-repo-review-demo/demo.md` and `review_agent/README.md` cover — each linked, each with one line saying what the reader will find there (FR-002, clauses D1, D3)
- [X] T005 Write the conventions block in `specs/004-agent-docs-runbook/guide.md`: the `module.symbol` anchor form and why line numbers are not used (research D3), and the three markers `[executed]` / `[read]` / `[unobserved]` with the rule that `[unobserved]` must name its closing observation (research D5, `contracts/verification-record.md` §1)
- [X] T006 [P] Capture the offline evidence into the scratchpad: run `python -m tests.demo.run`, keep the full transcript — eight phase lines plus the dry-run summary — as the **only** quotable transcript source for the whole deliverable (research D4/C14, clause V6, `contracts/verification-record.md` §3 G3)
- [X] T007 [P] Capture the CLI evidence into the scratchpad: `python -m review_agent --help` and `python review_agent/main.py --help`, confirming the five flags including `--local` (C6), for use by US1 and US4
- [X] T008 Read `contracts/verification-record.md` §3 and adopt the redaction gate before writing any prose: `.env` by key name only, placeholders for every host, project, repository and PR id, no value read or pasted at any point (FR-028, gate G1-G5)

**Checkpoint**: every later task can now state a claim in the required form and quote evidence it did not have to invent.

---

## Phase 3: User Story 1 - An operator runs a review by hand (Priority: P1) 🎯 MVP

**Goal**: someone who has never run the agent reaches a posted review from a clean checkout,
using only this part.

**Independent Test**: hand it to a person with credentials and a PR id and nothing else.
They reach a posted review without asking a question and without editing a command
(SC-001).

- [X] T009 [US1] Write the entry-point table in the *Run it by hand* part of `specs/004-agent-docs-runbook/guide.md` — `python -m review_agent`, `--local`, `python -m review_agent.run`, `python review_agent/main.py` — with what each runs, what it needs, and whether it announces which copy of the logic ran (research D6, C5, clause F4)
- [X] T010 [US1] Write step 1 (where you stand) in `specs/004-agent-docs-runbook/guide.md`: the run must start from the repository root because `.env` is read from the current working directory, with the `missing required configuration` symptom that a wrong directory produces (C7, clause R3)
- [X] T011 [US1] Write step 2 (install) in `specs/004-agent-docs-runbook/guide.md` from `review_agent/requirements.txt` and `requirements-dev.txt`, with the success signal and the `truststore` / `REQUESTS_CA_BUNDLE` symptom for a private CA (README's troubleshooting table, clause R2)
- [X] T012 [US1] Write step 3 (preflight) in `specs/004-agent-docs-runbook/guide.md`: `python -m pytest tests` **without `-q`**, stating `532 passed` as the passing result and explaining that the `-q` form prints no summary because `pytest.ini` already sets it (C1, C2, FR-024, clause R7)
- [X] T013 [US1] Write step 4 (configure) in `specs/004-agent-docs-runbook/guide.md`: the required settings, the canonical `TFS_REPO_CODE_SAMPLE` with its `TFS_REPO` alias (C4), and — at this step, not in an appendix — `TFS_API_VERSION=5.0` with the HTTP 404 symptom the `6.0` default produces and the misleading message that accompanies it (C12, FR-019, clause R4)
- [X] T014 [US1] Write the token-scope table in `specs/004-agent-docs-runbook/guide.md`: Code (read) to review, Code (write) to post, Work Items (read) to judge story coverage — each with what happens when it is missing, including that a missing Work Items scope **degrades to a checklist-only review rather than failing** (FR-020, clause R6)
- [X] T015 [US1] Write step 5 (preview run) in `specs/004-agent-docs-runbook/guide.md` using `python -m review_agent --local --dry-run --pr ID`, with the phase-log lines the operator should see and the note that `.env` carries no `TFS_PR_ID`, so `--pr` is not optional here (C13, clause R2)
- [X] T016 [US1] Write step 6 (read the preview) in `specs/004-agent-docs-runbook/guide.md`: how to tell inline comments from summary-only ones **before** anything is posted, cross-linked to the capability part (clause R2; T032 is the link target, so add the link once Phase 6 exists)
- [X] T017 [US1] Write step 7 (post) in `specs/004-agent-docs-runbook/guide.md`: `--post`, and the second token `TFS_PAT_FOR_PR` stated **at this step**, with its exact failure message `TFS_PAT_FOR_PR is required to post (omit --post for a dry run)` (C3, FR-019, clause R5)
- [X] T018 [US1] Write step 8 (confirm, then repeat) in `specs/004-agent-docs-runbook/guide.md`: what to check on the pull request, what a second `--post` run is expected to do, and what more comments appearing would mean — carried as `[unobserved]` with its closing observation, because 003's repair has never been seen live (FR-021, G-D, clause R9)
- [X] T019 [US1] Write the no-server path in `specs/004-agent-docs-runbook/guide.md`: `python -m tests.demo.run`, quoting the T006 transcript, and state plainly what it does **not** prove — no TFS call, no provider call, no posting, none of the three blocking corrections (FR-022, C14, clause R8)
- [X] T020 [US1] Write the shell note in `specs/004-agent-docs-runbook/guide.md`: commands are PowerShell from the repository root; give the Git Bash difference inline (`$env:NAME='value'` against `NAME=value`) and say once that the Python commands are identical in both (research D7, FR-023, clause R10)
- [X] T021 [US1] **Execute every command in the *Run it by hand* part of `specs/004-agent-docs-runbook/guide.md` exactly as written** and mark each step `[executed]` with its real output, or `[unobserved]` with the observation that would close it. Steps needing a live server and credentials are expected to end `[unobserved]`; steps 1-3 and the no-server path are not (SC-002, clauses R2, V2, V3)

**Checkpoint**: the MVP. Someone can run the agent. Stop here and validate before writing another word.

---

## Phase 4: User Story 2 - A maintainer finds where a behaviour lives (Priority: P2)

**Goal**: a developer names the file that owns a behaviour, and the rule that constrains
changing it there.

**Independent Test**: five behaviours named in plain language; 5 of 5 correctly attributed
using only this part (SC-003).

- [X] T022 [US2] Write the module rows of *Where things live* in `specs/004-agent-docs-runbook/guide.md` by transcribing `review_agent/README.md`'s module table and **verifying each row against the module** — 14 rows, one responsibility each (clause S2)
- [X] T023 [US2] Add the six modules the README omits to `specs/004-agent-docs-runbook/guide.md` — `__init__.py`, `__main__.py`, `run.py`, `bootstrap.py`, `textutil.py`, `source_fetch.py` — the six that decide how a run starts (clause S1; cross-reference T009's entry-point table)
- [X] T024 [US2] Add the invariant column in `specs/004-agent-docs-runbook/guide.md`: five architectural rules, each naming its enforcing file in `tests/contract/`, transcribed from `CLAUDE.md`'s invariant table and checked against the tests (clause S3)
- [X] T025 [US2] Add the non-module rows in `specs/004-agent-docs-runbook/guide.md` — root files, `specs/`, `.specify/`, `tests/fixtures/` — and mark the deliberate non-defects with their reason: `specs/002-.../example-files/` (faulty on purpose, never collected), `specs/003-.../demo-files/` (including a document meant to be unreadable), `.specify/memory/constitution.md` (unfilled template, four features running) (FR-006, clause S4)
- [X] T026 [US2] Write the test-group table in `specs/004-agent-docs-runbook/guide.md`: `contract` / `integration` / `unit` / `demo` / `fixtures`, each with what a failure there means and every test file placed, then reconcile the whole part against the T003 `git ls-files` inventory — zero paths missing (clauses S5, S1, SC-010)

**Checkpoint**: a maintainer can find the owner of any behaviour and the rule that guards it.

---

## Phase 5: User Story 3 - A reader traces one review end to end (Priority: P3)

**Goal**: follow one review from the command to the posted comment, including where the
path forks.

**Independent Test**: every line of a real run's phase log maps to exactly one documented
stage, and every stage to a line (SC-004).

- [X] T027 [US3] Write the stage table of *How one review flows* in `specs/004-agent-docs-runbook/guide.md` — one row per `log.phase` call in `main.run_review` plus `config` from `main.main` and the terminal `log.done` — each with input, output, the literal signal, and a `module.symbol` anchor (FR-008, clauses F1, F2)
- [X] T028 [US3] Reconcile the stage table in `specs/004-agent-docs-runbook/guide.md` against the T006 transcript: `pullrequest · workitems · checklists · rules · changes · prior · llm · parse` — no stage without a signal, no signal without a stage (clause F2, SC-004)
- [X] T029 [US3] Document the nine alternate paths in `specs/004-agent-docs-runbook/guide.md` (data-model entity 5: A1-A9), each with condition, visible signal, outcome and anchor — and for A4, A6 and A7 also the sentence the run puts on the pull request, because a degraded outcome that a reader cannot recognise is the defect this project calls silence (FR-009, clause F3)
- [X] T030 [US3] Write the finding-identity section in `specs/004-agent-docs-runbook/guide.md`: `checklist_key` (rule identifier), `criterion_key` (`wi{id}:c{ordinal}`), `code_issue_key` (`severity@line`), and the residual risk that a code issue whose line moves is a new comment — the claim `review_agent/README.md` still states in the opposite direction (C11, clause F5)

**Checkpoint**: a reader can follow a run, and can tell from its output where it went.

---

## Phase 6: User Story 4 - A stakeholder decides whether to trust it (Priority: P4)

**Goal**: what the tool will do, what it will never do, and what it cannot know — without
opening a source file.

**Independent Test**: a reader answers the five questions of SC-005 from this part alone.

- [X] T031 [US4] Write the routing table of *What it does and will not do* in `specs/004-agent-docs-runbook/guide.md` — six finding kinds — by transcribing `review_agent/README.md`'s table and adding the identity column (FR-012, clause C1)
- [X] T032 [US4] State the inline rule in `specs/004-agent-docs-runbook/guide.md` as the code applies it: **both** conditions — a stable identity *and* an anchorable changed line — with `output_layer.build_inline_comments` as the anchor and the note that a finding with no identity reaches the summary even when its line resolves (C15, FR-013, clause C2)
- [X] T033 [US4] State `not_addressed` in `specs/004-agent-docs-runbook/guide.md` as "never, under any condition", naming `tests/contract/test_routing_not_addressed.py`, and say why neutrality is the design rather than an omission (clause C3)
- [X] T034 [US4] Write the exit-code table in `specs/004-agent-docs-runbook/guide.md`: 0, 1, 2 with meaning and the action a person takes — plus 3, defined at `errors.EXIT_DEGRADED` and never returned, recorded so a later reader does not "fix" it (C10, FR-014, clause C4)
- [X] T035 [US4] Write the limits section in `specs/004-agent-docs-runbook/guide.md` (data-model entity 7): `REVIEW_MAX_FILES` 40, `REVIEW_MAX_DIFF_LINES` 3000, `LLM_MAX_CHUNK_LINES` 1200, `CHECKLIST_MAX_CHARS` 60000 — each naming the setting that changes it — plus excluded files never reaching the provider, and that the tool reasons over diff text and cannot observe running behaviour (FR-015, clause C5)
- [X] T036 [US4] State the open gaps in `specs/004-agent-docs-runbook/guide.md` by number: **G2** no run report is written, **G3** no severity threshold exists and `--inline-threshold` / `--report-dir` do not exist in `build_parser` — as deliberate open items, not mysteries (clause C6)

**Checkpoint**: all four parts stand on their own. The deliverable is readable end to end.

---

## Phase 7: Corrections (Cross-Cutting)

**Purpose**: the front door stops contradicting the guide. Every task cites its C-row
(`contracts/verification-record.md` §4 A1-A4) and **none touches `review_agent/*.py` or
`tests/`**.

- [X] T037 [P] Correct the authentication section of `review_agent/README.md`: the read credential and the **post** credential are different variables; add `TFS_PAT_FOR_PR` with its exact failure message (C3)
- [X] T038 [P] Correct the configuration tables of `review_agent/README.md`: canonical `TFS_REPO_CODE_SAMPLE` with `TFS_REPO` as alias (C4), and add `TFS_REPO_CODE_REVIEW_CodeReviewAgent` and `CHECKLIST_MAX_CHARS`, neither of which appears today (C4, C5)
- [X] T039 [P] Correct the quick start and CLI section of `review_agent/README.md`: add `python -m review_agent` and `python -m review_agent.run`, add the missing `--local` flag, and say which forms announce the copy of the logic that ran (C5, C6)
- [X] T040 [P] Correct the two design notes in `review_agent/README.md`: "fingerprints exclude the line number" becomes per-kind (C11), and the routing table's "yes, if located" gains the identity condition (C15)
- [X] T041 [P] Correct `CLAUDE.md`: 401 → **532** in both places, and change the prescribed command to `python -m pytest tests` so the number can actually be seen (C1, C2). **Do not** re-apply C8 or C9 — the active-feature block was already corrected during planning (plan.md, *Already applied during planning*)
- [X] T042 [P] Add to `CLAUDE.md`'s *Running the agent against this server* section what `.env` does not carry — `TFS_PR_ID`, `TFS_API_VERSION`, and that `--post` needs `TFS_PAT_FOR_PR` with write scope (C13, C3)
- [X] T043 [P] Add one superseding pointer at the top of `specs/001-pr-code-review-agent/quickstart.md`: its Part 1 setup corrections were applied and gap G5 is closed; the current setup path is this feature's guide (I4). Change nothing else in that file
- [X] T044 Link `specs/004-agent-docs-runbook/guide.md` from `review_agent/README.md` under *Worked examples*, saying what it covers that the walkthrough and the demonstration do not (FR-001, clause D5)

**Checkpoint**: the first document a reader meets no longer sends them at the wrong token.

---

## Phase 8: Polish & Verification

**Purpose**: the clauses that make this deliverable different from the seven before it.

- [X] T045 Write the Correction Register appendix in `specs/004-agent-docs-runbook/guide.md`: C1-C15, each with document, claimed, actual, evidence and whether this feature applied it — C10, C12 and C14 carry `applied = false` by design (data-model entity 10)
- [X] T046 Write the maintenance note in `specs/004-agent-docs-runbook/guide.md`: what to update here when a module, an entry point, a configuration setting or a finding kind is added or removed (FR-029, clause D4)
- [X] T047 Complete the Verification Record in `specs/004-agent-docs-runbook/guide.md`: commit, date, environment, `executed`, `read`, and an `unobserved` list that is **not empty** — at minimum C3's two-token case, C12's 404, and G-D's second live posting run, each with its closing observation (FR-026, FR-027, clauses V3, V4)
- [X] T048 Sweep `specs/004-agent-docs-runbook/guide.md` for anchors and markers: sample ten actionable claims; all ten carry `module.symbol` and one of the three markers, and all ten match the code they cite (SC-006, clauses V1, V2)
- [X] T049 **Run the redaction gate** over every file this feature touched (`specs/004-agent-docs-runbook/guide.md`, `review_agent/README.md`, `CLAUDE.md`, `specs/001-pr-code-review-agent/quickstart.md`), before any `git add`: read `git diff --cached` line by line; no token, no key, no live host, project, repository or PR id, no 40-plus-character opaque string — including inside quoted error messages (FR-028, SC-008, gate G1-G5). A failure here stops the commit; it is not fixed by a later edit
- [X] T050 Run `python -m pytest tests` over `tests/` and confirm **532 passed** — the same number as T001 (SC-009, §4 A3)
- [X] T051 Walk `contracts/documentation-contract.md` clause by clause (D1-D5, S1-S5, F1-F5, C1-C6, R1-R10, V1-V7) and record the result; any clause that fails sends the work back to its phase rather than being noted as a limitation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: needs Setup — **blocks all four stories**. T005's conventions and T006's transcript are used by every part
- **User stories (Phases 3-6)**: each needs Foundational. Independent of each other, with two soft links: T016 cross-links to the capability part (T031-T036), and T023 cross-references T009's entry-point table. Both are links, not blockers — write the section, add the link when the target exists
- **Corrections (Phase 7)**: T037-T043 need only the C-rows, which exist now; T044 needs `guide.md` to be worth linking, so it comes after at least Phase 3
- **Polish (Phase 8)**: needs every part that will ship. T049 and T050 are the last two tasks, in that order

### Within each story

The order is the reader's order, not the writer's convenience: entry points before steps,
steps before the execution pass. **T021 is last in US1 by necessity** — you cannot mark a
command `[executed]` before the command exists.

### Parallel Opportunities

Genuine, because they touch different files:

- T003, T006, T007 — three read-only evidence captures into the scratchpad
- T037-T043 — seven corrections across three documents (four in `review_agent/README.md`, two in `CLAUDE.md`, one in `specs/001-.../quickstart.md`). The four README tasks touch different sections but the **same file**: parallel across people, serial across commits
- Whole story phases, if staffed — US1, US2, US3 and US4 write into four different sections of one file. Coordinate by section, or expect to merge

Not parallel, however it looks: any two tasks writing into the same section of `guide.md`.

---

## Implementation Strategy

### MVP first (User Story 1 only)

1. Phase 1 → Phase 2 → Phase 3
2. **Stop and validate**: give the runbook to someone who has not run the agent and watch
   them use it (SC-001). Every question they ask is a missing `symptom` or `fix` field
3. That alone is worth shipping: it retires the three blocking corrections

### Recommended order after the MVP

The phases are numbered by spec priority (US1, US2, US3, US4). The **writing** order the
plan recommends is different, and deliberate: **US1 → US4 → US2 → US3**, matching the
document's own part order (research D2). The second question anyone asks after "how do I
run it" is "what is it about to do to my pull request" — so the capability part earns its
place before the two reference parts, even at P4.

Either order satisfies the dependencies. Pick one and say which in the commit.

### Incremental delivery

| After | A reader can |
|---|---|
| Phase 3 | Run the agent by hand and post a review |
| Phase 6 | Decide whether to adopt it, without opening a source file |
| Phase 4 | Find the file that owns any behaviour |
| Phase 5 | Follow a run, and read a run that stopped early |
| Phase 7 | Trust the README again |
| Phase 8 | Tell what was proved from what was reasoned |

### Parallel team strategy

Two people is the natural size: one takes US1 and Phase 7 (they are the same subject — the
operator's experience and the front door that misleads them), the other takes US2 and US3
(one is the index of the other). US4 goes to whoever finishes first. One person merges
Phase 8, because the Verification Record has to be written by someone who knows which
commands were really run.

---

## Task Summary

| Phase | Tasks | Story |
|---|---|---|
| 1 — Setup | T001-T003 | — |
| 2 — Foundational | T004-T008 | — |
| 3 — Runbook | T009-T021 (13) | US1 (P1) 🎯 MVP |
| 4 — Structure map | T022-T026 (5) | US2 (P2) |
| 5 — Flow trace | T027-T030 (4) | US3 (P3) |
| 6 — Capabilities | T031-T036 (6) | US4 (P4) |
| 7 — Corrections | T037-T044 (8) | — |
| 8 — Polish & verification | T045-T051 (7) | — |
| **Total** | **51** | |

**Suggested MVP**: Phases 1-3 — 21 tasks, and the only slice that delivers value alone.
