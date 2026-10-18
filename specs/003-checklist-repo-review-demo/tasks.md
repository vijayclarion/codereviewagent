---
description: "Task list for 003-checklist-repo-review-demo"
---

# Tasks: Checklist-Document Reviews from a Cloned Checklist Repository, with a Full-Cycle Demo

**Input**: Design documents from `/specs/003-checklist-repo-review-demo/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Included, and not optional here. This repository has a 401-test suite that is the
only thing holding five architecture invariants, and the four contracts in `contracts/` are
written as clauses a test asserts. `quickstart.md` states the rhythm: the failing test
first, for the right reason.

**Organization**: By user story. Read the plan's **Survey Findings** table before starting —
three complete, tested components are already in the package and connected to nothing, and
most tasks below are wiring rather than building.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1–US4, mapping to the user stories in spec.md

## Path Conventions

Single Python package at the repository root: `review_agent/`, `tests/`. The documentation
deliverable and its deliberately faulty sample code live under
`specs/003-checklist-repo-review-demo/`, which `pytest` never collects.

---

## Phase 1: Setup

**Purpose**: Establish the baseline and resolve the two research items that need the live
environment.

- [X] T001 Run `python -m pytest tests -q` and record the passing count in `specs/003-checklist-repo-review-demo/research.md` under a new "Baseline" note. If it is not green on arrival, stop and find out why before editing anything
- [X] T002 [P] Resolve research R10's open half: the checklist repository's default branch and folder layout. Record the answer in `specs/003-checklist-repo-review-demo/research.md` R10. *Requires the live collection*
- [X] T003 Resolve research R10's other open half: whether the sample repository still holds feature 002's demonstration artifacts, and fix this run's naming suffix accordingly. Record in `specs/003-checklist-repo-review-demo/research.md` R10. *Requires the live collection*
- [X] T004 Write the prerequisite probe — a read-only command sequence that confirms `TFS_API_VERSION`, the PAT's Code (read) and Work Items (read) scopes, and git availability in one pass — into `specs/003-checklist-repo-review-demo/demo-files/preflight.md`. Do **not** edit `.env`; its corrections (gap G5) stay a human-applied prerequisite

**Checkpoint**: baseline known, live unknowns resolved, `.env` untouched.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Entities, configuration, and the two component fixes that every user story
below depends on.

**⚠️ CRITICAL**: T012 (content-derived identifiers) MUST land before Phase 5's identity work.
Finding identity keys on the rule identifier; landing them in the wrong order makes the
suppression tests pass while the behaviour is still wrong the first time someone edits a
spreadsheet.

- [X] T005 [P] Add the frozen `ChecklistSource` dataclass with its `__post_init__` invariants (unavailable requires a reason; available requires a repo) to `review_agent/models.py` per data-model.md
- [X] T006 Add the frozen `RunInventory` dataclass to `review_agent/models.py`, with `reductions` **derived** from the other fields rather than assembled by the caller, plus the `rules_applied + rules_omitted == rules_read` invariant
- [X] T007 Extend `CombinedChecklist` in `review_agent/models.py` with `source`, `selection_basis`, `unavailable_reason` and the `prompt_text` property; add the invariants that omission requires a stated basis and that no item appears in both `items` and `dropped_for_budget`
- [X] T008 [P] Unit tests for the three entities above — every invariant asserted, including that a `ChecklistSource` with `available=False` and no reason raises — in `tests/unit/test_models_corpus.py`
- [X] T009 Add `rule_id` to `ChecklistViolation` and `inventory` to `ReviewReport` in `review_agent/models.py`
- [X] T010 Implement the four-name resolution order for the checklist repository in `review_agent/config.py`, canonical name first, recording which name supplied the value; when all four are empty the problem text names the canonical name only (research R1, survey S6)
- [X] T011 Change the `CHECKLIST_FILE_PATTERN` default to `*.xlsx,*.docx,*.md` and parse it as a comma-separated list; make an unset `CHECKLIST_BRANCH` mean "the repository's own default branch" rather than `main`, in `review_agent/config.py`
- [X] T012 [P] Unit tests for T010 and T011 — each legacy name still accepted, resolution order, the empty-everything message, the pattern list, the unset-branch sentinel — in `tests/unit/test_config.py`
- [X] T013 Replace positional derived identifiers with content-derived ones in `review_agent/checklist_docs.py`: `{stem}:{sheet}:{digest8}` for spreadsheets (`_items_from_sheet`) and `{stem}:{digest8}` for the docx tolerant path (`_docx_tolerant`), where `digest8` is `sha256(filename|section|title)[:8]`. Native identifiers stay verbatim (research R4)
- [X] T014 [P] Unit tests for identifier stability in `tests/unit/test_checklist_docs_xlsx.py` and `tests/unit/test_checklist_docs_docx.py`: inserting a row above a rule, deleting one below it, and reordering rules all leave every other rule's identifier unchanged; editing a rule's text changes only that rule's identifier
- [X] T015 Make `ref` optional in `review_agent/source_fetch.py:clone` so an unset reference omits `--branch` and takes the remote's default branch; keep the resolved commit on `ClonedSource` (research R2)
- [X] T016 [P] Unit test for the optional ref — the argument list contains no `--branch` when ref is unset, and does when it is set — in `tests/unit/test_source_fetch.py`
- [X] T017 Add `*.xlsx` and `*.docx` to `DEFAULT_EXCLUDE_PATTERNS` in `review_agent/config.py` so checklist documents can never be reviewed as code (FR-018)

**Checkpoint**: entities, settings, identifiers and the clone all ready. User stories can begin.

---

## Phase 3: User Story 1 — Review against the team's real checklist documents (P1) 🎯 MVP

**Goal**: A review obtains a working copy of the checklist repository, reads every
spreadsheet and Word document in it, and reports violations that cite the rule identifier
and the source document's filename.

**Independent Test**: Point the agent at a pull request with a known checklist violation and
at a checklist repository containing the rule that forbids it. The violation is reported and
cites the rule identifier and the document's filename. No user story and no posting step
are needed.

### Tests for User Story 1

- [X] T018 [P] [US1] Contract test for corpus boundaries — `checklist.py` contains no `git` literal and no `subprocess` call, imports no `openpyxl`, and reads no environment — as new cases in `tests/contract/test_import_boundaries.py`
- [X] T019 [P] [US1] Contract test for inventory completeness — the number of documents in the inventory equals the number of files the walk matched, for a fixture containing a readable `.xlsx`, a readable `.docx`, an empty document, a corrupt document and an unsupported one — in `tests/contract/test_checklist_inventory.py`
- [X] T020 [P] [US1] Integration test for the corpus path — rules from both formats applied, a violation citing a spreadsheet-derived identifier and one citing a `SEC-WEB-01` style identifier, each carrying the correct document filename — in `tests/integration/test_us1_corpus.py`
- [X] T021 [US1] Integration test for corpus degradation — an unreachable repository yields a story-coverage-only review with a stated reason and exit 0, not a setup failure — in `tests/integration/test_us1_corpus.py`

### Implementation for User Story 1

- [X] T022 [US1] Add `obtain_corpus(config, fetcher=source_fetch.clone)` to `review_agent/checklist.py`: request the working copy, build the `ChecklistSource` with repo, ref, commit and the setting that named it, and guarantee removal of the copy on every exit path (FR-002–FR-006)
- [X] T023 [US1] Add the recursive walk and pattern matching to `review_agent/checklist.py` — from `CHECKLIST_PATH`, filename-matched case-insensitively against the pattern list, `~$*` lock files ignored without comment (FR-007, contract §3)
- [X] T024 [US1] Read each matched file's bytes and hand them to `checklist_docs.read` in `review_agent/checklist.py`, assembling a `CombinedChecklist` whose `documents` accounts for **every** matched file and whose duplicate rules are folded with the existing `ChecklistItem.merged_with` (FR-008–FR-014)
- [X] T025 [US1] Implement the four distinct unavailability reasons in `review_agent/checklist.py` — no setting, not found, not permitted, nothing matched — each naming the setting or access to correct (FR-015, FR-024; the US4 tests in Phase 6 assert their distinctness)
- [X] T026 [US1] Add `prompt_text` rendering to `CombinedChecklist` in `review_agent/models.py`: grouped by document, each rule prefixed with its identifier in brackets, per data-model.md
- [X] T027 [US1] Add `select_rules(corpus, reviewable, budget)` to `review_agent/selection.py` — relevance to the changed files, reusing `_keywords`/`_path_tokens`, ties broken on `(document filename, item_id)`, everything omitted recorded on `dropped_for_budget` with `selection_basis` set (research R5)
- [X] T028 [P] [US1] Unit tests for `select_rules` in `tests/unit/test_selection.py` — the same change and corpus produce the same applied set regardless of document order; an over-budget corpus omits the least relevant rules and states the basis
- [X] T029 [US1] Wire the corpus into the run in `review_agent/main.py`: build it before the diff is fetched, fall back to the markdown path only when the repository yields no documents at all, remove the working copy in a `finally`, and log the phase with document and rule counts
- [X] T030 [US1] Render rules with their identifiers and add the `rule_id` instruction to the response contract in `review_agent/prompt_builder.py`, depending only on `available` / `unavailable_reason` / `prompt_text` so both corpus shapes work (research R9)
- [X] T031 [US1] Accept the optional `rule_id` and implement the four-case citation resolution in `review_agent/parser.py`: resolved citations take the corpus's filename, unresolvable ones become `dropped_citations` and never findings (contracts/llm-response.md)
- [X] T032 [P] [US1] Unit tests for citation resolution in `tests/unit/test_parser.py` — each of R1–R4, including that a review with no applied corpus drops every checklist violation
- [X] T033 [US1] Render the "what this review applied" inventory block in `review_agent/output_layer.py`, identically in the console preview and the posted summary, per contract §6
- [X] T034 [P] [US1] Test that the inventory block appears in both the preview text and the posted summary markdown, and that a skipped document's reason is present in both, in `tests/integration/test_us2_checklists.py`

**Checkpoint**: a review against the real document corpus works and says what it applied.

---

## Phase 4: User Story 2 — Review against the linked user stories (P1)

**Goal**: Every acceptance criterion of every linked work item receives an explicit verdict,
and a credential that cannot read work items costs the story half of the review — loudly,
without costing the checklist half.

**Independent Test**: Against a pull request linked to a work item with several acceptance
criteria — some satisfied, at least one not — run a review with no checklist repository
configured. Each criterion receives a verdict and the unmet one is identified.

### Tests for User Story 2

- [X] T035 [P] [US2] Unit test that a 401/403 from a work-item endpoint raises `WorkItemAccessDenied` while the same status from a pull-request endpoint still raises plain `SetupFailure`, in `tests/unit/test_auth_modes.py`
- [X] T036 [P] [US2] Integration test that a refused work-item read produces a checklist-only review — exit 0, the missing access named, the checklist findings still present — in `tests/integration/test_us1_review.py`
- [X] T037 [US2] Integration test that a pull request with no linked work item produces a checklist-only review with that stated as the reason, in `tests/integration/test_us1_review.py`

### Implementation for User Story 2

- [X] T038 [US2] Add `WorkItemAccessDenied(SetupFailure)` to `review_agent/errors.py`, carrying the access the credential is missing
- [X] T039 [US2] Raise it from `review_agent/tfs_client.py` when a 401 or 403 answers a work-item endpoint, with a remedy naming Work Items (read) — the client is the only module that knows which endpoint answered
- [X] T040 [US2] Catch it in `_fetch_story` in `review_agent/main.py`: return no work items plus the reason, continue as a checklist-only review, and carry the reason into the notes and the phase log (FR-023, survey S8)
- [X] T041 [US2] Add the story line to the inventory block in `review_agent/output_layer.py` — work items read and criteria judged, or the reason story coverage is absent (FR-022, FR-023)
- [X] T042 [US2] Verify and pin the existing per-criterion behaviour with tests in `tests/unit/test_parser.py`: every criterion receives a verdict identified by its ordinal, `not_addressed` never produces a comment, and a false coverage claim is reported against the criterion it concerns (FR-020, FR-021, FR-024)

**Checkpoint**: both halves of the review degrade independently. SC-009 holds in both directions.

---

## Phase 5: User Story 3 — Run the full review cycle end to end as a demonstration (P1)

**Goal**: One document carries an operator from an unconfigured start to feedback posted on
a pull request, and a second run adds nothing.

**Independent Test**: The self-contained demonstration, run twice from a clean checkout,
produces identical finding sets; the live half runs from an unconfigured start to a posted
review, supplying no content the document does not provide.

### Re-post suppression (FR-028, SC-007) — the defect 001 recorded as "no gap"

- [X] T043 [US3] Unit tests for the identity key of each finding kind in `tests/unit/test_parser.py` — checklist keys on the resolved rule id, coverage and false-coverage on `wi{id}:c{ordinal}`, code issues on `{severity}@{line}`; rewording the model's prose changes none of the first three
- [X] T044 [US3] Add the per-kind identity key helper to `review_agent/parser.py`, leaving `fingerprint`'s signature, hashing and 12-character width untouched (contracts/finding-identity.md)
- [X] T045 [US3] Use the stable keys at the four call sites in `review_agent/output_layer.py` (`:113`, `:123`, `:130`, `:135`), and route a coverage entry whose ordinal is 0 to the summary rather than inline, since it has no stable identity
- [X] T046 [P] [US3] Integration test for behaviours B1–B5 of contracts/finding-identity.md in `tests/integration/test_us3_posting.py` — a second run with reworded model output adds nothing; a rule-document row insertion does not resurface comments; a genuinely new violation is posted

### The sample material

- [X] T047 [P] [US3] Write the deliberately faulty sample code, every fault labelled with the rule identifier or criterion number it should trip, in `specs/003-checklist-repo-review-demo/demo-files/`
- [X] T048 [P] [US3] Write the sample checklist document generator — one spreadsheet with a banner row, a header on row 2 and an **empty** `#` column, one Word document with `SEC-WEB-01` style identifiers — reusing the shapes in `tests/fixtures/docs_builder.py`, in `specs/003-checklist-repo-review-demo/demo-files/generate_checklists.py`
- [X] T049 [P] [US3] Write the sample work item — title, description, and acceptance criteria including one the change satisfies, one it contradicts, and one outside its scope — in `specs/003-checklist-repo-review-demo/demo-files/work-item.md`

