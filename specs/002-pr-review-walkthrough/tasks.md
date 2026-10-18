---
description: "Task list for 002-pr-review-walkthrough"
---

# Tasks: Complete Worked Example — Create a Pull Request and Run the Review Agent

**Input**: Design documents from `/specs/002-pr-review-walkthrough/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: No automated test tasks. The spec requests none, and FR-034 makes the live verification run the test — see `contracts/verification-run.md`. The 401-test suite is a regression guard here, not a deliverable: this feature writes no code.

**Organization**: Tasks are grouped by user story. Note the honest exception recorded under Dependencies — the four stories share one continuous live run, so US1 → US2 → US4 has a real ordering that no amount of task structure removes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)

## Path Conventions

Deliverables live in `specs/002-pr-review-walkthrough/`. Captured run evidence goes to the session scratchpad and is **never committed** — it holds unredacted host names, identifiers and source excerpts.

**Out of bounds**: `review_agent/` and `tests/`. This feature changes no code. A task that edits a module has left the feature.

---

## Phase 1: Setup

**Purpose**: Create the shell the deliverable is written into, and correct the one requirement that cannot be satisfied as written.

- [X] T001 Create `specs/002-pr-review-walkthrough/example-files/` and a `walkthrough.md` skeleton carrying the 13 section headings in order from `contracts/walkthrough-structure.md`, each section empty
- [X] T002 Amend FR-011 in `specs/002-pr-review-walkthrough/spec.md` to the locatability-based wording given in `plan.md` § Spec Amendments, keeping the original severity-based intent as a parenthetical note for when a threshold is introduced
- [X] T003 [P] Create an evidence folder in the session scratchpad for captured run output, and confirm it is outside the repository so nothing captured can be committed by accident

**Checkpoint**: Skeleton exists, FR-011 is satisfiable, evidence has somewhere to land.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Close the two open research items and pass the run gate. Nothing in any user story can be written or verified until these hold.

**⚠️ CRITICAL**: T005 blocks all example-file work. T006 blocks every live run — the agent cannot start until a human fixes `.env`.

- [X] T004 Close research R1: list `TFS_REPO_CODE_SAMPLE` on its default branch, apply the plurality rule from `research.md` (Python if empty or mixed), and record the chosen language and which branch of the rule applied in `specs/002-pr-review-walkthrough/research.md`
- [X] T005 [P] Close research R6: list the sample repository's branches and the project's work items for artifacts left by earlier demonstrations, and record in `specs/002-pr-review-walkthrough/research.md` whether teardown needs a warning about pre-existing leftovers
- [X] T006 Pass the configuration gate in `contracts/verification-run.md`: run `python review_agent/main.py --dry-run --pr <id>` and confirm it reaches past validation. If it reports `LLM_PROVIDER is required`, stop and have a human apply the gap G5 corrections to `.env` — **this feature does not edit `.env`**. Also confirm `LLM_BASE_URL` is set (`config.py:374`), which 001's quickstart omits
- [X] T007 Confirm `python -m pytest tests -q` reports 401 passing, and record the agent version from `python review_agent/main.py --version` for FR-033

**Checkpoint**: Language fixed, naming scheme fixed, agent starts, baseline recorded.

---

## Phase 3: User Story 1 — Stand up the sample pull request from given artifacts (Priority: P1) 🎯 MVP

**Goal**: An operator with no prior exposure produces a linked work item and pull request containing every labelled fault, inventing nothing.

**Independent Test**: Perform stage 1 of `contracts/verification-run.md` following only sections 4–6 of the walkthrough. Every point where the author must decide something the document does not specify is a defect logged and fixed (SC-002). No agent run is needed.

### Writing the artifacts

- [X] T008 [P] [US1] Write walkthrough section 2 "Before you start" in `specs/002-pr-review-walkthrough/walkthrough.md` — access rights, tooling, the full required-variable set from research R3, the outstanding `.env` corrections, and the single command that confirms all of it at once (FR-004, FR-005)
- [X] T009 [P] [US1] Write walkthrough sections 1 and 3 in `specs/002-pr-review-walkthrough/walkthrough.md` — what the walkthrough demonstrates, that the agent is a reviewer aid not a merge gate, the time to budget, and the notice that source code and work-item content leave the network, placed before anything is created (FR-006)
- [X] T010 [US1] Write walkthrough section 4 "The sample work item" in `specs/002-pr-review-walkthrough/walkthrough.md` — title, description and four acceptance criteria verbatim, naming which criterion is left unimplemented and which is contradicted, with the naming suffix from research R6 (FR-007, FR-008, FR-013)
- [X] T011 [US1] Write the example files into `specs/002-pr-review-walkthrough/example-files/` in the language fixed by T004, implementing every acceptance criterion except the unimplemented one, and conflicting with the contradicted one (FR-009, FR-009c; design from research R4)
- [X] T012 [US1] Write walkthrough section 5 "The sample change" in `specs/002-pr-review-walkthrough/walkthrough.md` — where the example files are, what each fault is, and the fault-to-finding table per `contracts/expected-results.md`, leaving the availability column unfilled until Phase 4 (FR-009a, FR-009b, FR-010)
- [X] T013 [US1] Write walkthrough section 6 "Create the pull request" in `specs/002-pr-review-walkthrough/walkthrough.md` — branch, commit, open, link in order; the screen and control for each web step; what success looks like at each; the PR title and description verbatim including the false coverage claim; and that the work-item link is required and what its absence costs (FR-012, FR-015, FR-016, FR-017, FR-018)

### Verifying the story

- [X] T014 [US1] Perform stage 1 of `contracts/verification-run.md` — create the work item, branch, commit, pull request and link by following sections 4–6 only, logging every point where the document was insufficient to the scratchpad evidence folder
- [X] T015 [US1] Fix every insufficiency logged in T014 in `specs/002-pr-review-walkthrough/walkthrough.md` and, where the fault design was wrong rather than the prose, in `specs/002-pr-review-walkthrough/example-files/`

**Checkpoint**: A sample pull request exists that is known to contain the planted faults, produced by following the document alone. US1 is deliverable on its own — another reviewer can use this PR without any of the run sections existing.

---

## Phase 4: User Story 2 — Run the agent and confirm the run matched (Priority: P1)

**Goal**: The operator runs preview then post, and can tell from the document whether their run matched.

**Independent Test**: Against the pull request from Phase 3, follow sections 7–10 alone. Every finding observed is traceable to a planted fault, and the posting step puts comments on the pull request.

### Performing the run

- [X] T016 [US2] Perform stage 2 of `contracts/verification-run.md` — run `python review_agent/main.py --dry-run --pr <sample-pr-id>`, capturing full console output, the observed exit status, and which findings appeared inline versus summary-only, to the scratchpad evidence folder
- [X] T017 [US2] Perform stage 3 — run `python review_agent/main.py --post --pr <sample-pr-id>`, capturing console output, exit status, the file and line each inline comment landed on, and confirmation that exactly one summary comment exists
- [X] T018 [US2] Perform stage 4 — run the posting command again unchanged, capturing that the comment count is identical and how the console reported the repeat findings
- [ ] T019 ⚠️ **NOT RUN** (meaningless while finding identity depends on provider wording — see research R8) — [P] [US2] Perform stage 5 — push a whitespace-only commit that shifts line numbers, post again, and capture whether comments are still not duplicated. If skipped, record it as not performed rather than implying it passed (FR-035)

### Writing the run sections

- [X] T020 [US2] Write walkthrough section 7 "Preview the review" in `specs/002-pr-review-walkthrough/walkthrough.md` — the exact command, what output confirms success, the expected exit status, and the preview checkpoint list. Document exit statuses `0`, `1`, `2` only; **do not document `3`** — `EXIT_DEGRADED` is never returned (`errors.py:26`, `main.py:343-346`) (FR-019, FR-022, FR-023)
- [X] T021 [US2] Write walkthrough section 8 "What you should see" in `specs/002-pr-review-walkthrough/walkthrough.md` from captured output only, filling every column of the expected-results reference including the availability state, and listing checklist findings as `expected-absent` with the gap G1 reason rather than omitting them (FR-021, FR-026, FR-035, SC-009)
- [X] T022 [US2] Write walkthrough sections 9 and 10 in `specs/002-pr-review-walkthrough/walkthrough.md` — the posting command and what it makes visible, where to look in the pull request to confirm file and line placement and the single summary comment, and the repeat run as a required step with how to confirm it added nothing (FR-020, FR-024, FR-025)
- [X] T023 [US2] Verify against `contracts/expected-results.md` that no entry claims `observed` for a finding the run did not produce, that at least one entry is `summary-only`, and that no checkpoint asks the reader to confirm output the agent does not produce — specifically that 001's `.review-reports/` checkpoint is absent (FR-026a, FR-035)

**Checkpoint**: The run is reproducible and checkable. US1 + US2 together are the whole demonstration; everything after this is recovery and hygiene.

---

## Phase 5: User Story 3 — Recover when the run does not match (Priority: P2)

**Goal**: A reader whose run deviates resolves it from the document without asking anyone.

**Independent Test**: Deliberately introduce each documented deviation — omit the work-item link, skip the `.env` fix, target an abandoned pull request — and confirm the document names the symptom and resolves it.

- [X] T024 [US3] Write walkthrough section 11 "When it does not match" in `specs/002-pr-review-walkthrough/walkthrough.md` as a symptom reference with symptom, cause, fix and resume-from step, built from the deviations logged during T014 and T016–T019 plus the failures reachable from the document's own steps (FR-027)
- [X] T025 [US3] Classify every symptom-reference entry as `setting`, `transient` or `expected-today` per `data-model.md`, and state "no action needed" on every `expected-today` entry — the checklist-source warning is the one a first-time reader will certainly hit and misread as failure (FR-028)
- [X] T026 [US3] Verify the symptom reference by deliberately omitting the work-item link on a scratch run and confirming the document names the symptom and the cost, per the story's independent test

**Checkpoint**: A deviating reader has somewhere to go.

---

## Phase 6: User Story 4 — Leave nothing behind (Priority: P3)

**Goal**: Every artifact the walkthrough created is reversed, and the teardown steps are confirmed to work rather than assumed.

**Independent Test**: Run the teardown section against the completed walkthrough and confirm by inspection that the sample repository is back to its prior state.

- [X] T027 [US4] Write walkthrough section 12 "Clean up" in `specs/002-pr-review-walkthrough/walkthrough.md` — abandon the pull request with an explicit statement that it is never completed, delete the branch, retire the work item, and remove local artifacts containing copied source; note that pre-existing artifacts found in T005 are not this walkthrough's to remove (FR-029, FR-030)
- [ ] T028 ⏸️ **DEFERRED by decision, 2026-09-15** (artifacts intentionally retained — see Retained artifacts below) — [US4] Perform stage 6 of `contracts/verification-run.md` by following section 12 as written, capturing whether each step worked and anything the section missed
- [ ] T029 ⏸️ **DEFERRED by decision, 2026-09-15** (artifacts intentionally retained — see Retained artifacts below) — [US4] Fix anything T028 revealed in `specs/002-pr-review-walkthrough/walkthrough.md`, and confirm by inspection that the sample repository and the local machine hold no artifact the walkthrough created (SC-008)

**Checkpoint**: The demonstration is repeatable because it left nothing to collide with.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: The safety scan, the links, and the provenance that make the document trustworthy and findable. T030 is the one task in this feature most likely to matter.

- [X] T030 Run the redaction scan from `contracts/verification-run.md` over `specs/002-pr-review-walkthrough/walkthrough.md` and `specs/002-pr-review-walkthrough/example-files/` — no credential, token, base URL, collection, project name, repository name, pull request id, work item id, or account name, and every placeholder visibly distinguishable from a literal value (FR-031, SC-006)
- [X] T031 Write walkthrough section 13 "Provenance" in `specs/002-pr-review-walkthrough/walkthrough.md` — the date last verified, the agent version from T007, and the source of each quoted command, message and exit status per the table in `contracts/walkthrough-structure.md` (FR-032, FR-033)
- [X] T032 [P] Replace Part 2 of `specs/001-pr-code-review-agent/quickstart.md` with a pointer to the walkthrough, leaving Part 1 untouched and authoritative for operator setup (FR-003, FR-003a)
- [X] T033 [P] Add a link to the walkthrough in `review_agent/README.md` (FR-002)
- [X] T034 [P] Add a link to the walkthrough in `CLAUDE.md` inside the SPECKIT markers, alongside the existing plan pointer (FR-002)
- [X] T035 Verify the finished document against every row of `contracts/walkthrough-structure.md` — all 13 sections present in order, placement rules held, content rules held, and no reference to `--inline-threshold`, `--report-dir`, or exit status `3`
- [X] T036 Confirm `python -m pytest tests -q` still reports 401 passing and `git status` shows no change under `review_agent/` or `tests/` — the guard that catches a stray edit before it is attributed elsewhere

---

## Retained artifacts — cleanup still owed

Teardown (T028, T029) was **deliberately deferred on 2026-09-15**: the sample pull
request is being kept for inspection, not forgotten. These exist in
`TFS_REPO_CODE_SAMPLE` and its project until someone removes them:

| Artifact | Identifier |
|---|---|
| Pull request (active, 9 inline + 1 summary comment) | **47742** |
| Branch | `sample/pr-review-walkthrough-20260915` |
| Work item (User Story, linked to the PR) | **320312** |

**Nothing here is to be merged.** Walkthrough section 12 has the teardown steps; running
them closes T028 and T029.

Note for whoever tears down: 4 of the 9 inline comments are duplicates produced by the
defect in research R8. That is the evidence for it — capture anything needed from the
pull request before abandoning it.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Blocks everything. T005 blocks all example-file work; T006 blocks every live run
- **US1 (Phase 3)**: After Phase 2
- **US2 (Phase 4)**: After Phase 3 — needs the pull request T014 creates
- **US3 (Phase 5)**: Drafting can start after Phase 2; completion needs the deviation log from T014 and T016–T019
- **US4 (Phase 6)**: After Phase 4 — teardown removes what the run used
- **Polish (Phase 7)**: After all stories

### The honest exception

The template assumes user stories are independently deliverable. Here they share **one continuous live run against one pull request**, so US1 → US2 → US4 is a real ordering, not a staffing preference. US1 creates the pull request, US2 consumes it, US4 destroys it. Only US3 can be genuinely parallelised, and only its drafting.

Each story remains independently *testable* — its independent-test criterion stands alone — but they are not independently *runnable* against separate artifacts without repeating setup and spending more analysis calls.

### Within each story

- Write the sections, then perform the run stage that tests them, then fix what the run revealed
- The expected-results section (T021) is written from captured output only, never from reading the code

### Parallel Opportunities

- T004 and T005 — two independent lookups
- T008 and T009 — different sections, no shared content
- T019 — the line-drift stage is independent of the section writing
- T032, T033, T034 — three different files, no shared content
- US3 drafting (T024, T025) can proceed alongside Phase 4 once the deviation log has entries

---

## Implementation Strategy

### MVP — stop here and you have something

**Phases 1, 2 and 3.** A reproducible sample pull request containing known faults, produced by following a document that has been proven sufficient by someone actually following it. Another reviewer can use that pull request to exercise the agent even if no run section exists yet.

### Full demonstration

Add **Phase 4**. US1 + US2 is the whole product of this feature: a complete example that someone can follow end to end and check their own results against.

### Production-ready

Phases 5–7. Recovery for readers whose environment differs, teardown so demonstrations do not accumulate, and the redaction scan without which this document is a liability rather than an asset.

### Where this most likely goes wrong

1. **T006 — the `.env` gate.** The agent cannot start as shipped. If a human does not apply the gap G5 corrections, every live task blocks and nothing after Phase 2 can be done.
2. **T021 — writing predictions as observations.** The temptation is to fill the expected-results table from reading `output_layer.py` rather than from captured output. FR-035 exists because that is the failure that makes the document confidently wrong.
3. **T030 — the redaction scan.** The only defect here that is actively harmful rather than merely unhelpful, and it arrives by copy-paste rather than by reasoning.
4. **Research R4's risk.** Both findings come from provider judgement, not a deterministic rule. If the contradiction finding does not reproduce in T016, the sample is redesigned and the run repeated — it is not written up as though it had appeared.
