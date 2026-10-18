# Data Model: Complete Worked Example

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-15

This feature ships documents, not code, so these entities are structures in Markdown rather than dataclasses. They are modelled anyway for one reason: the walkthrough's correctness is entirely a matter of whether each expected finding carries the fields that make it checkable, and prose loses fields silently.

Validation rules below are what `/speckit.tasks` turns into review gates on the finished document.

---

## Walkthrough document

The deliverable. One file, `specs/002-pr-review-walkthrough/walkthrough.md`.

| Field | Type | Rule |
|---|---|---|
| `title` | text | Names the flow, not the feature number |
| `verified_on` | date | FR-033. Absent until the verification run completes; a document with no date has not been delivered |
| `verified_against` | version | FR-033. The agent version the run observed, from `--version` |
| `exposure_notice` | text | FR-006. Must appear before the first step that creates anything |
| `sections` | ordered list | Fixed by [contracts/walkthrough-structure.md](./contracts/walkthrough-structure.md); order is execution order |

**Invariants**

- Contains no credential, token, real host address, real project or repository name, or real identifier (FR-031). Placeholders are visibly distinguishable.
- Contains no instruction to look for output the agent does not produce (FR-026a).
- Does not restate the example files' contents (FR-009b).
- Every command, message and exit status quoted is attributable to the module that defines it (FR-032).

---

## Sample work item

| Field | Type | Rule |
|---|---|---|
| `title` | text | Carries the walkthrough's naming suffix (FR-013) |
| `description` | text | Supplied verbatim, copy-ready (FR-007) |
| `acceptance_criteria` | ordered list, ≥4 | Each independently checkable against the diff |
| `unimplemented_criterion` | reference | Exactly one. The criterion the change does not implement (FR-008) |
| `contradicted_criterion` | reference | Exactly one. Implemented, but conflicting with what the criterion states (research R4) |

**Invariants**

- `unimplemented_criterion` and `contradicted_criterion` are different criteria. Collapsing them into one loses the inline-versus-summary distinction the sample exists to show.
- At least two criteria are implemented correctly, so the demonstration is not entirely negative — a review that flags everything teaches the reader nothing about the agent's discrimination.
- Linked to the sample pull request. Without the link the agent retrieves no work item and both findings disappear (FR-018).

---

## Sample change set

Committed example files under `specs/002-pr-review-walkthrough/example-files/`, copied by the reader into the sample repository.

| Field | Type | Rule |
|---|---|---|
| `language` | text | Fixed by research R1. Recorded in the walkthrough with the basis for the choice (FR-009c) |
| `files` | list | Complete contents. The single copy of this code (FR-009, FR-009b) |
| `faults` | list of Deliberate fault | ≥2, satisfying the routing rule below |

**Invariants**

- Stored where `pytest` does not collect it and the import-boundary scan does not reach it. Verified: `pytest.ini` collects `tests` only; `tests/contract/test_import_boundaries.py:13` scans `review_agent/` only.
- Touches nothing in `review_agent/` and no production repository (FR-014).
- Implements every acceptance criterion except `unimplemented_criterion`, and conflicts with `contradicted_criterion`.

---

## Deliberate fault

The unit that makes the demonstration checkable. One per planted defect.

| Field | Type | Rule |
|---|---|---|
| `id` | label | Referenced from the expected-results reference |
| `location` | file, and line where anchorable | |
| `what_is_wrong` | text | Stated in the reader's terms, not the provider's |
| `expected_finding_kind` | enum | `false-coverage` \| `coverage` \| `checklist` \| `code` |
| `expected_placement` | enum | `inline` \| `summary-only` \| `either` |
| `expected_severity` | enum | `high` \| `medium` \| `low` \| not applicable |
| `traces_to` | reference | The acceptance criterion or checklist rule that produces it (FR-010) |
| `availability` | enum | `observed` \| `expected-absent` \| `varies` |

**Invariants**

- At least one fault has `expected_placement = summary-only` and does not depend on the checklist source (FR-011 as amended in plan.md).
- At least one fault has `expected_placement` of `inline` or `either`.
- `expected_severity` is recorded as *not applicable* for every kind except `code` — `CodeIssue` is the only entity carrying a severity (`review_agent/models.py:423`), and severity does not affect placement.
- Every fault with `availability = expected-absent` states the reason (FR-026, Principle VII).