### The self-contained execution

- [X] T050 [US3] Build the self-contained harness in `tests/demo/run.py`: generate the sample documents, serve the sample pull request, work item and diff through `tests/fakes.FakeTfsClient`, drive `main.run_review` in preview, print the observed output. Runnable as `python -m tests.demo.run`, needing no server and no credential
- [X] T051 [US3] Add the collected test that runs the harness twice and compares the finding sets — identical rule identifiers, criterion numbers, files and lines — in `tests/integration/test_us3_demo.py` (SC-006)
- [X] T052 [US3] Execute the self-contained demonstration and capture its output verbatim into `specs/003-checklist-repo-review-demo/demo-files/observed-selfcontained.md`

### The live execution

- [X] T053 [US3] Pass the live gate before anything else in this group: `.env` corrected, `TFS_API_VERSION=5.0`, `TFS_PAT` carrying Work Items (read), and either this branch pushed to the agent repository or the run using `--local` — because the default entry point re-fetches and re-executes the committed logic (research R10). Record which of the two was used
- [ ] T054 [US3] Create the sample work item and the sample pull request in the sample repository from the material in `specs/003-checklist-repo-review-demo/demo-files/`, using this run's naming suffix from T003 so nothing collides with feature 002's artifacts, and link the work item to the pull request
- [X] T055 [US3] Run the live preview, work the five-question checkpoint of contracts/demonstration.md §3, and capture the output into `specs/003-checklist-repo-review-demo/demo-files/observed-live.md`
- [X] T056 [US3] Run the live posting command and record which comments landed on which file and line, and that exactly one summary discussion exists, appending to `demo-files/observed-live.md`
- [X] T057 [US3] **Run the live posting command a second time against the unchanged pull request** and record that `suppressed` equals the first run's `inline` and that zero comments were added. This observation is what closes survey finding S7; per contracts/finding-identity.md it is not satisfied by a unit test. Append to `demo-files/observed-live.md`  
  **DONE 2026-09-16** — five runs; the 2nd failed (`inline=3 suppressed=2`, which found R14), the 4th and 5th reported `inline=0`
