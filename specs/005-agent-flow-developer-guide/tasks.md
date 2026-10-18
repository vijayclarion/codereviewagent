---

description: "Task list for 005-agent-flow-developer-guide"
---

# Tasks: Local-Mode Call Flow Diagram and Developer Onboarding Guide

**Input**: Design documents from `/specs/005-agent-flow-developer-guide/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: No test tasks. This feature writes no code; the suite is a **guard**, not a
deliverable — `python -m pytest tests` must report **532 passed** before the first task and
after the last (SC-009, FR-034). Adding a test means you have left the feature.

**Organization**: by user story, so each part of the deliverable can be written and judged on
its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallel-safe — a *different file* from every other task running with it
- **[Story]**: US1–US6, matching spec.md's priorities
- Every task names its file path and the contract clauses or Ledger rows it closes

## Why `[P]` works here, and where it stops

Unlike 004, this feature has **two** deliverable files, so the diagram and the guide are
genuinely parallel — **but only after Phase 2**. Both render the same Flow Ledger (research
**D1**), so writing them against an unfrozen Ledger reintroduces exactly the drift the Ledger
exists to prevent. Phase 2 freezes it; after that, US1 (`.puml`) runs alongside any guide
phase.

Inside the guide, sections share one file, so guide phases are **sequential with each other**
even though each is independent in content. See [Parallel Opportunities](#parallel-opportunities).

## Path Conventions

- **The deliverables**: `docs/local-mode-pr-review-activity.puml`, `docs/developer-guide.md`
- **Planning artifacts** (may be corrected in place): `specs/005-agent-flow-developer-guide/**`
- **Scratch** (never committed): the session scratchpad directory
- **Forbidden**: `review_agent/*.py`, `tests/**` — FR-034, gate G2

---

## Phase 1: Setup

**Purpose**: Establish the baseline the whole feature is measured against, and extract the
raw lists the later phases fill in. Nothing here is written to a deliverable.

- [X] T001 Record the opening baseline in the scratchpad: run `python -m pytest tests` (**not** `-q`) and `git status --short`, and note the commit. Expect `532 passed` and no entry under `review_agent/` or `tests/`. This is gate G1/G2's "before" reading
- [X] T002 [P] Create the empty deliverable directory `docs/` if absent, and confirm it holds nothing else that this feature would displace
- [X] T003 [P] Extract the complete shipped-path list into the scratchpad — every file and directory that ships, generated from the tree, not from memory. This is the raw material for SC-004's 100% check and for `FileEntry` in [data-model.md](./data-model.md#fileentry)
- [X] T004 [P] Capture a fresh offline demo transcript to the scratchpad: `python -m tests.demo.run`. Every log line and rendered summary quoted in either deliverable must come from this capture (contract **S6.2**), so capture it once and quote from the file

**Checkpoint**: baseline recorded, raw lists in hand, no deliverable touched yet.

---

## Phase 2: Foundational — freeze the Flow Ledger

**Purpose**: Produce the single description both deliverables render.

**⚠️ CRITICAL**: No US1–US6 task may begin until this phase is complete. Writing either
deliverable against an unfrozen Ledger is the defect research **D1** exists to prevent.

- [X] T005 Expand the twelve-stage Flow Ledger in `specs/005-agent-flow-developer-guide/plan.md` to full `MethodRole` granularity — for each stage, every method in call order with its one-line role, per [data-model.md](./data-model.md#methodrole). The stage names and log lines already there are 004's and must not be reworded (**S2.3**)
- [X] T006 Verify the `input`/`output` chain: the `input` of stage *n* equals the `output` of stage *n−1*, or the mismatch is explained in the Ledger. Closes the `Stage` validation rule that FR-011 depends on
- [X] T007 Write the fourteen `DecisionPoint` records (`D-A`–`D-N`) into `specs/005-agent-flow-developer-guide/plan.md` beneath the Ledger: condition, branches, each branch's label, **signal** and **destination**, and the 004 fork identifier (`A1`–`A9`) where one exists. Every branch must have a destination — FR-005, and the clause most likely to fail review
- [X] T008 Run the G3 pre-check against the Ledger in `specs/005-agent-flow-developer-guide/plan.md`: extract every `file.method` pair and assert each resolves under `review_agent/` in the current tree. Fixing a name now is cheap; fixing it after it is in two deliverables is not
- [X] T009 [P] Fill the `ContextSource` (4), `ReviewBlindSpot` (5), `SizeLimit` (7) and `FailureMode` (7) record tables into `specs/005-agent-flow-developer-guide/data-model.md` from the Boundary Register, carrying each row's anchor and `[executed]`/`[read]` basis forward unchanged
- [X] T010 [P] Walk the [Delegation Map](./plan.md#delegation-map) row by row and mark each as *link*, *extend* or *write fresh* in the scratchpad, with the exact 004 section to cite for every *link* row. Contract **S2.1** makes this the check performed before each paragraph — having the citations ready is what makes that practical

**Checkpoint**: the Ledger is frozen and every method in it resolves. US1–US6 may now begin, and US1 may run alongside any of them.

---

## Phase 3: User Story 1 — The activity diagram (Priority: P1) 🎯 MVP

**Goal**: One PlantUML activity diagram from which a developer can state where a run begins,
the stages it passes, and where it can diverge — without reading any prose.

**Independent Test**: Hand `docs/local-mode-pr-review-activity.puml` to a developer with a
PlantUML renderer and nothing else. They render it unedited and correctly state the start,
the stage count, and three or more decision points.

- [X] T011 [US1] Create `docs/local-mode-pr-review-activity.puml` with the file skeleton per contract **C1**: one `@startuml`/`@enduml` pair, **modern activity syntax only** (`start` / `:action;` / `if…endif` / `stop`), no `!include`, no remote `!theme`, plain ASCII. The legacy `(*) -->` form is forbidden — it needs Graphviz, which is absent here (**D2**, **E4**)
- [X] T012 [US1] Add the twelve Ledger stages to `docs/local-mode-pr-review-activity.puml`, once each, in execution order, **each node naming its owning file** (**C2.1**, **C2.2**; FR-003, FR-004)
- [X] T013 [US1] Add the entry-point fork at stage 0 to `docs/local-mode-pr-review-activity.puml` — `--local`, already-bootstrapped, and fetch — showing where the paths rejoin at stage 1 (**C2.5**; FR-006)
- [X] T014 [US1] Add the remaining thirteen decision points to `docs/local-mode-pr-review-activity.puml` as `if`/`else` constructs, every branch labelled and every branch reaching `stop`, `end` or a named stage. Carry the `A1`–`A9` identifiers in the labels where they apply (**C2.3**, **C2.4**, **C3.4**; FR-005)
- [X] T015 [US1] Show the reductions as flow in `docs/local-mode-pr-review-activity.puml`: files leaving the path at exclusion and at the bound (stages 6–7), and the split into *N* passes at stage 9 (**C2.6**; FR-007)
- [X] T016 [US1] Show at stage 9 of `docs/local-mode-pr-review-activity.puml` what is assembled into the request — diff, story, scope, rules — visibly distinguished from what stage 6 retrieved and did **not** send (**C2.7**; FR-029). This is US4's subject drawn rather than written
- [X] T017 [US1] Add the three exit-code terminals and the header note to `docs/local-mode-pr-review-activity.puml`: the exact command the diagram depicts, and a pointer to `docs/developer-guide.md` for method-level detail (**C2.8**, **C3.3**; FR-008)

**Checkpoint**: the diagram stands alone. It is the MVP — a reader with only this file gets the flow.

---

## Phase 4: User Story 2 — The method-by-method walkthrough (Priority: P1)

**Goal**: Behind every box in the diagram, the methods that run, in which file, what they
receive and hand on, and the line the run prints.

**Independent Test**: Give a reader five plain-language behaviours of the agent. Using only
the guide they name the stage, the file and the method for each, and every method named is
confirmed to exist.

- [X] T018 [US2] Create `docs/developer-guide.md` with section 0 — what this is, who it is for, the **one-sentence** answer to "changes only or whole project", and what to read in 004 instead (**S1** §0; FR-009, FR-021)
- [X] T019 [US2] Write section 1 of `docs/developer-guide.md`, "The flow at a glance": embed or link the diagram, give the render command verbatim, note that **Graphviz is not required** for this syntax, and list the twelve stages as a table (**S1** §1, diagram contract's render instruction)
- [X] T020 [US2] Write section 2 of `docs/developer-guide.md`, one subsection per stage: methods in call order with one-line roles, input, output, and the log line quoted from T004's capture (**S1** §2; FR-010, FR-011, FR-012)
- [X] T021 [US2] Verify no `role` line in section 2 of `docs/developer-guide.md` merely re-spells its method's name — the `MethodRole` validation rule. `_fetch_story` "fetches the story" fails; it recovers linked work items *and the reason when there are none, so a token without Work Items access loses the story half loudly instead of failing the run*
- [X] T022 [US2] Write section 3 of `docs/developer-guide.md`, "Where the path forks": the fourteen decision points with condition, **signal**, destination, and the 004 cross-reference where one exists; state plainly which five are new here so a reader does not go hunting for them in 004 (**S1** §3; FR-013)
- [X] T023 [US2] Cross-check section 2 and section 3 of `docs/developer-guide.md` against `docs/local-mode-pr-review-activity.puml`: two-way set comparison, twelve stages each way and fourteen decisions each way (diagram contract self-check item 6). A stage in one and not the other is the drift **D1** exists to prevent
- [X] T024 [US2] Run gate **G3** over `docs/developer-guide.md`: extract every `file.method` named and assert each resolves in the tree at the stated commit. By extraction, not by eye (**S3.5**)

**Checkpoint**: a developer can follow any box in the diagram into the code.

---

## Phase 5: User Story 3 — What every file is for (Priority: P2)

**Goal**: Every shipped path, tied to the stage it serves, with the rule that constrains it.

**Independent Test**: Name any file that ships. The reader states its purpose and whether a
rule constrains changes to it, without opening it.

- [X] T025 [US3] Write section 7 of `docs/developer-guide.md`, "Where everything lives", grouping the T003 path list **by the stage each file serves** — not alphabetically. The alphabetical cut already exists in 004 Part 3 and must not be reproduced (**D5**, FR-032)
- [X] T026 [US3] Cite each module's one-line purpose in section 7 of `docs/developer-guide.md` **to 004 Part 3** rather than rewriting it; anchor the citation to 004's section, not to the code (**S2.2**)
- [X] T027 [US3] Mark every path that serves no stage explicitly as `stage: none` in section 7 of `docs/developer-guide.md`. An omitted file and a file that takes no part must not look the same (FR-014)
- [X] T028 [US3] Bind the five architecture invariants to the stages they constrain in section 7 of `docs/developer-guide.md`, naming the enforcing test for each. Link 004's statement of the rule; add only the stage binding (**S2.1**; FR-015)

**Checkpoint**: SC-004's 100% coverage is verifiable by comparing section 7 against T003's list.

---

## Phase 6: User Story 4 — What the reviewer can see (Priority: P2)

**Goal**: The answer to the question that decides whether a reader trusts any finding.

**Independent Test**: Give a reader four proposed checklist rules, some answerable from a
changed region alone and some needing unchanged code elsewhere. They sort all four correctly.

- [X] T029 [US4] Write section 4 of `docs/developer-guide.md` opening with the answer in **one sentence** before any elaboration, then the diff shape: **three lines** of context each side of a hunk, stated as a number (**S4.1**, **S4.2**; FR-021, FR-022)
- [X] T030 [US4] State the two exceptions in section 4 of `docs/developer-guide.md`: a newly **added** file diffs against empty so effectively all of it is shown; an **untouched** file is neither fetched nor sent (**S4.3**, **S4.4**; FR-022, FR-023)
- [X] T031 [US4] State the fetched-versus-sent distinction in section 4 of `docs/developer-guide.md`: both complete blobs are retrieved to compute the diff locally, and only the diff reaches the request (**S4.5**; FR-025). This is the row the `ContextSource.withheld` field exists for
- [X] T032 [US4] List the four context sources in section 4 of `docs/developer-guide.md` with what each contributes and what a run says when one is missing, and state what a split pass sees of the others — quoting the chunk warning the prompt carries (**S4.6**; FR-024, FR-026)
- [X] T033 [US4] Write the blind-spot subsection of section 4 in `docs/developer-guide.md`: the five classes with concrete examples — an unchanged caller, a base class, a project-wide convention — plus the fact that a finding which cannot be anchored is **routed to the summary, not dropped** (**S4.7**, **S4.8**; FR-027)
- [X] T034 [US4] Close section 4 of `docs/developer-guide.md` with why the boundary is deliberate, so it reads as a boundary and not a bug — and confirm **no assembled prompt from a real run appears anywhere in the section** (**S4.9**, **S4.10**; FR-028, FR-035, **D6**)

**Checkpoint**: a reader can predict which findings this tool is in a position to make.

---

## Phase 7: User Story 5 — A very large change (Priority: P2)

**Goal**: What a huge pull request actually gets reviewed, chosen how, and what happens to the rest.

**Independent Test**: Describe a pull request of a stated large size. The reader states how
much is reviewed, what happens to the remainder, and how many provider passes it takes.

- [X] T035 [US5] Write section 5 of `docs/developer-guide.md` as an **ordered pipeline** of the seven reductions — skip, exclude, rank, file bound, line bound, rule budget, split — not an alphabetical settings table (**D8**; FR-016)
- [X] T036 [US5] Give each row in section 5 of `docs/developer-guide.md` its default and its setting, and state the ranking weights and the tie-break explicitly. "Most relevant first" is unfalsifiable; the smallest-first tie-break is what makes the bound cover more files (`SizeLimit` validation)
- [X] T037 [US5] State where each reduction is **reported** in section 5 of `docs/developer-guide.md`, quoting real output — the `### Not sent for review` table, a `RunInventory.reductions` line, `chunks=N` — from T004's capture. "Reported in the summary" fails (**D9**)
- [X] T038 [US5] State in section 5 of `docs/developer-guide.md` what the split respects, what each part is told about the others, and what happens to a **single file larger than the split size** — it goes alone, oversized, by design (**B2.1**; FR-017)

**Checkpoint**: a reader can predict the review of a pull request they have not run yet.

---

## Phase 8: User Story 6 — When a model limit is exceeded (Priority: P3)

**Goal**: The least guessable behaviour in the project, stated plainly.

**Independent Test**: Ask what the tool does when a request exceeds the model's limit. The
reader states the outcome, what is lost, and the exit code — and each matches the code.

- [X] T039 [US6] Open section 6 of `docs/developer-guide.md` with the plain statement that **nothing measures a request against the model's limit** before sending, and that the package's only token estimator is called from nowhere (**S5.1**, **S3.4**; FR-020)
- [X] T040 [US6] State in section 6 of `docs/developer-guide.md` that splitting bounds **changed diff lines**, and that story, scope and rules repeat in **every** chunk — so splitting shrinks the variable part of a request and not the fixed part (**S5.2**; FR-017)
- [X] T041 [US6] Write the provider-rejection path in section 6 of `docs/developer-guide.md`: it degrades the **whole run**, discarding findings from chunks already parsed; notice on the pull request; `phase=llm outcome=degraded`; **exit 0** (**S5.3**, **S5.4**; FR-018)
- [X] T042 [US6] Separate request limits from the **answer** cap in section 6 of `docs/developer-guide.md`, noting the 4096-token cap applies to one provider only, and give the truncated-answer path: invalid JSON → **one** stricter retry → degraded (**S5.5**, **S5.6**; FR-019)
- [X] T043 [US6] Close section 6 of `docs/developer-guide.md` with the retried-versus-fatal status table, attempt counts and exit codes, and the settings that **actually** reduce request size — without implying a token budget exists (**S5.7**, **S5.8**; FR-020)

**Checkpoint**: all six stories complete. Both deliverables exist and are content-complete.

---

## Phase 9: Polish, verification and the record

**Purpose**: The gates, and the honesty apparatus that makes this document checkable rather
than trusted.

- [X] T044 Write section 8 of `docs/developer-guide.md`, the Verification Record: what was executed and on what date, what was read, and every `[unobserved]` claim **with its closing condition**. No exceptions — this is the shape of gap G4, which this project has already paid for once (**S3.2**, **S3.3**; FR-031)
- [X] T045 Carry correction **005-C1** into section 8 of `docs/developer-guide.md` as the first row: `CLAUDE.md` called 004's `guide.md` "not yet written" when it is written; corrected during planning. Add any further disagreement found while writing (**S2.4**; FR-033)
- [X] T046 Audit every behavioural statement in `docs/developer-guide.md` for a `ClaimAnchor` and a `[executed]`/`[read]`/`[unobserved]` marker. An unmarked claim is a claim a reader cannot check (**S3.1**, **S3.2**; FR-030)
- [X] T047 Run the diagram's structural self-check over `docs/local-mode-pr-review-activity.puml` — all seven items from [contracts/diagram-contract.md](./contracts/diagram-contract.md#structural-self-check) — and record the result in section 8 of `docs/developer-guide.md` as `[read]`
- [X] T048 Attempt gate **G4**: if `plantuml.jar` can be obtained, render `docs/local-mode-pr-review-activity.puml` and record the result as `[executed]`. If it cannot, record rendering as `[unobserved]` with its closing condition. **Do not** use the installed Python `plantuml` package — it posts to a remote server and would send the flow off-machine (**D3**)
- [X] T049 [P] Run gate **G5** over both files in `docs/`: test every `.env` value for presence **without printing any**. Expect only the benign matches already recorded at planning — the public provider identifier and a repo name that is a substring of its own variable name (FR-035)
- [X] T050 [P] Run gate **G2**: `git status --short` shows no entry under `review_agent/` or `tests/`. This is what proves FR-034 held (SC-009)
- [X] T051 Run gate **G1**: `python -m pytest tests` (**not** `-q`) reports **532 passed**, matching T001's baseline
- [X] T052 Walk the seven acceptance clauses in [contracts/guide-contract.md](./contracts/guide-contract.md#acceptance) and confirm sections 4, 5 and 6 of `docs/developer-guide.md` each answer their question **in the first sentence** before elaborating (**S1.1**)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies — start immediately
- **Phase 2 (Foundational)**: depends on T003 and T004 — **BLOCKS every user story**
- **Phase 3 (US1)**: after Phase 2. Runs **in parallel with Phases 4–8** (different file)
- **Phases 4–8 (US2–US6)**: after Phase 2. **Sequential with each other** — one file
- **Phase 9 (Polish)**: after every story phase whose output it verifies

### User Story Dependencies

- **US1 (P1)** — independent. The MVP; needs only the frozen Ledger
- **US2 (P1)** — independent in content; T023 cross-checks against US1's file, so it lands after T017
- **US3 (P2)** — independent. Needs T003's path list
- **US4 (P2)** — independent in the guide. T016 draws the same subject in the diagram and belongs to US1
- **US5 (P2)** — independent. Reads most naturally after US4, since the limits act on what US4 describes
- **US6 (P3)** — independent, and the one that can be dropped without breaking the rest

### Within each story

- The section's opening sentence is written before its elaboration (**S1.1** is a structural rule, not a stylistic one)
- Content before cross-checks; cross-checks before gates

---

## Parallel Opportunities

**Genuine [P] tasks**: T002, T003, T004 (Phase 1, three different scratch outputs) · T009,
T010 (Phase 2, different files) · T049, T050 (Phase 9, read-only gates).

**The real parallelism is at phase level.** Once Phase 2 closes, one person can write the
entire diagram (Phase 3) while another writes the guide (Phases 4–8) — two files, no
contention. That is the whole benefit of the two-file shape, and it is available only because
the Ledger was frozen first.

**Where it stops**: the guide is one file. US2 through US6 cannot be written concurrently by
different people without conflict, regardless of how independent their content is. This is a
real constraint of the chosen shape, not an oversight.

### Parallel example — after Phase 2

```bash
# Developer A — the diagram
T011 → T012 → T013 → T014 → T015 → T016 → T017

# Developer B — the guide, concurrently
T018 → T019 → T020 → T021 → T022 → T025 … → T043

# Rejoin: T023 (cross-check) needs T017; Phase 9 needs both
```

---

## Implementation Strategy

### MVP — stop here and you have delivered something

**Phases 1–3.** The diagram alone answers the request's first and loudest ask, and a reader
with only `docs/local-mode-pr-review-activity.puml` can see the whole flow. Every later phase
adds depth behind a picture that already stands.

### Incremental delivery

1. **Phases 1–3** → the diagram. Shippable.
2. **+ Phase 4** → a developer can follow any box into the code. This is the point the feature
   meets its stated goal — *another developer can start working*.
3. **+ Phases 6–7** → the two questions nothing in the project answers. Highest value per
   paragraph of anything here; **prefer these over Phase 5 if time runs short** (**S1.1**).
4. **+ Phase 5** → the file map. Partly served by 004 already, which is why it yields.
5. **+ Phase 8** → the model-limit section.
6. **+ Phase 9** → the gates and the Verification Record. **Not optional**: a document whose
   claims are unmarked is the failure mode this project has already paid for once.

### Three ways to lose a day

Repeated from [quickstart.md](./quickstart.md) because they are what actually goes wrong:

- **Re-documenting 004.** Check the Delegation Map before every paragraph. T010 prepares the
  citations so that check costs seconds.
- **Writing the diagram and the guide separately.** Both render the Ledger. T023 catches the
  drift, but catching it late means rewriting both.
- **Claiming the diagram renders.** No renderer is available offline here. T048 records the
  honest outcome either way.

## Task Summary

| Phase | Story | Tasks | Count |
|---|---|---|---|
| 1 — Setup | — | T001–T004 | 4 |
| 2 — Foundational | — | T005–T010 | 6 |
| 3 — Diagram | US1 (P1) | T011–T017 | 7 |
| 4 — Walkthrough | US2 (P1) | T018–T024 | 7 |
| 5 — File map | US3 (P2) | T025–T028 | 4 |
| 6 — What it can see | US4 (P2) | T029–T034 | 6 |
| 7 — Large change | US5 (P2) | T035–T038 | 4 |
| 8 — Model limits | US6 (P3) | T039–T043 | 5 |
| 9 — Polish & gates | — | T044–T052 | 9 |
| **Total** | | | **52** |