### Placement — how the agent actually decides

Not by severity. `build_inline_comments` routes a finding inline when `_locate` resolves its file and line inside the reviewed diff, and to the summary otherwise (`review_agent/output_layer.py:87-137`).

| Finding kind | Routed with | Placement |
|---|---|---|
| `false-coverage` | the claim's own file and line | `either` — depends on whether the provider supplied a resolvable line |
| `coverage`, `possible_contradiction` | `""` and `0` (`output_layer.py:126`) | **always `summary-only`** |
| `coverage`, `not_addressed` | — skipped at `:117` | **never appears at all** |
| `checklist` | the violation's file and line | `either`; `expected-absent` today (gap G1) |
| `code` | the issue's file and line | `either` |

---

## Sample pull request

| Field | Type | Rule |
|---|---|---|
| `title` | text | Supplied verbatim, carries the naming suffix |
| `description` | text | Supplied verbatim (FR-012) |
| `covered_claims` | list | Includes `unimplemented_criterion` — the deliberate false claim |
| `source_branch` | ref | Naming scheme from research R6 |
| `target_branch` | ref | The repository's default branch, named by role not by literal name |
| `linked_work_item` | ref | Required (FR-018) |
| `state` | enum | Must be active when the agent runs |

**Invariant**: the description's "Covered" list is a superset of what the change implements. That gap is the headline finding; without it the demonstration has no point.

---

## Expected-results reference

The table that makes a run verifiable rather than merely performable. Format fixed by [contracts/expected-results.md](./contracts/expected-results.md).

| Field | Type | Rule |
|---|---|---|
| `entries` | list | One per Deliberate fault, plus one per finding observed but not planted |
| `checklist_dependency` | flag | Per entry. Drives the expected-absent marking (FR-026) |
| `observed_in_run` | boolean | Per entry. False is permitted only with `availability = expected-absent` (FR-035) |

**Invariant**: an entry with `availability = observed` and `observed_in_run = false` is a defect in the document, not in the agent. It means a prediction was written up as an observation.

---

## Checkpoint list

The reader's own pass/fail record, worked against preview output before anything is posted (FR-022).

| Field | Type | Rule |
|---|---|---|
| `items` | ordered list | Each independently checkable from console output alone |
| `stage` | enum | `preview` \| `post` \| `repeat` |

**Invariants**

- No item asks the reader to confirm something the agent does not produce (FR-026a). This removes 001's `.review-reports/` checkpoint — nothing writes a run report (gap G2).
- Every `preview` item is satisfiable without posting, so the preview path stands alone as a demonstration.
- One item confirms no secret appears in the output (SC-006 in the reader's hands, FR-031 in the author's).

---

## Symptom reference

| Field | Type | Rule |
|---|---|---|
| `symptom` | text | As the reader sees it — the message, not a description of it |
| `cause` | text | |
| `fix` | text | |
| `resume_from` | reference | A step in this walkthrough (FR-027) |
| `class` | enum | `setting` \| `transient` \| `expected-today` (FR-028) |

**Invariant**: every entry with `class = expected-today` states that no action is needed. The checklist-source warning is the one a first-time reader will certainly hit, and reading it as a failure is the most likely way this walkthrough loses a reader.

### Exit statuses — as the agent actually returns them

| Status | Meaning | Source |
|---|---|---|
| `0` | Review completed — **including a degraded run** | `main.py:346`, `:354-356` |
| `1` | Blocking findings, only with `FAIL_ON_CONTRADICTION=true` | `main.py:354` |
| `2` | Setup failure — nothing works until a setting changes | `main.py:334`, `:341`, `:350` |

`EXIT_DEGRADED = 3` is defined at `errors.py:26` and **never returned**. The walkthrough must not document it; 001's `contracts/cli.md` and quickstart currently do, and are wrong on this point.

---

## Teardown checklist

| Field | Type | Rule |
|---|---|---|
| `remote_artifacts` | list | Pull request, branch, work item |
| `local_artifacts` | list | Anything the run wrote locally containing copied source |
| `merge_prohibition` | statement | Explicit: the sample is never merged (FR-029) |

**Invariant**: covers local artifacts, not only remote ones (FR-030). Today the agent writes no run report, so this list is short — but it is stated rather than assumed, because when G2 lands the run will start writing source excerpts to disk and this checklist is where that gets caught.