- [ ] T058 [US3] Run the live review once with a Code-only credential and record the statement it produces, so the FR-023 path is observed rather than asserted. Append to `demo-files/observed-live.md`  
  **NOT DONE** — both available tokens carry Work Items (read), so the narrower path could not be exercised live. Asserted by test instead
- [ ] T059 [US3] Generate a third checklist document, re-run without changing any configuration, and record that it was applied (SC-010). Append to `demo-files/observed-live.md`

### The deliverable

- [X] T060 [US3] Write `specs/003-checklist-repo-review-demo/demo.md` sections 1–8 (what this demonstrates, prerequisites, which copy of the agent runs, what leaves the network, the sample documents, the sample work item, the sample change, the self-contained run) per contracts/demonstration.md §1, with per-step time budgets summing under 45 minutes
- [X] T061 [US3] Write `demo.md` sections 9–17 from the observed live output, every result labelled as self-contained or live, and the expected-results table carrying its mandatory availability column — any finding the demonstration expects but the agent cannot produce recorded as `expected-absent` with its reason (FR-038)  
  **DONE 2026-09-16** — every live result labelled; the three that remain unobserved are named in §17
- [X] T062 [US3] Run the redaction scan over `specs/003-checklist-repo-review-demo/demo.md` — token values, the real collection host, real project or repository identifiers, real work-item content — and remove or replace every hit. This is a gate, not a review suggestion
- [ ] T063 [US3] Tear down the live artifacts per `demo.md`'s cleanup section and confirm the sample pull request was not merged  
  **BLOCKED** — nothing was created live, so nothing is to be torn down

**Checkpoint**: the cycle is proven, twice over, and the second-run defect is closed by observation.

---

## Phase 6: User Story 4 — Diagnose a misconfigured checklist source (P2)

**Goal**: An operator whose configuration names no checklist repository, names an unreachable
one, or matches no documents finds out which from the run itself, in terms naming the
setting to change.

**Independent Test**: Run a review with the setting empty, then naming a repository that does
not exist, then naming a reachable repository containing no supported documents. Each
produces a different, actionable statement.

- [X] T064 [P] [US4] Test that the four conditions produce four **distinct** reasons — not merely four non-empty ones — and that each names the setting or the access to correct, in `tests/integration/test_us4_diagnosis.py`
- [X] T065 [US4] Refine the reason text in `review_agent/checklist.py` until T064 passes: not-found distinguished from not-permitted, and the no-match reason carrying the pattern, the path and the reference it looked at
- [X] T066 [P] [US4] Test that a configuration using each of the three legacy setting names still resolves a checklist repository, so no existing configuration has to be renamed (FR-001), in `tests/unit/test_config.py`

**Checkpoint**: the condition this project was actually in now announces itself.

---

### Found by the live run (research R13, R14)

- [X] T072 Present the credential to git as an `Authorization` header through git's environment config in `review_agent/source_fetch.py`, because this collection challenges with Negotiate/NTLM only and `GIT_ASKPASS` is therefore never asked (R13)
- [X] T073 Assert argv, disk and output for the **encoded** credential as well as the raw one in `tests/contract/test_no_secrets_leak.py`, and correct the module docstring's claim that the token exists in exactly one place
- [X] T074 Match a code issue against the text already posted on the same file in `review_agent/output_layer.py`, and retain posted comment text in `review_agent/dedupe.py`, because severity and line are both regenerated by the provider (R14)
- [X] T075 Pin the live failure as tests in `tests/integration/test_us3_posting.py`: a reworded issue, a moved line, a genuinely different issue, and the same text on another file

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T067 [P] Correct `CLAUDE.md`: G1 closed, the S11 claim about a Code-only credential replaced with the observed behaviour from T058, and the known-defect section updated with T057's result
- [X] T068 [P] Document the document-checklist path and link `demo.md` from `review_agent/README.md`
- [X] T069 [P] Update `review_agent/.env.example` with the canonical checklist setting name, the new pattern default, and the unset-branch semantics
- [X] T070 Run `python -m pytest tests -q` and confirm the count is the T001 baseline plus the tests added here, with no failures
- [X] T071 Walk the definition of done in `specs/003-checklist-repo-review-demo/quickstart.md` and confirm each item, including that the five checkpoint questions are answerable from a preview's own output  
  **DONE 2026-09-16** — the live run is performed; three items remain unobserved and are named in demo.md §17

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies. T002 and T003 need the live collection and gate nothing except T054's naming
- **Foundational (Phase 2)**: depends on Setup. **Blocks every user story**
- **US1 (Phase 3)**: depends on Phase 2. No dependency on other stories
- **US2 (Phase 4)**: depends on Phase 2 only. Fully parallel with US1 — different modules, different tests
- **US3 (Phase 5)**: the identity group (T043–T046) depends on Phase 2's T013 only; the demonstration groups depend on **US1 and US2 being complete**, because the demonstration exercises both
- **US4 (Phase 6)**: depends on US1's T025
- **Polish (Phase 7)**: depends on everything; T067 specifically depends on T057 and T058

### The one ordering that is easy to get wrong

**T013 before T044.** Finding identity keys on the rule identifier. If the identity work
lands while identifiers still contain row numbers, every suppression test passes and the
behaviour is still wrong the first time someone inserts a row in a spreadsheet.

### Within each story

- Tests first, failing for the right reason
- Entities before the code that populates them
- `checklist.py` before `main.py` wiring; `parser.py` before `output_layer.py`
- The full suite after every change, not just the file you touched — the import-boundary
  tests are cheap and they catch a stray `subprocess` import or a literal `git`

---

## Parallel Opportunities

```bash
# Phase 2 — three independent files
T005  models.py: ChecklistSource
T006  models.py: RunInventory          # same file as T005: serialise these two
T014  tests/unit/test_checklist_docs_*.py
T016  tests/unit/test_source_fetch.py

# Phase 3 — all four US1 tests, before any US1 implementation
T018  tests/contract/test_import_boundaries.py
T019  tests/contract/test_checklist_inventory.py
T020  tests/integration/test_us1_corpus.py
T021  tests/integration/test_us1_corpus.py   # same file as T020: serialise

# Phases 3 and 4 in parallel with two people
Developer A: US1 — checklist.py, selection.py, prompt_builder.py
Developer B: US2 — errors.py, tfs_client.py, main.py::_fetch_story

# Phase 5 — sample material, all separate files
T047  demo-files/ sample code
T048  demo-files/generate_checklists.py
T049  demo-files/work-item.md
```

Note that T005/T006/T007/T009 all edit `review_agent/models.py` and T010/T011/T017 all edit
`review_agent/config.py`. They are listed with `[P]` only where the file differs; within a
file they are sequential.

---

## Implementation Strategy

### MVP (US1 only)

1. Phase 1 → Phase 2 → Phase 3.
2. **Stop and validate**: run a preview against a real pull request with the checklist
   repository configured. The inventory block names documents and rule counts, and at least
   one finding cites a rule identifier and a filename.
3. That alone is the thing the team asked for and has never had. It is worth demonstrating
   before the rest is built.

### Incremental delivery

1. Setup + Foundational → both component fixes landed, suite green
2. + US1 → checklist documents actually reviewed **(MVP)**
3. + US2 → the story half degrades loudly instead of killing the run
4. + US3 → the cycle proven end to end, the re-posting defect closed by observation
5. + US4 → the misconfiguration this project was in announces itself

### What to check before calling any phase done

Run `python -m pytest tests -q`. The count only goes up.

---

## Notes

- `[P]` means a different file and no dependency on an incomplete task
- The deliberately faulty code under `demo-files/` is never imported, never collected, and
  never to be "fixed" — the same rule as feature 002's `example-files/`
- `.env` is not edited by any task here. It holds live credentials and is gitignored
- Commit after each task or logical group
